"""Fake repositories for OAuth domain testing."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection import Connection
from airweave.models.connection_init_session import ConnectionInitSession
from airweave.models.integration_credential import IntegrationCredential
from airweave.models.redirect_session import RedirectSession
from airweave.models.source import Source
from airweave.schemas.connection import ConnectionCreate
from airweave.schemas.integration_credential import (
    IntegrationCredentialCreateEncrypted,
    IntegrationCredentialUpdate,
)


class FakeOAuthConnectionRepository:
    """In-memory fake for OAuthConnectionRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, Connection] = {}
        self._calls: list[tuple[Any, ...]] = []
        self._created: list[ConnectionCreate] = []

    def seed(self, id: UUID, obj: Connection) -> None:
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
        self._store: dict[UUID, IntegrationCredential] = {}
        self._calls: list[tuple[Any, ...]] = []
        self._created: list[IntegrationCredentialCreateEncrypted] = []
        self._updated: list[tuple[Any, ...]] = []

    def seed(self, id: UUID, obj: IntegrationCredential) -> None:
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
        self._store: dict[str, Source] = {}
        self._calls: list[tuple[Any, ...]] = []

    def seed(self, short_name: str, obj: Source) -> None:
        self._store[short_name] = obj

    async def get_by_short_name(self, db: AsyncSession, short_name: str) -> Optional[Source]:
        self._calls.append(("get_by_short_name", db, short_name))
        return self._store.get(short_name)


class FakeOAuthRedirectSessionRepository:
    """In-memory fake for OAuthRedirectSessionRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[str, RedirectSession] = {}
        self._calls: list[tuple[Any, ...]] = []
        self._counter: int = 0

    def seed(self, code: str, obj: RedirectSession) -> None:
        self._store[code] = obj

    async def get_by_code(self, db: AsyncSession, code: str) -> Optional[RedirectSession]:
        self._calls.append(("get_by_code", db, code))
        return self._store.get(code)

    async def generate_unique_code(self, db: AsyncSession, *, length: int) -> str:
        self._counter += 1
        return f"fakecode{self._counter:0{length}d}"[:length]

    async def create(
        self,
        db: AsyncSession,
        *,
        code: str,
        final_url: str,
        expires_at: datetime,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Any:
        self._calls.append(("create", code, final_url))

        class _FakeRedirect:
            id = uuid4()

        obj = _FakeRedirect()
        self._store[code] = obj
        return obj


class FakeOAuthInitSessionRepository:
    """In-memory fake for OAuthInitSessionRepositoryProtocol."""

    def __init__(self) -> None:
        self._store_by_state: dict[str, ConnectionInitSession] = {}
        self._store_by_token: dict[str, ConnectionInitSession] = {}
        self._calls: list[tuple[Any, ...]] = []

    def seed_by_state(self, state: str, obj: ConnectionInitSession) -> None:
        self._store_by_state[state] = obj

    def seed_by_oauth_token(self, oauth_token: str, obj: ConnectionInitSession) -> None:
        self._store_by_token[oauth_token] = obj

    async def get_by_state_no_auth(
        self, db: AsyncSession, *, state: str
    ) -> Optional[ConnectionInitSession]:
        self._calls.append(("get_by_state_no_auth", state))
        return self._store_by_state.get(state)

    async def get_by_oauth_token_no_auth(
        self, db: AsyncSession, *, oauth_token: str
    ) -> Optional[ConnectionInitSession]:
        self._calls.append(("get_by_oauth_token_no_auth", oauth_token))
        return self._store_by_token.get(oauth_token)

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: Dict[str, Any],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> ConnectionInitSession:
        self._calls.append(("create", obj_in))
        return obj_in

    async def mark_completed(
        self,
        db: AsyncSession,
        *,
        session_id: UUID,
        final_connection_id: Optional[UUID],
        ctx: ApiContext,
    ) -> None:
        self._calls.append(("mark_completed", session_id, final_connection_id))
