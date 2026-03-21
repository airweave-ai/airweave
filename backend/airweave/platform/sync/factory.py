"""Sync factory - builds orchestrator with SyncContext (data) and SyncRuntime (services).

The factory is responsible for:
1. Building SyncContext (data) via SyncContextBuilder
2. Building live services (source, destinations, trackers) via sub-builders
3. Building per-sync event emitter with subscribers (progress relay, billing)
4. Assembling SyncRuntime from the services
5. Wiring everything into SyncOrchestrator
"""

import asyncio
import time
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core import container as container_mod
from airweave.core.context import BaseContext
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import LoggerConfigurator, logger
from airweave.domains.browse_tree.repository import NodeSelectionRepository
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.builders import SyncContextBuilder
from airweave.platform.builders.tracking import TrackingContextBuilder
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
from airweave.platform.sync.pipeline.entity_tracker import EntityTracker
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
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        ctx: BaseContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> SyncOrchestrator:
        """Create a dedicated orchestrator instance for a sync run."""
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
        source_result, destinations_result, entity_tracker_result = await asyncio.gather(
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

        source, cursor, files, node_selections = source_result
        destinations, entity_map = destinations_result

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
            entity_tracker=entity_tracker_result,
            event_bus=container_mod.container.event_bus,
            usage_checker=container_mod.container.usage_checker,
            cursor=cursor,
            dense_embedder=container_mod.container.dense_embedder,
            sparse_embedder=container_mod.container.sparse_embedder,
            destinations=destinations,
        )

        logger.debug(f"Context + runtime built in {time.time() - init_start:.2f}s")

        # Step 6: Build pipelines using runtime services
        assert container_mod.container is not None, (
            "Container must be initialized before building sync orchestrator"
        )
        dispatcher = EntityDispatcherBuilder.build(
            destinations=runtime.destinations,
            arf_service=container_mod.container.arf_service,
            execution_config=resolved_config,
            logger=sync_context.logger,
        )

        action_resolver = EntityActionResolver(entity_map=sync_context.entity_map)

        entity_pipeline = EntityPipeline(
            entity_tracker=runtime.entity_tracker,
            event_bus=container_mod.container.event_bus,
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

        worker_pool = AsyncWorkerPool(logger=sync_context.logger)

        stream = AsyncSourceStream(
            source_generator=runtime.source.generate_entities(
                cursor=runtime.cursor,
                files=files,
                node_selections=node_selections,
            ),
            queue_size=10000,
            logger=sync_context.logger,
        )

        # Step 7: Create orchestrator
        orchestrator = SyncOrchestrator(
            entity_pipeline=entity_pipeline,
            worker_pool=worker_pool,
            stream=stream,
            sync_context=sync_context,
            runtime=runtime,
            access_control_pipeline=access_control_pipeline,
            sync_cursor_service=container_mod.container.sync_cursor_service,
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
        """Build source, cursor, file service, and node selections.

        Returns (source, cursor, files, node_selections) tuple.
        """
        sync_logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync.source_build",
            dimensions={
                "sync_id": str(sync.id),
                "organization_id": str(ctx.organization.id),
            },
        )

        if execution_config and execution_config.behavior.replay_from_arf:
            source, cursor = await cls._build_arf_replay_source(
                db=db,
                sync=sync,
                ctx=ctx,
                logger=sync_logger,
            )
            return source, cursor, None, None

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

        cls._validate_not_completed_snapshot(source_connection_obj)

        source = await container_mod.container.source_lifecycle_service.create(
            db=db,
            source_connection_id=UUID(str(source_connection_obj.id)),
            ctx=ctx,
            access_token=access_token,
        )

        files = FileService(
            sync_job_id=sync_job.id,
            storage_backend=container_mod.container.storage_backend,
        )

        cursor = await cls._create_cursor(
            db=db,
            sync=sync,
            source_class=type(source),
            ctx=ctx,
            logger=sync_logger,
            force_full_sync=force_full_sync,
            execution_config=execution_config,
        )

        node_selections = await cls._load_node_selections(
            db, UUID(str(source_connection_obj.id)), ctx
        )
        if node_selections:
            sync_logger.info(f"Loaded {len(node_selections)} node selections for targeted sync")

        return source, cursor, files, node_selections

    @classmethod
    async def _build_arf_replay_source(cls, db, sync, ctx, logger):
        """Build source for ARF replay mode. Returns (source, cursor)."""
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
            storage=container_mod.container.storage_backend,
            logger=logger,
            restore_files=True,
            original_short_name=original_short_name,
        )

        await source.validate()

        cursor = SyncCursor(sync_id=sync.id, cursor_schema=None, cursor_data=None)
        return source, cursor

    @staticmethod
    def _validate_not_completed_snapshot(source_connection_obj) -> None:
        """Guard: completed snapshots that had their short_name restored cannot re-sync."""
        if source_connection_obj.short_name != "snapshot":
            from pydantic import ValidationError

            from airweave.platform.configs.config import SnapshotConfig

            try:
                SnapshotConfig(**(source_connection_obj.config_fields or {}))
                from airweave.platform.sync.exceptions import SyncFailureError

                raise SyncFailureError(
                    f"Cannot re-sync a completed snapshot source connection "
                    f"('{source_connection_obj.name}'). Snapshot data is immutable — "
                    f"create a new snapshot source connection instead."
                )
            except ValidationError:
                pass

    @classmethod
    async def _create_cursor(
        cls, db, sync, source_class, ctx, logger, force_full_sync, execution_config
    ) -> Optional[SyncCursor]:
        """Create sync cursor, or None if source doesn't support cursors.

        Returns:
            None — source has no cursor support (every sync is full).
            SyncCursor(cursor_data=None) — supports cursors, but first run or force full.
            SyncCursor(cursor_data={...}) — incremental sync with loaded cursor.
        """
        registry_entry = container_mod.container.source_registry.get(source_class.short_name)
        if not registry_entry.supports_cursor:
            return None

        cursor_schema = source_class.cursor_class

        if force_full_sync:
            logger.info(
                "FORCE FULL SYNC: Skipping cursor data to ensure all entities are fetched "
                "for accurate orphaned entity cleanup."
            )
            cursor_data = None
        elif execution_config and execution_config.cursor.skip_load:
            logger.info("SKIP CURSOR LOAD: Fetching all entities (skip_load=True)")
            cursor_data = None
        else:
            cursor_data = await container_mod.container.sync_cursor_service.get_cursor_data(
                db=db, sync_id=sync.id, ctx=ctx
            )
            if cursor_data:
                logger.info(f"Incremental sync: Using cursor data with {len(cursor_data)} keys")

        return SyncCursor(sync_id=sync.id, cursor_schema=cursor_schema, cursor_data=cursor_data)

    @staticmethod
    async def _load_node_selections(db, source_connection_id, ctx):
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
    async def _build_tracking(
        cls,
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
