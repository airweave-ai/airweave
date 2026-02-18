"""Fake repositories for OAuth domain testing."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection import Connection
from airweave.models.integration_credential import IntegrationCredential
from airweave.models.source import Source
from airweave.schemas.connection import ConnectionCreate
from airweave.schemas.integration_credential import (
    IntegrationCredentialCreateEncrypted,
    IntegrationCredentialUpdate,
)


class FakeOAuthConnectionRepository:
    """In-memory fake for OAuthConnectionRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, Any] = {}
        self._calls: list[tuple] = []
        self._created: list[Any] = []

    def seed(self, id: UUID, obj: Any) -> None:
        self._store[id] = obj

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Connection:
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: ConnectionCreate,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Connection:
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

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> IntegrationCredential:
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: IntegrationCredential,
        obj_in: IntegrationCredentialUpdate,
        ctx: ApiContext,
    ) -> IntegrationCredential:
        self._calls.append(("update", db, db_obj, obj_in, ctx))
        self._updated.append((db_obj, obj_in))
        return db_obj

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: IntegrationCredentialCreateEncrypted,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> IntegrationCredential:
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

    async def get_by_short_name(self, db: AsyncSession, short_name: str) -> Optional[Source]:
        self._calls.append(("get_by_short_name", db, short_name))
        return self._store.get(short_name)
