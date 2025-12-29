"""CRUD operations for sync connections.

Provides methods for managing destination slots in the multiplexer.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airweave.db.unit_of_work import UnitOfWork
from airweave.models.sync_connection import DestinationRole, SyncConnection


class CRUDSyncConnection:
    """CRUD operations for sync connections.

    Note: SyncConnection doesn't have organization_id directly.
    Access control should be enforced at the Sync level before calling these methods.
    """

    def __init__(self):
        """Initialize the CRUD object."""
        self.model = SyncConnection

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
    ) -> Optional[SyncConnection]:
        """Get sync connection by ID.

        Args:
            db: Database session
            id: Sync connection ID

        Returns:
            SyncConnection if found, None otherwise
        """
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_by_sync_id(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> List[SyncConnection]:
        """Get all sync connections for a sync.

        Args:
            db: Database session
            sync_id: Sync ID

        Returns:
            List of sync connections
        """
        result = await db.execute(
            select(self.model)
            .where(self.model.sync_id == sync_id)
            .options(selectinload(self.model.connection))
        )
        return list(result.scalars().all())

    async def get_by_sync_and_connection(
        self,
        db: AsyncSession,
        sync_id: UUID,
        connection_id: UUID,
    ) -> Optional[SyncConnection]:
        """Get sync connection by sync ID and connection ID.

        Args:
            db: Database session
            sync_id: Sync ID
            connection_id: Connection ID

        Returns:
            SyncConnection if found, None otherwise
        """
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.sync_id == sync_id,
                    self.model.connection_id == connection_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_sync_and_role(
        self,
        db: AsyncSession,
        sync_id: UUID,
        role: DestinationRole,
    ) -> List[SyncConnection]:
        """Get sync connections by sync ID and role.

        Args:
            db: Database session
            sync_id: Sync ID
            role: Destination role (active, shadow, deprecated)

        Returns:
            List of sync connections with the specified role
        """
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.sync_id == sync_id,
                    self.model.role == role.value,
                )
            )
            .options(selectinload(self.model.connection))
        )
        return list(result.scalars().all())

    async def get_active_and_shadow(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> List[SyncConnection]:
        """Get active and shadow sync connections for a sync.

        Used during sync to get all destinations that should receive writes.

        Args:
            db: Database session
            sync_id: Sync ID

        Returns:
            List of active and shadow sync connections
        """
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.sync_id == sync_id,
                    self.model.role.in_(
                        [DestinationRole.ACTIVE.value, DestinationRole.SHADOW.value]
                    ),
                )
            )
            .options(selectinload(self.model.connection))
        )
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        connection_id: UUID,
        role: DestinationRole = DestinationRole.ACTIVE,
        uow: Optional[UnitOfWork] = None,
    ) -> SyncConnection:
        """Create a new sync connection.

        Args:
            db: Database session
            sync_id: Sync ID
            connection_id: Connection ID
            role: Destination role (default: active)
            uow: Optional unit of work for transaction control

        Returns:
            Created sync connection
        """
        db_obj = SyncConnection(
            sync_id=sync_id,
            connection_id=connection_id,
            role=role.value,
        )
        db.add(db_obj)

        if uow:
            await uow.flush()
        else:
            await db.commit()
            await db.refresh(db_obj)

        return db_obj

    async def update_role(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        role: DestinationRole,
        uow: Optional[UnitOfWork] = None,
    ) -> Optional[SyncConnection]:
        """Update the role of a sync connection.

        Args:
            db: Database session
            id: Sync connection ID
            role: New role
            uow: Optional unit of work for transaction control

        Returns:
            Updated sync connection
        """
        await db.execute(update(self.model).where(self.model.id == id).values(role=role.value))

        if uow:
            await uow.flush()
        else:
            await db.commit()

        return await self.get(db, id=id)

    async def bulk_update_role(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        from_role: DestinationRole,
        to_role: DestinationRole,
        uow: Optional[UnitOfWork] = None,
    ) -> int:
        """Bulk update roles for all sync connections with a specific role.

        Args:
            db: Database session
            sync_id: Sync ID
            from_role: Current role to match
            to_role: New role to set
            uow: Optional unit of work for transaction control

        Returns:
            Number of rows updated
        """
        result = await db.execute(
            update(self.model)
            .where(
                and_(
                    self.model.sync_id == sync_id,
                    self.model.role == from_role.value,
                )
            )
            .values(role=to_role.value)
        )

        if uow:
            await uow.flush()
        else:
            await db.commit()

        return result.rowcount

    async def remove(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        uow: Optional[UnitOfWork] = None,
    ) -> bool:
        """Remove a sync connection.

        Args:
            db: Database session
            id: Sync connection ID
            uow: Optional unit of work for transaction control

        Returns:
            True if deleted, False if not found
        """
        db_obj = await self.get(db, id=id)
        if not db_obj:
            return False

        await db.delete(db_obj)

        if uow:
            await uow.flush()
        else:
            await db.commit()

        return True


# Singleton instance
sync_connection = CRUDSyncConnection()
