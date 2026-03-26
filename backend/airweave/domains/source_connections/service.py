"""Service for source connections."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.datetime_utils import utc_now
from airweave.core.events.sync import SyncLifecycleEvent
from airweave.core.exceptions import NotFoundException
from airweave.core.protocols.event_bus import EventBus
from airweave.domains.auth_provider.protocols import AuthProviderRegistryProtocol
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.oauth.protocols import OAuthRedirectSessionRepositoryProtocol
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionCreateServiceProtocol,
    SourceConnectionDeletionServiceProtocol,
    SourceConnectionRepositoryProtocol,
    SourceConnectionServiceProtocol,
    SourceConnectionUpdateServiceProtocol,
)
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.domains.syncs.protocols import SyncServiceProtocol
from airweave.domains.temporal.protocols import TemporalWorkflowServiceProtocol
from airweave.models.source_connection import SourceConnection
from airweave.schemas.source_connection import (
    SourceConnection as SourceConnectionSchema,
)
from airweave.schemas.source_connection import (
    SourceConnectionCreate,
    SourceConnectionJob,
    SourceConnectionListItem,
    SourceConnectionUpdate,
)


def _duration_seconds(
    started_at: Optional[datetime], completed_at: Optional[datetime]
) -> Optional[float]:
    if started_at and completed_at:
        return (completed_at - started_at).total_seconds()
    return None


class SourceConnectionService(SourceConnectionServiceProtocol):
    """Service for source connections."""

    def __init__(  # noqa: D107
        self,
        # Repositories
        sc_repo: SourceConnectionRepositoryProtocol,
        collection_repo: CollectionRepositoryProtocol,
        connection_repo: ConnectionRepositoryProtocol,
        redirect_session_repo: OAuthRedirectSessionRepositoryProtocol,
        # Registries
        source_registry: SourceRegistryProtocol,
        auth_provider_registry: AuthProviderRegistryProtocol,
        # Helpers
        response_builder: ResponseBuilderProtocol,
        sync_service: SyncServiceProtocol,
        temporal_workflow_service: TemporalWorkflowServiceProtocol,
        event_bus: EventBus,
        # Sub-services
        create_service: SourceConnectionCreateServiceProtocol,
        update_service: SourceConnectionUpdateServiceProtocol,
        deletion_service: SourceConnectionDeletionServiceProtocol,
    ) -> None:
        self.sc_repo = sc_repo
        self.collection_repo = collection_repo
        self.connection_repo = connection_repo
        self._redirect_session_repo = redirect_session_repo
        self.source_registry = source_registry
        self.auth_provider_registry = auth_provider_registry
        self.response_builder = response_builder
        self._sync_service = sync_service
        self._temporal_workflow_service = temporal_workflow_service
        self._event_bus = event_bus
        self._create_service = create_service
        self._update_service = update_service
        self._deletion_service = deletion_service

    async def get(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> SourceConnection:
        """Get a source connection by ID."""
        source_connection = await self.sc_repo.get(db, id=id, ctx=ctx)
        if not source_connection:
            raise NotFoundException("Source connection not found")

        return await self.response_builder.build_response(db, source_connection, ctx)

    async def list(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        readable_collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnectionListItem]:
        """List source connections with complete stats."""
        connections_with_stats = await self.sc_repo.get_multi_with_stats(
            db, ctx=ctx, collection_id=readable_collection_id, skip=skip, limit=limit
        )

        result = []
        for stats in connections_with_stats:
            last_job = stats.last_job
            last_job_status = last_job.status if last_job else None
            last_job_error_category = last_job.error_category if last_job else None

            result.append(
                SourceConnectionListItem(
                    id=stats.id,
                    name=stats.name,
                    short_name=stats.short_name,
                    readable_collection_id=stats.readable_collection_id,
                    created_at=stats.created_at,
                    modified_at=stats.modified_at,
                    is_authenticated=stats.is_authenticated,
                    authentication_method=stats.authentication_method,
                    entity_count=stats.entity_count,
                    federated_search=stats.federated_search,
                    is_active=stats.is_active,
                    last_job_status=last_job_status,
                    last_job_error_category=last_job_error_category,
                )
            )

        return result

    async def create(
        self, db: AsyncSession, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnectionSchema:
        """Create a source connection."""
        return await self._create_service.create(db, obj_in=obj_in, ctx=ctx)

    async def update(
        self, db: AsyncSession, id: UUID, obj_in: SourceConnectionUpdate, ctx: ApiContext
    ) -> SourceConnectionSchema:
        """Update a source connection."""
        return await self._update_service.update(db, id=id, obj_in=obj_in, ctx=ctx)

    async def reinitiate_oauth(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
    ) -> SourceConnectionSchema:
        """Create a fresh OAuth session for an un-authenticated connection."""
        return await self._create_service.reinitiate_oauth(db, id=id, ctx=ctx)

    async def delete(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> SourceConnectionSchema:
        """Delete a source connection."""
        return await self._deletion_service.delete(db, id=id, ctx=ctx)

    # ------------------------------------------------------------------
    # Sync lifecycle proxies — resolve source_connection → sync_id, then
    # delegate to the unified SyncService and map results.
    # ------------------------------------------------------------------

    async def run(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        force_full_sync: bool = False,
    ) -> SourceConnectionJob:
        """Trigger a sync run for this source connection."""
        source_conn = await self._resolve_source_connection(db, id, ctx)
        sync_id = source_conn.sync_id
        assert sync_id is not None

        if force_full_sync:
            await self._sync_service.validate_force_full_sync(db, sync_id, ctx)

        collection = await self._resolve_collection(db, source_conn, ctx)
        connection = await self._resolve_connection(db, source_conn, ctx)

        sync, sync_job = await self._sync_service.trigger_run(db, sync_id=sync_id, ctx=ctx)

        try:
            await self._event_bus.publish(
                SyncLifecycleEvent.pending(
                    organization_id=ctx.organization.id,
                    source_connection_id=id,
                    sync_job_id=sync_job.id,
                    sync_id=sync_id,
                    collection_id=collection.id,
                    source_type=connection.short_name,
                    collection_name=collection.name,
                    collection_readable_id=collection.readable_id,
                )
            )
        except Exception as e:
            ctx.logger.warning(f"Failed to publish sync.pending event: {e}")

        await self._temporal_workflow_service.run_source_connection_workflow(
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,
            ctx=ctx,
            force_full_sync=force_full_sync,
        )

        return SourceConnectionJob(
            id=sync_job.id,
            source_connection_id=id,
            status=sync_job.status,
            started_at=sync_job.started_at,
            completed_at=sync_job.completed_at,
            duration_seconds=_duration_seconds(sync_job.started_at, sync_job.completed_at),
            entities_inserted=sync_job.entities_inserted or 0,
            entities_updated=sync_job.entities_updated or 0,
            entities_deleted=sync_job.entities_deleted or 0,
            entities_failed=sync_job.entities_skipped or 0,
            error=sync_job.error,
            error_category=sync_job.error_category,
        )

    async def get_jobs(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        limit: int = 100,
    ) -> List[SourceConnectionJob]:
        """List sync jobs for this source connection."""
        source_conn = await self._resolve_source_connection(db, id, ctx)
        sync_id = source_conn.sync_id
        assert sync_id is not None

        jobs = await self._sync_service.get_jobs(db, sync_id=sync_id, ctx=ctx, limit=limit)

        return [
            SourceConnectionJob(
                id=j.id,
                source_connection_id=id,
                status=j.status,
                started_at=j.started_at,
                completed_at=j.completed_at,
                duration_seconds=_duration_seconds(j.started_at, j.completed_at),
                entities_inserted=j.entities_inserted or 0,
                entities_updated=j.entities_updated or 0,
                entities_deleted=j.entities_deleted or 0,
                entities_failed=j.entities_skipped or 0,
                error=j.error,
                error_category=j.error_category,
            )
            for j in jobs
        ]

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> SourceConnectionJob:
        """Cancel a running sync job."""
        source_conn = await self._resolve_source_connection(db, source_connection_id, ctx)
        sync_id = source_conn.sync_id
        assert sync_id is not None

        sync_job = await self._sync_service.cancel_job(db, job_id=job_id, ctx=ctx)

        if sync_job.sync_id != sync_id:
            raise NotFoundException("Job not found for this source connection")

        return SourceConnectionJob(
            id=sync_job.id,
            source_connection_id=source_connection_id,
            status=sync_job.status,
            started_at=sync_job.started_at,
            completed_at=sync_job.completed_at,
            duration_seconds=_duration_seconds(sync_job.started_at, sync_job.completed_at),
            entities_inserted=sync_job.entities_inserted or 0,
            entities_updated=sync_job.entities_updated or 0,
            entities_deleted=sync_job.entities_deleted or 0,
            entities_failed=sync_job.entities_skipped or 0,
            error=sync_job.error,
            error_category=sync_job.error_category,
        )

    async def get_sync_id(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> dict:
        """Get the sync_id for a source connection."""
        source_connection = await self.sc_repo.get(db, id=id, ctx=ctx)
        if not source_connection:
            raise NotFoundException("Source connection not found")
        if not source_connection.sync_id:
            raise NotFoundException("No sync found for this source connection")
        return {"sync_id": str(source_connection.sync_id)}

    async def count_by_organization(self, db: AsyncSession, organization_id: UUID) -> int:
        """Count source connections belonging to an organization."""
        return await self.sc_repo.count_by_organization(db, organization_id)

    async def get_redirect_url(self, db: AsyncSession, *, code: str) -> str:
        """Resolve a short redirect code to its final OAuth authorization URL."""
        redirect_info = await self._redirect_session_repo.consume(db, code=code)
        if not redirect_info:
            raise NotFoundException("Authorization link expired or invalid")
        if redirect_info.expires_at <= utc_now():
            raise NotFoundException("Authorization link expired or invalid")
        return redirect_info.final_url

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _resolve_source_connection(
        self, db: AsyncSession, id: UUID, ctx: ApiContext
    ) -> SourceConnection:
        """Get a source connection and validate it has an associated sync."""
        source_conn = await self.sc_repo.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise NotFoundException("Source connection not found")
        if not source_conn.sync_id:
            raise NotFoundException("No sync found for this source connection")
        return source_conn

    async def _resolve_collection(
        self, db: AsyncSession, source_conn: SourceConnection, ctx: ApiContext
    ) -> schemas.CollectionRecord:
        """Resolve the CollectionRecord schema for a source connection."""
        readable_id = source_conn.readable_collection_id
        if not readable_id:
            raise ValueError(f"Source connection {source_conn.id} has no readable_collection_id")
        collection = await self.collection_repo.get_by_readable_id(db, str(readable_id), ctx)
        if not collection:
            raise NotFoundException("Collection not found")
        return schemas.CollectionRecord.model_validate(collection, from_attributes=True)

    async def _resolve_connection(
        self, db: AsyncSession, source_conn: SourceConnection, ctx: ApiContext
    ) -> schemas.Connection:
        """Resolve the Connection schema (not SourceConnection) for a source connection."""
        if not source_conn.connection_id:
            raise ValueError(f"Source connection {source_conn.id} has no connection_id")
        conn = await self.connection_repo.get(db, source_conn.connection_id, ctx)
        if not conn:
            raise ValueError(f"Connection {source_conn.connection_id} not found")
        return schemas.Connection.model_validate(conn, from_attributes=True)
