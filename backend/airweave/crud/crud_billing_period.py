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

    async def get_by_organization(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        limit: int = 10,
    ) -> List[BillingPeriod]:
        """Get billing periods for an organization.

        Args:
            db: Database session
            organization_id: Organization ID
            limit: Maximum number of periods to return

        Returns:
            List of billing periods ordered by period_start desc
        """
        query = (
            select(self.model)
            .where(self.model.organization_id == organization_id)
            .order_by(desc(self.model.period_start))
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

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

    async def get_by_stripe_subscription(
        self,
        db: AsyncSession,
        *,
        stripe_subscription_id: str,
        status: Optional[BillingPeriodStatus] = None,
    ) -> Optional[BillingPeriod]:
        """Get billing period by Stripe subscription ID.

        Args:
            db: Database session
            stripe_subscription_id: Stripe subscription ID
            status: Optional status filter

        Returns:
            Billing period or None
        """
        query = select(self.model).where(
            self.model.stripe_subscription_id == stripe_subscription_id
        )
        if status:
            query = query.where(self.model.status == status)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_stripe_invoice(
        self,
        db: AsyncSession,
        *,
        stripe_invoice_id: str,
    ) -> Optional[BillingPeriod]:
        """Get billing period by Stripe invoice ID.

        Args:
            db: Database session
            stripe_invoice_id: Stripe invoice ID

        Returns:
            Billing period or None
        """
        query = select(self.model).where(self.model.stripe_invoice_id == stripe_invoice_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def complete_active_periods(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        end_time: datetime,
    ) -> int:
        """Complete all active periods for an organization.

        Args:
            db: Database session
            organization_id: Organization ID
            end_time: Time to set as period end

        Returns:
            Number of periods updated
        """
        # Get active periods
        query = select(self.model).where(
            and_(
                self.model.organization_id == organization_id,
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
        periods = list(result.scalars().all())

        # Update each period
        for period in periods:
            period.status = BillingPeriodStatus.COMPLETED
            period.period_end = end_time
            period.modified_at = datetime.utcnow()

        await db.flush()
        return len(periods)

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
