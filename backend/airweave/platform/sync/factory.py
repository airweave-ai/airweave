"""Sync factory - builds orchestrator with SyncContext (data) and SyncRuntime (services).

The factory is responsible for:
1. Building SyncContext (data) via SyncContextBuilder
2. Building live services (source, destinations, trackers) via sub-builders
3. Assembling SyncRuntime from the services
4. Wiring everything into SyncOrchestrator
"""

import asyncio
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.config import settings
from airweave.core.context import BaseContext
from airweave.core.logging import logger
from airweave.platform.builders import SyncContextBuilder
from airweave.platform.contexts.runtime import SyncRuntime
from airweave.platform.sync.access_control_pipeline import AccessControlPipeline
from airweave.platform.sync.actions import (
    ACActionDispatcher,
    ACActionResolver,
    EntityActionResolver,
    EntityDispatcherBuilder,
)
from airweave.platform.sync.config import SyncConfig, SyncConfigBuilder
from airweave.platform.sync.entity_pipeline import EntityPipeline
from airweave.platform.sync.handlers import ACPostgresHandler
from airweave.platform.sync.orchestrator import SyncOrchestrator
from airweave.platform.sync.pipeline.acl_membership_tracker import ACLMembershipTracker
from airweave.platform.sync.stream import AsyncSourceStream
from airweave.platform.sync.worker_pool import AsyncWorkerPool


class SyncFactory:
    """Factory for sync orchestrator.

    Builds SyncContext (data), SyncRuntime (services), and wires them
    into the orchestrator and pipeline components.
    """

    @classmethod
    async def create_orchestrator(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        connection: schemas.Connection,
        ctx: BaseContext,
        access_token: Optional[str] = None,
        max_workers: int = None,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> SyncOrchestrator:
        """Create a dedicated orchestrator instance for a sync run."""
        if max_workers is None:
            max_workers = settings.SYNC_MAX_WORKERS
            logger.debug(f"Using configured max_workers: {max_workers}")

        init_start = time.time()
        logger.info("Creating sync orchestrator...")

        # Step 0: Build layered sync configuration
        resolved_config = SyncConfigBuilder.build(
            collection_overrides=collection.sync_config,
            sync_overrides=sync.sync_config,
            job_overrides=sync_job.sync_config or execution_config,
        )
        logger.debug(
            f"Resolved layered sync config: handlers={resolved_config.handlers.model_dump()}, "
            f"destinations={resolved_config.destinations.model_dump()}"
        )

        # Step 1: Get source connection ID (needed before parallel build)
        source_connection_id = await SyncContextBuilder.get_source_connection_id(db, sync, ctx)

        # Step 2: Build services in parallel
        source_result, destinations_result, tracking_result = await asyncio.gather(
            cls._build_source(
                db=db,
                sync=sync,
                sync_job=sync_job,
                ctx=ctx,
                access_token=access_token,
                force_full_sync=force_full_sync,
                execution_config=resolved_config,
            ),
            cls._build_destinations(
                db=db,
                sync=sync,
                collection=collection,
                ctx=ctx,
                execution_config=resolved_config,
            ),
            cls._build_tracking(
                db=db,
                sync=sync,
                sync_job=sync_job,
                ctx=ctx,
            ),
        )

        source, cursor = source_result
        destinations, entity_map = destinations_result
        entity_tracker, state_publisher, guard_rail = tracking_result

        # Step 3: Build SyncContext (data only)
        sync_context = await SyncContextBuilder.build(
            db=db,
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,
            ctx=ctx,
            source_connection_id=source_connection_id,
            source_short_name=getattr(source, "short_name", "") or "",
            entity_map=entity_map,
            force_full_sync=force_full_sync,
            execution_config=resolved_config,
        )

        # Step 4: Assemble SyncRuntime (live services)
        runtime = SyncRuntime(
            source=source,
            cursor=cursor,
            destinations=destinations,
            entity_tracker=entity_tracker,
            state_publisher=state_publisher,
            guard_rail=guard_rail,
        )

        logger.debug(f"Context + runtime built in {time.time() - init_start:.2f}s")

        # Step 5: Build pipelines using runtime services
        dispatcher = EntityDispatcherBuilder.build(
            destinations=runtime.destinations,
            execution_config=resolved_config,
            logger=sync_context.logger,
            guard_rail=runtime.guard_rail,
        )

        action_resolver = EntityActionResolver(entity_map=sync_context.entity_map)

        entity_pipeline = EntityPipeline(
            entity_tracker=runtime.entity_tracker,
            state_publisher=runtime.state_publisher,
            action_resolver=action_resolver,
            action_dispatcher=dispatcher,
        )

        access_control_pipeline = AccessControlPipeline(
            resolver=ACActionResolver(),
            dispatcher=ACActionDispatcher(handlers=[ACPostgresHandler()]),
            tracker=ACLMembershipTracker(
                source_connection_id=sync_context.source_connection_id,
                organization_id=sync_context.organization_id,
                logger=sync_context.logger,
            ),
        )

        worker_pool = AsyncWorkerPool(max_workers=max_workers, logger=sync_context.logger)

        stream = AsyncSourceStream(
            source_generator=runtime.source.generate_entities(),
            queue_size=10000,
            logger=sync_context.logger,
        )

        # Step 6: Create orchestrator
        orchestrator = SyncOrchestrator(
            entity_pipeline=entity_pipeline,
            worker_pool=worker_pool,
            stream=stream,
            sync_context=sync_context,
            runtime=runtime,
            access_control_pipeline=access_control_pipeline,
        )

        logger.info(f"Total orchestrator initialization took {time.time() - init_start:.2f}s")
        return orchestrator

    # -------------------------------------------------------------------------
    # Private: Service builders (delegate to sub-builders)
    # -------------------------------------------------------------------------

    @classmethod
    async def _build_source(
        cls, db, sync, sync_job, ctx, access_token, force_full_sync, execution_config
    ):
        """Build source and cursor. Returns (source, cursor) tuple."""
        from airweave.core.logging import LoggerConfigurator
        from airweave.platform.builders.source import SourceContextBuilder
        from airweave.platform.contexts.infra import InfraContext

        sync_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync.source_build",
            dimensions={
                "sync_id": str(sync.id),
                "organization_id": str(ctx.organization.id),
            },
        )
        infra = InfraContext(ctx=ctx, logger=sync_logger)

        source_ctx = await SourceContextBuilder.build(
            db=db,
            sync=sync,
            sync_job=sync_job,
            infra=infra,
            access_token=access_token,
            force_full_sync=force_full_sync,
            execution_config=execution_config,
        )
        return source_ctx.source, source_ctx.cursor

    @classmethod
    async def _build_destinations(cls, db, sync, collection, ctx, execution_config):
        """Build destinations and entity map. Returns (destinations, entity_map) tuple."""
        from airweave.core.logging import LoggerConfigurator
        from airweave.platform.builders.destinations import DestinationsContextBuilder

        dest_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync.dest_build",
            dimensions={
                "sync_id": str(sync.id),
                "organization_id": str(ctx.organization.id),
            },
        )

        return await DestinationsContextBuilder.build(
            db=db,
            sync=sync,
            collection=collection,
            ctx=ctx,
            logger=dest_logger,
            execution_config=execution_config,
        )

    @classmethod
    async def _build_tracking(cls, db, sync, sync_job, ctx):
        """Build tracking components. Returns (entity_tracker, state_publisher, guard_rail)."""
        from airweave.core.logging import LoggerConfigurator
        from airweave.platform.builders.tracking import TrackingContextBuilder

        track_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync.tracking_build",
            dimensions={
                "sync_id": str(sync.id),
                "organization_id": str(ctx.organization.id),
            },
        )

        return await TrackingContextBuilder.build(
            db=db,
            sync=sync,
            sync_job=sync_job,
            ctx=ctx,
            logger=track_logger,
        )
