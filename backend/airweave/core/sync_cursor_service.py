"""Service for managing sync cursor operations."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.logging import logger


class SyncCursorService:
    """Service for managing sync cursor operations."""

    async def get_cursor_data(self, db: AsyncSession, sync_id: UUID, ctx: ApiContext) -> dict:
        """Get cursor data for a sync.

        Args:
            db: Database session
            sync_id: The sync ID
            ctx: API context

        Returns:
            Cursor data dictionary, empty dict if no cursor exists
        """
        try:
            cursor = await crud.sync_cursor.get_by_sync_id(db, sync_id=sync_id, ctx=ctx)
            if cursor:
                return cursor.cursor_data or {}
            return {}
        except Exception as e:
            logger.warning(f"Failed to load cursor data for sync {sync_id}: {e}")
            return {}

    async def get_cursor_field(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> Optional[str]:
        """Get cursor field for a sync.

        Args:
            db: Database session
            sync_id: The sync ID
            ctx: API context

        Returns:
            Cursor field name, None if no cursor exists or field not set
        """
        try:
            cursor = await crud.sync_cursor.get_by_sync_id(db, sync_id=sync_id, ctx=ctx)
            if cursor:
                return cursor.cursor_field
            return None
        except Exception as e:
            logger.warning(f"Failed to load cursor field for sync {sync_id}: {e}")
            return None

    async def create_or_update_cursor(
        self,
        db: AsyncSession,
        sync_id: UUID,
        cursor_data: dict,
        ctx: ApiContext,
        cursor_field: Optional[str] = None,
    ) -> Optional[schemas.SyncCursor]:
        """Create or update cursor data for a sync.

        Args:
            db: Database session
            sync_id: The sync ID
            cursor_data: Cursor data to store
            ctx: API context
            cursor_field: Optional cursor field name

        Returns:
            Created or updated sync cursor, None if operation failed
        """
        try:
            cursor_create = schemas.SyncCursorCreate(
                sync_id=sync_id, cursor_data=cursor_data, cursor_field=cursor_field
            )

            cursor = await crud.sync_cursor.create_or_update(
                db=db,
                obj_in=cursor_create,
                sync_id=sync_id,
                ctx=ctx,
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
        ctx: ApiContext,
    ) -> Optional[schemas.SyncCursor]:
        """Update cursor data for a sync.

        Args:
            db: Database session
            sync_id: The sync ID
            cursor_data: New cursor data
            ctx: API context

        Returns:
            Updated sync cursor, None if operation failed
        """
        try:
            cursor = await crud.sync_cursor.update_cursor_data(
                db, sync_id=sync_id, cursor_data=cursor_data, ctx=ctx
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
        ctx: ApiContext,
    ) -> bool:
        """Delete cursor for a sync.

        Args:
            db: Database session
            sync_id: The sync ID
            ctx: API context

        Returns:
            True if cursor was deleted, False otherwise
        """
        try:
            deleted = await crud.sync_cursor.delete_by_sync_id(db, sync_id=sync_id, ctx=ctx)

            if deleted:
                logger.info(f"Successfully deleted cursor for sync {sync_id}")
            else:
                logger.warning(f"No cursor found to delete for sync {sync_id}")

            return deleted

        except Exception as e:
            logger.error(f"Failed to delete cursor for sync {sync_id}: {e}")
            return False

    async def get_cursor_summary(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> dict:
        """Get a summary of cursor data including dual cursor information.
        
        This is useful for debugging and monitoring dual cursor state.
        
        Args:
            db: Database session
            sync_id: The sync ID
            ctx: API context
            
        Returns:
            Dictionary with cursor summary information
        """
        try:
            cursor = await crud.sync_cursor.get_by_sync_id(db, sync_id=sync_id, ctx=ctx)
            if not cursor:
                return {"status": "no_cursor", "cursor_field": None, "data": {}}
                
            cursor_data = cursor.cursor_data or {}
            cursor_field = cursor.cursor_field
            
            # Analyze cursor data structure
            summary = {
                "status": "active",
                "cursor_field": cursor_field,
                "last_updated": cursor.last_updated.isoformat() if cursor.last_updated else None,
                "data_keys": list(cursor_data.keys()),
                "has_dual_cursor": False,
                "overlap_keys": [],
                "original_values": {},
                "overlap_values": {}
            }
            
            # Check for dual cursor structure
            if cursor_field and cursor_field in cursor_data:
                summary["original_values"][cursor_field] = cursor_data[cursor_field]
                
                # Check for overlap cursor
                overlap_key = f"{cursor_field}_overlap"
                if overlap_key in cursor_data:
                    summary["has_dual_cursor"] = True
                    summary["overlap_keys"].append(overlap_key)
                    summary["overlap_values"][overlap_key] = cursor_data[overlap_key]
            
            # Find all overlap keys in data
            for key in cursor_data.keys():
                if key.endswith("_overlap"):
                    if key not in summary["overlap_keys"]:
                        summary["overlap_keys"].append(key)
                        summary["overlap_values"][key] = cursor_data[key]
                        summary["has_dual_cursor"] = True
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get cursor summary for sync {sync_id}: {e}")
            return {"status": "error", "error": str(e)}


# Singleton instance
sync_cursor_service = SyncCursorService()
