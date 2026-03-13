"""Source context builder for sync operations.

Handles sync-specific orchestration on top of SourceLifecycleService:
- Resolves source_connection from sync
- Snapshot guard
- File downloader setup
- Cursor creation
- ARF replay mode
"""

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.container import (
    container as app_container,
)  # [code blue] todo: remove container import
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger
from airweave.core.sync_cursor_service import sync_cursor_service
from airweave.domains.browse_tree.repository import NodeSelectionRepository
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sync_pipeline.contexts.infra import InfraContext
from airweave.domains.sync_pipeline.contexts.source import SourceContext
from airweave.platform.sources._base import BaseSource
from airweave.domains.sync_pipeline.config import SyncConfig
from airweave.domains.sync_pipeline.cursor import SyncCursor


class SourceContextBuilder:
    """Builds source context with all required configuration."""

    @classmethod
    async def build(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        infra: InfraContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> SourceContext:
        """Build complete source context.

        Args:
            db: Database session
            sync: Sync configuration
            sync_job: The sync job (needed for file downloader)
            infra: Infrastructure context (provides ctx and logger)
            access_token: Optional direct token (skips credential loading)
            force_full_sync: If True, skip cursor loading
            execution_config: Optional execution config

        Returns:
            SourceContext with configured source and cursor.
        """
        ctx = infra.ctx
        logger = infra.logger

        # Check for ARF replay mode - override source with ArfReplaySource
        if execution_config and execution_config.behavior.replay_from_arf:
            return await cls._build_arf_replay_context(
                db=db,
                sync=sync,
                infra=infra,
                execution_config=execution_config,
            )

        # 1. Load source connection from sync
        source_connection_obj = await crud.source_connection.get_by_sync_id(
            db, sync_id=sync.id, ctx=ctx
        )
        if not source_connection_obj:
            raise NotFoundException(
                f"Source connection record not found for sync {sync.id}. "
                f"This typically occurs when a source connection is deleted while a "
                f"scheduled workflow is queued. The workflow should self-destruct and "
                f"clean up orphaned schedules."
            )

        # 2. Guard: snapshot sources that completed have their short_name updated
        # to the original source (e.g., "github"). Detect this by checking if the
        # stored config validates as a SnapshotConfig.
        cls._validate_not_completed_snapshot(source_connection_obj)

        # 3. Create source instance
        if app_container is None:
            raise RuntimeError("Container not initialized")

        source = await app_container.source_lifecycle_service.create(
            db=db,
            source_connection_id=UUID(str(source_connection_obj.id)),
            ctx=ctx,
            access_token=access_token,
        )

        # Setup file downloader for file-based sources
        cls._setup_file_downloader(source, sync_job, logger)

        # 4. Create cursor
        cursor = await cls._create_cursor(
            db=db,
            sync=sync,
            source_class=type(source),
            ctx=ctx,
            logger=logger,
            force_full_sync=force_full_sync,
            execution_config=execution_config,
        )

        # 5. Set cursor on source
        source.set_cursor(cursor)

        # 5. Load node selections if they exist for this source connection
        node_selections = await cls._load_node_selections(
            db, UUID(str(source_connection_obj.id)), ctx
        )
        if node_selections:
            source.set_node_selections(node_selections)
            logger.info(f"Loaded {len(node_selections)} node selections for targeted sync")

        return SourceContext(source=source, cursor=cursor)

    @classmethod
    async def _build_arf_replay_context(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        infra: InfraContext,
        execution_config: SyncConfig,
    ) -> SourceContext:
        """Build source context for ARF replay mode.

        Creates an ArfReplaySource instead of the normal source,
        reading entities from ARF storage.

        Args:
            db: Database session
            sync: Sync configuration
            infra: Infrastructure context
            execution_config: Execution config (must have replay_from_arf=True)

        Returns:
            SourceContext with ArfReplaySource
        """
        from airweave.domains.arf.replay_source import ArfReplaySource

        ctx = infra.ctx
        logger = infra.logger

        source_connection = await crud.source_connection.get_by_sync_id(
            db, sync_id=sync.id, ctx=ctx
        )
        original_short_name = source_connection.short_name if source_connection else None

        logger.info(
            f"ARF Replay mode: Creating ArfReplaySource for sync {sync.id} "
            f"(masquerading as '{original_short_name}')"
        )

        source = await ArfReplaySource.create(
            sync_id=sync.id,
            storage=app_container.storage_backend,
            logger=logger,
            restore_files=True,
            original_short_name=original_short_name,
        )

        # Set logger on source
        if hasattr(source, "set_logger"):
            source.set_logger(logger)

        # Validate ARF data exists
        if not await source.validate():
            from airweave.core.exceptions import NotFoundException

            raise NotFoundException(
                f"ARF data not found for sync {sync.id}. "
                f"Cannot replay - ensure ARF capture was enabled for previous syncs."
            )

        # No cursor for ARF replay (we're replaying all entities)
        cursor = SyncCursor(
            sync_id=sync.id,
            cursor_schema=None,
            cursor_data=None,
        )

        return SourceContext(source=source, cursor=cursor)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_not_completed_snapshot(source_connection_obj) -> None:
        """Guard: completed snapshots that had their short_name restored cannot re-sync."""
        if source_connection_obj.short_name != "snapshot":
            from pydantic import ValidationError

            from airweave.platform.configs.config import SnapshotConfig

            try:
                SnapshotConfig(**(source_connection_obj.config_fields or {}))
                # Config is a valid SnapshotConfig but short_name is not "snapshot"
                # → this is a completed snapshot, can't re-sync
                from airweave.domains.sync_pipeline.exceptions import SyncFailureError

                raise SyncFailureError(
                    f"Cannot re-sync a completed snapshot source connection "
                    f"('{source_connection_obj.name}'). Snapshot data is immutable — "
                    f"create a new snapshot source connection instead."
                )
            except ValidationError:
                pass  # Not a snapshot config, proceed normally

    @classmethod
    def _setup_file_downloader(
        cls, source: BaseSource, sync_job: Optional[Any], logger: ContextualLogger
    ) -> None:
        """Setup file downloader for file-based sources."""
        from airweave.domains.storage.file_service import FileService

        # Require sync_job - we're always in sync context when this is called
        if not sync_job or not hasattr(sync_job, "id"):
            raise ValueError(
                "sync_job is required for file downloader initialization. "
                "This method should only be called from create_orchestrator() "
                "where sync_job exists."
            )

        file_downloader = FileService(
            sync_job_id=sync_job.id,
            storage_backend=app_container.storage_backend,
        )
        source.set_file_downloader(file_downloader)
        logger.debug(
            f"File downloader configured for {source.__class__.__name__} "
            f"(sync_job_id: {sync_job.id})"
        )

    # -------------------------------------------------------------------------
    # Private: Cursor Creation
    # -------------------------------------------------------------------------

    @classmethod
    async def _create_cursor(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        source_class: type,
        ctx: ApiContext,
        logger: ContextualLogger,
        force_full_sync: bool,
        execution_config: Optional[SyncConfig],
    ) -> SyncCursor:
        """Create sync cursor with optional data loading."""
        # Get cursor schema from source class (direct reference, no string lookup!)
        cursor_schema = None
        if hasattr(source_class, "cursor_class") and source_class.cursor_class:
            cursor_schema = source_class.cursor_class
            logger.debug(f"Source has typed cursor: {cursor_schema.__name__}")

        # Determine whether to load cursor data
        if force_full_sync:
            logger.info(
                "🔄 FORCE FULL SYNC: Skipping cursor data to ensure all entities are fetched "
                "for accurate orphaned entity cleanup. Will still track cursor for next sync."
            )
            cursor_data = None
        elif execution_config and execution_config.cursor.skip_load:
            logger.info(
                "🔄 SKIP CURSOR LOAD: Fetching all entities "
                "(execution_config.cursor.skip_load=True)"
            )
            cursor_data = None
        else:
            # Normal incremental sync - load cursor data
            cursor_data = await sync_cursor_service.get_cursor_data(db=db, sync_id=sync.id, ctx=ctx)
            if cursor_data:
                logger.info(f"📊 Incremental sync: Using cursor data with {len(cursor_data)} keys")

        return SyncCursor(
            sync_id=sync.id,
            cursor_schema=cursor_schema,
            cursor_data=cursor_data,
        )

    # -------------------------------------------------------------------------
    # Private: Node Selection Loading
    # -------------------------------------------------------------------------

    @classmethod
    async def _load_node_selections(
        cls,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
    ) -> List[NodeSelectionData]:
        """Load node selections for a source connection (for targeted sync)."""
        repo = NodeSelectionRepository()
        rows = await repo.get_by_source_connection(db, source_connection_id, ctx.organization.id)
        return [
            NodeSelectionData(
                source_node_id=row.source_node_id,
                node_type=row.node_type,
                node_title=row.node_title,
                node_metadata=row.node_metadata,
            )
            for row in rows
        ]
