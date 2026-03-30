"""Collection repository wrapping crud.collection with ephemeral status enrichment."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.core.shared_models import CollectionStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.collections.protocols import (
    CollectionListResult,
    CollectionRepositoryProtocol,
)
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.models.collection import Collection
from airweave.schemas.collection import SourceConnectionSummary


class CollectionRepository(CollectionRepositoryProtocol):
    """Delegates to crud.collection, enriches with ephemeral status."""

    def __init__(  # noqa: D107
        self,
        source_registry: SourceRegistryProtocol,
        sc_repo: SourceConnectionRepositoryProtocol,
    ) -> None:
        self._source_registry = source_registry
        self._sc_repo = sc_repo

    def _federated_lookup(self, short_name: str) -> bool:
        try:
            return self._source_registry.get(short_name).federated_search
        except KeyError:
            return False

    @staticmethod
    def _compute_collection_status(
        connections_with_stats: List[Dict[str, Any]],
    ) -> CollectionStatus:
        """Derive ephemeral status from pre-fetched connection data."""
        if not connections_with_stats:
            return CollectionStatus.NEEDS_SOURCE

        active_connections = [
            conn for conn in connections_with_stats if conn.get("is_authenticated", False)
        ]
        if not active_connections:
            return CollectionStatus.NEEDS_SOURCE

        working_count = 0
        failing_count = 0

        for conn in active_connections:
            if conn.get("federated_search", False):
                working_count += 1
                continue

            last_job = conn.get("last_job", {})
            last_job_status = last_job.get("status") if last_job else None

            if last_job_status == "completed":
                working_count += 1
            elif last_job_status in ("running", "cancelling"):
                working_count += 1
            elif last_job_status == "failed":
                failing_count += 1

        if working_count > 0:
            return CollectionStatus.ACTIVE
        if failing_count == len(active_connections):
            return CollectionStatus.ERROR
        return CollectionStatus.NEEDS_SOURCE

    async def _attach_ephemeral_status(
        self, db: AsyncSession, collections: List[Collection], ctx: ApiContext
    ) -> CollectionListResult:
        """Compute ephemeral status and build source connection summaries."""
        summaries: Dict[str, List[SourceConnectionSummary]] = {}

        if not collections:
            return CollectionListResult(collections=[])

        collection_ids = [c.readable_id for c in collections]

        all_connections = await self._sc_repo.get_by_collection_ids(
            db,
            organization_id=ctx.organization.id,
            readable_collection_ids=collection_ids,
        )

        if not all_connections:
            for collection in collections:
                collection.status = CollectionStatus.NEEDS_SOURCE
            return CollectionListResult(collections=collections)

        last_jobs = await self._sc_repo.fetch_last_jobs(db, all_connections)

        connections_by_collection: Dict[str, List[Dict[str, Any]]] = {}
        for sc in all_connections:
            coll_id = sc.readable_collection_id
            if coll_id is None:
                continue
            coll_id = str(coll_id)

            if coll_id not in connections_by_collection:
                connections_by_collection[coll_id] = []

            connections_by_collection[coll_id].append(
                {
                    "is_authenticated": sc.is_authenticated,
                    "federated_search": self._federated_lookup(sc.short_name),
                    "last_job": last_jobs.get(sc.id),
                }
            )

            if coll_id not in summaries:
                summaries[coll_id] = []
            summaries[coll_id].append(
                SourceConnectionSummary(short_name=sc.short_name, name=sc.name)
            )

        for collection in collections:
            conn_data = connections_by_collection.get(collection.readable_id, [])
            collection.status = self._compute_collection_status(conn_data)

        return CollectionListResult(collections=collections, summaries_by_collection=summaries)

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Collection:
        """Get a collection by ID with ephemeral status."""
        collection = await crud.collection.get(db, id, ctx)
        result = await self._attach_ephemeral_status(db, [collection], ctx)
        return result.collections[0]

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Collection]:
        """Get a collection by readable ID with ephemeral status."""
        try:
            collection = await crud.collection.get_by_readable_id(
                db, readable_id=readable_id, ctx=ctx
            )
        except NotFoundException:
            return None
        if collection:
            result = await self._attach_ephemeral_status(db, [collection], ctx)
            collection = result.collections[0]
        return collection

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
    ) -> CollectionListResult:
        """Get multiple collections with pagination, optional search, and ephemeral status."""
        collections = await crud.collection.get_multi(
            db, ctx=ctx, skip=skip, limit=limit, search_query=search_query
        )
        return await self._attach_ephemeral_status(db, collections, ctx)

    async def count(
        self, db: AsyncSession, *, ctx: ApiContext, search_query: Optional[str] = None
    ) -> int:
        """Get total count of collections."""
        return await crud.collection.count(db, ctx=ctx, search_query=search_query)

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: dict,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Collection:
        """Create a new collection."""
        return await crud.collection.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Collection,
        obj_in: schemas.CollectionUpdate,
        ctx: ApiContext,
    ) -> Collection:
        """Update an existing collection."""
        return await crud.collection.update(db, db_obj=db_obj, obj_in=obj_in, ctx=ctx)

    async def remove(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> Collection:
        """Delete a collection by ID."""
        return await crud.collection.remove(db, id=id, ctx=ctx)
