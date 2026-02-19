"""Sync context builder - constructs flat SyncContext directly.

Collapses all sub-builders (InfraContextBuilder, ScopeContextBuilder,
SourceContextBuilder, DestinationsContextBuilder, TrackingContextBuilder)
into private methods on this single builder class.
"""

import asyncio
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.logging import ContextualLogger, LoggerConfigurator
from airweave.platform.contexts.sync import SyncContext
from airweave.platform.sync.config import SyncConfig


class SyncContextBuilder:
    """Builds flat SyncContext with all required components."""

    @classmethod
    async def build(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        connection: schemas.Connection,
        ctx: BaseContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> SyncContext:
        """Build complete sync context.

        Args:
            db: Database session
            sync: The sync configuration
            sync_job: The sync job
            collection: The collection to sync to
            connection: The connection
            ctx: The base context (provides org identity for CRUD)
            access_token: Optional token to use instead of stored credentials
            force_full_sync: If True, forces a full sync with orphaned entity deletion
            execution_config: Optional execution config for controlling sync behavior

        Returns:
            Flat SyncContext with all fields populated.
        """
        # Step 1: Get source connection ID (needed for logger dimensions)
        source_connection_id = await cls._get_source_connection_id(db, sync, ctx)

        # Step 2: Build sync-specific logger with all relevant dimensions
        logger = cls._build_logger(
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            source_connection_id=source_connection_id,
            ctx=ctx,
        )

        logger.info("Building sync context...")

        # Step 3: Build source, destinations, and tracking in parallel
        source_result, destinations_result, tracking_result = await asyncio.gather(
            cls._build_source(
                db=db,
                sync=sync,
                sync_job=sync_job,
                ctx=ctx,
                logger=logger,
                access_token=access_token,
                force_full_sync=force_full_sync,
                execution_config=execution_config,
            ),
            cls._build_destinations(
                db=db,
                sync=sync,
                collection=collection,
                ctx=ctx,
                logger=logger,
                execution_config=execution_config,
            ),
            cls._build_tracking(
                db=db,
                sync=sync,
                sync_job=sync_job,
                ctx=ctx,
                logger=logger,
            ),
        )

        source, cursor = source_result
        destinations, entity_map = destinations_result
        entity_tracker, state_publisher, guard_rail = tracking_result

        # Step 4: Assemble flat SyncContext
        sync_context = SyncContext(
            # BaseContext fields
            organization=ctx.organization,
            user=ctx.user,
            logger=logger,
            # Scope
            sync_id=sync.id,
            sync_job_id=sync_job.id,
            collection_id=collection.id,
            source_connection_id=source_connection_id,
            # Source pipeline
            source=source,
            cursor=cursor,
            # Destination pipeline
            destinations=destinations,
            entity_map=entity_map,
            # Tracking
            entity_tracker=entity_tracker,
            state_publisher=state_publisher,
            guard_rail=guard_rail,
            # Batch config
            force_full_sync=force_full_sync,
            # Schema objects
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,
            # Execution config
            execution_config=execution_config,
        )

        logger.info("Sync context created")
        return sync_context

    # -------------------------------------------------------------------------
    # Private: Logger
    # -------------------------------------------------------------------------

    @classmethod
    def _build_logger(
        cls,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        source_connection_id: UUID,
        ctx: BaseContext,
    ) -> ContextualLogger:
        """Build sync-specific logger with all relevant dimensions."""
        return LoggerConfigurator.configure_logger(
            "airweave.platform.sync",
            dimensions={
                "sync_id": str(sync.id),
                "sync_job_id": str(sync_job.id),
                "organization_id": str(ctx.organization.id),
                "source_connection_id": str(source_connection_id),
                "collection_readable_id": str(collection.readable_id),
                "organization_name": ctx.organization.name,
                "scheduled": str(sync_job.scheduled),
            },
        )

    # -------------------------------------------------------------------------
    # Private: Source Connection ID
    # -------------------------------------------------------------------------

    @classmethod
    async def _get_source_connection_id(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        ctx: BaseContext,
    ) -> UUID:
        """Get user-facing source connection ID for logging and scoping."""
        from airweave.platform.builders.source import SourceContextBuilder

        return await SourceContextBuilder.get_source_connection_id(db, sync, ctx)

    # -------------------------------------------------------------------------
    # Private: Source
    # -------------------------------------------------------------------------

    @classmethod
    async def _build_source(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        ctx: BaseContext,
        logger: ContextualLogger,
        access_token: Optional[str],
        force_full_sync: bool,
        execution_config: Optional[SyncConfig],
    ) -> tuple:
        """Build source and cursor. Returns (source, cursor) tuple."""
        from airweave.platform.builders.source import SourceContextBuilder
        from airweave.platform.contexts.infra import InfraContext

        # SourceContextBuilder still expects InfraContext for now — create a thin wrapper.
        # TODO: Refactor SourceContextBuilder to accept (ctx, logger) directly.
        infra = InfraContext(ctx=ctx, logger=logger)

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

    # -------------------------------------------------------------------------
    # Private: Destinations
    # -------------------------------------------------------------------------

    @classmethod
    async def _build_destinations(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.Collection,
        ctx: BaseContext,
        logger: ContextualLogger,
        execution_config: Optional[SyncConfig],
    ) -> tuple:
        """Build destinations and entity map. Returns (destinations, entity_map) tuple."""
        from airweave.platform.builders.destinations import DestinationsContextBuilder

        return await DestinationsContextBuilder.build(
            db=db,
            sync=sync,
            collection=collection,
            ctx=ctx,
            logger=logger,
            execution_config=execution_config,
        )

    # -------------------------------------------------------------------------
    # Private: Tracking
    # -------------------------------------------------------------------------

    @classmethod
    async def _build_tracking(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        ctx: BaseContext,
        logger: ContextualLogger,
    ) -> tuple:
        """Build tracking components.

        Returns (entity_tracker, state_publisher, guard_rail) tuple.
        """
        from airweave.platform.builders.tracking import TrackingContextBuilder

        return await TrackingContextBuilder.build(
            db=db,
            sync=sync,
            sync_job=sync_job,
            ctx=ctx,
            logger=logger,
        )
