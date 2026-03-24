"""Sync factory - builds orchestrator with SyncContext (data) and SyncRuntime (services).

The factory is responsible for:
1. Building SyncContext (data) via SyncContextBuilder
2. Building live services (source, destinations, trackers) directly
3. Assembling SyncRuntime from per-sync state
4. Wiring everything into SyncOrchestrator

Instance-based with injected deps (code blue architecture).
All container imports eliminated — deps flow through constructor.
"""

import time
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.context import BaseContext
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger, LoggerConfigurator, logger
from airweave.core.protocols.event_bus import EventBus
from airweave.domains.access_control.dispatcher import ACActionDispatcher
from airweave.domains.access_control.membership_tracker import ACLMembershipTracker
from airweave.domains.access_control.pipeline import AccessControlPipeline
from airweave.domains.access_control.postgres_handler import ACPostgresHandler
from airweave.domains.access_control.protocols import AccessControlMembershipRepositoryProtocol
from airweave.domains.access_control.resolver import ACActionResolver
from airweave.domains.arf.protocols import ArfServiceProtocol
from airweave.domains.browse_tree.protocols import NodeSelectionRepositoryProtocol
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.entities.protocols import (
    EntityCountRepositoryProtocol,
    EntityRepositoryProtocol,
)
from airweave.domains.entities.registry import EntityDefinitionRegistry
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.sources.lifecycle import SourceLifecycleService
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.domains.storage.file_service import FileService
from airweave.domains.storage.protocols import StorageBackend
from airweave.domains.sync_pipeline.builders import SyncContextBuilder
from airweave.domains.sync_pipeline.builders.destinations import DestinationsContextBuilder
from airweave.domains.sync_pipeline.config import SyncConfig
from airweave.domains.sync_pipeline.contexts.runtime import SyncRuntime
from airweave.domains.sync_pipeline.contexts.sync import SyncContext
from airweave.domains.sync_pipeline.entity.dispatcher_builder import EntityDispatcherBuilder
from airweave.domains.sync_pipeline.orchestrator import SyncOrchestrator
from airweave.domains.sync_pipeline.pipeline.entity_tracker import EntityTracker
from airweave.domains.sync_pipeline.protocols import (
    ChunkEmbedProcessorProtocol,
    SyncFactoryProtocol,
)
from airweave.domains.sync_pipeline.stream import AsyncSourceStream
from airweave.domains.sync_pipeline.worker_pool import AsyncWorkerPool
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.domains.syncs.cursors.service import SyncCursorService
from airweave.domains.syncs.protocols import SyncJobStateMachineProtocol
from airweave.domains.usage.protocols import UsageLedgerProtocol, UsageLimitCheckerProtocol
from airweave.models.source_connection import SourceConnection
from airweave.platform.sources._base import BaseSource

from .entity.pipeline import EntityPipeline
from .entity.resolver import EntityActionResolver


@dataclass(frozen=True, slots=True)
class SourceBuildResult:
    """Result of building a source for a sync run."""

    source: BaseSource
    cursor: Optional[SyncCursor]
    files: Optional[FileService]
    node_selections: Optional[List[NodeSelectionData]]


class SyncFactory(SyncFactoryProtocol):
    """Factory for sync orchestrator.

    Builds SyncContext (data), SyncRuntime (services), and wires them
    into the orchestrator and pipeline components.
    """

    def __init__(
        self,
        # Repositories
        sc_repo: SourceConnectionRepositoryProtocol,
        entity_repo: EntityRepositoryProtocol,
        entity_count_repo: EntityCountRepositoryProtocol,
        acl_repo: AccessControlMembershipRepositoryProtocol,
        selection_repo: NodeSelectionRepositoryProtocol,
        # Registries
        entity_definition_registry: EntityDefinitionRegistry,
        source_registry: SourceRegistryProtocol,
        # Services
        source_lifecycle_service: SourceLifecycleService,
        sync_cursor_service: SyncCursorService,
        processor: ChunkEmbedProcessorProtocol,
        arf_service: ArfServiceProtocol,
        # Infrastructure
        event_bus: EventBus,
        usage_checker: UsageLimitCheckerProtocol,
        usage_ledger: UsageLedgerProtocol,
        storage_backend: StorageBackend,
        state_machine: "SyncJobStateMachineProtocol",
    ) -> None:
        """Initialize with all required service and repository dependencies."""
        # Repositories
        self._sc_repo = sc_repo
        self._entity_repo = entity_repo
        self._entity_count_repo = entity_count_repo
        self._acl_repo = acl_repo
        self._selection_repo = selection_repo

        # Registries
        self._entity_definition_registry = entity_definition_registry
        self._source_registry = source_registry

        # Services
        self._source_lifecycle_service = source_lifecycle_service
        self._sync_cursor_service = sync_cursor_service
        self._processor = processor
        self._arf_service = arf_service

        # Infrastructure
        self._event_bus = event_bus
        self._usage_checker = usage_checker
        self._usage_ledger = usage_ledger
        self._storage_backend = storage_backend
        self._state_machine = state_machine

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
        access_token: Optional[str] = None,
    ) -> SyncOrchestrator:
        """Create a dedicated orchestrator instance for a sync run."""
        init_start = time.time()
        logger.info("Creating sync orchestrator...")

        # 1. Resolve config
        resolved_config = SyncConfig.build(
            collection_overrides=collection.sync_config,
            sync_overrides=sync.sync_config,
            job_overrides=sync_job.sync_config or execution_config,
        )
        logger.debug(
            f"Resolved layered sync config: handlers={resolved_config.handlers.model_dump()}, "
            f"destinations={resolved_config.destinations.model_dump()}"
        )

        sc = await self._resolve_source_connection(db, sync, ctx)
        sc_id = sc.id  # extract before _build_source can expire the ORM instance via OAuth refresh

        # 2. Build source, destinations, tracker
        sync_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync.source_build",
            dimensions={
                "sync_id": str(sync.id),
                "organization_id": str(ctx.organization.id),
            },
        )

        source_result = await self._build_source(
            db=db,
            sync=sync,
            sync_job=sync_job,
            ctx=ctx,
            logger=sync_logger,
            source_connection=sc,
            force_full_sync=force_full_sync,
            execution_config=resolved_config,
            access_token=access_token,
        )
        destinations = await self._build_destinations(
            db=db,
            sync=sync,
            collection=collection,
            ctx=ctx,
            execution_config=resolved_config,
        )
        entity_tracker = await self._build_entity_tracker(
            db=db,
            sync=sync,
            sync_job=sync_job,
            ctx=ctx,
        )

        # 3. Assemble context + runtime
        sync_context = await SyncContextBuilder.build(
            db=db,
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,
            ctx=ctx,
            source_connection_id=sc_id,
            source_short_name=getattr(source_result.source, "short_name", "") or "",
            force_full_sync=force_full_sync,
            execution_config=resolved_config,
        )

        runtime = SyncRuntime(
            source=source_result.source,
            cursor=source_result.cursor,
            entity_tracker=entity_tracker,
            destinations=destinations,
        )

        logger.debug(f"Context + runtime built in {time.time() - init_start:.2f}s")

        # 4. Wire pipelines
        entity_pipeline = self._build_entity_pipeline(
            sync_context, runtime, destinations, resolved_config
        )
        access_control_pipeline = self._build_access_control_pipeline(sync_context)
        stream = self._build_stream(runtime, source_result, sync_context)

        # 5. Create orchestrator
        orchestrator = SyncOrchestrator(
            entity_pipeline=entity_pipeline,
            worker_pool=AsyncWorkerPool(logger=sync_context.logger),
            stream=stream,
            sync_context=sync_context,
            runtime=runtime,
            access_control_pipeline=access_control_pipeline,
            event_bus=self._event_bus,
            usage_checker=self._usage_checker,
            usage_ledger=self._usage_ledger,
            sync_cursor_service=self._sync_cursor_service,
            state_machine=self._state_machine,
        )

        logger.info(f"Total orchestrator initialization took {time.time() - init_start:.2f}s")
        return orchestrator

    # -------------------------------------------------------------------------
    # Private: Orchestrator assembly helpers
    # -------------------------------------------------------------------------

    async def _resolve_source_connection(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        ctx: BaseContext,
    ) -> SourceConnection:
        """Look up the source connection for a sync, or raise NotFoundException."""
        sc = await self._sc_repo.get_by_sync_id(db, sync_id=sync.id, ctx=ctx)
        if not sc:
            raise NotFoundException(f"Source connection record not found for sync {sync.id}")
        return sc

    def _build_entity_pipeline(
        self,
        sync_context: SyncContext,
        runtime: SyncRuntime,
        destinations: list,
        resolved_config: SyncConfig,
    ) -> EntityPipeline:
        """Build entity pipeline with dispatcher and action resolver."""
        dispatcher_builder = EntityDispatcherBuilder(
            processor=self._processor,
            entity_repo=self._entity_repo,
            arf_service=self._arf_service,
        )
        dispatcher = dispatcher_builder.build(
            destinations=destinations,
            execution_config=resolved_config,
            logger=sync_context.logger,
        )
        action_resolver = EntityActionResolver(
            entity_registry=self._entity_definition_registry,
            entity_repo=self._entity_repo,
        )
        return EntityPipeline(
            entity_tracker=runtime.entity_tracker,
            event_bus=self._event_bus,
            action_resolver=action_resolver,
            action_dispatcher=dispatcher,
            entity_repo=self._entity_repo,
        )

    def _build_access_control_pipeline(self, sync_context: SyncContext) -> AccessControlPipeline:
        """Build access control pipeline with resolver, dispatcher, and tracker."""
        return AccessControlPipeline(
            resolver=ACActionResolver(),
            dispatcher=ACActionDispatcher(handlers=[ACPostgresHandler(acl_repo=self._acl_repo)]),
            tracker=ACLMembershipTracker(
                source_connection_id=sync_context.source_connection_id,
                organization_id=sync_context.organization_id,
                logger=sync_context.logger,
            ),
            acl_repo=self._acl_repo,
        )

    def _build_stream(
        self,
        runtime: SyncRuntime,
        source_result: SourceBuildResult,
        sync_context: SyncContext,
    ) -> AsyncSourceStream:
        """Build the async source stream from the source generator."""
        return AsyncSourceStream(
            source_generator=runtime.source.generate_entities(
                cursor=runtime.cursor,
                files=source_result.files,
                node_selections=source_result.node_selections,
            ),
            queue_size=10000,
            logger=sync_context.logger,
        )

    # -------------------------------------------------------------------------
    # Private: Source building
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
        access_token: Optional[str] = None,
    ) -> SourceBuildResult:
        """Build source instance, cursor, file service, and node selections."""
        if execution_config and execution_config.behavior.replay_from_arf:
            return await self._build_arf_replay_source(db=db, sync=sync, ctx=ctx, logger=logger)

        self._validate_not_completed_snapshot(source_connection)

        source_connection_id = source_connection.id

        source = await self._source_lifecycle_service.create(
            db=db,
            source_connection_id=source_connection_id,
            ctx=ctx,
            access_token=access_token,
        )

        files = FileService(sync_job_id=sync_job.id, storage_backend=self._storage_backend)

        cursor = await self._create_cursor(
            db=db,
            sync=sync,
            source_class=type(source),
            ctx=ctx,
            logger=logger,
            force_full_sync=force_full_sync,
            execution_config=execution_config,
        )

        node_selections = await self._load_node_selections(db, source_connection_id, ctx)
        if node_selections:
            logger.info(f"Loaded {len(node_selections)} node selections for targeted sync")

        return SourceBuildResult(
            source=source, cursor=cursor, files=files, node_selections=node_selections
        )

    async def _build_arf_replay_source(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        ctx: BaseContext,
        logger: ContextualLogger,
    ) -> SourceBuildResult:
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

        await source.validate()

        cursor = SyncCursor(sync_id=sync.id, cursor_schema=None, cursor_data=None)
        return SourceBuildResult(source=source, cursor=cursor, files=None, node_selections=None)

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

    async def _create_cursor(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        source_class: type,
        ctx: BaseContext,
        logger: ContextualLogger,
        force_full_sync: bool,
        execution_config: Optional[SyncConfig],
    ) -> Optional[SyncCursor]:
        """Create sync cursor with optional data loading."""
        entry = self._source_registry.get(source_class.short_name)
        if not entry.supports_cursor:
            return None
        cursor_schema = source_class.cursor_class
        if cursor_schema:
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
            cursor_data = await self._sync_cursor_service.get_cursor_data(
                db=db, sync_id=sync.id, ctx=ctx
            )
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
    ) -> list:
        """Build destination instances for the sync."""
        dest_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync.dest_build",
            dimensions={
                "sync_id": str(sync.id),
                "organization_id": str(ctx.organization.id),
            },
        )

        return await DestinationsContextBuilder.build_destinations(
            sync=sync,
            collection=collection,
            logger=dest_logger,
            execution_config=execution_config,
        )

    # -------------------------------------------------------------------------
    # Private: Entity tracker (inlined from TrackingContextBuilder)
    # -------------------------------------------------------------------------

    async def _build_entity_tracker(
        self,
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

        initial_counts = await self._entity_count_repo.get_counts_per_sync_and_type(db, sync.id)
        track_logger.info(f"Loaded initial entity counts: {len(initial_counts)} entity types")

        return EntityTracker(
            job_id=sync_job.id,
            sync_id=sync.id,
            logger=track_logger,
            initial_counts=initial_counts,
        )
