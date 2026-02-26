"""Fake source connection repository for testing."""

from typing import Any, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.source_connections.types import ScheduleInfo, SourceConnectionStats
from airweave.models.connection_init_session import ConnectionInitSession
from airweave.models.source_connection import SourceConnection


class FakeSourceConnectionRepository:
    """In-memory fake for SourceConnectionRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize with empty stores."""
        self._store: dict[UUID, SourceConnection] = {}
        self._by_sync_id: dict[UUID, SourceConnection] = {}
        self._schedule_info: dict[UUID, ScheduleInfo] = {}
        self._init_sessions: dict[UUID, ConnectionInitSession] = {}
        self._stats: List[SourceConnectionStats] = []
        self._sync_ids_by_collection: dict[str, List[UUID]] = {}
        self._calls: list[tuple[Any, ...]] = []

    def seed(self, id: UUID, obj: SourceConnection) -> None:
        """Seed a source connection by ID."""
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

    def seed_sync_ids_for_collection(
        self, readable_collection_id: str, sync_ids: List[UUID]
    ) -> None:
        """Seed sync IDs returned by get_sync_ids_for_collection."""
        self._sync_ids_by_collection[readable_collection_id] = list(sync_ids)

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

    async def get_by_init_session(
        self, db: AsyncSession, *, init_session_id: UUID, ctx: ApiContext
    ) -> Optional[SourceConnection]:
        """Get source connection by init session ID within org scope."""
        self._calls.append(("get_by_init_session", db, init_session_id, ctx))
        for sc in self._store.values():
            if getattr(sc, "connection_init_session_id", None) == init_session_id:
                return sc
        return None

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

    async def get_sync_ids_for_collection(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        readable_collection_id: str,
    ) -> List[UUID]:
        """Return seeded sync IDs for a collection."""
        self._calls.append(
            ("get_sync_ids_for_collection", db, organization_id, readable_collection_id)
        )
        return self._sync_ids_by_collection.get(readable_collection_id, [])

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: SourceConnection,
        obj_in: dict[str, Any],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> SourceConnection:
        """Update a source connection in the in-memory store."""
        self._calls.append(("update", db, db_obj, obj_in, ctx, uow))
        update_data = obj_in
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        self._store[db_obj.id] = db_obj
        return db_obj

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: dict[str, Any],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> SourceConnection:
        """Create a source connection in the in-memory store."""
        self._calls.append(("create", db, obj_in, ctx, uow))
        source_connection = SourceConnection(
            id=UUID(str(obj_in.get("id"))) if obj_in.get("id") else uuid4(),
            organization_id=ctx.organization.id,
            name=obj_in["name"],
            description=obj_in.get("description"),
            short_name=obj_in["short_name"],
            config_fields=obj_in.get("config_fields"),
            readable_auth_provider_id=obj_in.get("readable_auth_provider_id"),
            auth_provider_config=obj_in.get("auth_provider_config"),
            sync_id=obj_in.get("sync_id"),
            readable_collection_id=obj_in.get("readable_collection_id"),
            connection_id=obj_in.get("connection_id"),
            connection_init_session_id=obj_in.get("connection_init_session_id"),
            is_authenticated=obj_in.get("is_authenticated", False),
        )
        self._store[source_connection.id] = source_connection
        if source_connection.sync_id:
            self._by_sync_id[source_connection.sync_id] = source_connection
        return source_connection

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
