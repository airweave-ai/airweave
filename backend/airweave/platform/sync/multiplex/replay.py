"""Replay service - populates destinations from ARF storage.

Enables replaying raw entities from ARF to new destinations without
hitting the source again. Used for migration workflows.

Design: Uses builders + SyncOrchestrator with ARFReplaySource that
reads from ARF instead of an external source.
"""

import time
from typing import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger, LoggerConfigurator
from airweave.core.shared_models import SyncJobStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.factory import SyncFactory
from airweave.platform.sync.factory._context import ReplayContextBuilder
from airweave.platform.sync.factory._destination import DestinationBuilder
from airweave.platform.sync.factory._pipeline import PipelineBuilder
from airweave.platform.sync.orchestrator import SyncOrchestrator
from airweave.platform.sync.raw_data import raw_data_service
from airweave.platform.sync.stream import AsyncSourceStream
from airweave.platform.sync.worker_pool import AsyncWorkerPool


class ARFReplaySource(BaseSource):
    """Pseudo-source that reads entities from ARF storage.

    This allows reusing the SyncOrchestrator pipeline for replay operations.
    Instead of fetching from an external API, it iterates over the ARF store.
    """

    _name = "ARF Replay"
    _short_name = "arf_replay"
    _auth_type = None

    def __init__(self, sync_id: str, logger: ContextualLogger):
        """Initialize ARF replay source.

        Args:
            sync_id: Sync ID to replay from
            logger: Contextual logger
        """
        self._sync_id = sync_id
        self.logger = logger

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from ARF store.

        Yields:
            BaseEntity instances reconstructed from ARF
        """
        self.logger.info(f"Starting ARF replay for sync {self._sync_id}")
        count = 0

        async for entity in raw_data_service.iter_entities_for_replay(self._sync_id):
            count += 1
            if count % 100 == 0:
                self.logger.debug(f"Replayed {count} entities from ARF")
            yield entity

        self.logger.info(f"ARF replay completed: {count} entities yielded")


async def replay_to_destination(
    db: AsyncSession,
    ctx: ApiContext,
    sync_id: UUID,
    target_connection_id: UUID,
) -> schemas.SyncJob:
    """Replay entities from ARF to a specific destination.

    High-level API that creates an orchestrator and runs it.

    Args:
        db: Database session
        ctx: API context
        sync_id: Sync ID to replay from
        target_connection_id: Destination connection ID

    Returns:
        SyncJob tracking the replay progress

    Raises:
        ValueError: If ARF store doesn't exist
        NotFoundException: If sync or destination not found
    """
    orchestrator = await create_replay_orchestrator(
        db=db,
        ctx=ctx,
        sync_id=sync_id,
        target_connection_id=target_connection_id,
    )

    await orchestrator.run()
    return orchestrator.sync_context.sync_job


async def create_replay_orchestrator(
    db: AsyncSession,
    ctx: ApiContext,
    sync_id: UUID,
    target_connection_id: UUID,
    max_workers: int = None,
) -> SyncOrchestrator:
    """Create an orchestrator for ARF replay operations.

    Uses builders for modular construction:
    - DestinationBuilder: Creates target destination
    - ReplayContextBuilder: Creates lightweight context
    - PipelineBuilder: Creates pipeline (without RawDataHandler)

    Args:
        db: Database session
        ctx: API context
        sync_id: Sync ID to replay from
        target_connection_id: Target destination connection ID
        max_workers: Max concurrent workers

    Returns:
        SyncOrchestrator configured for replay
    """
    from airweave.core.config import settings

    if max_workers is None:
        max_workers = settings.SYNC_MAX_WORKERS

    init_start = time.time()

    # 1. Validate ARF store exists
    arf_stats = await raw_data_service.get_replay_stats(str(sync_id))
    if not arf_stats.get("exists"):
        raise ValueError(f"No ARF store found for sync {sync_id}")

    entity_count = arf_stats.get("entity_count", 0)

    # 2. Get sync and source connection
    sync = await crud.sync.get(db, id=sync_id, ctx=ctx, with_connections=True)
    if not sync:
        raise NotFoundException(f"Sync {sync_id} not found")

    source_conn = await crud.source_connection.get_by_sync_id(db, sync_id=sync_id, ctx=ctx)
    if not source_conn:
        raise NotFoundException(f"No source connection found for sync {sync_id}")

    collection = await crud.collection.get_by_readable_id(
        db, readable_id=source_conn.readable_collection_id, ctx=ctx
    )
    if not collection:
        raise NotFoundException(f"Collection not found for sync {sync_id}")

    collection_schema = schemas.Collection.model_validate(collection, from_attributes=True)

    # 3. Create sync job
    async with UnitOfWork(db) as uow:
        sync_job = await crud.sync_job.create(
            db,
            obj_in=schemas.SyncJobCreate(
                sync_id=sync_id,
                status=SyncJobStatus.PENDING,
                scheduled=False,
            ),
            ctx=ctx,
            uow=uow,
        )
        await uow.commit()

    sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

    # 4. Create contextual logger
    replay_logger = LoggerConfigurator.configure_logger(
        "airweave.platform.sync.replay",
        dimensions={
            "sync_id": str(sync_id),
            "sync_job_id": str(sync_job.id),
            "organization_id": str(ctx.organization.id),
            "target_connection_id": str(target_connection_id),
            "mode": "replay",
        },
    )

    replay_logger.info(
        f"Starting replay from ARF for sync {sync_id} → connection {target_connection_id}",
        extra={"entity_count": entity_count},
    )

    # 5. Build destination
    dest_builder = DestinationBuilder(db, ctx, replay_logger)
    destinations = await dest_builder.build_for_ids(
        destination_ids=[target_connection_id],
        collection=collection_schema,
        sync_id=sync_id,
    )

    if not destinations:
        raise ValueError(f"Could not create destination for connection {target_connection_id}")

    # 6. Get entity map
    entity_map = await SyncFactory._get_entity_definition_map(db)

    # 7. Create ARF source
    arf_source = ARFReplaySource(str(sync_id), replay_logger)

    # 8. Build context (using replay-specific builder)
    context_builder = ReplayContextBuilder(db, ctx, replay_logger)
    sync_context = await context_builder.build(
        source=arf_source,
        destinations=destinations,
        sync=sync,
        sync_job=sync_job_schema,
        collection=collection_schema,
        entity_map=entity_map,
    )

    # 9. Build pipeline (skip RawDataHandler for replay)
    entity_pipeline = PipelineBuilder.build(
        sync_context=sync_context,
        include_raw_data_handler=False,
    )

    # 10. Create worker pool and stream
    worker_pool = AsyncWorkerPool(max_workers=max_workers, logger=replay_logger)
    stream = AsyncSourceStream(
        source_generator=arf_source.generate_entities(),
        queue_size=10000,
        logger=replay_logger,
    )

    # 11. Create orchestrator
    orchestrator = SyncOrchestrator(
        entity_pipeline=entity_pipeline,
        worker_pool=worker_pool,
        stream=stream,
        sync_context=sync_context,
    )

    replay_logger.info(f"Replay orchestrator created in {time.time() - init_start:.2f}s")
    return orchestrator
