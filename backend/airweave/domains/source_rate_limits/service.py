"""Domain service for source rate limit configuration management.

Handles list / set / delete of per-org rate limit configs stored in PostgreSQL.
Runtime enforcement (Redis sliding window) lives in adapters/source_rate_limiter/.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.shared_models import FeatureFlag
from airweave.domains.source_rate_limits.protocols import SourceRateLimitRepositoryProtocol
from airweave.domains.source_rate_limits.types import (
    PIPEDREAM_PROXY_LIMIT,
    PIPEDREAM_PROXY_WINDOW,
)
from airweave.models.source_rate_limit import SourceRateLimit
from airweave.schemas.source_rate_limit import (
    SourceRateLimitCreate,
    SourceRateLimitResponse,
    SourceRateLimitUpdate,
)


class SourceRateLimitService:
    """Manages source rate limit configurations (CRUD + listing)."""

    def __init__(self, repo: SourceRateLimitRepositoryProtocol) -> None:
        """Initialize with a rate limit repository."""
        self.repo = repo

    def _check_feature_flag(self, ctx: ApiContext) -> None:
        if not ctx.has_feature(FeatureFlag.SOURCE_RATE_LIMITING):
            raise HTTPException(
                status_code=403,
                detail="SOURCE_RATE_LIMITING feature not enabled for this organization",
            )

    async def list_rate_limits(
        self, db: AsyncSession, *, ctx: ApiContext
    ) -> list[SourceRateLimitResponse]:
        """List all sources merged with their configured rate limits.

        Fetches every source from the database, joins with the org's configured
        limits, sorts (supported sources first), and prepends the Pipedream proxy
        entry with its effective limit.
        """
        self._check_feature_flag(ctx)

        sources = await self.repo.get_all_sources(db)
        limits = await self.repo.get_all_limits_for_org(db, org_id=ctx.organization.id)
        limits_map = {lim.source_short_name: lim for lim in limits}

        results: list[SourceRateLimitResponse] = []
        for source in sources:
            if source.short_name == "pipedream_proxy":
                continue

            limit_obj = limits_map.get(source.short_name)
            results.append(
                SourceRateLimitResponse(
                    source_short_name=source.short_name,
                    rate_limit_level=source.rate_limit_level,
                    limit=limit_obj.limit if limit_obj else None,
                    window_seconds=limit_obj.window_seconds if limit_obj else None,
                    id=UUID(str(limit_obj.id)) if limit_obj else None,
                )
            )

        results.sort(key=lambda x: (x.rate_limit_level is None, x.source_short_name))

        pipedream_limit = limits_map.get("pipedream_proxy")
        results.insert(
            0,
            SourceRateLimitResponse(
                source_short_name="pipedream_proxy",
                rate_limit_level="org",
                limit=pipedream_limit.limit if pipedream_limit else PIPEDREAM_PROXY_LIMIT,
                window_seconds=(
                    pipedream_limit.window_seconds if pipedream_limit else PIPEDREAM_PROXY_WINDOW
                ),
                id=UUID(str(pipedream_limit.id)) if pipedream_limit else None,
            ),
        )

        return results

    async def set_rate_limit(
        self,
        db: AsyncSession,
        *,
        source_short_name: str,
        limit: int,
        window_seconds: int,
        ctx: ApiContext,
    ) -> SourceRateLimit:
        """Create or update a rate limit configuration for a source.

        Upserts: checks for an existing row, updates if found, creates otherwise.
        Returns the ORM model; FastAPI's response_model handles serialization.
        """
        self._check_feature_flag(ctx)

        existing = await self.repo.get_limit(
            db, org_id=ctx.organization.id, source_short_name=source_short_name
        )

        if existing:
            updated = await self.repo.update(
                db,
                db_obj=existing,
                obj_in=SourceRateLimitUpdate(limit=limit, window_seconds=window_seconds),
                ctx=ctx,
            )
            await db.commit()
            await db.refresh(updated)
            ctx.logger.info(
                f"Updated rate limit for {source_short_name}: {limit} req/{window_seconds}s"
            )
            return updated
        else:
            created = await self.repo.create(
                db,
                obj_in=SourceRateLimitCreate(
                    source_short_name=source_short_name,
                    limit=limit,
                    window_seconds=window_seconds,
                ),
                ctx=ctx,
            )
            await db.commit()
            await db.refresh(created)
            ctx.logger.info(
                f"Created rate limit for {source_short_name}: {limit} req/{window_seconds}s"
            )
            return created

    async def delete_rate_limit(
        self, db: AsyncSession, *, source_short_name: str, ctx: ApiContext
    ) -> None:
        """Remove rate limit configuration for a source.

        No-op if no limit is configured.
        """
        self._check_feature_flag(ctx)

        existing = await self.repo.get_limit(
            db, org_id=ctx.organization.id, source_short_name=source_short_name
        )

        if existing:
            await self.repo.remove(db, id=UUID(str(existing.id)), ctx=ctx)
            await db.commit()
            ctx.logger.info(f"Removed rate limit for {source_short_name}")
        else:
            ctx.logger.debug(f"No rate limit configured for {source_short_name}, nothing to delete")
