"""SyncFactory - creates orchestrators for sync operations.

This is the main factory class. See __init__.py for public exports.
"""

import importlib
import time
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.constants.reserved_ids import RESERVED_TABLE_ENTITY_ID
from airweave.core.logging import LoggerConfigurator, logger
from airweave.db.init_db_native import init_db_with_entity_definitions
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sync.factory._context import ContextBuilder
from airweave.platform.sync.factory._destination import DestinationBuilder
from airweave.platform.sync.factory._pipeline import PipelineBuilder
from airweave.platform.sync.factory._source import SourceBuilder
from airweave.platform.sync.orchestrator import SyncOrchestrator
from airweave.platform.sync.stream import AsyncSourceStream
from airweave.platform.sync.worker_pool import AsyncWorkerPool


class SyncFactory:
    """Factory for creating sync orchestrators.

    Example:
        orchestrator = await SyncFactory.create_orchestrator(
            db=db,
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,
            ctx=ctx,
        )
        await orchestrator.run()

    For replay operations, see sync/multiplex/ module.
    """

    @classmethod
    async def create_orchestrator(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        connection: schemas.Connection,  # Unused - kept for backwards compatibility
        ctx: ApiContext,
        access_token: Optional[str] = None,
        max_workers: Optional[int] = None,
        force_full_sync: bool = False,
    ) -> SyncOrchestrator:
        """Create a sync orchestrator with all required components.

        Args:
            db: Database session
            sync: Sync configuration
            sync_job: Sync job for tracking
            collection: Target collection
            connection: Unused (kept for API compatibility)
            ctx: API context
            access_token: Optional token override
            max_workers: Max concurrent workers (default: from settings)
            force_full_sync: Whether to force full sync (skips cursor)

        Returns:
            Configured SyncOrchestrator ready to run
        """
        if max_workers is None:
            max_workers = settings.SYNC_MAX_WORKERS
            logger.debug(f"Using configured max_workers: {max_workers}")

        init_start = time.time()

        # 1. Create contextual logger
        sync_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync",
            dimensions={
                "sync_id": str(sync.id),
                "sync_job_id": str(sync_job.id),
                "organization_id": str(ctx.organization.id),
                "collection_readable_id": str(collection.readable_id),
                "organization_name": ctx.organization.name,
                "scheduled": str(sync_job.scheduled),
            },
        )

        # 2. Build source
        source_builder = SourceBuilder(db, ctx, sync_logger)
        source, source_connection_data = await source_builder.build(
            sync=sync,
            access_token=access_token,
            sync_job=sync_job,
        )

        # Update logger with source connection ID
        sync_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync",
            dimensions={
                "sync_id": str(sync.id),
                "sync_job_id": str(sync_job.id),
                "organization_id": str(ctx.organization.id),
                "source_connection_id": str(source_connection_data["source_connection_id"]),
                "collection_readable_id": str(collection.readable_id),
                "organization_name": ctx.organization.name,
                "scheduled": str(sync_job.scheduled),
            },
        )

        # 3. Build destinations
        dest_builder = DestinationBuilder(db, ctx, sync_logger)
        destinations = await dest_builder.build(sync=sync, collection=collection)

        # 4. Get entity map
        entity_map = await cls._get_entity_definition_map(db)

        # 5. Build sync context
        context_builder = ContextBuilder(db, ctx, sync_logger)
        sync_context = await context_builder.build(
            source=source,
            source_connection_data=source_connection_data,
            destinations=destinations,
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            entity_map=entity_map,
            force_full_sync=force_full_sync,
        )

        # 6. Build pipeline
        entity_pipeline = PipelineBuilder.build(
            sync_context=sync_context,
            include_raw_data_handler=True,
        )

        # 7. Create worker pool and stream
        worker_pool = AsyncWorkerPool(max_workers=max_workers, logger=sync_logger)
        stream = AsyncSourceStream(
            source_generator=source.generate_entities(),
            queue_size=10000,
            logger=sync_logger,
        )

        # 8. Create orchestrator
        orchestrator = SyncOrchestrator(
            entity_pipeline=entity_pipeline,
            worker_pool=worker_pool,
            stream=stream,
            sync_context=sync_context,
        )

        logger.info(f"Total orchestrator initialization took {time.time() - init_start:.2f}s")
        return orchestrator

    @classmethod
    async def _get_entity_definition_map(
        cls,
        db: AsyncSession,
    ) -> dict[type[BaseEntity], UUID]:
        """Get entity class to definition ID map."""
        await init_db_with_entity_definitions(db)

        entity_definitions = await crud.entity_definition.get_all(db)

        entity_map = {}
        for entity_def in entity_definitions:
            if entity_def.id == RESERVED_TABLE_ENTITY_ID:
                continue
            full_module = f"airweave.platform.entities.{entity_def.module_name}"
            module = importlib.import_module(full_module)
            entity_class = getattr(module, entity_def.class_name)
            entity_map[entity_class] = entity_def.id

        return entity_map
