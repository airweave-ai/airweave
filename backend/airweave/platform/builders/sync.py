"""Sync context builder - orchestrates all context builders."""

import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.platform.builders.destinations import DestinationsContextBuilder
from airweave.platform.builders.infra import InfraContextBuilder
from airweave.platform.builders.scope import ScopeContextBuilder
from airweave.platform.builders.source import SourceContextBuilder
from airweave.platform.builders.tracking import TrackingContextBuilder
from airweave.platform.contexts.batch import BatchContext
from airweave.platform.contexts.sync import SyncContext
from airweave.platform.sync.config import SyncConfig


class SyncContextBuilder:
    """Orchestrates all context builders to create SyncContext."""

    @classmethod
    async def build(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        connection: schemas.Connection,
        ctx: ApiContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> SyncContext:
        """Build complete sync context using all builders.

        This method coordinates the builders to construct all sub-contexts,
        then assembles them into a SyncContext.

        Args:
            db: Database session
            sync: The sync configuration
            sync_job: The sync job
            collection: The collection to sync to
            connection: The connection
            ctx: The API context
            access_token: Optional token to use instead of stored credentials
            force_full_sync: If True, forces a full sync with orphaned entity deletion
            execution_config: Optional execution config for controlling sync behavior

        Returns:
            SyncContext with all sub-contexts assembled.
        """
        # Step 1: Get source connection ID early (needed for logger dimensions)
        source_connection_id = await SourceContextBuilder.get_source_connection_id(db, sync, ctx)

        # Step 2: Build infrastructure context (needed by all other builders)
        infra = InfraContextBuilder.build(
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            source_connection_id=source_connection_id,
            ctx=ctx,
        )

        infra.logger.info("Building sync context via context builders...")

        # Step 3: Build scope context
        scope = ScopeContextBuilder.build(
            sync=sync,
            collection=collection,
            ctx=ctx,
            source_connection_id=source_connection_id,
            job_id=sync_job.id,
        )

        # Step 4: Build all remaining contexts in parallel (where possible)
        source_task = SourceContextBuilder.build(
            db=db,
            sync=sync,
            sync_job=sync_job,
            infra=infra,
            access_token=access_token,
            force_full_sync=force_full_sync,
            execution_config=execution_config,
        )

        destinations_task = DestinationsContextBuilder.build(
            db=db,
            sync=sync,
            collection=collection,
            infra=infra,
            execution_config=execution_config,
        )

        tracking_task = TrackingContextBuilder.build(
            db=db,
            sync=sync,
            sync_job=sync_job,
            infra=infra,
        )

        # Run all builders in parallel
        source, destinations, tracking = await asyncio.gather(
            source_task,
            destinations_task,
            tracking_task,
        )

        # Step 5: Create batch context
        batch = BatchContext(
            should_batch=True,
            batch_size=64,
            max_batch_latency_ms=200,
            force_full_sync=force_full_sync,
        )

        # Step 6: Assemble SyncContext
        sync_context = SyncContext(
            scope=scope,
            infra=infra,
            source=source,
            destinations=destinations,
            tracking=tracking,
            batch=batch,
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,
            execution_config=execution_config,
        )

        infra.logger.info("Sync context created via context builders")

        return sync_context
