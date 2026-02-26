"""Cleanup context builder for deletion operations."""

from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.context import BaseContext
from airweave.core.logging import LoggerConfigurator
from airweave.platform.builders.destinations import DestinationsContextBuilder
from airweave.platform.contexts.cleanup import CleanupContext


class CleanupContextBuilder:
    """Builds cleanup context for deletion operations."""

    @classmethod
    async def build_for_sync(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.Collection,
        ctx: BaseContext,
    ) -> CleanupContext:
        """Build cleanup context for a single sync's entities.

        Args:
            db: Database session
            sync: Sync to clean up
            collection: Collection the sync belongs to
            ctx: Base context (provides org identity)

        Returns:
            CleanupContext ready for deletion operations.
        """
        # Get source connection ID
        source_connection = await crud.source_connection.get_by_sync_id(
            db, sync_id=sync.id, ctx=ctx
        )
        source_connection_id = source_connection.id if source_connection else sync.id

        # Build cleanup-specific logger
        logger = LoggerConfigurator.configure_logger(
            "airweave.platform.cleanup",
            dimensions={
                "operation": "cleanup",
                "sync_id": str(sync.id),
                "collection_id": str(collection.id),
                "organization_id": str(ctx.organization.id),
            },
        )

        # Build destinations for cleanup
        destinations = await DestinationsContextBuilder.build_for_cleanup(
            db=db,
            collection=collection,
            logger=logger,
        )

        return CleanupContext(
            organization=ctx.organization,
            sync_id=sync.id,
            collection_id=collection.id,
            source_connection_id=source_connection_id,
            destinations=destinations,
            logger=logger,
        )

    @classmethod
    async def build_for_collection(
        cls,
        db: AsyncSession,
        collection: schemas.Collection,
        ctx: BaseContext,
    ) -> List[CleanupContext]:
        """Build cleanup contexts for all syncs in a collection.

        Args:
            db: Database session
            collection: Collection to clean up
            ctx: Base context

        Returns:
            List of CleanupContext, one per sync.
        """
        syncs = await crud.sync.get_by_collection(db, collection.id, ctx)

        contexts = []
        for sync in syncs:
            cleanup_ctx = await cls.build_for_sync(db, sync, collection, ctx)
            contexts.append(cleanup_ctx)

        return contexts
