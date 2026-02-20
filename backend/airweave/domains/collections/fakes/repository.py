"""Fake collection repository for testing."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.models.collection import Collection


class FakeCollectionRepository:
    """In-memory fake for CollectionRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, Collection] = {}
        self._readable_store: dict[str, Collection] = {}
        self._calls: list[tuple[Any, ...]] = []

    def seed(self, id: UUID, obj: Collection) -> None:
        self._store[id] = obj

    def seed_readable(self, readable_id: str, obj: Collection) -> None:
        self._readable_store[readable_id] = obj

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Collection]:
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Collection]:
        self._calls.append(("get_by_readable_id", db, readable_id, ctx))
        return self._readable_store.get(readable_id)
