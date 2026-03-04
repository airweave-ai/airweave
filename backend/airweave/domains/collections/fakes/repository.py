"""Fake collection repository for testing."""

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.collection import Collection


class FakeCollectionRepository:
    """In-memory fake for CollectionRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize with empty stores."""
        self._store: dict[UUID, Collection] = {}
        self._readable_store: dict[str, Collection] = {}
        self._calls: list[tuple[Any, ...]] = []

    def seed(self, id: UUID, obj: Collection) -> None:
        """Seed a collection by ID."""
        self._store[id] = obj

    def seed_readable(self, readable_id: str, obj: Collection) -> None:
        """Seed a collection by readable ID."""
        self._readable_store[readable_id] = obj

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Collection]:
        """Return seeded collection by ID."""
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Collection]:
        """Return seeded collection by readable ID."""
        self._calls.append(("get_by_readable_id", db, readable_id, ctx))
        return self._readable_store.get(readable_id)

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
    ) -> List[Collection]:
        """Return seeded collections with optional search filter."""
        self._calls.append(("get_multi", db, ctx, skip, limit, search_query))
        items = list(self._readable_store.values())
        if search_query:
            q = search_query.lower()
            items = [
                c
                for c in items
                if q in getattr(c, "name", "").lower() or q in getattr(c, "readable_id", "").lower()
            ]
        return items[skip : skip + limit]

    async def count(
        self, db: AsyncSession, *, ctx: ApiContext, search_query: Optional[str] = None
    ) -> int:
        """Return count of seeded collections."""
        self._calls.append(("count", db, ctx, search_query))
        if search_query:
            q = search_query.lower()
            return len(
                [
                    c
                    for c in self._readable_store.values()
                    if q in getattr(c, "name", "").lower()
                    or q in getattr(c, "readable_id", "").lower()
                ]
            )
        return len(self._readable_store)

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: dict,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Collection:
        """Create and store a fake collection."""
        self._calls.append(("create", db, obj_in, ctx, uow))
        from datetime import datetime, timezone
        from unittest.mock import MagicMock

        from airweave.domains.embedders.config import (
            DENSE_EMBEDDER,
            EMBEDDING_DIMENSIONS,
        )

        col = MagicMock(spec=Collection)
        for k, v in obj_in.items():
            setattr(col, k, v)
        col.id = obj_in.get("id", UUID("00000000-0000-0000-0000-000000000001"))
        col.organization_id = ctx.organization.id
        col.created_at = datetime.now(timezone.utc)
        col.modified_at = datetime.now(timezone.utc)
        col.created_by_email = None
        col.modified_by_email = None
        from airweave.core.shared_models import CollectionStatus

        col.status = CollectionStatus.NEEDS_SOURCE

        # Provide a mock deployment metadata so schema model_validator can derive
        # vector_size and embedding_model_name from the relationship.
        dep_meta = MagicMock()
        dep_meta.embedding_dimensions = EMBEDDING_DIMENSIONS
        dep_meta.dense_embedder = DENSE_EMBEDDER
        col.vector_db_deployment_metadata = dep_meta

        self._readable_store[obj_in.get("readable_id", "")] = col
        return col

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Collection,
        obj_in: schemas.CollectionUpdate,
        ctx: ApiContext,
    ) -> Collection:
        """Apply updates to the existing fake collection."""
        self._calls.append(("update", db, db_obj, obj_in, ctx))
        # Apply updates to the existing object
        update_data = obj_in.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(db_obj, k, v)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> Optional[Collection]:
        """Remove a collection from the fake store."""
        self._calls.append(("remove", db, id, ctx))
        obj = self._store.pop(id, None)
        if obj is None:
            # Try to find by iterating readable_store
            for rid, c in list(self._readable_store.items()):
                if getattr(c, "id", None) == id:
                    del self._readable_store[rid]
                    return c
        else:
            # Also remove from readable store
            rid = getattr(obj, "readable_id", None)
            if rid and rid in self._readable_store:
                del self._readable_store[rid]
        return obj
