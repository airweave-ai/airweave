"""CRUD operations for the SourceRateLimit model."""

from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.context import BaseContext
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.source_rate_limit import SourceRateLimit
from airweave.schemas.source_rate_limit import SourceRateLimitCreate, SourceRateLimitUpdate


class CRUDSourceRateLimit(
    CRUDBaseOrganization[SourceRateLimit, SourceRateLimitCreate, SourceRateLimitUpdate]
):
    """CRUD operations for the SourceRateLimit model."""

    async def get_limit(
        self,
        db: AsyncSession,
        *,
        org_id: UUID,
        source_short_name: str,
    ) -> Optional[SourceRateLimit]:
        """Get rate limit configuration for a specific org+source.

        Returns ONE limit that applies to all users/connections of this source
        in the organization. Counts are tracked separately in Redis based on
        the source's rate_limit_level.

        Args:
            db: Database session
            org_id: Organization ID
            source_short_name: Source identifier (e.g., "google_drive", "notion")

        Returns:
            SourceRateLimit if configured, None otherwise
        """
        query = select(self.model).where(
            and_(
                self.model.organization_id == org_id,
                self.model.source_short_name == source_short_name,
            )
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: SourceRateLimitCreate,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> SourceRateLimit:
        """Create a new source rate limit configuration.

        Args:
            db: Database session
            obj_in: Rate limit creation data
            ctx: API context
            uow: Optional unit of work for transaction management

        Returns:
            Created SourceRateLimit
        """
        # Convert schema to dict and add organization_id
        rate_limit_data = obj_in.model_dump()
        rate_limit_data["organization_id"] = ctx.organization.id

        # Use parent create method which handles user tracking and timestamps
        return await super().create(
            db=db,
            obj_in=rate_limit_data,
            ctx=ctx,
            uow=uow,
            skip_validation=True,  # We add org_id manually above
        )


source_rate_limit = CRUDSourceRateLimit(SourceRateLimit)
