"""Cleanup context builder for deletion operations."""

from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.platform.builders.destinations import DestinationsContextBuilder
from airweave.platform.builders.infra import InfraContextBuilder
from airweave.platform.builders.scope import ScopeContextBuilder
from airweave.platform.contexts.cleanup import CleanupContext


class CleanupContextBuilder:
    """Builds cleanup context for deletion operations."""

    @classmethod
    async def build_for_sync(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.Collection,
        ctx: ApiContext,
    ) -> CleanupContext:
        """Build cleanup context for a single sync's entities.

        Args:
            db: Database session
            sync: Sync to clean up
            collection: Collection the sync belongs to
            ctx: API context

        Returns:
            CleanupContext ready for deletion operations.
        """
        # Build scope
        scope = ScopeContextBuilder.build_minimal(
            sync_id=sync.id,
            collection_id=collection.id,
            organization_id=collection.organization_id,
            job_id=None,  # No job for cleanup
        )

        # Build infra (minimal)
        infra = InfraContextBuilder.build_minimal(
            ctx=ctx,
            operation="cleanup",
            sync_id=sync.id,
            collection_id=collection.id,
        )

        # Build destinations
        destinations = await DestinationsContextBuilder.build_for_collection(
            db=db,
            sync=sync,
            collection=collection,
            infra=infra,
        )

        return CleanupContext(
            scope=scope,
            infra=infra,
            destinations=destinations,
        )

    @classmethod
    async def build_for_collection(
        cls,
        db: AsyncSession,
        collection: schemas.Collection,
        ctx: ApiContext,
    ) -> List[CleanupContext]:
        """Build cleanup contexts for all syncs in a collection.

        Args:
            db: Database session
            collection: Collection to clean up
            ctx: API context

        Returns:
            List of CleanupContext, one per sync.
        """
        # Get all syncs for this collection
        syncs = await crud.sync.get_by_collection(db, collection.id, ctx)

        contexts = []
        for sync in syncs:
            cleanup_ctx = await cls.build_for_sync(db, sync, collection, ctx)
            contexts.append(cleanup_ctx)

        return contexts
