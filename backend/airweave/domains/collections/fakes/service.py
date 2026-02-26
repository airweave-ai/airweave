"""Fake collection service for testing."""

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.domains.collections.exceptions import CollectionNotFoundError
from airweave.models.collection import Collection


class FakeCollectionService:
    """In-memory fake for CollectionServiceProtocol."""

    def __init__(self) -> None:
        """Initialize with empty stores."""
        self._store: dict[UUID, Collection] = {}
        self._readable_store: dict[str, Collection] = {}
        self._calls: list[tuple[Any, ...]] = []
        self._create_result: Optional[schemas.Collection] = None
        self._delete_result: Optional[schemas.Collection] = None

    def seed(self, id: UUID, obj: Collection) -> None:
        """Seed a collection by ID."""
        self._store[id] = obj

    def seed_readable(self, readable_id: str, obj: Collection) -> None:
        """Seed a collection by readable ID."""
        self._readable_store[readable_id] = obj

    def set_create_result(self, result: schemas.Collection) -> None:
        """Set the result returned by create."""
        self._create_result = result

    def set_delete_result(self, result: schemas.Collection) -> None:
        """Set the result returned by delete."""
        self._delete_result = result

    async def list(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
    ) -> List[Collection]:
        """Return seeded collections."""
        self._calls.append(("list", db, ctx, skip, limit, search_query))
        return list(self._readable_store.values())[skip : skip + limit]

    async def count(
        self, db: AsyncSession, *, ctx: ApiContext, search_query: Optional[str] = None
    ) -> int:
        """Return count of seeded collections."""
        self._calls.append(("count", db, ctx, search_query))
        return len(self._readable_store)

    async def create(
        self,
        db: AsyncSession,
        *,
        collection_in: schemas.CollectionCreate,
        ctx: ApiContext,
    ) -> schemas.Collection:
        """Return the pre-configured create result."""
        self._calls.append(("create", db, collection_in, ctx))
        if self._create_result is None:
            raise RuntimeError("FakeCollectionService.create_result not configured")
        return self._create_result

    async def get(self, db: AsyncSession, *, readable_id: str, ctx: ApiContext) -> Collection:
        """Return seeded collection by readable ID."""
        self._calls.append(("get", db, readable_id, ctx))
        obj = self._readable_store.get(readable_id)
        if obj is None:
            raise CollectionNotFoundError(readable_id)
        return obj

    async def update(
        self,
        db: AsyncSession,
        *,
        readable_id: str,
        collection_in: schemas.CollectionUpdate,
        ctx: ApiContext,
    ) -> Collection:
        """Return seeded collection after recording the update call."""
        self._calls.append(("update", db, readable_id, collection_in, ctx))
        obj = self._readable_store.get(readable_id)
        if obj is None:
            raise CollectionNotFoundError(readable_id)
        return obj

    async def delete(
        self, db: AsyncSession, *, readable_id: str, ctx: ApiContext
    ) -> schemas.Collection:
        """Return the pre-configured delete result."""
        self._calls.append(("delete", db, readable_id, ctx))
        if self._delete_result is None:
            raise RuntimeError("FakeCollectionService.delete_result not configured")
        return self._delete_result
