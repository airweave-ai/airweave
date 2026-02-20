"""Fake source connection service for testing."""

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.models.source_connection import SourceConnection
from airweave.schemas.source_connection import (
    SourceConnectionCreate,
    SourceConnectionListItem,
    SourceConnectionUpdate,
)


class FakeSourceConnectionService:
    """In-memory fake for SourceConnectionServiceProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, SourceConnection] = {}
        self._list_items: List[SourceConnectionListItem] = []
        self._calls: list[tuple[Any, ...]] = []

    def seed(self, id: UUID, obj: SourceConnection) -> None:
        self._store[id] = obj

    def seed_list_items(self, items: List[SourceConnectionListItem]) -> None:
        self._list_items = list(items)

    async def get(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> SourceConnection:
        self._calls.append(("get", db, id, ctx))
        obj = self._store.get(id)
        if not obj:
            raise NotFoundException("Source connection not found")
        return obj

    async def list(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        readable_collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnectionListItem]:
        self._calls.append(("list", db, ctx, readable_collection_id, skip, limit))
        items = self._list_items
        if readable_collection_id is not None:
            items = [i for i in items if i.readable_collection_id == readable_collection_id]
        return items[skip : skip + limit]

    async def create(
        self, db: AsyncSession, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnection:
        self._calls.append(("create", db, obj_in, ctx))
        raise NotImplementedError("FakeSourceConnectionService.create not implemented")

    async def update(
        self, db: AsyncSession, id: UUID, obj_in: SourceConnectionUpdate, ctx: ApiContext
    ) -> SourceConnection:
        self._calls.append(("update", db, id, obj_in, ctx))
        raise NotImplementedError("FakeSourceConnectionService.update not implemented")

    async def delete(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> SourceConnection:
        self._calls.append(("delete", db, id, ctx))
        obj = self._store.get(id)
        if not obj:
            raise NotFoundException("Source connection not found")
        del self._store[id]
        return obj
