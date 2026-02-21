"""Sync repository wrapping crud.sync."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.syncs.protocols import SyncRepositoryProtocol
from airweave.models.sync import Sync
from airweave.schemas.sync import SyncUpdate


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
