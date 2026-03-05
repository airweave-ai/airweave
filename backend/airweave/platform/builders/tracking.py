"""Tracking builder for sync operations.

Builds the EntityTracker (centralized entity state tracking).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.context import BaseContext
from airweave.core.logging import ContextualLogger
from airweave.platform.sync.pipeline.entity_tracker import EntityTracker


class TrackingContextBuilder:
    """Builds entity tracking components for sync operations."""

    @classmethod
    async def build(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        ctx: BaseContext,
        logger: ContextualLogger,
    ) -> EntityTracker:
        """Build tracking components.

        Args:
            db: Database session
            sync: Sync configuration
            sync_job: The sync job being tracked
            ctx: Base context (provides org identity)
            logger: Contextual logger

        Returns:
            EntityTracker.
        """
        initial_counts = await crud.entity_count.get_counts_per_sync_and_type(db, sync.id)

        logger.info(f"Loaded initial entity counts: {len(initial_counts)} entity types")

        for count in initial_counts:
            logger.debug(f"  - {count.entity_definition_name}: {count.count} entities")

        entity_tracker = EntityTracker(
            job_id=sync_job.id,
            sync_id=sync.id,
            logger=logger,
            initial_counts=initial_counts,
        )

        logger.info(f"Created EntityTracker for job {sync_job.id}")

        return entity_tracker
