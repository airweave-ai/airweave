"""Context builder - creates SyncContext with all dependencies.

This is an internal implementation detail of the factory module.
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.logging import ContextualLogger
from airweave.core.sync_cursor_service import sync_cursor_service
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.cursor import SyncCursor
from airweave.platform.sync.pipeline.entity_tracker import EntityTracker
from airweave.platform.sync.state_publisher import SyncStatePublisher


class ContextBuilder:
    """Builder for creating SyncContext with all its dependencies.

    Handles:
    - EntityTracker creation with initial counts
    - SyncStatePublisher setup
    - Cursor loading (incremental vs full sync)
    - GuardRailService creation
    - Keyword index capability detection
    """

    def __init__(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        logger: ContextualLogger,
    ):
        """Initialize the context builder."""
        self.db = db
        self.ctx = ctx
        self.logger = logger

    async def build(
        self,
        source: BaseSource,
        source_connection_data: dict,
        destinations: list[BaseDestination],
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        entity_map: dict,
        force_full_sync: bool = False,
    ) -> SyncContext:
        """Build a complete SyncContext."""
        # 1. Load initial entity counts
        initial_counts = await crud.entity_count.get_counts_per_sync_and_type(self.db, sync.id)
        self.logger.info(f"🔢 Loaded initial entity counts: {len(initial_counts)} entity types")

        for count in initial_counts:
            self.logger.debug(f"  - {count.entity_definition_name}: {count.count} entities")

        # 2. Create EntityTracker
        entity_tracker = EntityTracker(
            job_id=sync_job.id,
            sync_id=sync.id,
            logger=self.logger,
            initial_counts=initial_counts,
        )

        # 3. Create SyncStatePublisher
        state_publisher = SyncStatePublisher(
            job_id=sync_job.id,
            sync_id=sync.id,
            entity_tracker=entity_tracker,
            logger=self.logger,
        )

        self.logger.info(f"✅ Created EntityTracker and SyncStatePublisher for job {sync_job.id}")

        # 4. Create GuardRailService
        guard_rail = GuardRailService(
            organization_id=self.ctx.organization.id,
            logger=self.logger.with_context(component="guardrail"),
        )

        # 5. Create cursor
        cursor = await self._create_cursor(
            sync=sync,
            source_connection_data=source_connection_data,
            force_full_sync=force_full_sync,
        )

        # 6. Detect keyword index capability
        has_keyword_index = await self._detect_keyword_index(destinations)

        # 7. Build SyncContext
        sync_context = SyncContext(
            source=source,
            destinations=destinations,
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=None,
            entity_tracker=entity_tracker,
            state_publisher=state_publisher,
            cursor=cursor,
            entity_map=entity_map,
            ctx=self.ctx,
            logger=self.logger,
            guard_rail=guard_rail,
            force_full_sync=force_full_sync,
            has_keyword_index=has_keyword_index,
        )

        # 8. Set cursor on source
        source.set_cursor(cursor)

        self.logger.info("Sync context created")
        return sync_context

    async def _create_cursor(
        self,
        sync: schemas.Sync,
        source_connection_data: dict,
        force_full_sync: bool,
    ) -> SyncCursor:
        """Create cursor with optional data loading."""
        cursor_schema = None
        source_class = source_connection_data["source_class"]
        if hasattr(source_class, "_cursor_class") and source_class._cursor_class:
            cursor_schema = source_class._cursor_class
            self.logger.debug(f"Source has typed cursor: {cursor_schema.__name__}")

        cursor_data = None
        if force_full_sync:
            self.logger.info(
                "🔄 FORCE FULL SYNC: Skipping cursor data to ensure all entities are fetched "
                "for accurate orphaned entity cleanup. Will still track cursor for next sync."
            )
        else:
            cursor_data = await sync_cursor_service.get_cursor_data(
                db=self.db, sync_id=sync.id, ctx=self.ctx
            )
            if cursor_data:
                self.logger.info(
                    f"📊 Incremental sync: Using cursor data with {len(cursor_data)} keys"
                )

        return SyncCursor(
            sync_id=sync.id,
            cursor_schema=cursor_schema,
            cursor_data=cursor_data,
        )

    async def _detect_keyword_index(
        self,
        destinations: list[BaseDestination],
    ) -> bool:
        """Detect if any destination has keyword index capability."""
        if not destinations:
            return False

        try:
            results = await asyncio.gather(
                *[dest.has_keyword_index() for dest in destinations],
                return_exceptions=True,
            )
            return any(r is True for r in results if not isinstance(r, Exception))
        except Exception as e:
            self.logger.warning(f"Failed to detect keyword index capability: {e}")
            return False


class ReplayContextBuilder:
    """Simplified context builder for replay operations.

    Creates a lightweight context without source connection data
    or cursor tracking (since replay doesn't need incremental sync).
    """

    def __init__(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        logger: ContextualLogger,
    ):
        """Initialize the replay context builder."""
        self.db = db
        self.ctx = ctx
        self.logger = logger

    async def build(
        self,
        source: BaseSource,
        destinations: list[BaseDestination],
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        entity_map: dict,
    ) -> SyncContext:
        """Build a SyncContext for replay operations."""
        initial_counts = await crud.entity_count.get_counts_per_sync_and_type(self.db, sync.id)

        entity_tracker = EntityTracker(
            job_id=sync_job.id,
            sync_id=sync.id,
            logger=self.logger,
            initial_counts=initial_counts,
        )

        state_publisher = SyncStatePublisher(
            job_id=sync_job.id,
            sync_id=sync.id,
            entity_tracker=entity_tracker,
            logger=self.logger,
        )

        guard_rail = GuardRailService(
            organization_id=self.ctx.organization.id,
            logger=self.logger.with_context(component="guardrail"),
        )

        cursor = SyncCursor(sync_id=sync.id)

        return SyncContext(
            source=source,
            destinations=destinations,
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=None,
            entity_tracker=entity_tracker,
            state_publisher=state_publisher,
            cursor=cursor,
            entity_map=entity_map,
            ctx=self.ctx,
            logger=self.logger,
            guard_rail=guard_rail,
            force_full_sync=True,
            has_keyword_index=False,
        )
