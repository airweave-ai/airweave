"""Sync factory - builds orchestrator with SyncContext (data) and SyncRuntime (services).

The factory is responsible for:
1. Building SyncContext (data) via SyncContextBuilder
2. Building live services (source, destinations, trackers) directly
3. Assembling SyncRuntime from per-sync state
4. Wiring everything into SyncOrchestrator

Instance-based with injected deps (code blue architecture).
All container imports eliminated — deps flow through constructor.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.context import BaseContext
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger, LoggerConfigurator, logger
from airweave.core.protocols.event_bus import EventBus
from airweave.core.sync_cursor_service import sync_cursor_service
from airweave.domains.access_control.dispatcher import ACActionDispatcher
from airweave.domains.access_control.membership_tracker import ACLMembershipTracker
from airweave.domains.access_control.pipeline import AccessControlPipeline
from airweave.domains.access_control.postgres_handler import ACPostgresHandler
from airweave.domains.access_control.protocols import AccessControlMembershipRepositoryProtocol
from airweave.domains.access_control.resolver import ACActionResolver
from airweave.domains.arf.protocols import ArfServiceProtocol
from airweave.domains.browse_tree.protocols import NodeSelectionRepositoryProtocol
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.entities.protocols import EntityRepositoryProtocol
from airweave.domains.entities.registry import EntityDefinitionRegistry
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.sources.lifecycle import SourceLifecycleService
from airweave.domains.sync_pipeline.builders import SyncContextBuilder
from airweave.domains.sync_pipeline.builders.destinations import DestinationsContextBuilder
from airweave.domains.sync_pipeline.config import SyncConfig, SyncConfigBuilder
from airweave.domains.sync_pipeline.contexts.runtime import SyncRuntime
from airweave.domains.sync_pipeline.cursor import SyncCursor
from airweave.domains.sync_pipeline.entity.dispatcher_builder import EntityDispatcherBuilder
from airweave.domains.sync_pipeline.orchestrator import SyncOrchestrator
from airweave.domains.sync_pipeline.pipeline.entity_tracker import EntityTracker
from airweave.domains.sync_pipeline.protocols import ChunkEmbedProcessorProtocol
from airweave.domains.sync_pipeline.stream import AsyncSourceStream
from airweave.domains.sync_pipeline.worker_pool import AsyncWorkerPool
from airweave.domains.usage.protocols import UsageLedgerProtocol, UsageLimitCheckerProtocol
from airweave.models.source_connection import SourceConnection
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource

from .entity.pipeline import EntityPipeline
from .entity.resolver import EntityActionResolver


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
        usage_ledger: UsageLedgerProtocol,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        entity_repo: EntityRepositoryProtocol,
        entity_definition_registry: EntityDefinitionRegistry,
        acl_repo: AccessControlMembershipRepositoryProtocol,
        processor: ChunkEmbedProcessorProtocol,
        source_lifecycle_service: SourceLifecycleService,
        storage_backend: Any,
        selection_repo: NodeSelectionRepositoryProtocol,
        arf_service: Optional[ArfServiceProtocol] = None,
    ) -> None:
        """Initialize with all required service and repository dependencies."""
        self._sc_repo = sc_repo
        self._event_bus = event_bus
        self._usage_checker = usage_checker
        self._usage_ledger = usage_ledger
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder
        self._entity_repo = entity_repo
        self._entity_definition_registry = entity_definition_registry
        self._acl_repo = acl_repo
        self._processor = processor
        self._source_lifecycle_service = source_lifecycle_service
        self._storage_backend = storage_backend
        self._selection_repo = selection_repo
        self._arf_service = arf_service

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

        sc = await self._sc_repo.get_by_sync_id(db, sync_id=sync.id, ctx=ctx)
        if not sc:
            raise NotFoundException(f"Source connection record not found for sync {sync.id}")
        source_connection_id = sc.id

        sync_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync.source_build",
            dimensions={
                "sync_id": str(sync.id),
                "organization_id": str(ctx.organization.id),
            },
        )

        source_result, destinations_result, entity_tracker = await asyncio.gather(
            self._build_source(
                db=db,
                sync=sync,
                sync_job=sync_job,
                ctx=ctx,
                logger=sync_logger,
                source_connection=sc,
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
            self._build_entity_tracker(
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
            entity_tracker=entity_tracker,
            destinations=destinations,
        )

        logger.debug(f"Context + runtime built in {time.time() - init_start:.2f}s")

        dispatcher_builder = EntityDispatcherBuilder(
            processor=self._processor,
            entity_repo=self._entity_repo,
            arf_service=self._arf_service,
            vector_size=self._dense_embedder.dimensions,
            embedding_model_name=self._dense_embedder.model_name,
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
            dispatcher=ACActionDispatcher(handlers=[ACPostgresHandler(acl_repo=self._acl_repo)]),
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
            event_bus=self._event_bus,
            usage_checker=self._usage_checker,
            usage_ledger=self._usage_ledger,
        )

        logger.info(f"Total orchestrator initialization took {time.time() - init_start:.2f}s")
        return orchestrator

    # -------------------------------------------------------------------------
    # Private: Source building (inlined from SourceContextBuilder)
    # -------------------------------------------------------------------------

    async def _build_source(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        ctx: BaseContext,
        logger: ContextualLogger,
        source_connection: SourceConnection,
        force_full_sync: bool,
        execution_config: SyncConfig,
    ) -> Tuple[BaseSource, SyncCursor]:
        """Build source instance and cursor. Returns (source, cursor)."""
        if execution_config and execution_config.behavior.replay_from_arf:
            return await self._build_arf_replay_source(db=db, sync=sync, ctx=ctx, logger=logger)

        self._validate_not_completed_snapshot(source_connection)

        source_connection_id = source_connection.id

        source = await self._source_lifecycle_service.create(
            db=db,
            source_connection_id=source_connection_id,
            ctx=ctx,
        )

        # TODO(@felix): add pre-sync validation
        # short_name = source.source_name
        # try:
        #     is_valid = await source.validate()
        #     if not is_valid:
        #         raise SourceValidationError(short_name, "validate() returned False")
        # except SourceValidationError:
        #     raise
        # except Exception as exc:
        #     raise SourceValidationError(
        #         short_name, f"pre-sync validation raised: {exc}"
        #     ) from exc

        # TODO(@felix): pause temporal schedule
        # schedule so we stop burning runs while creds are broken.
        # Needs: inject TemporalScheduleService into SyncFactory, then:
        #   schedule_id = sync.temporal_schedule_id
        #   if schedule_id:
        #       await self._temporal_schedule_service.pause_schedule(schedule_id)
        # Also update source_connection status to NEEDS_REAUTH here.

        self._setup_file_downloader(source, sync_job, logger)

        cursor = await self._create_cursor(
            db=db,
            sync=sync,
            source_class=type(source),
            ctx=ctx,
            logger=logger,
            force_full_sync=force_full_sync,
            execution_config=execution_config,
        )

        source.set_cursor(cursor)

        node_selections = await self._load_node_selections(db, source_connection_id, ctx)
        if node_selections:
            source.set_node_selections(node_selections)
            logger.info(f"Loaded {len(node_selections)} node selections for targeted sync")

        return source, cursor

    async def _build_arf_replay_source(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        ctx: BaseContext,
        logger: ContextualLogger,
    ) -> Tuple[BaseSource, SyncCursor]:
        """Build source context for ARF replay mode."""
        from airweave.domains.arf.replay_source import ArfReplaySource

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
            storage=self._storage_backend,
            logger=logger,
            restore_files=True,
            original_short_name=original_short_name,
        )

        if hasattr(source, "set_logger"):
            source.set_logger(logger)

        if not await source.validate():
            raise NotFoundException(
                f"ARF data not found for sync {sync.id}. "
                f"Cannot replay — ensure ARF capture was enabled for previous syncs."
            )

        cursor = SyncCursor(sync_id=sync.id, cursor_schema=None, cursor_data=None)
        return source, cursor

    @staticmethod
    def _validate_not_completed_snapshot(source_connection_obj: SourceConnection) -> None:
        """Guard: completed snapshots that had their short_name restored cannot re-sync."""
        if source_connection_obj.short_name != "snapshot":
            from pydantic import ValidationError

            from airweave.platform.configs.config import SnapshotConfig

            try:
                SnapshotConfig(**(source_connection_obj.config_fields or {}))
                from airweave.domains.sync_pipeline.exceptions import SyncFailureError

                raise SyncFailureError(
                    f"Cannot re-sync a completed snapshot source connection "
                    f"('{source_connection_obj.name}'). Snapshot data is immutable — "
                    f"create a new snapshot source connection instead."
                )
            except ValidationError:
                pass

    def _setup_file_downloader(
        self, source: BaseSource, sync_job: Any, logger: ContextualLogger
    ) -> None:
        """Setup file downloader for file-based sources."""
        from airweave.domains.storage.file_service import FileService

        if not sync_job or not hasattr(sync_job, "id"):
            raise ValueError("sync_job is required for file downloader initialization.")

        file_downloader = FileService(
            sync_job_id=sync_job.id,
            storage_backend=self._storage_backend,
        )
        source.set_file_downloader(file_downloader)

    @staticmethod
    async def _create_cursor(
        db: AsyncSession,
        sync: schemas.Sync,
        source_class: type,
        ctx: BaseContext,
        logger: ContextualLogger,
        force_full_sync: bool,
        execution_config: Optional[SyncConfig],
    ) -> SyncCursor:
        """Create sync cursor with optional data loading."""
        cursor_schema = None
        if hasattr(source_class, "cursor_class") and source_class.cursor_class:
            cursor_schema = source_class.cursor_class
            logger.debug(f"Source has typed cursor: {cursor_schema.__name__}")

        if force_full_sync:
            logger.info("FORCE FULL SYNC: Skipping cursor data to ensure all entities are fetched.")
            cursor_data = None
        elif execution_config and execution_config.cursor.skip_load:
            logger.info(
                "SKIP CURSOR LOAD: Fetching all entities (execution_config.cursor.skip_load=True)"
            )
            cursor_data = None
        else:
            cursor_data = await sync_cursor_service.get_cursor_data(db=db, sync_id=sync.id, ctx=ctx)
            if cursor_data:
                logger.info(f"Incremental sync: Using cursor data with {len(cursor_data)} keys")

        return SyncCursor(
            sync_id=sync.id,
            cursor_schema=cursor_schema,
            cursor_data=cursor_data,
        )

    async def _load_node_selections(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: BaseContext,
    ) -> List[NodeSelectionData]:
        """Load node selections for targeted sync."""
        rows = await self._selection_repo.get_by_source_connection(
            db, source_connection_id, ctx.organization.id
        )
        return [
            NodeSelectionData(
                source_node_id=row.source_node_id,
                node_type=row.node_type,
                node_title=row.node_title,
                node_metadata=row.node_metadata,
            )
            for row in rows
        ]

    # -------------------------------------------------------------------------
    # Private: Destinations building (delegates to DestinationsContextBuilder)
    # -------------------------------------------------------------------------

    async def _build_destinations(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.CollectionRecord,
        ctx: BaseContext,
        execution_config: SyncConfig,
    ) -> Tuple[List[Any], Dict[type[BaseEntity], str]]:
        """Build destinations and entity map."""
        dest_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync.dest_build",
            dimensions={
                "sync_id": str(sync.id),
                "organization_id": str(ctx.organization.id),
            },
        )

        destinations = await DestinationsContextBuilder.build_destinations_only(
            db=db,
            sync=sync,
            collection=collection,
            ctx=ctx,
            logger=dest_logger,
            execution_config=execution_config,
        )

        entity_map: Dict[type[BaseEntity], str] = {
            entry.entity_class_ref: entry.short_name
            for entry in self._entity_definition_registry.list_all()
        }

        return destinations, entity_map

    # -------------------------------------------------------------------------
    # Private: Entity tracker (inlined from TrackingContextBuilder)
    # -------------------------------------------------------------------------

    @staticmethod
    async def _build_entity_tracker(
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        ctx: BaseContext,
    ) -> EntityTracker:
        """Build entity tracker with initial counts."""
        track_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync.tracking_build",
            dimensions={
                "sync_id": str(sync.id),
                "organization_id": str(ctx.organization.id),
            },
        )

        initial_counts = await crud.entity_count.get_counts_per_sync_and_type(db, sync.id)
        track_logger.info(f"Loaded initial entity counts: {len(initial_counts)} entity types")

        return EntityTracker(
            job_id=sync_job.id,
            sync_id=sync.id,
            logger=track_logger,
            initial_counts=initial_counts,
        )
