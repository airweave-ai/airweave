"""Service for source connections."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.domains.auth_provider.protocols import AuthProviderRegistryProtocol
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionDeletionServiceProtocol,
    SourceConnectionRepositoryProtocol,
    SourceConnectionServiceProtocol,
    SourceConnectionUpdateServiceProtocol,
)
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.domains.syncs.protocols import SyncLifecycleServiceProtocol
from airweave.models.source_connection import SourceConnection
from airweave.schemas.source_connection import (
    SourceConnection as SourceConnectionSchema,
)
from airweave.schemas.source_connection import (
    SourceConnectionJob,
    SourceConnectionListItem,
    SourceConnectionUpdate,
)


class SourceConnectionService(SourceConnectionServiceProtocol):
    """Service for source connections."""

    def __init__(
        self,
        # Repositories
        sc_repo: SourceConnectionRepositoryProtocol,
        collection_repo: CollectionRepositoryProtocol,
        connection_repo: ConnectionRepositoryProtocol,
        # Registries
        source_registry: SourceRegistryProtocol,
        auth_provider_registry: AuthProviderRegistryProtocol,
        # Helpers
        response_builder: ResponseBuilderProtocol,
        sync_lifecycle: SyncLifecycleServiceProtocol,
        # Sub-services
        update_service: SourceConnectionUpdateServiceProtocol,
        deletion_service: SourceConnectionDeletionServiceProtocol,
    ) -> None:
        self.sc_repo = sc_repo
        self.collection_repo = collection_repo
        self.connection_repo = connection_repo
        self.source_registry = source_registry
        self.auth_provider_registry = auth_provider_registry
        self.response_builder = response_builder
        self._sync_lifecycle = sync_lifecycle
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
                )
            )

        return result

    async def update(
        self, db: AsyncSession, id: UUID, obj_in: SourceConnectionUpdate, ctx: ApiContext
    ) -> SourceConnectionSchema:
        """Update a source connection."""
        return await self._update_service.update(db, id=id, obj_in=obj_in, ctx=ctx)

    async def delete(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> SourceConnectionSchema:
        """Delete a source connection."""
        return await self._deletion_service.delete(db, id=id, ctx=ctx)

    # ------------------------------------------------------------------
    # Sync lifecycle proxies
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
        return await self._sync_lifecycle.run(db, id=id, ctx=ctx, force_full_sync=force_full_sync)

    async def get_jobs(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        limit: int = 100,
    ) -> List[SourceConnectionJob]:
        """List sync jobs for this source connection."""
        return await self._sync_lifecycle.get_jobs(db, id=id, ctx=ctx, limit=limit)

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> SourceConnectionJob:
        """Cancel a running sync job."""
        return await self._sync_lifecycle.cancel_job(
            db, source_connection_id=source_connection_id, job_id=job_id, ctx=ctx
        )
