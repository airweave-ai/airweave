"""Cleanup service for persistent data deletion.

Provides unified cleanup for:
- Temporal schedules
- Destination data (Qdrant, Vespa) - via builder-constructed destinations
- ARF storage
"""

from typing import TYPE_CHECKING, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.platform.builders.destinations import DestinationsContextBuilder

if TYPE_CHECKING:
    from airweave.api.context import ApiContext


class CleanupService:
    """Cleanup service for persistent data deletion.

    Uses DestinationsContextBuilder for destination flexibility - the service
    doesn't know what destinations exist, it just iterates what the builder returns.
    """

    async def cleanup_sync(
        self,
        db: AsyncSession,
        sync_id: UUID,
        collection: schemas.CollectionRecord,
        ctx: "ApiContext",
    ) -> None:
        """Clean up all data for a sync.

        Always removes:
        - Temporal schedules (sync, minute-sync, daily-cleanup)
        - Destination data (Qdrant, Vespa, etc.) by sync_id
        - ARF storage by sync_id

        Args:
            db: Database session
            sync_id: Sync ID to clean up
            collection: Collection the sync belongs to
            ctx: API context
        """
        ctx.logger.info(f"Cleaning up sync {sync_id}")

        # 1. Temporal schedules
        await self._cleanup_schedules(sync_id, ctx)

        # 2. Destination data
        await self._cleanup_destinations_by_sync(db, sync_id, collection, ctx)

        # 3. ARF storage
        await self._cleanup_arf(sync_id, ctx)

        ctx.logger.info(f"Completed cleanup for sync {sync_id}")

    async def cleanup_collection(
        self,
        db: AsyncSession,
        collection: schemas.CollectionRecord,
        sync_ids: List[UUID],
        ctx: "ApiContext",
    ) -> None:
        """Clean up all data for a collection.

        Reuses cleanup_sync for each sync in the collection.

        Args:
            db: Database session
            collection: Collection to clean up
            sync_ids: List of sync IDs (must be collected before CASCADE deletes them)
            ctx: API context
        """
        ctx.logger.info(f"Cleaning up collection {collection.id} ({len(sync_ids)} syncs)")

        # Clean up each sync
        for sync_id in sync_ids:
            await self.cleanup_sync(db, sync_id, collection, ctx)

        ctx.logger.info(f"Completed cleanup for collection {collection.id}")

    # -------------------------------------------------------------------------
    # Private: Schedules
    # -------------------------------------------------------------------------

    async def _cleanup_schedules(self, sync_id: UUID, ctx: "ApiContext") -> None:
        """Delete all Temporal schedules for a sync."""
        from airweave.platform.temporal.schedule_service import temporal_schedule_service

        for prefix in ("sync", "minute-sync", "daily-cleanup"):
            schedule_id = f"{prefix}-{sync_id}"
            try:
                await temporal_schedule_service.delete_schedule_handle(schedule_id)
            except Exception as e:
                ctx.logger.debug(f"Schedule {schedule_id} not deleted: {e}")

    # -------------------------------------------------------------------------
    # Private: Destinations
    # -------------------------------------------------------------------------

    async def _cleanup_destinations_by_sync(
        self,
        db: AsyncSession,
        sync_id: UUID,
        collection: schemas.CollectionRecord,
        ctx: "ApiContext",
    ) -> None:
        """Delete destination data by sync_id."""
        destinations = await DestinationsContextBuilder.build_for_cleanup(
            db=db,
            collection=collection,
            logger=ctx.logger,
        )

        for dest in destinations:
            try:
                await dest.delete_by_sync_id(sync_id)
                ctx.logger.debug(f"Deleted {dest.__class__.__name__} data for sync {sync_id}")
            except Exception as e:
                ctx.logger.error(
                    f"Failed to delete from {dest.__class__.__name__} for sync {sync_id}: {e}"
                )

    # -------------------------------------------------------------------------
    # Private: ARF
    # -------------------------------------------------------------------------

    async def _cleanup_arf(self, sync_id: UUID, ctx: "ApiContext") -> None:
        """Delete ARF storage for a sync."""
        from airweave.platform.sync.arf import arf_service

        try:
            sync_id_str = str(sync_id)
            if await arf_service.sync_exists(sync_id_str):
                deleted = await arf_service.delete_sync(sync_id_str)
                if deleted:
                    ctx.logger.debug(f"Deleted ARF store for sync {sync_id}")
        except Exception as e:
            ctx.logger.warning(f"Failed to cleanup ARF for sync {sync_id}: {e}")


# Singleton instance
cleanup_service = CleanupService()
