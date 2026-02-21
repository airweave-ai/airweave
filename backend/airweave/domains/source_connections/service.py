"""Service for source connections."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionCreationServiceProtocol,
    SourceConnectionRepositoryProtocol,
    SourceConnectionServiceProtocol,
)
from airweave.domains.syncs.protocols import SyncLifecycleServiceProtocol
from airweave.schemas.source_connection import (
    SourceConnectionCreate,
    SourceConnectionJob,
    SourceConnectionListItem,
)
from airweave.schemas.source_connection import (
    SourceConnection as SourceConnectionSchema,
)


class SourceConnectionService(SourceConnectionServiceProtocol):
    """Service for source connections."""

    def __init__(
        self,
        sc_repo: SourceConnectionRepositoryProtocol,
        response_builder: ResponseBuilderProtocol,
        sync_lifecycle: SyncLifecycleServiceProtocol,
        creation_service: SourceConnectionCreationServiceProtocol,
    ) -> None:
        self._sc_repo = sc_repo
        self._response_builder = response_builder
        self._sync_lifecycle = sync_lifecycle
        self._creation_service = creation_service

        # Keep public attrs used by router/other modules
        self.sc_repo = sc_repo
        self.response_builder = response_builder

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> SourceConnectionSchema:
        source_connection = await self._sc_repo.get(db, id=id, ctx=ctx)
        if not source_connection:
            raise NotFoundException("Source connection not found")
        return await self._response_builder.build_response(db, source_connection, ctx)

    async def list(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        readable_collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnectionListItem]:
        connections_with_stats = await self._sc_repo.get_multi_with_stats(
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

    # ------------------------------------------------------------------
    # Create (delegates to SourceConnectionCreationService)
    # ------------------------------------------------------------------

    async def create(
        self, db: AsyncSession, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnectionSchema:
        return await self._creation_service.create(db, obj_in, ctx)

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
        return await self._sync_lifecycle.run(db, id=id, ctx=ctx, force_full_sync=force_full_sync)

    async def get_jobs(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        limit: int = 100,
    ) -> List[SourceConnectionJob]:
        return await self._sync_lifecycle.get_jobs(db, id=id, ctx=ctx, limit=limit)

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> SourceConnectionJob:
        return await self._sync_lifecycle.cancel_job(
            db, source_connection_id=source_connection_id, job_id=job_id, ctx=ctx
        )
