"""Sync repository wrapping crud.sync."""

from typing import Optional
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.shared_models import SyncStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.syncs.protocols import SyncRepositoryProtocol
from airweave.domains.syncs.types import OptimisticLockError
from airweave.models.sync import Sync
from airweave.schemas.sync import SyncCreate, SyncUpdate


class SyncRepository(SyncRepositoryProtocol):
    """Delegates to the crud.sync singleton."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[schemas.Sync]:
        """Get a sync by ID, including connections."""
        return await crud.sync.get(db, id=id, ctx=ctx, with_connections=True)

    async def get_without_connections(
        self, db: AsyncSession, id: UUID, ctx: ApiContext
    ) -> Optional[Sync]:
        """Get a sync by ID without connections."""
        return await crud.sync.get(db, id=id, ctx=ctx, with_connections=False)

    async def transition_status(
        self,
        db: AsyncSession,
        sync_id: UUID,
        expected: SyncStatus,
        target: SyncStatus,
    ) -> None:
        """Optimistic status update: SET status=target WHERE id=sync_id AND status=expected.

        Raises OptimisticLockError if the status changed since read.
        """
        result = await db.execute(
            update(Sync).where(Sync.id == sync_id, Sync.status == expected).values(status=target)
        )
        if result.rowcount == 0:
            raise OptimisticLockError(sync_id, expected)

    async def create(
        self,
        db: AsyncSession,
        obj_in: SyncCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.Sync:
        """Create a new sync with its connection associations."""
        return await crud.sync.create(db=db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def update(
        self,
        db: AsyncSession,
        db_obj: Sync,
        obj_in: SyncUpdate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Sync:
        """Update an existing sync."""
        return await crud.sync.update(db=db, db_obj=db_obj, obj_in=obj_in, ctx=ctx, uow=uow)
