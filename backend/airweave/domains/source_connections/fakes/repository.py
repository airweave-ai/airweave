"""Fake source connection repository for testing."""

from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.source_connections.types import ScheduleInfo, SourceConnectionStats
from airweave.models.connection_init_session import ConnectionInitSession
from airweave.models.source_connection import SourceConnection
from airweave.schemas.source_connection import SourceConnectionUpdate


class FakeSourceConnectionRepository:
    """In-memory fake for SourceConnectionRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize with empty stores."""
        self._store: dict[UUID, SourceConnection] = {}
        self._by_sync_id: dict[UUID, SourceConnection] = {}
        self._schedule_info: dict[UUID, ScheduleInfo] = {}
        self._init_sessions: dict[UUID, ConnectionInitSession] = {}
        self._stats: List[SourceConnectionStats] = []
        self._calls: list[tuple[Any, ...]] = []

    def seed(self, id: UUID, obj: SourceConnection) -> None:
        self._store[id] = obj

    def seed_by_sync_id(self, sync_id: UUID, obj: SourceConnection) -> None:
        """Seed a source connection for a given sync_id."""
        self._by_sync_id[sync_id] = obj

    def seed_schedule_info(self, sc_id: UUID, info: ScheduleInfo) -> None:
        """Seed schedule info for a source connection."""
        self._schedule_info[sc_id] = info

    def seed_init_session(self, session_id: UUID, obj: ConnectionInitSession) -> None:
        """Seed an init session by session ID."""
        self._init_sessions[session_id] = obj

    def seed_stats(self, stats: List[SourceConnectionStats]) -> None:
        """Seed the stats list returned by get_multi_with_stats."""
        self._stats = list(stats)

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[SourceConnection]:
        """Return seeded source connection by ID."""
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def get_by_sync_id(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> Optional[SourceConnection]:
        """Return seeded source connection by sync ID."""
        self._calls.append(("get_by_sync_id", db, sync_id, ctx))
        return self._by_sync_id.get(sync_id)

    async def get_schedule_info(
        self, db: AsyncSession, source_connection: SourceConnection
    ) -> Optional[ScheduleInfo]:
        """Return seeded schedule info."""
        self._calls.append(("get_schedule_info", db, source_connection))
        return self._schedule_info.get(source_connection.id)

    async def get_init_session_with_redirect(
        self, db: AsyncSession, session_id: UUID, ctx: ApiContext
    ) -> Optional[ConnectionInitSession]:
        """Return seeded init session."""
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
        """Return seeded stats filtered by collection_id."""
        self._calls.append(("get_multi_with_stats", db, ctx, collection_id, skip, limit))
        stats = self._stats
        if collection_id is not None:
            stats = [s for s in stats if s.readable_collection_id == collection_id]
        return stats[skip : skip + limit]

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: SourceConnection,
        obj_in: Union[SourceConnectionUpdate, Dict[str, Any]],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> SourceConnection:
        """Update a source connection in the in-memory store."""
        self._calls.append(("update", db, db_obj, obj_in, ctx, uow))
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self._store[db_obj.id] = db_obj
        return db_obj

    async def remove(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
    ) -> Optional[SourceConnection]:
        """Remove a source connection from the in-memory store."""
        self._calls.append(("remove", db, id, ctx))
        return self._store.pop(id, None)
