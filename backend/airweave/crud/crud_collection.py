# airweave/crud/crud_collection.py

"""CRUD operations for collections."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.core.shared_models import CollectionStatus, SourceConnectionStatus
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.collection import Collection
from airweave.schemas.collection import CollectionCreate, CollectionUpdate


class CRUDCollection(CRUDBaseOrganization[Collection, CollectionCreate, CollectionUpdate]):
    """CRUD operations for collections."""

    async def _compute_collection_status(
        self, db: AsyncSession, collection: Collection, ctx: ApiContext
    ) -> CollectionStatus:
        """Compute the ephemeral status of a collection based on its source connections.

        Logic:
        - If no source connections: NEEDS_SOURCE
        - If all source connections are failing: ERROR
        - If some source connections are failing: PARTIAL_ERROR
        - If any source connection is in progress: ACTIVE (this is considered an OK state)
        - Otherwise: ACTIVE

        Args:
            db: The database session
            collection: The collection
            ctx: The API context

        Returns:
            The computed ephemeral status
        """
        # Get all source connections for this collection
        source_connections = await crud.source_connection.get_for_collection(
            db, readable_collection_id=collection.readable_id, ctx=ctx
        )

        if not source_connections:
            return CollectionStatus.NEEDS_SOURCE

        # Filter out pending shells to evaluate the status of active connections
        active_connections = [sc for sc in source_connections if sc.is_authenticated]

        # If there are no authenticated connections, it's effectively the same as needing a source
        if not active_connections:
            return CollectionStatus.NEEDS_SOURCE

        # Count the number of failing/in-progress connections among the active ones
        failing_count = 0
        in_progress_count = 0

        for sc in active_connections:
            if sc.status == SourceConnectionStatus.ERROR:
                failing_count += 1
            elif sc.status in [
                SourceConnectionStatus.SYNCING,
                SourceConnectionStatus.PENDING_SYNC,
                SourceConnectionStatus.ACTIVE,
            ]:
                in_progress_count += 1

        # If any active connections are in progress, the collection is active
        if in_progress_count > 0:
            return CollectionStatus.ACTIVE

        # If all active connections are failing, the collection is in error
        if failing_count == len(active_connections):
            return CollectionStatus.ERROR

        # If some but not all are failing, the collection is in partial error
        if failing_count > 0:
            return CollectionStatus.PARTIAL_ERROR

        # Otherwise, the collection is active
        return CollectionStatus.ACTIVE

    async def _attach_ephemeral_status(
        self, db: AsyncSession, collections: List[Collection], ctx: ApiContext
    ) -> List[Collection]:
        """Attach ephemeral status to collections.

        Args:
            db: The database session
            collections: The collections to process
            ctx: The API context

        Returns:
            Collections with computed status
        """
        if not collections:
            return []

        for collection in collections:
            # Compute and set the ephemeral status
            collection.status = await self._compute_collection_status(db, collection, ctx)

        return collections

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Collection]:
        """Get a collection by its ID with computed ephemeral status."""
        # Get the collection using the parent method
        collection = await super().get(db, id=id, ctx=ctx)

        if collection:
            # Compute and set the ephemeral status
            collection = (await self._attach_ephemeral_status(db, [collection], ctx))[0]

        return collection

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Collection]:
        """Get a collection by its readable ID with computed ephemeral status."""
        result = await db.execute(select(Collection).where(Collection.readable_id == readable_id))
        collection = result.scalar_one_or_none()

        if not collection:
            raise NotFoundException(f"Collection with readable ID {readable_id} not found")

        await self._validate_organization_access(ctx, collection.organization_id)

        # Compute and set the ephemeral status
        collection = (await self._attach_ephemeral_status(db, [collection], ctx))[0]

        return collection

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100, ctx: ApiContext
    ) -> List[Collection]:
        """Get multiple collections with computed ephemeral statuses."""
        # Get collections using the parent method
        collections = await super().get_multi(db, skip=skip, limit=limit, ctx=ctx)

        # Compute and set the ephemeral status for each collection
        collections = await self._attach_ephemeral_status(db, collections, ctx)

        return collections


collection = CRUDCollection(Collection)
