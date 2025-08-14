"""Service for managing sync cursor operations."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.logging import logger
from airweave.schemas.auth import AuthContext


class SyncCursorService:
    """Service for managing sync cursor operations."""

    async def get_cursor_data(
        self, db: AsyncSession, sync_id: UUID, auth_context: AuthContext
    ) -> dict:
        """Get cursor data for a sync.

        Args:
            db: Database session
            sync_id: The sync ID
            auth_context: Authentication context

        Returns:
            Cursor data dictionary, empty dict if no cursor exists
        """
        try:
            cursor = await crud.sync_cursor.get_by_sync_id(
                db, sync_id=sync_id, auth_context=auth_context
            )
            if cursor:
                return cursor.cursor_data or {}
            return {}
        except Exception as e:
            logger.warning(f"Failed to load cursor data for sync {sync_id}: {e}")
            return {}

    async def create_or_update_cursor(
        self,
        db: AsyncSession,
        sync_id: UUID,
        cursor_data: dict,
        auth_context: AuthContext,
    ) -> Optional[schemas.SyncCursor]:
        """Create or update cursor data for a sync.

        Args:
            db: Database session
            sync_id: The sync ID
            cursor_data: Cursor data to store
            auth_context: Authentication context

        Returns:
            Created or updated sync cursor, None if operation failed
        """
        try:
            cursor_create = schemas.SyncCursorCreate(sync_id=sync_id, cursor_data=cursor_data)

            cursor = await crud.sync_cursor.create_or_update(
                db=db,
                obj_in=cursor_create,
                sync_id=sync_id,
                auth_context=auth_context,
            )

            logger.info(f"Successfully created/updated cursor for sync {sync_id}")
            return cursor

        except Exception as e:
            logger.error(f"Failed to create/update cursor for sync {sync_id}: {e}")
            return None

    async def update_cursor_data(
        self,
        db: AsyncSession,
        sync_id: UUID,
        cursor_data: dict,
        auth_context: AuthContext,
    ) -> Optional[schemas.SyncCursor]:
        """Update cursor data for a sync.

        Args:
            db: Database session
            sync_id: The sync ID
            cursor_data: New cursor data
            auth_context: Authentication context

        Returns:
            Updated sync cursor, None if operation failed
        """
        try:
            cursor = await crud.sync_cursor.update_cursor_data(
                db, sync_id=sync_id, cursor_data=cursor_data, auth_context=auth_context
            )

            if cursor:
                logger.info(f"Successfully updated cursor for sync {sync_id}")
            else:
                logger.warning(f"No cursor found to update for sync {sync_id}")

            return cursor

        except Exception as e:
            logger.error(f"Failed to update cursor data for sync {sync_id}: {e}")
            return None

    async def delete_cursor(
        self,
        db: AsyncSession,
        sync_id: UUID,
        auth_context: AuthContext,
    ) -> bool:
        """Delete cursor for a sync.

        Args:
            db: Database session
            sync_id: The sync ID
            auth_context: Authentication context

        Returns:
            True if cursor was deleted, False otherwise
        """
        try:
            deleted = await crud.sync_cursor.delete_by_sync_id(
                db, sync_id=sync_id, auth_context=auth_context
            )

            if deleted:
                logger.info(f"Successfully deleted cursor for sync {sync_id}")
            else:
                logger.warning(f"No cursor found to delete for sync {sync_id}")

            return deleted

        except Exception as e:
            logger.error(f"Failed to delete cursor for sync {sync_id}: {e}")
            return False


# Singleton instance
sync_cursor_service = SyncCursorService()
