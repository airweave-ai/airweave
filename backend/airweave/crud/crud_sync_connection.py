"""CRUD operations for sync connections (multiplexer support)."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airweave.db.unit_of_work import UnitOfWork
from airweave.models.sync_connection import DestinationRole, SyncConnection


class CRUDSyncConnection:
    """CRUD for sync connections - used by multiplexer.

    Note: Access control is enforced at the Sync level before calling these.
    """

    async def get_by_sync_id(self, db: AsyncSession, sync_id: UUID) -> List[SyncConnection]:
        """Get all sync connections for a sync."""
        result = await db.execute(
            select(SyncConnection)
            .where(SyncConnection.sync_id == sync_id)
            .options(selectinload(SyncConnection.connection))
        )
        return list(result.scalars().all())

    async def get_active_and_shadow(self, db: AsyncSession, sync_id: UUID) -> List[SyncConnection]:
        """Get destinations that should receive writes (active + shadow)."""
        result = await db.execute(
            select(SyncConnection)
            .where(
                and_(
                    SyncConnection.sync_id == sync_id,
                    SyncConnection.role.in_(
                        [DestinationRole.ACTIVE.value, DestinationRole.SHADOW.value]
                    ),
                )
            )
            .options(selectinload(SyncConnection.connection))
        )
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        connection_id: UUID,
        role: DestinationRole = DestinationRole.SHADOW,
        uow: Optional[UnitOfWork] = None,
    ) -> SyncConnection:
        """Create a new sync connection slot."""
        db_obj = SyncConnection(sync_id=sync_id, connection_id=connection_id, role=role.value)
        db.add(db_obj)
        if uow:
            await uow.flush()
        else:
            await db.commit()
            await db.refresh(db_obj)
        return db_obj

    async def update_role(
        self, db: AsyncSession, *, id: UUID, role: DestinationRole, uow: Optional[UnitOfWork] = None
    ) -> None:
        """Update role of a sync connection."""
        await db.execute(
            update(SyncConnection).where(SyncConnection.id == id).values(role=role.value)
        )
        if uow:
            await uow.flush()
        else:
            await db.commit()


sync_connection = CRUDSyncConnection()
