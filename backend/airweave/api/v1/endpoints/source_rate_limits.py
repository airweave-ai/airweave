"""Source rate limits API endpoints."""

from typing import List

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.inject import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.db.session import get_db
from airweave.domains.source_rate_limits.protocols import SourceRateLimitServiceProtocol
from airweave.models.source_rate_limit import SourceRateLimit

router = TrailingSlashRouter()


@router.get("/", response_model=List[schemas.SourceRateLimitResponse])
async def list_source_rate_limits(
    *,
    db: AsyncSession = Depends(get_db),
    ctx: ApiContext = Depends(deps.get_context),
    service: SourceRateLimitServiceProtocol = Inject(SourceRateLimitServiceProtocol),
) -> List[schemas.SourceRateLimitResponse]:
    """Get all sources with their rate limit configurations.

    Returns list of all sources (from source table) merged with configured
    limits (from source_rate_limits table), plus Pipedream proxy limit.

    Only accessible if SOURCE_RATE_LIMITING feature flag is enabled.
    """
    return await service.list_rate_limits(db, ctx=ctx)


@router.put("/{source_short_name}", response_model=schemas.SourceRateLimit)
async def set_source_rate_limit(
    *,
    source_short_name: str,
    request: schemas.SourceRateLimitUpdateRequest,
    db: AsyncSession = Depends(get_db),
    ctx: ApiContext = Depends(deps.get_context),
    service: SourceRateLimitServiceProtocol = Inject(SourceRateLimitServiceProtocol),
) -> SourceRateLimit:
    """Set or update rate limit for a source or Pipedream proxy.

    Creates new limit if doesn't exist, updates if it does.
    Works for both regular sources and the special 'pipedream_proxy' source.
    """
    return await service.set_rate_limit(
        db,
        source_short_name=source_short_name,
        limit=request.limit,
        window_seconds=request.window_seconds,
        ctx=ctx,
    )


@router.delete("/{source_short_name}", status_code=204)
async def delete_source_rate_limit(
    *,
    source_short_name: str,
    db: AsyncSession = Depends(get_db),
    ctx: ApiContext = Depends(deps.get_context),
    service: SourceRateLimitServiceProtocol = Inject(SourceRateLimitServiceProtocol),
) -> None:
    """Remove rate limit configuration for a source.

    Reverts to no rate limiting for this source (or default Pipedream limit).
    """
    await service.delete_rate_limit(db, source_short_name=source_short_name, ctx=ctx)
