"""Sync context builder - constructs SyncContext (frozen data only).

Builds the data-only SyncContext. Live services (source, destinations, trackers)
are built by SyncFactory directly using the sub-builders.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.logging import ContextualLogger, LoggerConfigurator
from airweave.platform.contexts.sync import SyncContext
from airweave.platform.sync.config import SyncConfig


class SyncContextBuilder:
    """Builds SyncContext (frozen data only).

    Does NOT build services — those are the factory's responsibility.
    """

    @classmethod
    async def build(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        ctx: BaseContext,
        source_connection_id: UUID,
        source_short_name: str,
        entity_map: dict,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> SyncContext:
        """Build data-only SyncContext.

        Args:
            db: Database session
            sync: The sync configuration
            sync_job: The sync job
            collection: The collection to sync to
            connection: The connection
            ctx: The base context (provides org identity)
            source_connection_id: Pre-resolved source connection ID
            source_short_name: Source short name (extracted from source instance)
            entity_map: Entity class to definition ID mapping
            force_full_sync: If True, forces a full sync
            execution_config: Optional execution config

        Returns:
            SyncContext with all data fields populated.
        """
        logger = cls._build_logger(
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            source_connection_id=source_connection_id,
            ctx=ctx,
        )

        return SyncContext(
            organization=ctx.organization,
            sync_id=sync.id,
            sync_job_id=sync_job.id,
            collection_id=collection.id,
            source_connection_id=source_connection_id,
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,
            execution_config=execution_config,
            force_full_sync=force_full_sync,
            entity_map=entity_map,
            source_short_name=source_short_name,
            logger=logger,
        )

    @classmethod
    def _build_logger(
        cls,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
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

    @classmethod
    async def get_source_connection_id(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        ctx: BaseContext,
    ) -> UUID:
        """Get user-facing source connection ID for logging and scoping."""
        from airweave.platform.builders.source import SourceContextBuilder

        return await SourceContextBuilder.get_source_connection_id(db, sync, ctx)
