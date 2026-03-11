"""Protocols for source rate limit configuration domain."""

from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.models.source import Source
from airweave.models.source_rate_limit import SourceRateLimit
from airweave.schemas.source_rate_limit import (
    SourceRateLimitCreate,
    SourceRateLimitResponse,
    SourceRateLimitUpdate,
)


class SourceRateLimitRepositoryProtocol(Protocol):
    """Data access for source rate limit configurations."""

    async def get_limit(
        self, db: AsyncSession, *, org_id: UUID, source_short_name: str
    ) -> Optional[SourceRateLimit]:
        """Get rate limit config for an org+source pair."""
        ...

    async def get_all_limits_for_org(
        self, db: AsyncSession, *, org_id: UUID
    ) -> list[SourceRateLimit]:
        """Get all configured rate limits for an organization."""
        ...

    async def create(
        self, db: AsyncSession, *, obj_in: SourceRateLimitCreate, ctx: ApiContext
    ) -> SourceRateLimit:
        """Create a new rate limit configuration."""
        ...

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: SourceRateLimit,
        obj_in: SourceRateLimitUpdate,
        ctx: ApiContext,
    ) -> SourceRateLimit:
        """Update an existing rate limit configuration."""
        ...

    async def remove(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> None:
        """Delete a rate limit configuration by ID."""
        ...

    async def get_all_sources(self, db: AsyncSession) -> list[Source]:
        """Get all sources (for building the merged rate-limit list)."""
        ...


class SourceRateLimitServiceProtocol(Protocol):
    """Business logic for managing source rate limit configurations."""

    async def list_rate_limits(
        self, db: AsyncSession, *, ctx: ApiContext
    ) -> list[SourceRateLimitResponse]:
        """List all sources merged with their configured rate limits."""
        ...

    async def set_rate_limit(
        self,
        db: AsyncSession,
        *,
        source_short_name: str,
        limit: int,
        window_seconds: int,
        ctx: ApiContext,
    ) -> SourceRateLimit:
        """Create or update a rate limit configuration for a source."""
        ...

    async def delete_rate_limit(
        self, db: AsyncSession, *, source_short_name: str, ctx: ApiContext
    ) -> None:
        """Remove rate limit configuration for a source."""
        ...
