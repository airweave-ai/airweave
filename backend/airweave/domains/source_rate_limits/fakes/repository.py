"""In-memory fake for SourceRateLimitRepositoryProtocol."""

from types import SimpleNamespace
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.models.source import Source
from airweave.models.source_rate_limit import SourceRateLimit
from airweave.schemas.source_rate_limit import SourceRateLimitCreate, SourceRateLimitUpdate


class FakeSourceRateLimitRepository:
    """In-memory fake repository for source rate limit tests."""

    def __init__(self) -> None:
        self._store: dict[tuple[UUID, str], SimpleNamespace] = {}
        self._sources: list[SimpleNamespace] = []
        self._calls: list[tuple] = []
        self._should_raise: Optional[Exception] = None

    def seed_limit(
        self,
        org_id: UUID,
        source_short_name: str,
        limit: int,
        window_seconds: int = 60,
        id: Optional[UUID] = None,
    ) -> SimpleNamespace:
        """Add a rate limit to the in-memory store."""
        obj = SimpleNamespace(
            id=id or uuid4(),
            organization_id=org_id,
            source_short_name=source_short_name,
            limit=limit,
            window_seconds=window_seconds,
        )
        self._store[(org_id, source_short_name)] = obj
        return obj

    def seed_source(
        self,
        short_name: str,
        rate_limit_level: Optional[str] = None,
    ) -> SimpleNamespace:
        """Add a source to the in-memory store."""
        obj = SimpleNamespace(short_name=short_name, rate_limit_level=rate_limit_level)
        self._sources.append(obj)
        return obj

    def set_error(self, error: Exception) -> None:
        self._should_raise = error

    async def get_limit(
        self, db: AsyncSession, *, org_id: UUID, source_short_name: str
    ) -> Optional[SourceRateLimit]:
        self._calls.append(("get_limit", db, org_id, source_short_name))
        if self._should_raise:
            raise self._should_raise
        return self._store.get((org_id, source_short_name))  # type: ignore[return-value]

    async def get_all_limits_for_org(
        self, db: AsyncSession, *, org_id: UUID
    ) -> list[SourceRateLimit]:
        self._calls.append(("get_all_limits_for_org", db, org_id))
        if self._should_raise:
            raise self._should_raise
        return [v for (oid, _), v in self._store.items() if oid == org_id]  # type: ignore[misc]

    async def create(
        self, db: AsyncSession, *, obj_in: SourceRateLimitCreate, ctx: ApiContext
    ) -> SourceRateLimit:
        self._calls.append(("create", db, obj_in, ctx))
        if self._should_raise:
            raise self._should_raise
        obj = SimpleNamespace(
            id=uuid4(),
            organization_id=ctx.organization.id,
            source_short_name=obj_in.source_short_name,
            limit=obj_in.limit,
            window_seconds=obj_in.window_seconds,
        )
        self._store[(ctx.organization.id, obj_in.source_short_name)] = obj
        return obj  # type: ignore[return-value]

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: SourceRateLimit,
        obj_in: SourceRateLimitUpdate,
        ctx: ApiContext,
    ) -> SourceRateLimit:
        self._calls.append(("update", db, db_obj, obj_in, ctx))
        if self._should_raise:
            raise self._should_raise
        if obj_in.limit is not None:
            db_obj.limit = obj_in.limit  # type: ignore[attr-defined]
        if obj_in.window_seconds is not None:
            db_obj.window_seconds = obj_in.window_seconds  # type: ignore[attr-defined]
        return db_obj

    async def remove(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> None:
        self._calls.append(("remove", db, id, ctx))
        if self._should_raise:
            raise self._should_raise
        to_delete = None
        for key, val in self._store.items():
            if val.id == id:
                to_delete = key
                break
        if to_delete:
            del self._store[to_delete]

    async def get_all_sources(self, db: AsyncSession) -> list[Source]:
        self._calls.append(("get_all_sources", db))
        if self._should_raise:
            raise self._should_raise
        return self._sources  # type: ignore[return-value]
