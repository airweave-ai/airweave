"""CRUD operations for BillingPeriod model."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.billing_period import BillingPeriod
from airweave.schemas.billing_period import (
    BillingPeriodCreate,
    BillingPeriodStatus,
    BillingPeriodUpdate,
)


class CRUDBillingPeriod(
    CRUDBaseOrganization[BillingPeriod, BillingPeriodCreate, BillingPeriodUpdate]
):
    """CRUD operations for BillingPeriod model."""

    async def get_current_period(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
    ) -> Optional[BillingPeriod]:
        """Get the current active billing period for an organization.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            Current active billing period or None
        """
        now = datetime.utcnow()
        query = select(self.model).where(
            and_(
                self.model.organization_id == organization_id,
                self.model.period_start <= now,
                self.model.period_end > now,
                self.model.status.in_(
                    [
                        BillingPeriodStatus.ACTIVE,
                        BillingPeriodStatus.TRIAL,
                        BillingPeriodStatus.GRACE,
                    ]
                ),
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_current_period_at(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        at: datetime,
    ) -> Optional[BillingPeriod]:
        """Get the active billing period for an organization at a specific time.

        This is useful for tests that simulate time (e.g., Stripe Test Clock),
        allowing callers to evaluate the current period at a provided timestamp
        rather than the wall-clock time.

        Args:
            db: Database session
            organization_id: Organization ID
            at: The timestamp to consider as "now"

        Returns:
            Billing period active at the provided time or None
        """
        query = select(self.model).where(
            and_(
                self.model.organization_id == organization_id,
                self.model.period_start <= at,
                self.model.period_end > at,
                self.model.status.in_(
                    [
                        BillingPeriodStatus.ACTIVE,
                        BillingPeriodStatus.TRIAL,
                        BillingPeriodStatus.GRACE,
                    ]
                ),
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_previous_periods(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        limit: int = 6,
    ) -> List[BillingPeriod]:
        """Get previous billing periods for an organization.

        Excludes the current active period.

        Args:
            db: Database session
            organization_id: Organization ID
            limit: Maximum number of periods to return

        Returns:
            List of previous billing periods ordered by period_end desc
        """
        now = datetime.utcnow()

        # Get all periods that have ended
        query = (
            select(self.model)
            .where(
                and_(
                    self.model.organization_id == organization_id,
                    self.model.period_end <= now,
                )
            )
            .order_by(desc(self.model.period_end))
            .limit(limit)
        )

        result = await db.execute(query)
        return list(result.scalars().all())


# Create instance
billing_period = CRUDBillingPeriod(BillingPeriod, track_user=False)
