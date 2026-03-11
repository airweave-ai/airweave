"""In-memory fake for SourceRateLimitServiceProtocol."""

from types import SimpleNamespace
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.models.source_rate_limit import SourceRateLimit
from airweave.schemas.source_rate_limit import (
    SourceRateLimitResponse,
)


class FakeSourceRateLimitService:
    """In-memory fake service for testing endpoint DI."""

    def __init__(self) -> None:
        self._limits: dict[str, SourceRateLimitResponse] = {}
        self._configs: dict[tuple[UUID, str], SimpleNamespace] = {}
        self._calls: list[tuple] = []
        self._should_raise: Optional[Exception] = None

    def seed_response(self, response: SourceRateLimitResponse) -> None:
        """Seed a canned response for list_rate_limits."""
        self._limits[response.source_short_name] = response

    def set_error(self, error: Exception) -> None:
        self._should_raise = error

    async def list_rate_limits(
        self, db: AsyncSession, *, ctx: ApiContext
    ) -> list[SourceRateLimitResponse]:
        self._calls.append(("list_rate_limits", db, ctx))
        if self._should_raise:
            raise self._should_raise
        return list(self._limits.values())

    async def set_rate_limit(
        self,
        db: AsyncSession,
        *,
        source_short_name: str,
        limit: int,
        window_seconds: int,
        ctx: ApiContext,
    ) -> SourceRateLimit:
        self._calls.append(("set_rate_limit", db, source_short_name, limit, window_seconds, ctx))
        if self._should_raise:
            raise self._should_raise
        obj = SimpleNamespace(
            id=uuid4(),
            organization_id=ctx.organization.id,
            source_short_name=source_short_name,
            limit=limit,
            window_seconds=window_seconds,
        )
        self._configs[(ctx.organization.id, source_short_name)] = obj
        return obj  # type: ignore[return-value]

    async def delete_rate_limit(
        self, db: AsyncSession, *, source_short_name: str, ctx: ApiContext
    ) -> None:
        self._calls.append(("delete_rate_limit", db, source_short_name, ctx))
        if self._should_raise:
            raise self._should_raise
        self._configs.pop((ctx.organization.id, source_short_name), None)
