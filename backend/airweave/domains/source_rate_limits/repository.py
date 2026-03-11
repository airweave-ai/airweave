"""Repository for source rate limit configurations.

Thin wrapper around crud.source_rate_limit and crud.source singletons.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.models.source import Source
from airweave.models.source_rate_limit import SourceRateLimit
from airweave.schemas.source_rate_limit import SourceRateLimitCreate, SourceRateLimitUpdate


class SourceRateLimitRepository:
    """Delegates to crud.source_rate_limit and crud.source singletons."""

    async def get_limit(
        self, db: AsyncSession, *, org_id: UUID, source_short_name: str
    ) -> Optional[SourceRateLimit]:
        """Get rate limit config for an org+source pair."""
        return await crud.source_rate_limit.get_limit(
            db, org_id=org_id, source_short_name=source_short_name
        )

    async def get_all_limits_for_org(
        self, db: AsyncSession, *, org_id: UUID
    ) -> list[SourceRateLimit]:
        """Get all configured rate limits for an organization."""
        stmt = select(SourceRateLimit).where(SourceRateLimit.organization_id == org_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self, db: AsyncSession, *, obj_in: SourceRateLimitCreate, ctx: ApiContext
    ) -> SourceRateLimit:
        """Create a new rate limit configuration."""
        return await crud.source_rate_limit.create(db, obj_in=obj_in, ctx=ctx)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: SourceRateLimit,
        obj_in: SourceRateLimitUpdate,
        ctx: ApiContext,
    ) -> SourceRateLimit:
        """Update an existing rate limit configuration."""
        return await crud.source_rate_limit.update(db, db_obj=db_obj, obj_in=obj_in, ctx=ctx)

    async def remove(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> None:
        """Delete a rate limit configuration by ID."""
        await crud.source_rate_limit.remove(db, id=id, ctx=ctx)

    async def get_all_sources(self, db: AsyncSession) -> list[Source]:
        """Get all sources (public table, no org scoping)."""
        return await crud.source.get_all(db)
