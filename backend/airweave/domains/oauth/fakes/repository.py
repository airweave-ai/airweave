"""Fake repositories for OAuth2 domain testing."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext


class FakeOAuthConnectionRepository:
    """In-memory fake for OAuthConnectionRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, Any] = {}
        self._calls: list[tuple] = []
        self._created: list[Any] = []

    def seed(self, id: UUID, obj: Any) -> None:
        self._store[id] = obj

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Any]:
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def create(self, db: AsyncSession, *, obj_in: Any, ctx: ApiContext, uow: Any) -> Any:
        self._calls.append(("create", db, obj_in, ctx, uow))
        self._created.append(obj_in)
        return obj_in


class FakeOAuthCredentialRepository:
    """In-memory fake for OAuthCredentialRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, Any] = {}
        self._calls: list[tuple] = []
        self._created: list[Any] = []
        self._updated: list[tuple] = []

    def seed(self, id: UUID, obj: Any) -> None:
        self._store[id] = obj

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Any]:
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def update(self, db: AsyncSession, *, db_obj: Any, obj_in: Any, ctx: ApiContext) -> Any:
        self._calls.append(("update", db, db_obj, obj_in, ctx))
        self._updated.append((db_obj, obj_in))
        return db_obj

    async def create(self, db: AsyncSession, *, obj_in: Any, ctx: ApiContext, uow: Any) -> Any:
        self._calls.append(("create", db, obj_in, ctx, uow))
        self._created.append(obj_in)
        return obj_in


class FakeOAuthSourceRepository:
    """In-memory fake for OAuthSourceRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._calls: list[tuple] = []

    def seed(self, short_name: str, obj: Any) -> None:
        self._store[short_name] = obj

    async def get_by_short_name(self, db: AsyncSession, short_name: str) -> Optional[Any]:
        self._calls.append(("get_by_short_name", db, short_name))
        return self._store.get(short_name)
