"""Sync job repository wrapping crud.sync_job."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.syncs.protocols import SyncJobRepositoryProtocol
from airweave.models.sync_job import SyncJob
from airweave.schemas.sync_job import SyncJobCreate


class SyncJobRepository(SyncJobRepositoryProtocol):
    """Delegates to the crud.sync_job singleton."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[SyncJob]:
        """Get a sync job by ID within org scope."""
        return await crud.sync_job.get(db, id=id, ctx=ctx)

    async def get_latest_by_sync_id(self, db: AsyncSession, sync_id: UUID) -> Optional[SyncJob]:
        """Get the most recent sync job for a sync."""
        return await crud.sync_job.get_latest_by_sync_id(db, sync_id=sync_id)

    async def get_active_for_sync(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> List[SyncJob]:
        """Get all active (PENDING, RUNNING, CANCELLING) jobs for a sync."""
        return await crud.sync_job.get_all_by_sync_id(
            db, sync_id=sync_id, status=["PENDING", "RUNNING", "CANCELLING"]
        )

    async def get_all_by_sync_id(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> List[SyncJob]:
        """Get all jobs for a specific sync."""
        return await crud.sync_job.get_all_by_sync_id(db, sync_id=sync_id)

    async def create(
        self,
        db: AsyncSession,
        obj_in: SyncJobCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> SyncJob:
        """Create a new sync job."""
        return await crud.sync_job.create(db, obj_in=obj_in, ctx=ctx, uow=uow)
