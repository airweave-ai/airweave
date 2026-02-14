"""Source connection service -- thin orchestrator.

Coordinates sub-services (credentials, OAuth, schedule, response builder)
and repositories (source connection, connection, collection) to implement
the source connection API contract.

No direct crud.source_connection calls -- all DB access goes through repositories.
Singletons (sync_service, temporal_service, etc.) are called directly until
they get their own refactor.
"""

import asyncio
from typing import Any, List, Optional
from uuid import UUID

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.events.sync import SyncLifecycleEvent
from airweave.core.protocols.credential import CredentialServiceProtocol
from airweave.core.protocols.oauth import OAuthFlowServiceProtocol
from airweave.core.shared_models import SyncJobStatus
from airweave.core.source_connection_service_helpers import source_connection_helpers
from airweave.core.sync_service import sync_service
from airweave.core.temporal_service import temporal_service
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.source_connections.exceptions import (
    NoSyncError,
    SourceConnectionNotFoundError,
)
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionRepositoryProtocol,
)
from airweave.domains.source_connections.schedule import validate_cron_for_source
from airweave.domains.sources.exceptions import SourceNotFoundError
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.schemas.source_connection import (
    AuthenticationMethod,
    SourceConnection,
    SourceConnectionJob,
    SourceConnectionListItem,
    SourceConnectionUpdate,
    determine_auth_method,
)


class NewSourceConnectionService:
    """Thin orchestrator for source connection operations.

    Named NewSourceConnectionService to coexist with the legacy service
    during the transition. Will be renamed once the old service is removed.
    """

    def __init__(
        self,
        sc_repo: SourceConnectionRepositoryProtocol,
        response_builder: ResponseBuilderProtocol,
        source_registry: SourceRegistryProtocol,
        credential_service: CredentialServiceProtocol,
        oauth_flow_service: OAuthFlowServiceProtocol,
    ) -> None:
        """Initialize with all dependencies."""
        self._sc_repo = sc_repo
        self._response_builder = response_builder
        self._source_registry = source_registry
        self._credential_service = credential_service
        self._oauth_flow_service = oauth_flow_service

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get(self, db: Any, *, id: UUID, ctx: ApiContext) -> SourceConnection:
        """Get a source connection with complete details."""
        source_conn = await self._sc_repo.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise SourceConnectionNotFoundError(id)

        return await self._response_builder.build_response(db, source_conn, ctx)

    async def list(
        self,
        db: Any,
        *,
        ctx: ApiContext,
        readable_collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnectionListItem]:
        """List source connections with stats."""
        connections_with_stats = await self._sc_repo.get_multi_with_stats(
            db, ctx=ctx, collection_id=readable_collection_id, skip=skip, limit=limit
        )

        return [self._response_builder.build_list_item(data) for data in connections_with_stats]

    async def get_jobs(
        self, db: Any, *, id: UUID, ctx: ApiContext, limit: int = 100
    ) -> List[SourceConnectionJob]:
        """Get sync jobs for a source connection."""
        source_conn = await self._sc_repo.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise SourceConnectionNotFoundError(id)

        if not source_conn.sync_id:
            return []

        sync_jobs = await sync_service.list_sync_jobs(
            db, ctx=ctx, sync_id=source_conn.sync_id, limit=limit
        )

        return [self._response_builder.map_sync_job(job, source_conn.id) for job in sync_jobs]

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def update(
        self, db: Any, *, id: UUID, obj_in: SourceConnectionUpdate, ctx: ApiContext
    ) -> SourceConnection:
        """Update a source connection.

        Handles config validation, schedule updates, and credential updates.
        """
        async with UnitOfWork(db) as uow:
            source_conn = await self._sc_repo.get(uow.session, id=id, ctx=ctx)
            if not source_conn:
                raise SourceConnectionNotFoundError(id)

            update_data = obj_in.model_dump(exclude_unset=True)

            # Normalize nested authentication payloads (direct auth updates)
            if "authentication" in update_data:
                auth_payload = update_data.get("authentication") or {}
                credentials_data = auth_payload.get("credentials")
                if credentials_data:
                    update_data["credentials"] = credentials_data
                del update_data["authentication"]

            # Validate and apply config update
            if "config" in update_data:
                enabled_features = ctx.organization.enabled_features or []
                validated_config = await self._credential_service.validate_config_fields(
                    source_conn.short_name, update_data["config"], enabled_features
                )
                update_data["config_fields"] = validated_config
                del update_data["config"]

            # Handle schedule update
            await self._handle_schedule_update(uow, source_conn, update_data, ctx)

            # Handle credential update (direct auth only)
            if "credentials" in update_data:
                auth_method = determine_auth_method(source_conn)
                if auth_method != AuthenticationMethod.DIRECT:
                    from airweave.core.exceptions import BadRequestError

                    raise BadRequestError(
                        "Credentials can only be updated for direct authentication"
                    )
                await source_connection_helpers.update_auth_fields(
                    uow.session, source_conn, update_data["credentials"], ctx, uow
                )
                del update_data["credentials"]

            # Apply remaining field updates
            if update_data:
                source_conn = await self._sc_repo.update(
                    uow.session, db_obj=source_conn, obj_in=update_data, ctx=ctx, uow=uow
                )

            await uow.commit()
            await uow.session.refresh(source_conn)

        return await self._response_builder.build_response(db, source_conn, ctx)

    async def delete(self, db: Any, *, id: UUID, ctx: ApiContext) -> SourceConnection:
        """Delete a source connection and all related data.

        1. Cancel any running sync workflows and wait for them to stop.
        2. CASCADE-delete the DB records.
        3. Fire-and-forget Temporal cleanup workflow for external data.
        """
        source_conn = await self._sc_repo.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise SourceConnectionNotFoundError(id)

        sync_id = source_conn.sync_id
        collection = await crud.collection.get_by_readable_id(
            db, readable_id=source_conn.readable_collection_id, ctx=ctx
        )
        if not collection:
            from airweave.domains.source_connections.exceptions import CollectionNotFoundError

            raise CollectionNotFoundError(source_conn.readable_collection_id)
        collection_id = str(collection.id)
        organization_id = str(collection.organization_id)

        # Build response before deletion
        response = await self._response_builder.build_response(db, source_conn, ctx)

        # Cancel running jobs and wait for terminal state
        if sync_id:
            latest_job = await crud.sync_job.get_latest_by_sync_id(db, sync_id=sync_id)
            if latest_job and latest_job.status in [
                SyncJobStatus.PENDING,
                SyncJobStatus.RUNNING,
                SyncJobStatus.CANCELLING,
            ]:
                if latest_job.status in [SyncJobStatus.PENDING, SyncJobStatus.RUNNING]:
                    ctx.logger.info(
                        f"Cancelling job {latest_job.id} for source connection {id} before deletion"
                    )
                    try:
                        await self.cancel_job(
                            db, source_connection_id=id, job_id=latest_job.id, ctx=ctx
                        )
                    except Exception as e:
                        ctx.logger.warning(
                            f"Failed to cancel job {latest_job.id} during deletion: {e}"
                        )

                reached_terminal = await self._wait_for_sync_job_terminal_state(
                    db, sync_id, timeout_seconds=15
                )
                if not reached_terminal:
                    ctx.logger.warning(
                        f"Job for sync {sync_id} did not reach terminal state within 15s "
                        f"-- proceeding with deletion anyway"
                    )

        # CASCADE delete
        await self._sc_repo.remove(db, id=id, ctx=ctx)

        # Fire-and-forget external cleanup
        if sync_id:
            try:
                await temporal_service.start_cleanup_sync_data_workflow(
                    sync_ids=[str(sync_id)],
                    collection_id=collection_id,
                    organization_id=organization_id,
                    ctx=ctx,
                )
            except Exception as e:
                ctx.logger.error(
                    f"Failed to schedule async cleanup for sync {sync_id}: {e}. "
                    f"Data may be orphaned in Vespa/ARF."
                )

        return response

    # ------------------------------------------------------------------
    # Sync job operations
    # ------------------------------------------------------------------

    async def run(
        self,
        db: Any,
        *,
        id: UUID,
        ctx: ApiContext,
        force_full_sync: bool = False,
    ) -> SourceConnectionJob:
        """Trigger a sync run for a source connection."""
        source_conn = await self._sc_repo.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise SourceConnectionNotFoundError(id)

        if not source_conn.sync_id:
            raise NoSyncError(id)

        # Validate force_full_sync for continuous syncs only
        if force_full_sync:
            cursor = await crud.sync_cursor.get_by_sync_id(db, sync_id=source_conn.sync_id, ctx=ctx)
            if not cursor or not cursor.cursor_data:
                from airweave.core.exceptions import BadRequestError

                raise BadRequestError(
                    "force_full_sync can only be used with continuous syncs "
                    "(syncs with cursor data)."
                )
            ctx.logger.info(f"Force full sync requested for continuous sync {source_conn.sync_id}.")

        # Prepare schemas for Temporal workflow
        collection = await crud.collection.get_by_readable_id(
            db, readable_id=source_conn.readable_collection_id, ctx=ctx
        )
        collection_schema = schemas.Collection.model_validate(collection, from_attributes=True)

        source_connection_schema = await self._response_builder.build_response(db, source_conn, ctx)

        connection_schema = await source_connection_helpers.get_connection_for_source_connection(
            db=db, source_connection=source_conn, ctx=ctx
        )

        # Trigger sync
        sync, sync_job = await sync_service.trigger_sync_run(
            db, sync_id=source_conn.sync_id, ctx=ctx
        )
        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

        # Publish PENDING event
        from airweave.core.container import container

        if container is not None:
            await container.event_bus.publish(
                SyncLifecycleEvent.pending(
                    organization_id=ctx.organization.id,
                    source_connection_id=source_connection_schema.id,
                    sync_job_id=sync_job_schema.id,
                    sync_id=source_connection_schema.sync_id,
                    collection_id=collection_schema.id,
                    source_type=connection_schema.short_name,
                    collection_name=collection_schema.name,
                    collection_readable_id=collection_schema.readable_id,
                )
            )

        await temporal_service.run_source_connection_workflow(
            sync=sync,
            sync_job=sync_job,
            collection=collection_schema,
            connection=connection_schema,
            ctx=ctx,
            force_full_sync=force_full_sync,
        )

        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
        return sync_job_schema.to_source_connection_job(source_connection_schema.id)

    async def cancel_job(
        self,
        db: Any,
        *,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> SourceConnectionJob:
        """Cancel a running sync job."""
        source_conn = await self._sc_repo.get(db, id=source_connection_id, ctx=ctx)
        if not source_conn:
            raise SourceConnectionNotFoundError(source_connection_id)

        if not source_conn.sync_id:
            raise NoSyncError(source_connection_id)

        sync_job = await crud.sync_job.get(db, id=job_id, ctx=ctx)
        if not sync_job:
            from airweave.core.exceptions import NotFoundException

            raise NotFoundException("Sync job not found")

        if sync_job.sync_id != source_conn.sync_id:
            from airweave.core.exceptions import BadRequestError

            raise BadRequestError("Sync job does not belong to this source connection")

        if sync_job.status not in [SyncJobStatus.PENDING, SyncJobStatus.RUNNING]:
            from airweave.core.exceptions import BadRequestError

            raise BadRequestError(f"Cannot cancel job in {sync_job.status} state")

        # Set CANCELLING status
        from airweave.core.sync_job_service import sync_job_service

        await sync_job_service.update_status(
            sync_job_id=job_id, status=SyncJobStatus.CANCELLING, ctx=ctx
        )

        # Request cancellation from Temporal
        cancel_result = await temporal_service.cancel_sync_job_workflow(str(job_id), ctx)

        if not cancel_result["success"]:
            fallback_status = (
                SyncJobStatus.RUNNING
                if sync_job.status == SyncJobStatus.RUNNING
                else SyncJobStatus.PENDING
            )
            await sync_job_service.update_status(
                sync_job_id=job_id, status=fallback_status, ctx=ctx
            )
            from airweave.core.exceptions import BadGatewayError

            raise BadGatewayError("Failed to request cancellation from Temporal")

        if not cancel_result["workflow_found"]:
            ctx.logger.info(f"Workflow not found for job {job_id} - marking as CANCELLED directly")
            from airweave.core.datetime_utils import utc_now_naive

            await sync_job_service.update_status(
                sync_job_id=job_id,
                status=SyncJobStatus.CANCELLED,
                ctx=ctx,
                completed_at=utc_now_naive(),
                error="Workflow not found in Temporal - may have already completed",
            )

        await db.refresh(sync_job)
        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
        return sync_job_schema.to_source_connection_job(source_connection_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _handle_schedule_update(
        self, uow: UnitOfWork, source_conn: Any, update_data: dict, ctx: ApiContext
    ) -> None:
        """Handle schedule create/update/remove during an update operation."""
        if "schedule" not in update_data:
            return

        if update_data["schedule"] is None:
            new_cron = None
        else:
            new_cron = update_data["schedule"].get("cron")

        if source_conn.sync_id:
            # Update existing sync's schedule
            if new_cron:
                source_entry = self._get_source_entry(source_conn.short_name)
                validate_cron_for_source(
                    new_cron, source_conn.short_name, source_entry.supports_continuous
                )
            await source_connection_helpers.update_sync_schedule(
                uow.session, source_conn.sync_id, new_cron, ctx, uow
            )
        elif new_cron:
            # No sync exists -- create one with the schedule
            source_entry = self._get_source_entry(source_conn.short_name)
            validate_cron_for_source(
                new_cron, source_conn.short_name, source_entry.supports_continuous
            )

            if not source_conn.connection_id:
                ctx.logger.warning(
                    f"Cannot create schedule for SC {source_conn.id} without connection_id"
                )
                del update_data["schedule"]
                return

            collection = await crud.collection.get_by_readable_id(
                uow.session, readable_id=source_conn.readable_collection_id, ctx=ctx
            )

            sync, _ = await source_connection_helpers.create_sync_without_schedule(
                uow.session,
                source_conn.name,
                source_conn.connection_id,
                collection.id,
                collection.readable_id,
                new_cron,
                False,
                ctx,
                uow,
            )

            source_conn = await self._sc_repo.update(
                uow.session,
                db_obj=source_conn,
                obj_in={"sync_id": sync.id},
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            from airweave.platform.temporal.schedule_service import temporal_schedule_service

            await temporal_schedule_service.create_or_update_schedule(
                sync_id=sync.id, cron_schedule=new_cron, db=uow.session, ctx=ctx, uow=uow
            )

        if "schedule" in update_data:
            del update_data["schedule"]

    async def _wait_for_sync_job_terminal_state(
        self,
        db: Any,
        sync_id: UUID,
        *,
        timeout_seconds: int = 30,
        poll_interval: float = 1.0,
    ) -> bool:
        """Wait for the latest sync job to reach a terminal state."""
        terminal_states = {
            SyncJobStatus.COMPLETED,
            SyncJobStatus.FAILED,
            SyncJobStatus.CANCELLED,
        }
        elapsed = 0.0
        while elapsed < timeout_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            db.expire_all()
            job = await crud.sync_job.get_latest_by_sync_id(db, sync_id=sync_id)
            if job and job.status in terminal_states:
                return True
        return False

    def _get_source_entry(self, short_name: str):
        """Look up source entry from registry."""
        try:
            return self._source_registry.get(short_name)
        except KeyError:
            raise SourceNotFoundError(short_name)

    # ------------------------------------------------------------------
    # Create -- delegates to the legacy _create_with_* handlers via
    # source_connection_service for the multi-step atomic transactions.
    # The routing logic (auth method determination, validation) lives here.
    # Individual handlers will be migrated to use sub-services incrementally.
    # ------------------------------------------------------------------

    async def create(
        self,
        db: Any,
        *,
        obj_in: Any,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Create a source connection with nested authentication.

        Routes to auth-specific handlers based on the authentication type.
        """
        from airweave.core.source_connection_service import source_connection_service

        # Delegate to the legacy service for create -- it has 7 auth-specific
        # handlers with complex multi-step transactions. These will be migrated
        # incrementally to use the new sub-services.
        source_connection = await source_connection_service.create(db, obj_in=obj_in, ctx=ctx)

        return source_connection

    # ------------------------------------------------------------------
    # OAuth callbacks -- delegate to legacy service during transition.
    # The OAuthFlowService handles the protocol-level token exchange,
    # but the connection completion (credential, sync, etc.) still uses
    # the old helpers.
    # ------------------------------------------------------------------

    async def complete_oauth1_callback(
        self,
        db: Any,
        *,
        oauth_token: str,
        oauth_verifier: str,
    ) -> SourceConnection:
        """Complete OAuth1 callback flow."""
        from airweave.core.source_connection_service import source_connection_service

        return await source_connection_service.complete_oauth1_callback(
            db, oauth_token=oauth_token, oauth_verifier=oauth_verifier
        )

    async def complete_oauth2_callback(
        self,
        db: Any,
        *,
        state: str,
        code: str,
    ) -> SourceConnection:
        """Complete OAuth2 callback flow."""
        from airweave.core.source_connection_service import source_connection_service

        return await source_connection_service.complete_oauth2_callback(db, state=state, code=code)
