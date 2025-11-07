"""Source rate limits API endpoints."""

from typing import List

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.core.shared_models import FeatureFlag
from airweave.db.session import get_db
from airweave.models.source_rate_limit import SourceRateLimit

router = TrailingSlashRouter()


@router.get("/", response_model=List[schemas.SourceRateLimitResponse])
async def list_source_rate_limits(
    *,
    db: AsyncSession = Depends(get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.SourceRateLimitResponse]:
    """Get all sources with their rate limit configurations.

    Returns list of all sources (from source table) merged with configured
    limits (from source_rate_limits table), plus Pipedream proxy limit.

    Only accessible if SOURCE_RATE_LIMITING feature flag is enabled.
    """
    # Check feature flag
    if not ctx.has_feature(FeatureFlag.SOURCE_RATE_LIMITING):
        raise HTTPException(
            status_code=403, detail="SOURCE_RATE_LIMITING feature not enabled for this organization"
        )

    # Get all sources
    sources = await crud.source.get_all(db)

    # Get configured limits for this org
    stmt = select(SourceRateLimit).where(SourceRateLimit.organization_id == ctx.organization.id)
    result = await db.execute(stmt)
    limits = result.scalars().all()
    limits_map = {limit.source_short_name: limit for limit in limits}

    # Build response with all sources
    results = []
    for source in sources:
        # Skip the special pipedream_proxy entry (handled separately)
        if source.short_name == "pipedream_proxy":
            continue

        limit_obj = limits_map.get(source.short_name)
        results.append(
            schemas.SourceRateLimitResponse(
                source_short_name=source.short_name,
                rate_limit_level=source.rate_limit_level,
                limit=limit_obj.limit if limit_obj else None,
                window_seconds=limit_obj.window_seconds if limit_obj else None,
                id=limit_obj.id if limit_obj else None,
            )
        )

    # Sort: sources with rate_limit_level first, then "Not supported" sources
    results.sort(key=lambda x: (x.rate_limit_level is None, x.source_short_name))

    # Add Pipedream proxy as first item (special source name)
    # Always show the effective limit (custom or default) so UI reflects reality
    pipedream_limit = limits_map.get("pipedream_proxy")
    from airweave.core.source_rate_limiter_service import SourceRateLimiter

    results.insert(
        0,
        schemas.SourceRateLimitResponse(
            source_short_name="pipedream_proxy",
            rate_limit_level="org",  # Always org-wide
            limit=(
                pipedream_limit.limit
                if pipedream_limit
                else SourceRateLimiter.PIPEDREAM_PROXY_LIMIT
            ),  # Show default if not configured
            window_seconds=(
                pipedream_limit.window_seconds
                if pipedream_limit
                else SourceRateLimiter.PIPEDREAM_PROXY_WINDOW
            ),  # Show default if not configured
            id=pipedream_limit.id if pipedream_limit else None,
        ),
    )

    return results


@router.put("/{source_short_name}", response_model=schemas.SourceRateLimit)
async def set_source_rate_limit(
    *,
    source_short_name: str,
    request: schemas.SourceRateLimitUpdateRequest,
    db: AsyncSession = Depends(get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SourceRateLimit:
    """Set or update rate limit for a source or Pipedream proxy.

    Creates new limit if doesn't exist, updates if it does.
    Works for both regular sources and the special 'pipedream_proxy' source.
    """
    # Check feature flag
    if not ctx.has_feature(FeatureFlag.SOURCE_RATE_LIMITING):
        raise HTTPException(status_code=403, detail="Feature not enabled")

    from airweave.core.source_rate_limit_helpers import set_source_rate_limit

    result = await set_source_rate_limit(
        db,
        org_id=ctx.organization.id,
        source_short_name=source_short_name,
        limit=request.limit,
        window_seconds=request.window_seconds,
        ctx=ctx,
    )

    return result


@router.delete("/{source_short_name}", status_code=204)
async def delete_source_rate_limit(
    *,
    source_short_name: str,
    db: AsyncSession = Depends(get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> None:
    """Remove rate limit configuration for a source.

    Reverts to no rate limiting for this source (or default Pipedream limit).
    """
    # Check feature flag
    if not ctx.has_feature(FeatureFlag.SOURCE_RATE_LIMITING):
        raise HTTPException(status_code=403, detail="Feature not enabled")

    # Get existing limit
    existing = await crud.source_rate_limit.get_limit(
        db, org_id=ctx.organization.id, source_short_name=source_short_name
    )

    if existing:
        await crud.source_rate_limit.remove(db, id=existing.id, ctx=ctx)
        await db.commit()
        ctx.logger.info(f"Removed rate limit for {source_short_name}")
    else:
        ctx.logger.debug(f"No rate limit configured for {source_short_name}, nothing to delete")
