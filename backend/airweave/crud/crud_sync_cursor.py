"""CRUD operations for sync cursor."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import models, schemas
from airweave.crud._base_organization import CRUDBaseOrganization


class CRUDSyncCursor(
    CRUDBaseOrganization[models.SyncCursor, schemas.SyncCursorCreate, schemas.SyncCursorUpdate]
):
    """CRUD operations for sync cursor."""

    async def get_by_sync_id(
        self, db: AsyncSession, *, sync_id: UUID, auth_context: schemas.AuthContext
    ) -> Optional[models.SyncCursor]:
        """Get sync cursor by sync ID.

        Args:
            db: Database session
            sync_id: The sync ID
            auth_context: Authentication context

        Returns:
            Sync cursor if found, None otherwise
        """
        stmt = select(models.SyncCursor).where(
            models.SyncCursor.sync_id == sync_id,
            models.SyncCursor.organization_id == auth_context.organization_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        db: AsyncSession,
        *,
        obj_in: schemas.SyncCursorCreate,
        sync_id: UUID,
        auth_context: schemas.AuthContext,
    ) -> models.SyncCursor:
        """Create or update sync cursor for a sync.

        Args:
            db: Database session
            obj_in: Sync cursor data
            sync_id: The sync ID
            auth_context: Authentication context

        Returns:
            Created or updated sync cursor
        """
        # Check if cursor already exists for this sync
        existing_cursor = await self.get_by_sync_id(db, sync_id=sync_id, auth_context=auth_context)

        if existing_cursor:
            # Update existing cursor
            return await self.update(
                db, db_obj=existing_cursor, obj_in=obj_in, auth_context=auth_context
            )
        else:
            # Create new cursor
            obj_in.sync_id = sync_id
            return await self.create(db, obj_in=obj_in, auth_context=auth_context)

    async def update_cursor_data(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        cursor_data: dict,
        auth_context: schemas.AuthContext,
    ) -> Optional[models.SyncCursor]:
        """Update cursor data for a sync.

        Args:
            db: Database session
            sync_id: The sync ID
            cursor_data: New cursor data
            auth_context: Authentication context

        Returns:
            Updated sync cursor if found, None otherwise
        """
        cursor = await self.get_by_sync_id(db, sync_id=sync_id, auth_context=auth_context)

        if cursor:
            update_data = schemas.SyncCursorUpdate(cursor_data=cursor_data)
            return await self.update(
                db, db_obj=cursor, obj_in=update_data, auth_context=auth_context
            )

        return None

    async def delete_by_sync_id(
        self, db: AsyncSession, *, sync_id: UUID, auth_context: schemas.AuthContext
    ) -> bool:
        """Delete sync cursor by sync ID.

        Args:
            db: Database session
            sync_id: The sync ID
            auth_context: Authentication context

        Returns:
            True if deleted, False if not found
        """
        cursor = await self.get_by_sync_id(db, sync_id=sync_id, auth_context=auth_context)

        if cursor:
            await self.remove(db, id=cursor.id, auth_context=auth_context)
            return True

        return False


# Create singleton instance
sync_cursor = CRUDSyncCursor(models.SyncCursor, track_user=False)
