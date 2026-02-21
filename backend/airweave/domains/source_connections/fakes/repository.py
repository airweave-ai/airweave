"""Fake source connection repository for testing."""

import secrets
import string
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.source_connections.types import ScheduleInfo, SourceConnectionStats
from airweave.models.connection_init_session import ConnectionInitSession
from airweave.models.redirect_session import RedirectSession
from airweave.models.source_connection import SourceConnection


class FakeSourceConnectionRepository:
    """In-memory fake for SourceConnectionRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, SourceConnection] = {}
        self._by_sync_id: dict[UUID, SourceConnection] = {}
        self._schedule_info: dict[UUID, ScheduleInfo] = {}
        self._init_sessions: dict[UUID, ConnectionInitSession] = {}
        self._redirect_sessions: dict[str, RedirectSession] = {}
        self._stats: List[SourceConnectionStats] = []
        self._calls: list[tuple[Any, ...]] = []

    def seed(self, id: UUID, obj: SourceConnection) -> None:
        self._store[id] = obj

    def seed_by_sync_id(self, sync_id: UUID, obj: SourceConnection) -> None:
        self._by_sync_id[sync_id] = obj

    def seed_schedule_info(self, sc_id: UUID, info: ScheduleInfo) -> None:
        self._schedule_info[sc_id] = info

    def seed_init_session(self, session_id: UUID, obj: ConnectionInitSession) -> None:
        self._init_sessions[session_id] = obj

    def seed_stats(self, stats: List[SourceConnectionStats]) -> None:
        self._stats = list(stats)

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[SourceConnection]:
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def get_by_sync_id(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> Optional[SourceConnection]:
        self._calls.append(("get_by_sync_id", db, sync_id, ctx))
        return self._by_sync_id.get(sync_id)

    async def get_schedule_info(
        self, db: AsyncSession, source_connection: SourceConnection
    ) -> Optional[ScheduleInfo]:
        self._calls.append(("get_schedule_info", db, source_connection))
        return self._schedule_info.get(source_connection.id)

    async def get_init_session_with_redirect(
        self, db: AsyncSession, session_id: UUID, ctx: ApiContext
    ) -> Optional[ConnectionInitSession]:
        self._calls.append(("get_init_session_with_redirect", db, session_id, ctx))
        return self._init_sessions.get(session_id)

    async def get_multi_with_stats(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnectionStats]:
        self._calls.append(("get_multi_with_stats", db, ctx, collection_id, skip, limit))
        stats = self._stats
        if collection_id is not None:
            stats = [s for s in stats if s.readable_collection_id == collection_id]
        return stats[skip : skip + limit]

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: Union[Dict[str, Any], Any],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> SourceConnection:
        self._calls.append(("create", obj_in))
        data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump()
        now = datetime.now(timezone.utc)
        obj = SourceConnection(**data)
        if not obj.id:
            obj.id = uuid4()
        if not obj.organization_id and ctx:
            obj.organization_id = ctx.organization.id
        if not obj.created_at:
            obj.created_at = now
        if not obj.modified_at:
            obj.modified_at = now
        self._store[obj.id] = obj
        if getattr(obj, "sync_id", None):
            self._by_sync_id[obj.sync_id] = obj
        return obj

    async def create_init_session(
        self,
        db: AsyncSession,
        *,
        obj_in: Dict[str, Any],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> ConnectionInitSession:
        self._calls.append(("create_init_session", obj_in))
        obj = ConnectionInitSession(**obj_in)
        if not obj.id:
            obj.id = uuid4()
        self._init_sessions[obj.id] = obj
        return obj

    async def create_redirect_session(
        self,
        db: AsyncSession,
        *,
        code: str,
        final_url: str,
        expires_at: datetime,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> RedirectSession:
        self._calls.append(("create_redirect_session", code, final_url))
        obj = RedirectSession(code=code, final_url=final_url, expires_at=expires_at)
        obj.id = uuid4()
        self._redirect_sessions[code] = obj
        return obj

    async def generate_unique_redirect_code(self, db: AsyncSession, *, length: int = 8) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))
