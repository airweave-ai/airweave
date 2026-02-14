"""Source connection service -- thin orchestrator.

Coordinates sub-services (credentials, OAuth, schedule, response builder)
and repositories (source connection, connection, collection) to implement
the source connection API contract.

No direct crud calls -- all DB access goes through injected repositories.
All service dependencies are injected via __init__.
"""

import asyncio
from typing import Any, List, Optional, Tuple
from uuid import UUID

from airweave import schemas
from airweave.analytics import business_events
from airweave.api.context import ApiContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.events.sync import SyncLifecycleEvent
from airweave.core.exceptions import BadGatewayError, BadRequestError, NotFoundException
from airweave.core.protocols.auth_provider_service import AuthProviderServiceProtocol
from airweave.core.protocols.collection import CollectionRepositoryProtocol
from airweave.core.protocols.connection import ConnectionRepositoryProtocol
from airweave.core.protocols.credential import CredentialServiceProtocol
from airweave.core.protocols.event_bus import EventBus
from airweave.core.protocols.oauth import OAuthFlowServiceProtocol
from airweave.core.protocols.sync import SyncRepositoryProtocol
from airweave.core.protocols.sync_cursor import SyncCursorRepositoryProtocol
from airweave.core.protocols.sync_job import SyncJobRepositoryProtocol
from airweave.core.protocols.sync_job_service import SyncJobServiceProtocol
from airweave.core.protocols.sync_service import SyncServiceProtocol
from airweave.core.protocols.temporal_schedule_service import TemporalScheduleServiceProtocol
from airweave.core.protocols.temporal_service import TemporalServiceProtocol
from airweave.core.shared_models import SyncJobStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.credentials.exceptions import InvalidConfigFieldsError
from airweave.domains.source_connections.exceptions import (
    ByocRequiredError,
    CollectionNotFoundError,
    InvalidAuthMethodError,
    NoSyncError,
    SourceConnectionNotFoundError,
    SyncImmediatelyNotAllowedError,
)
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionHelpersProtocol,
    SourceConnectionRepositoryProtocol,
)
from airweave.domains.source_connections.schedule import (
    determine_schedule,
    validate_cron_for_source,
)
from airweave.domains.sources.exceptions import SourceNotFoundError
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.platform.auth.schemas import OAuth1Settings
from airweave.platform.auth.settings import integration_settings
from airweave.schemas.source_connection import (
    AuthenticationMethod,
    AuthProviderAuthentication,
    DirectAuthentication,
    OAuthBrowserAuthentication,
    OAuthTokenAuthentication,
    SourceConnection,
    SourceConnectionCreate,
    SourceConnectionJob,
    SourceConnectionListItem,
    SourceConnectionUpdate,
    determine_auth_method,
)


class SourceConnectionService:
    """Thin orchestrator for source connection operations.

    Coordinates sub-services (credentials, OAuth, schedule, response builder)
    and repositories to implement the source connection API contract.
    """

    def __init__(
        self,
        sc_repo: SourceConnectionRepositoryProtocol,
        response_builder: ResponseBuilderProtocol,
        source_registry: SourceRegistryProtocol,
        credential_service: CredentialServiceProtocol,
        oauth_flow_service: OAuthFlowServiceProtocol,
        collection_repo: CollectionRepositoryProtocol,
        connection_repo: ConnectionRepositoryProtocol,
        sync_job_repo: SyncJobRepositoryProtocol,
        sync_cursor_repo: SyncCursorRepositoryProtocol,
        sync_repo: SyncRepositoryProtocol,
        sync_service: SyncServiceProtocol,
        temporal_service: TemporalServiceProtocol,
        sync_job_service: SyncJobServiceProtocol,
        temporal_schedule_service: TemporalScheduleServiceProtocol,
        helpers: SourceConnectionHelpersProtocol,
        auth_provider_service: AuthProviderServiceProtocol,
        event_bus: EventBus,
    ) -> None:
        """Initialize with all dependencies."""
        self._sc_repo = sc_repo
        self._response_builder = response_builder
        self._source_registry = source_registry
        self._credential_service = credential_service
        self._oauth_flow_service = oauth_flow_service
        self._collection_repo = collection_repo
        self._connection_repo = connection_repo
        self._sync_job_repo = sync_job_repo
        self._sync_cursor_repo = sync_cursor_repo
        self._sync_repo = sync_repo
        self._sync_service = sync_service
        self._temporal_service = temporal_service
        self._sync_job_service = sync_job_service
        self._temporal_schedule_service = temporal_schedule_service
        self._helpers = helpers
        self._auth_provider_service = auth_provider_service
        self._event_bus = event_bus

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

        sync_jobs = await self._sync_service.list_sync_jobs(
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
                    raise BadRequestError(
                        "Credentials can only be updated for direct authentication"
                    )
                await self._helpers.update_auth_fields(
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
        collection = await self._collection_repo.get_by_readable_id(
            db, readable_id=source_conn.readable_collection_id, ctx=ctx
        )
        if not collection:
            raise CollectionNotFoundError(source_conn.readable_collection_id)
        collection_id = str(collection.id)
        organization_id = str(collection.organization_id)

        # Build response before deletion
        response = await self._response_builder.build_response(db, source_conn, ctx)

        # Cancel running jobs and wait for terminal state
        if sync_id:
            latest_job = await self._sync_job_repo.get_latest_by_sync_id(db, sync_id=sync_id)
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
                await self._temporal_service.start_cleanup_sync_data_workflow(
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
            cursor = await self._sync_cursor_repo.get_by_sync_id(
                db, sync_id=source_conn.sync_id, ctx=ctx
            )
            if not cursor or not cursor.cursor_data:
                raise BadRequestError(
                    "force_full_sync can only be used with continuous syncs "
                    "(syncs with cursor data)."
                )
            ctx.logger.info(f"Force full sync requested for continuous sync {source_conn.sync_id}.")

        # Prepare schemas for Temporal workflow
        collection = await self._collection_repo.get_by_readable_id(
            db, readable_id=source_conn.readable_collection_id, ctx=ctx
        )
        collection_schema = schemas.Collection.model_validate(collection, from_attributes=True)

        source_connection_schema = await self._response_builder.build_response(db, source_conn, ctx)

        connection_schema = await self._helpers.get_connection_for_source_connection(
            db=db, source_connection=source_conn, ctx=ctx
        )

        # Trigger sync
        sync, sync_job = await self._sync_service.trigger_sync_run(
            db, sync_id=source_conn.sync_id, ctx=ctx
        )
        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

        # Publish PENDING event
        await self._event_bus.publish(
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

        await self._temporal_service.run_source_connection_workflow(
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

        sync_job = await self._sync_job_repo.get(db, id=job_id, ctx=ctx)
        if not sync_job:
            raise NotFoundException("Sync job not found")

        if sync_job.sync_id != source_conn.sync_id:
            raise BadRequestError("Sync job does not belong to this source connection")

        if sync_job.status not in [SyncJobStatus.PENDING, SyncJobStatus.RUNNING]:
            raise BadRequestError(f"Cannot cancel job in {sync_job.status} state")

        # Set CANCELLING status
        await self._sync_job_service.update_status(
            sync_job_id=job_id, status=SyncJobStatus.CANCELLING, ctx=ctx
        )

        # Request cancellation from Temporal
        cancel_result = await self._temporal_service.cancel_sync_job_workflow(str(job_id), ctx)

        if not cancel_result["success"]:
            fallback_status = (
                SyncJobStatus.RUNNING
                if sync_job.status == SyncJobStatus.RUNNING
                else SyncJobStatus.PENDING
            )
            await self._sync_job_service.update_status(
                sync_job_id=job_id, status=fallback_status, ctx=ctx
            )
            raise BadGatewayError("Failed to request cancellation from Temporal")

        if not cancel_result["workflow_found"]:
            ctx.logger.info(f"Workflow not found for job {job_id} - marking as CANCELLED directly")
            await self._sync_job_service.update_status(
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
            await self._helpers.update_sync_schedule(
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

            collection = await self._collection_repo.get_by_readable_id(
                uow.session, readable_id=source_conn.readable_collection_id, ctx=ctx
            )

            sync, _ = await self._helpers.create_sync_without_schedule(
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

            await self._temporal_schedule_service.create_or_update_schedule(
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
            job = await self._sync_job_repo.get_latest_by_sync_id(db, sync_id=sync_id)
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
    # Create
    # ------------------------------------------------------------------

    async def create(  # noqa: C901
        self,
        db: Any,
        *,
        obj_in: SourceConnectionCreate,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Create a source connection with nested authentication."""
        source_entry = self._get_source_entry(obj_in.short_name)
        source_cls = source_entry.source_class_ref

        if obj_in.name is None:
            obj_in.name = f"{source_entry.name} Connection"

        auth_method = self._determine_auth_method(obj_in, source_cls)

        if not source_cls.supports_auth_method(auth_method):
            supported = source_cls.get_supported_auth_methods()
            raise InvalidAuthMethodError(auth_method.value, [m.value for m in supported])

        if source_cls.requires_byoc and auth_method == AuthenticationMethod.OAUTH_BROWSER:
            raise ByocRequiredError(obj_in.short_name)

        if obj_in.sync_immediately is None:
            if auth_method in [AuthenticationMethod.OAUTH_BROWSER, AuthenticationMethod.OAUTH_BYOC]:
                obj_in.sync_immediately = False
            else:
                obj_in.sync_immediately = True

        if auth_method in [AuthenticationMethod.OAUTH_BROWSER, AuthenticationMethod.OAUTH_BYOC]:
            if obj_in.sync_immediately:
                raise SyncImmediatelyNotAllowedError()

        if auth_method == AuthenticationMethod.DIRECT:
            result = await self._create_with_direct_auth(db, obj_in, ctx)
        elif auth_method == AuthenticationMethod.OAUTH_BROWSER:
            result = await self._create_with_oauth_browser(db, obj_in, ctx)
        elif auth_method == AuthenticationMethod.OAUTH_TOKEN:
            result = await self._create_with_oauth_token(db, obj_in, ctx)
        elif auth_method == AuthenticationMethod.OAUTH_BYOC:
            result = await self._create_with_oauth_byoc(db, obj_in, ctx)
        elif auth_method == AuthenticationMethod.AUTH_PROVIDER:
            result = await self._create_with_auth_provider(db, obj_in, ctx)
        else:
            raise BadRequestError(f"Unsupported authentication method: {auth_method.value}")

        business_events.track_source_connection_created(
            ctx=ctx,
            connection_id=result.id,
            source_short_name=result.short_name,
        )

        return result

    # ------------------------------------------------------------------
    # OAuth callbacks
    # ------------------------------------------------------------------

    async def complete_oauth1_callback(
        self,
        db: Any,
        *,
        oauth_token: str,
        oauth_verifier: str,
    ) -> SourceConnection:
        """Complete OAuth1 callback: exchange verifier, complete connection, trigger sync."""
        completion = await self._oauth_flow_service.complete_oauth1_callback(
            oauth_token=oauth_token, oauth_verifier=oauth_verifier, db=db
        )

        ctx = await self._helpers.reconstruct_context_from_session(db, completion.init_session)

        source_conn_shell = await self._sc_repo.get_by_query_and_org(
            db, ctx=ctx, connection_init_session_id=completion.init_session.id
        )
        if not source_conn_shell:
            raise SourceConnectionNotFoundError("shell (OAuth1 callback)")

        source_conn = await self._helpers.complete_oauth1_connection(
            db, source_conn_shell, completion.init_session, completion.token_response, ctx
        )

        return await self._finalize_oauth_callback(db, source_conn, ctx)

    async def complete_oauth2_callback(
        self,
        db: Any,
        *,
        state: str,
        code: str,
    ) -> SourceConnection:
        """Complete OAuth2 callback: exchange code, validate token, complete connection."""
        completion = await self._oauth_flow_service.complete_oauth2_callback(
            state=state, code=code, db=db
        )

        ctx = await self._helpers.reconstruct_context_from_session(db, completion.init_session)

        source_conn_shell = await self._sc_repo.get_by_query_and_org(
            db, ctx=ctx, connection_init_session_id=completion.init_session.id
        )
        if not source_conn_shell:
            raise SourceConnectionNotFoundError("shell (OAuth2 callback)")

        # Validate the token
        await self._credential_service.validate_oauth_token(
            completion.short_name, completion.token_response.access_token, None
        )

        source_conn = await self._helpers.complete_oauth2_connection(
            db, source_conn_shell, completion.init_session, completion.token_response, ctx
        )

        return await self._finalize_oauth_callback(db, source_conn, ctx)

    # ------------------------------------------------------------------
    # Private: create handlers
    # ------------------------------------------------------------------

    async def _create_with_direct_auth(
        self, db: Any, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnection:
        """Create with direct credentials (API key, etc.)."""
        source_entry = self._get_source_entry(obj_in.short_name)

        if not obj_in.authentication or not isinstance(obj_in.authentication, DirectAuthentication):
            raise BadRequestError("Direct authentication requires credentials")

        validated_auth = await self._credential_service.validate_auth_fields(
            obj_in.short_name, obj_in.authentication.credentials
        )
        enabled_features = ctx.organization.enabled_features or []
        validated_config = await self._credential_service.validate_config_fields(
            obj_in.short_name, obj_in.config, enabled_features
        )
        await self._credential_service.validate_direct_auth(
            obj_in.short_name, validated_auth, validated_config
        )

        async with UnitOfWork(db) as uow:
            collection = await self._helpers.get_collection(
                uow.session, obj_in.readable_collection_id, ctx
            )
            credential = await self._credential_service.create_credential(
                source_short_name=source_entry.short_name,
                source_name=source_entry.name,
                auth_fields=validated_auth,
                organization_id=ctx.organization.id,
                auth_method=AuthenticationMethod.DIRECT,
                oauth_type=source_entry.oauth_type,
                auth_config_class=(
                    source_entry.auth_config_ref.__name__ if source_entry.auth_config_ref else None
                ),
                db=uow.session,
                uow=uow,
                ctx=ctx,
            )
            await uow.session.flush()

            connection = await self._helpers.create_connection(
                uow.session, obj_in.name, source_entry, credential.id, ctx, uow
            )
            await uow.session.flush()
            connection_schema = schemas.Connection.model_validate(connection, from_attributes=True)

            sync_id, sync, sync_job = await self._handle_sync_creation(
                uow,
                obj_in,
                source_entry,
                source_entry,
                connection.id,
                collection.id,
                collection.readable_id,
                ctx,
            )

            source_conn = await self._helpers.create_source_connection(
                uow.session,
                obj_in,
                connection.id,
                collection.readable_id,
                sync_id,
                validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            cron_schedule = determine_schedule(obj_in, source_entry.supports_continuous)
            await self._create_temporal_schedule_if_needed(uow, cron_schedule, sync_id, ctx)

            (
                sync_schema,
                sync_job_schema,
                collection_schema,
            ) = await self._prepare_sync_schemas_for_workflow(
                uow, sync, sync_job, collection, obj_in
            )

            await uow.commit()
            await uow.session.refresh(source_conn)

        response = await self._response_builder.build_response(db, source_conn, ctx)

        if sync_job and obj_in.sync_immediately:
            await self._trigger_sync_workflow(
                connection_schema, sync_schema, sync_job_schema, collection_schema, ctx
            )

        return response

    async def _create_with_oauth_browser(
        self, db: Any, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnection:
        """Create shell + start OAuth browser flow (OAuth1 or OAuth2)."""
        self._get_source_entry(obj_in.short_name)  # validate source exists
        enabled_features = ctx.organization.enabled_features or []
        validated_config = await self._credential_service.validate_config_fields(
            obj_in.short_name, obj_in.config, enabled_features
        )

        # Extract template configs for OAuth URL
        template_configs = await self._validate_and_extract_template_configs(
            db, obj_in.short_name, validated_config, ctx
        )

        # Extract BYOC credentials from authentication if present
        oauth_auth = (
            obj_in.authentication
            if isinstance(obj_in.authentication, OAuthBrowserAuthentication)
            else OAuthBrowserAuthentication()
        )

        # Determine OAuth1 vs OAuth2
        oauth_settings = await integration_settings.get_by_short_name(obj_in.short_name)

        if isinstance(oauth_settings, OAuth1Settings):
            init_result = await self._oauth_flow_service.initiate_oauth1(
                short_name=obj_in.short_name,
                payload=obj_in.model_dump(
                    exclude={"authentication", "client_id", "client_secret"}, exclude_none=True
                ),
                organization_id=ctx.organization.id,
                redirect_url=getattr(obj_in, "redirect_url", None),
                byoc_consumer_key=None,
                byoc_consumer_secret=None,
                db=db,
                uow=None,  # Will create own UoW inside
                ctx=ctx,
            )
        else:
            init_result = await self._oauth_flow_service.initiate_oauth2(
                short_name=obj_in.short_name,
                payload=obj_in.model_dump(
                    exclude={"authentication", "client_id", "client_secret"}, exclude_none=True
                ),
                organization_id=ctx.organization.id,
                redirect_url=getattr(oauth_auth, "redirect_url", None)
                or getattr(obj_in, "redirect_url", None),
                byoc_client_id=None,
                byoc_client_secret=None,
                template_configs=template_configs,
                db=db,
                uow=None,
                ctx=ctx,
            )

        # Create shell source connection and link to init session
        async with UnitOfWork(db) as uow:
            source_conn = await self._helpers.create_source_connection(
                uow.session,
                obj_in,
                connection_id=None,
                collection_id=obj_in.readable_collection_id,
                sync_id=None,
                config_fields=validated_config,
                is_authenticated=False,
                ctx=ctx,
                uow=uow,
            )
            source_conn.connection_init_session_id = init_result.init_session_id
            source_conn.authentication_url = init_result.proxy_url
            source_conn.authentication_url_expiry = init_result.proxy_expiry
            uow.session.add(source_conn)
            await uow.commit()
            await uow.session.refresh(source_conn)

        return await self._response_builder.build_response(db, source_conn, ctx)

    async def _create_with_oauth_token(
        self, db: Any, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnection:
        """Create with injected OAuth token."""
        source_entry = self._get_source_entry(obj_in.short_name)

        if not obj_in.authentication or not isinstance(
            obj_in.authentication, OAuthTokenAuthentication
        ):
            raise BadRequestError("OAuth token authentication requires an access token")

        oauth_creds = {
            "access_token": obj_in.authentication.access_token,
            "refresh_token": obj_in.authentication.refresh_token,
            "token_type": "Bearer",
        }
        if obj_in.authentication.expires_at:
            oauth_creds["expires_at"] = obj_in.authentication.expires_at.isoformat()

        enabled_features = ctx.organization.enabled_features or []
        validated_config = await self._credential_service.validate_config_fields(
            obj_in.short_name, obj_in.config, enabled_features
        )
        await self._credential_service.validate_oauth_token(
            obj_in.short_name, obj_in.authentication.access_token, validated_config
        )

        async with UnitOfWork(db) as uow:
            collection = await self._helpers.get_collection(
                uow.session, obj_in.readable_collection_id, ctx
            )
            credential = await self._credential_service.create_credential(
                source_short_name=source_entry.short_name,
                source_name=source_entry.name,
                auth_fields=oauth_creds,
                organization_id=ctx.organization.id,
                auth_method=AuthenticationMethod.OAUTH_TOKEN,
                oauth_type=source_entry.oauth_type,
                auth_config_class=(
                    source_entry.auth_config_ref.__name__ if source_entry.auth_config_ref else None
                ),
                db=uow.session,
                uow=uow,
                ctx=ctx,
            )
            await uow.session.flush()

            connection = await self._helpers.create_connection(
                uow.session, obj_in.name, source_entry, credential.id, ctx, uow
            )
            await uow.session.flush()
            connection_schema = schemas.Connection.model_validate(connection, from_attributes=True)

            sync_id, sync, sync_job = await self._handle_sync_creation(
                uow,
                obj_in,
                source_entry,
                source_entry,
                connection.id,
                collection.id,
                collection.readable_id,
                ctx,
            )

            source_conn = await self._helpers.create_source_connection(
                uow.session,
                obj_in,
                connection.id,
                collection.readable_id,
                sync_id,
                validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            cron_schedule = determine_schedule(obj_in, source_entry.supports_continuous)
            await self._create_temporal_schedule_if_needed(uow, cron_schedule, sync_id, ctx)

            (
                sync_schema,
                sync_job_schema,
                collection_schema,
            ) = await self._prepare_sync_schemas_for_workflow(
                uow, sync, sync_job, collection, obj_in
            )

            await uow.commit()
            await uow.session.refresh(source_conn)

        response = await self._response_builder.build_response(db, source_conn, ctx)

        if sync_job and obj_in.sync_immediately:
            await self._trigger_sync_workflow(
                connection_schema, sync_schema, sync_job_schema, collection_schema, ctx
            )

        return response

    async def _create_with_oauth_byoc(
        self, db: Any, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnection:
        """Create with BYOC OAuth (user provides client credentials)."""
        if not obj_in.authentication or not isinstance(
            obj_in.authentication, OAuthBrowserAuthentication
        ):
            raise BadRequestError(
                "OAuth BYOC requires browser authentication with client credentials"
            )

        self._get_source_entry(obj_in.short_name)  # validate source exists
        enabled_features = ctx.organization.enabled_features or []
        validated_config = await self._credential_service.validate_config_fields(
            obj_in.short_name, obj_in.config, enabled_features
        )
        template_configs = await self._validate_and_extract_template_configs(
            db, obj_in.short_name, validated_config, ctx
        )

        oauth_settings = await integration_settings.get_by_short_name(obj_in.short_name)

        if isinstance(oauth_settings, OAuth1Settings):
            if not obj_in.authentication.consumer_key or not obj_in.authentication.consumer_secret:
                raise BadRequestError("OAuth1 BYOC requires consumer_key and consumer_secret")

            init_result = await self._oauth_flow_service.initiate_oauth1(
                short_name=obj_in.short_name,
                payload=obj_in.model_dump(exclude={"authentication"}, exclude_none=True),
                organization_id=ctx.organization.id,
                redirect_url=getattr(obj_in, "redirect_url", None),
                byoc_consumer_key=obj_in.authentication.consumer_key,
                byoc_consumer_secret=obj_in.authentication.consumer_secret,
                db=db,
                uow=None,
                ctx=ctx,
            )
        else:
            if not obj_in.authentication.client_id or not obj_in.authentication.client_secret:
                raise BadRequestError("OAuth2 BYOC requires client_id and client_secret")

            init_result = await self._oauth_flow_service.initiate_oauth2(
                short_name=obj_in.short_name,
                payload=obj_in.model_dump(exclude={"authentication"}, exclude_none=True),
                organization_id=ctx.organization.id,
                redirect_url=getattr(obj_in.authentication, "redirect_url", None)
                or getattr(obj_in, "redirect_url", None),
                byoc_client_id=obj_in.authentication.client_id,
                byoc_client_secret=obj_in.authentication.client_secret,
                template_configs=template_configs,
                db=db,
                uow=None,
                ctx=ctx,
            )

        async with UnitOfWork(db) as uow:
            source_conn = await self._helpers.create_source_connection(
                uow.session,
                obj_in,
                connection_id=None,
                collection_id=obj_in.readable_collection_id,
                sync_id=None,
                config_fields=validated_config,
                is_authenticated=False,
                ctx=ctx,
                uow=uow,
            )
            source_conn.connection_init_session_id = init_result.init_session_id
            source_conn.authentication_url = init_result.proxy_url
            source_conn.authentication_url_expiry = init_result.proxy_expiry
            uow.session.add(source_conn)
            await uow.commit()
            await uow.session.refresh(source_conn)

        return await self._response_builder.build_response(db, source_conn, ctx)

    async def _create_with_auth_provider(
        self, db: Any, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnection:
        """Create using external auth provider (Composio, Pipedream)."""
        source_entry = self._get_source_entry(obj_in.short_name)

        if not obj_in.authentication or not isinstance(
            obj_in.authentication, AuthProviderAuthentication
        ):
            raise BadRequestError("Auth provider authentication requires provider configuration")

        auth_provider_conn = await self._connection_repo.get_by_readable_id(
            db, readable_id=obj_in.authentication.provider_readable_id, ctx=ctx
        )
        if not auth_provider_conn:
            raise NotFoundException(
                f"Auth provider '{obj_in.authentication.provider_readable_id}' not found"
            )

        supported_providers = self._auth_provider_service.get_supported_providers_for_source(
            obj_in.short_name
        )
        if auth_provider_conn.short_name not in supported_providers:
            raise BadRequestError(
                f"Source '{obj_in.short_name}' does not support "
                f"'{auth_provider_conn.short_name}' as an auth provider."
            )

        validated_auth_config = None
        if obj_in.authentication.provider_config:
            validated_auth_config = await self._auth_provider_service.validate_auth_provider_config(
                db, auth_provider_conn.short_name, obj_in.authentication.provider_config
            )

        enabled_features = ctx.organization.enabled_features or []
        validated_config = await self._credential_service.validate_config_fields(
            obj_in.short_name, obj_in.config, enabled_features
        )

        async with UnitOfWork(db) as uow:
            collection = await self._helpers.get_collection(
                uow.session, obj_in.readable_collection_id, ctx
            )
            connection = await self._helpers.create_connection(
                uow.session, obj_in.name, source_entry, None, ctx, uow
            )
            await uow.session.flush()

            sync_id, sync, sync_job = await self._handle_sync_creation(
                uow,
                obj_in,
                source_entry,
                source_entry,
                connection.id,
                collection.id,
                collection.readable_id,
                ctx,
            )

            source_conn = await self._helpers.create_source_connection(
                uow.session,
                obj_in,
                connection.id,
                collection.readable_id,
                sync_id,
                validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
                auth_provider_id=auth_provider_conn.readable_id,
                auth_provider_config=validated_auth_config,
            )
            await uow.session.flush()

            cron_schedule = determine_schedule(obj_in, source_entry.supports_continuous)
            await self._create_temporal_schedule_if_needed(uow, cron_schedule, sync_id, ctx)

            (
                sync_schema,
                sync_job_schema,
                collection_schema,
            ) = await self._prepare_sync_schemas_for_workflow(
                uow, sync, sync_job, collection, obj_in
            )

            await uow.commit()
            await uow.session.refresh(source_conn)

        response = await self._response_builder.build_response(db, source_conn, ctx)

        if sync_job and obj_in.sync_immediately:
            connection_schema = await self._helpers.get_connection_for_source_connection(
                db=db, source_connection=source_conn, ctx=ctx
            )
            await self._trigger_sync_workflow(
                connection_schema, sync_schema, sync_job_schema, collection_schema, ctx
            )

        return response

    # ------------------------------------------------------------------
    # Private: shared create helpers
    # ------------------------------------------------------------------

    def _determine_auth_method(
        self, obj_in: SourceConnectionCreate, source_cls: type
    ) -> AuthenticationMethod:
        """Determine auth method from nested authentication object."""
        auth = obj_in.authentication
        if auth is None:
            return AuthenticationMethod.OAUTH_BROWSER
        if isinstance(auth, DirectAuthentication):
            return AuthenticationMethod.DIRECT
        if isinstance(auth, OAuthTokenAuthentication):
            return AuthenticationMethod.OAUTH_TOKEN
        if isinstance(auth, OAuthBrowserAuthentication):
            has_oauth2_byoc = auth.client_id and auth.client_secret
            has_oauth1_byoc = auth.consumer_key and auth.consumer_secret
            if has_oauth2_byoc or has_oauth1_byoc:
                return AuthenticationMethod.OAUTH_BYOC
            return AuthenticationMethod.OAUTH_BROWSER
        if isinstance(auth, AuthProviderAuthentication):
            return AuthenticationMethod.AUTH_PROVIDER
        raise BadRequestError("Invalid authentication configuration")

    async def _handle_sync_creation(
        self,
        uow,
        obj_in,
        source,
        source_entry,
        connection_id,
        collection_id,
        collection_readable_id,
        ctx,
    ) -> Tuple[Optional[UUID], Any, Any]:
        """Create sync with schedule during source connection creation."""
        if getattr(source_entry.source_class_ref, "federated_search", False):
            ctx.logger.info(
                f"Skipping sync for federated search source '{source_entry.short_name}'"
            )
            return None, None, None

        cron_schedule = determine_schedule(obj_in, source_entry.supports_continuous)

        if not cron_schedule and not obj_in.sync_immediately:
            return None, None, None

        if cron_schedule:
            validate_cron_for_source(
                cron_schedule, source_entry.short_name, source_entry.supports_continuous
            )

        sync, sync_job = await self._helpers.create_sync_without_schedule(
            uow.session,
            obj_in.name,
            connection_id,
            collection_id,
            collection_readable_id,
            cron_schedule,
            obj_in.sync_immediately,
            ctx,
            uow,
        )
        await uow.session.flush()

        sync_id = sync.id if sync else None
        return sync_id, sync, sync_job

    async def _create_temporal_schedule_if_needed(self, uow, cron_schedule, sync_id, ctx) -> None:
        """Create Temporal schedule if we have both cron and sync_id."""
        if cron_schedule and sync_id:
            await self._temporal_schedule_service.create_or_update_schedule(
                sync_id=sync_id, cron_schedule=cron_schedule, db=uow.session, ctx=ctx, uow=uow
            )

    async def _prepare_sync_schemas_for_workflow(
        self, uow, sync, sync_job, collection, obj_in
    ) -> Tuple[Any, Any, Any]:
        """Prepare schemas for Temporal workflow if sync_immediately."""
        if sync_job and obj_in.sync_immediately:
            await uow.session.flush()
            await uow.session.refresh(sync_job)
            await uow.session.refresh(collection)
            return (
                schemas.Sync.model_validate(sync, from_attributes=True),
                schemas.SyncJob.model_validate(sync_job, from_attributes=True),
                schemas.Collection.model_validate(collection, from_attributes=True),
            )
        return None, None, None

    async def _trigger_sync_workflow(self, connection, sync, sync_job, collection, ctx) -> None:
        """Trigger Temporal workflow for sync."""
        await self._temporal_service.run_source_connection_workflow(
            sync=sync, sync_job=sync_job, collection=collection, connection=connection, ctx=ctx
        )

    async def _finalize_oauth_callback(
        self, db: Any, source_conn: Any, ctx: ApiContext
    ) -> SourceConnection:
        """Build response and trigger sync workflow after OAuth completion."""
        response = await self._response_builder.build_response(db, source_conn, ctx)

        if source_conn.sync_id:
            sync = await self._sync_repo.get(db, id=source_conn.sync_id, ctx=ctx)
            if sync:
                jobs = await self._sync_job_repo.get_all_by_sync_id(db, sync_id=sync.id)
                if jobs and len(jobs) > 0:
                    sync_job = jobs[0]
                    if sync_job.status == SyncJobStatus.PENDING:
                        collection = await self._collection_repo.get_by_readable_id(
                            db, readable_id=source_conn.readable_collection_id, ctx=ctx
                        )
                        if collection:
                            collection_schema = schemas.Collection.model_validate(
                                collection, from_attributes=True
                            )
                            sync_job_schema = schemas.SyncJob.model_validate(
                                sync_job, from_attributes=True
                            )
                            sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)
                            connection_schema = (
                                await self._helpers.get_connection_for_source_connection(
                                    db=db,
                                    source_connection=source_conn,
                                    ctx=ctx,
                                )
                            )
                            await self._temporal_service.run_source_connection_workflow(
                                sync=sync_schema,
                                sync_job=sync_job_schema,
                                collection=collection_schema,
                                connection=connection_schema,
                                ctx=ctx,
                            )

        return response

    async def _validate_and_extract_template_configs(
        self, db: Any, short_name: str, validated_config: Optional[dict], ctx: ApiContext
    ) -> Optional[dict]:
        """Extract template configs needed before OAuth can start (e.g., Zendesk subdomain)."""
        source_entry = self._get_source_entry(short_name)
        if source_entry.config_ref is None or validated_config is None:
            return None

        try:
            template_fields = source_entry.config_ref.get_template_config_fields()
            if template_fields:
                source_entry.config_ref.validate_template_configs(validated_config)
                return source_entry.config_ref.extract_template_configs(validated_config)
        except ValueError as e:
            raise InvalidConfigFieldsError(str(e))
        except Exception as e:
            ctx.logger.warning(f"Could not process template configs for {short_name}: {e}")

        return None
