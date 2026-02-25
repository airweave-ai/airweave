"""Helper functions for managing source rate limits."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.context import BaseContext


async def set_source_rate_limit(
    db: AsyncSession,
    org_id: UUID,
    source_short_name: str,
    limit: int,
    window_seconds: int = 60,
    ctx: Optional[BaseContext] = None,
) -> schemas.SourceRateLimit:
    """Set or update rate limit for a source in an organization.

    Sets ONE limit that applies to ALL users/connections of this source.
    Counts are tracked separately in Redis based on the source's rate_limit_level:
    - Connection-level (Notion): Redis tracks per user connection
    - Org-level (Google Drive): Redis tracks for entire org

    Args:
        db: Database session
        org_id: Organization ID
        source_short_name: Source identifier (e.g., "google_drive", "notion")
        limit: Maximum requests per window
        window_seconds: Time window in seconds (default: 60 = 1 minute)
        ctx: Optional context (will create minimal one if not provided)

    Returns:
        Created or updated SourceRateLimit

    Examples:
        # Google Drive: 800 req/min (80% of 1000 req/min quota)
        # All users share this limit
        await set_source_rate_limit(
            db, org_id, "google_drive", limit=800, window_seconds=60
        )

        # Notion: 2 req/sec (conservative from 3 req/sec)
        # Each user's connection tracks separately in Redis
        await set_source_rate_limit(
            db, org_id, "notion", limit=2, window_seconds=1
        )
    """
    if not ctx:
        org = await crud.organization.get(db, id=org_id, skip_access_validation=True)
        org_schema = schemas.Organization.model_validate(org)
        ctx = BaseContext(organization=org_schema)

    # Check if limit already exists
    existing = await crud.source_rate_limit.get_limit(
        db, org_id=org_id, source_short_name=source_short_name
    )

    if existing:
        # Update existing limit
        updated = await crud.source_rate_limit.update(
            db,
            db_obj=existing,
            obj_in=schemas.SourceRateLimitUpdate(limit=limit, window_seconds=window_seconds),
            ctx=ctx,
        )
        await db.commit()
        # Refresh to avoid MissingGreenlet errors when serializing
        await db.refresh(updated)
        ctx.logger.info(
            f"Updated rate limit for {source_short_name} in org {org_id}: "
            f"{limit} requests per {window_seconds}s"
        )
        return updated
    else:
        # Create new limit
        created = await crud.source_rate_limit.create(
            db,
            obj_in=schemas.SourceRateLimitCreate(
                source_short_name=source_short_name,
                limit=limit,
                window_seconds=window_seconds,
            ),
            ctx=ctx,
        )
        await db.commit()
        # Refresh to avoid MissingGreenlet errors when serializing
        await db.refresh(created)
        ctx.logger.info(
            f"Created rate limit for {source_short_name} in org {org_id}: "
            f"{limit} requests per {window_seconds}s"
        )
        return created
