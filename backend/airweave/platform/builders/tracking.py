"""Tracking builder for sync operations.

Builds progress tracking components:
- EntityTracker: Centralized entity state tracking
- SyncStatePublisher: Redis pubsub publishing
- GuardRailService: Rate limiting
"""

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.context import BaseContext
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.logging import ContextualLogger
from airweave.platform.sync.pipeline.entity_tracker import EntityTracker
from airweave.platform.sync.state_publisher import SyncStatePublisher


class TrackingContextBuilder:
    """Builds progress tracking components for sync operations."""

    @classmethod
    async def build(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        ctx: BaseContext,
        logger: ContextualLogger,
    ) -> tuple:
        """Build tracking components.

        Args:
            db: Database session
            sync: Sync configuration
            sync_job: The sync job being tracked
            ctx: Base context (provides org identity)
            logger: Contextual logger

        Returns:
            Tuple of (entity_tracker, state_publisher, guard_rail).
        """
        # Load initial entity counts from database
        initial_counts = await crud.entity_count.get_counts_per_sync_and_type(db, sync.id)

        logger.info(f"🔢 Loaded initial entity counts: {len(initial_counts)} entity types")

        # Log the initial counts for debugging
        for count in initial_counts:
            logger.debug(f"  - {count.entity_definition_name}: {count.count} entities")

        # Create EntityTracker (pure state tracking)
        entity_tracker = EntityTracker(
            job_id=sync_job.id,
            sync_id=sync.id,
            logger=logger,
            initial_counts=initial_counts,
        )

        # Create SyncStatePublisher (handles pubsub publishing)
        state_publisher = SyncStatePublisher(
            job_id=sync_job.id,
            sync_id=sync.id,
            entity_tracker=entity_tracker,
            logger=logger,
        )

        # Create GuardRailService with contextual logger
        guard_rail = GuardRailService(
            organization_id=ctx.organization.id,
            logger=logger.with_context(component="guardrail"),
        )

        logger.info(f"✅ Created EntityTracker and SyncStatePublisher for job {sync_job.id}")

        return entity_tracker, state_publisher, guard_rail
