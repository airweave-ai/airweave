# airweave/crud/crud_collection.py

"""CRUD operations for collections."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.core.context import BaseContext
from airweave.core.exceptions import NotFoundException, PermissionException
from airweave.core.shared_models import CollectionStatus
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.collection import Collection
from airweave.models.source_connection import SourceConnection
from airweave.schemas.collection import CollectionCreate, CollectionUpdate


class CRUDCollection(CRUDBaseOrganization[Collection, CollectionCreate, CollectionUpdate]):
    """CRUD operations for collections."""

    def _compute_collection_status(
        self, connections_with_stats: List[Dict[str, Any]]
    ) -> CollectionStatus:
        """Compute collection status from pre-fetched connection data.

        Logic:
        - If no authenticated source connections or no syncs completed yet: NEEDS_SOURCE
        - If at least one connection has completed or is running: ACTIVE
        - If all connections have failed: ERROR

        Args:
            connections_with_stats: List of connection dicts with stats already fetched

        Returns:
            The computed ephemeral status
        """
        if not connections_with_stats:
            return CollectionStatus.NEEDS_SOURCE

        # Filter out pending shells to evaluate the status of active connections
        active_connections = [
            conn for conn in connections_with_stats if conn.get("is_authenticated", False)
        ]

        # If there are no authenticated connections, it's effectively the same as needing a source
        if not active_connections:
            return CollectionStatus.NEEDS_SOURCE

        # Count connections by their sync status
        working_count = 0  # Connections with completed or in-progress syncs (or federated)
        failing_count = 0  # Connections with failed syncs

        for conn in active_connections:
            # Federated sources are always "working" when authenticated
            if conn.get("federated_search", False):
                working_count += 1
                continue

            # Get last job status to compute connection status for non-federated sources
            last_job = conn.get("last_job", {})
            last_job_status = last_job.get("status") if last_job else None

            # Only count connections that have completed or are actively syncing
            if last_job_status == "completed":
                working_count += 1
            elif last_job_status in ("running", "cancelling"):
                working_count += 1
            elif last_job_status == "failed":
                failing_count += 1
            # Connections with no jobs, pending, created, or cancelled are not counted

        # If at least one connection has successfully synced or is syncing, collection is active
        if working_count > 0:
            return CollectionStatus.ACTIVE

        # If all active connections have failed, the collection is in error
        if failing_count == len(active_connections):
            return CollectionStatus.ERROR

        # No working connections and not all failed - treat as needing source
        # (connections exist but haven't successfully synced yet)
        return CollectionStatus.NEEDS_SOURCE

    async def _attach_ephemeral_status(
        self, db: AsyncSession, collections: List[Collection], ctx: BaseContext
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

        # Fetch all data in ~5 queries total to avoid N+1 problem
        collection_ids = [c.readable_id for c in collections]

        # 1. Get ALL source connections for ALL collections (1 query)
        query = select(SourceConnection).where(
            and_(
                SourceConnection.organization_id == ctx.organization.id,
                SourceConnection.readable_collection_id.in_(collection_ids),
            )
        )
        result = await db.execute(query)
        all_connections = list(result.scalars().all())

        if not all_connections:
            # All collections have no sources
            for collection in collections:
                collection.status = CollectionStatus.NEEDS_SOURCE
            return collections

        # 2. Bulk fetch all related data using existing optimized methods (4 queries)
        _auth_methods = await crud.source_connection._fetch_auth_methods(db, all_connections)
        last_jobs = await crud.source_connection._fetch_last_jobs(db, all_connections)
        _entity_counts = await crud.source_connection._fetch_entity_counts(db, all_connections)
        federated_flags = await crud.source_connection._fetch_federated_search_flags(
            db, all_connections
        )

        # 3. Group connections by collection (in-memory operation)
        connections_by_collection: Dict[str, List[Dict[str, Any]]] = {}
        for sc in all_connections:
            if sc.readable_collection_id not in connections_by_collection:
                connections_by_collection[sc.readable_collection_id] = []

            # Build same data structure that get_multi_with_stats returns
            connections_by_collection[sc.readable_collection_id].append(
                {
                    "is_authenticated": sc.is_authenticated,
                    "federated_search": federated_flags.get(sc.short_name, False),
                    "last_job": last_jobs.get(sc.id),
                }
            )

        # 4. Compute status for each collection using pre-fetched data (no DB calls)
        for collection in collections:
            conn_data = connections_by_collection.get(collection.readable_id, [])
            collection.status = self._compute_collection_status(conn_data)

        return collections

    async def get(self, db: AsyncSession, id: UUID, ctx: BaseContext) -> Optional[Collection]:
        """Get a collection by its ID with computed ephemeral status."""
        # Get the collection using the parent method
        collection = await super().get(db, id=id, ctx=ctx)

        if collection:
            # Compute and set the ephemeral status
            collection = (await self._attach_ephemeral_status(db, [collection], ctx))[0]

        return collection

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: BaseContext
    ) -> Optional[Collection]:
        """Get a collection by its readable ID with computed ephemeral status."""
        result = await db.execute(select(Collection).where(Collection.readable_id == readable_id))
        collection = result.scalar_one_or_none()

        if not collection:
            raise NotFoundException(f"Collection '{readable_id}' not found.")

        # Validate organization access - convert PermissionException to NotFoundException
        # to avoid leaking information about collection existence across organizations
        try:
            await self._validate_organization_access(ctx, collection.organization_id)
        except PermissionException:
            # Don't reveal that the collection exists but belongs to another organization
            raise NotFoundException(f"Collection '{readable_id}' not found.")

        # Compute and set the ephemeral status
        collection = (await self._attach_ephemeral_status(db, [collection], ctx))[0]

        return collection

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        ctx: BaseContext,
        search_query: Optional[str] = None,
    ) -> List[Collection]:
        """Get multiple collections with computed ephemeral statuses and search.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            ctx: API context
            search_query: Optional search term to filter by name or readable_id

        Returns:
            List of collections with computed statuses
        """
        # Build query with org scope
        query = select(Collection).where(Collection.organization_id == ctx.organization.id)

        # Apply search filter if provided
        if search_query:
            search_pattern = f"%{search_query.lower()}%"
            query = query.where(
                (func.lower(Collection.name).like(search_pattern))
                | (func.lower(Collection.readable_id).like(search_pattern))
            )

        # Apply sorting (always by created_at desc)
        query = query.order_by(Collection.created_at.desc())

        # Apply pagination
        query = query.offset(skip).limit(limit)

        # Execute query
        result = await db.execute(query)
        collections = list(result.scalars().all())

        # Compute and set the ephemeral status for each collection
        collections = await self._attach_ephemeral_status(db, collections, ctx)

        return collections

    async def count(
        self, db: AsyncSession, ctx: BaseContext, search_query: Optional[str] = None
    ) -> int:
        """Get total count of collections for the organization.

        Args:
            db: Database session
            ctx: API context
            search_query: Optional search term to filter by name or readable_id

        Returns:
            Count of collections matching criteria
        """
        query = (
            select(func.count())
            .select_from(Collection)
            .where(Collection.organization_id == ctx.organization.id)
        )

        # Apply search filter if provided
        if search_query:
            search_pattern = f"%{search_query.lower()}%"
            query = query.where(
                (func.lower(Collection.name).like(search_pattern))
                | (func.lower(Collection.readable_id).like(search_pattern))
            )

        result = await db.execute(query)
        return result.scalar_one()


collection = CRUDCollection(Collection)
