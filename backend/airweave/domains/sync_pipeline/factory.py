"""Sync factory - builds orchestrator with SyncContext (data) and SyncRuntime (services).

The factory is responsible for:
1. Building SyncContext (data) via SyncContextBuilder
2. Building live services (source, destinations, trackers) via sub-builders
3. Building per-sync event emitter with subscribers (progress relay, billing)
4. Assembling SyncRuntime from the services
5. Wiring everything into SyncOrchestrator

Instance-based with injected deps (code blue architecture).
"""

import asyncio
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.logging import LoggerConfigurator, logger
from airweave.core.protocols.event_bus import EventBus
from airweave.domains.access_control.protocols import AccessControlMembershipRepositoryProtocol
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.entities.protocols import EntityRepositoryProtocol
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.usage.protocols import UsageLimitCheckerProtocol
from airweave.domains.sync_pipeline.builders import SyncContextBuilder
from airweave.domains.sync_pipeline.builders.tracking import TrackingContextBuilder
from airweave.domains.sync_pipeline.contexts.runtime import SyncRuntime
from airweave.domains.sync_pipeline.access_control_pipeline import AccessControlPipeline
from airweave.domains.sync_pipeline.access_control_dispatcher import ACActionDispatcher
from airweave.domains.sync_pipeline.access_control_resolver import ACActionResolver
from airweave.domains.sync_pipeline.entity_dispatcher_builder import EntityDispatcherBuilder
from airweave.domains.sync_pipeline.config import SyncConfig, SyncConfigBuilder
from airweave.domains.sync_pipeline.handlers import ACPostgresHandler
from airweave.domains.sync_pipeline.orchestrator import SyncOrchestrator
from airweave.domains.sync_pipeline.pipeline.acl_membership_tracker import ACLMembershipTracker
from airweave.domains.sync_pipeline.pipeline.entity_tracker import EntityTracker
from airweave.domains.sync_pipeline.protocols import ChunkEmbedProcessorProtocol
from airweave.domains.sync_pipeline.stream import AsyncSourceStream
from airweave.domains.sync_pipeline.worker_pool import AsyncWorkerPool

from .entity_action_resolver import EntityActionResolver
from .entity_pipeline import EntityPipeline


class SyncFactory:
    """Factory for sync orchestrator.

    Builds SyncContext (data), SyncRuntime (services), and wires them
    into the orchestrator and pipeline components.
    """

    def __init__(
        self,
        sc_repo: SourceConnectionRepositoryProtocol,
        event_bus: EventBus,
        usage_checker: UsageLimitCheckerProtocol,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        entity_repo: EntityRepositoryProtocol,
        acl_repo: AccessControlMembershipRepositoryProtocol,
        processor: ChunkEmbedProcessorProtocol,
    ) -> None:
        self._sc_repo = sc_repo
        self._event_bus = event_bus
        self._usage_checker = usage_checker
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder
        self._entity_repo = entity_repo
        self._acl_repo = acl_repo
        self._processor = processor

    async def create_orchestrator(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        ctx: BaseContext,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> SyncOrchestrator:
        """Create a dedicated orchestrator instance for a sync run."""
        init_start = time.time()
        logger.info("Creating sync orchestrator...")

        resolved_config = SyncConfigBuilder.build(
            collection_overrides=collection.sync_config,
            sync_overrides=sync.sync_config,
            job_overrides=sync_job.sync_config or execution_config,
        )
        logger.debug(
            f"Resolved layered sync config: handlers={resolved_config.handlers.model_dump()}, "
            f"destinations={resolved_config.destinations.model_dump()}"
        )

        # Direct repo call — replaces SyncContextBuilder -> SourceContextBuilder chain
        sc = await self._sc_repo.get_by_sync_id(db, sync_id=sync.id, ctx=ctx)
        if not sc:
            from airweave.core.exceptions import NotFoundException

            raise NotFoundException(f"Source connection record not found for sync {sync.id}")
        source_connection_id = sc.id

        source_result, destinations_result, entity_tracker_result = await asyncio.gather(
            self._build_source(
                db=db,
                sync=sync,
                sync_job=sync_job,
                ctx=ctx,
                force_full_sync=force_full_sync,
                execution_config=resolved_config,
            ),
            self._build_destinations(
                db=db,
                sync=sync,
                collection=collection,
                ctx=ctx,
                execution_config=resolved_config,
            ),
            self._build_tracking(
                db=db,
                sync=sync,
                sync_job=sync_job,
                ctx=ctx,
            ),
        )

        source, cursor = source_result
        destinations, entity_map = destinations_result

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

        runtime = SyncRuntime(
            source=source,
            cursor=cursor,
            dense_embedder=self._dense_embedder,
            sparse_embedder=self._sparse_embedder,
            destinations=destinations,
            entity_tracker=entity_tracker_result,
            event_bus=self._event_bus,
            usage_checker=self._usage_checker,
        )

        logger.debug(f"Context + runtime built in {time.time() - init_start:.2f}s")

        dispatcher_builder = EntityDispatcherBuilder(
            processor=self._processor,
            entity_repo=self._entity_repo,
        )
        dispatcher = dispatcher_builder.build(
            destinations=runtime.destinations,
            execution_config=resolved_config,
            logger=sync_context.logger,
        )

        action_resolver = EntityActionResolver(
            entity_map=sync_context.entity_map,
            entity_repo=self._entity_repo,
        )

        entity_pipeline = EntityPipeline(
            entity_tracker=runtime.entity_tracker,
            event_bus=self._event_bus,
            action_resolver=action_resolver,
            action_dispatcher=dispatcher,
            entity_repo=self._entity_repo,
        )

        access_control_pipeline = AccessControlPipeline(
            resolver=ACActionResolver(),
            dispatcher=ACActionDispatcher(
                handlers=[ACPostgresHandler(acl_repo=self._acl_repo)]
            ),
            tracker=ACLMembershipTracker(
                source_connection_id=sync_context.source_connection_id,
                organization_id=sync_context.organization_id,
                logger=sync_context.logger,
            ),
            acl_repo=self._acl_repo,
        )

        worker_pool = AsyncWorkerPool(logger=sync_context.logger)

        stream = AsyncSourceStream(
            source_generator=runtime.source.generate_entities(),
            queue_size=10000,
            logger=sync_context.logger,
        )

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

    @staticmethod
    async def _build_source(db, sync, sync_job, ctx, force_full_sync, execution_config):
        """Build source and cursor. Returns (source, cursor) tuple."""
        from airweave.domains.sync_pipeline.builders.source import SourceContextBuilder
        from airweave.domains.sync_pipeline.contexts.infra import InfraContext

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
            force_full_sync=force_full_sync,
            execution_config=execution_config,
        )
        return source_ctx.source, source_ctx.cursor

    @staticmethod
    async def _build_destinations(db, sync, collection, ctx, execution_config):
        """Build destinations and entity map. Returns (destinations, entity_map) tuple."""
        from airweave.domains.sync_pipeline.builders.destinations import DestinationsContextBuilder

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

    @staticmethod
    async def _build_tracking(
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        ctx: BaseContext,
    ) -> EntityTracker:
        """Build tracking components. Returns EntityTracker."""
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
