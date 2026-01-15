"""Module for sync factory that creates orchestrator instances.

This factory uses SyncContextBuilder and DispatcherBuilder to construct
all components needed for a sync run.
"""

import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.builders import SyncContextBuilder
from airweave.platform.sync.access_control_pipeline import AccessControlPipeline
from airweave.platform.sync.actions import (
    ACActionDispatcher,
    ACActionResolver,
    EntityActionResolver,
    EntityDispatcherBuilder,
)
from airweave.platform.sync.config import SyncExecutionConfig
from airweave.platform.sync.entity_pipeline import EntityPipeline
from airweave.platform.sync.handlers import ACPostgresHandler
from airweave.platform.sync.orchestrator import SyncOrchestrator
from airweave.platform.sync.pipeline.acl_membership_tracker import ACLMembershipTracker
from airweave.platform.sync.stream import AsyncSourceStream
from airweave.platform.sync.worker_pool import AsyncWorkerPool


class SyncFactory:
    """Factory for sync orchestrator.

    Uses SyncContextBuilder to create contexts and DispatcherBuilder
    to create the action dispatcher with handlers.
    """

    @classmethod
    async def create_orchestrator(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        connection: schemas.Connection,
        ctx: ApiContext,
        access_token: Optional[str] = None,
        max_workers: int = None,
        force_full_sync: bool = False,
        execution_config: Optional[SyncExecutionConfig] = None,
    ) -> SyncOrchestrator:
        """Create a dedicated orchestrator instance for a sync run.

        This method creates all necessary components for a sync run, including the
        context and a dedicated orchestrator instance for concurrent execution.

        Args:
            db: Database session
            sync: The sync configuration
            sync_job: The sync job
            collection: The collection to sync to
            connection: The connection
            ctx: The API context
            access_token: Optional token to use instead of stored credentials
            max_workers: Maximum number of concurrent workers (default: from settings)
            force_full_sync: If True, forces a full sync with orphaned entity deletion
            execution_config: Optional execution config for controlling sync behavior

        Returns:
            A dedicated SyncOrchestrator instance
        """
        # Use configured value if max_workers not specified
        if max_workers is None:
            max_workers = settings.SYNC_MAX_WORKERS
            logger.debug(f"Using configured max_workers: {max_workers}")

        # Track initialization timing
        init_start = time.time()
        logger.info("Creating sync context via context builders...")

        # Step 1: Build sync context using SyncContextBuilder
        sync_context = await SyncContextBuilder.build(
            db=db,
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,
            ctx=ctx,
            access_token=access_token,
            force_full_sync=force_full_sync,
            execution_config=execution_config,
        )

        logger.debug(f"Sync context created in {time.time() - init_start:.2f}s")

        # Step 2: Build dispatcher using DispatcherBuilder
        logger.debug("Initializing pipeline components...")

        dispatcher = EntityDispatcherBuilder.build(
            destinations=sync_context.destinations,
            execution_config=execution_config,
            logger=sync_context.logger,
        )

        # Step 3: Build pipelines
        action_resolver = EntityActionResolver(entity_map=sync_context.entity_map)

        entity_pipeline = EntityPipeline(
            entity_tracker=sync_context.entity_tracker,
            action_resolver=action_resolver,
            action_dispatcher=dispatcher,
        )

        # Access control pipeline (simple resolver + dispatcher)
        access_control_resolver = ACActionResolver()
        access_control_dispatcher = ACActionDispatcher(handlers=[ACPostgresHandler()])
        access_control_tracker = ACLMembershipTracker(
            source_connection_id=sync_context.source_connection_id,
            organization_id=sync_context.organization_id,
            logger=sync_context.logger,
        )
        access_control_pipeline = AccessControlPipeline(
            resolver=access_control_resolver,
            dispatcher=access_control_dispatcher,
            tracker=access_control_tracker,
        )

        # Step 4: Create worker pool
        worker_pool = AsyncWorkerPool(max_workers=max_workers, logger=sync_context.logger)

        # Step 5: Create stream
        stream = AsyncSourceStream(
            source_generator=sync_context.source_instance.generate_entities(),
            queue_size=10000,  # TODO: make this configurable
            logger=sync_context.logger,
        )

        # Step 6: Create orchestrator
        orchestrator = SyncOrchestrator(
            entity_pipeline=entity_pipeline,
            worker_pool=worker_pool,
            stream=stream,
            sync_context=sync_context,
            access_control_pipeline=access_control_pipeline,
        )

        logger.info(f"Total orchestrator initialization took {time.time() - init_start:.2f}s")

        return orchestrator
