"""Billing repositories and protocols."""

from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.core.context import BaseContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models import OrganizationBilling
from airweave.models.billing_period import BillingPeriod
from airweave.models.processed_webhook_event import ProcessedWebhookEvent
from airweave.schemas.billing_period import BillingPeriodCreate, BillingPeriodStatus
from airweave.schemas.organization_billing import (
    OrganizationBillingCreate,
    OrganizationBillingUpdate,
)


class OrganizationBillingRepositoryProtocol(Protocol):
    """Read-only access to organization billing records."""

    async def get_by_org_id(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> Optional[OrganizationBilling]:
        """Get billing record by organization ID."""
        ...

    async def get_by_stripe_subscription_id(
        self, db: AsyncSession, *, stripe_subscription_id: str
    ) -> Optional[OrganizationBilling]:
        """Get billing record by Stripe subscription ID."""
        ...

    async def get_by_stripe_customer_id(
        self, db: AsyncSession, *, stripe_customer_id: str
    ) -> Optional[OrganizationBilling]:
        """Get billing record by Stripe customer ID."""
        ...

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: OrganizationBillingCreate,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> OrganizationBilling:
        """Create a billing record."""
        ...

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: OrganizationBilling,
        obj_in: OrganizationBillingUpdate,
        ctx: BaseContext,
    ) -> OrganizationBilling:
        """Update a billing record."""
        ...


class OrganizationBillingRepository(OrganizationBillingRepositoryProtocol):
    """Delegates to the crud.organization_billing singleton."""

    async def get_by_org_id(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> Optional[OrganizationBilling]:
        """Get billing record by organization ID."""
        return await crud.organization_billing.get_by_organization(
            db, organization_id=organization_id
        )

    async def get_by_stripe_subscription_id(
        self, db: AsyncSession, *, stripe_subscription_id: str
    ) -> Optional[OrganizationBilling]:
        """Get billing record by Stripe subscription ID."""
        return await crud.organization_billing.get_by_stripe_subscription(
            db, stripe_subscription_id=stripe_subscription_id
        )

    async def get_by_stripe_customer_id(
        self, db: AsyncSession, *, stripe_customer_id: str
    ) -> Optional[OrganizationBilling]:
        """Get billing record by Stripe customer ID."""
        return await crud.organization_billing.get_by_stripe_customer(
            db, stripe_customer_id=stripe_customer_id
        )

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: OrganizationBillingCreate,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> OrganizationBilling:
        """Create a billing record."""
        return await crud.organization_billing.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: OrganizationBilling,
        obj_in: OrganizationBillingUpdate,
        ctx: BaseContext,
    ) -> OrganizationBilling:
        """Update a billing record."""
        return await crud.organization_billing.update(db, db_obj=db_obj, obj_in=obj_in, ctx=ctx)


class BillingPeriodRepositoryProtocol(Protocol):
    """Access to billing period records."""

    async def get(self, db: AsyncSession, *, id: UUID, ctx: BaseContext) -> Optional[BillingPeriod]:
        """Get a billing period by ID."""
        ...

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: BillingPeriodCreate,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> BillingPeriod:
        """Create a billing period."""
        ...

    async def get_current_period(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> Optional[BillingPeriod]:
        """Get the current active billing period for an organization."""
        ...

    async def get_current_period_at(
        self, db: AsyncSession, *, organization_id: UUID, at: datetime
    ) -> Optional[BillingPeriod]:
        """Get the active billing period for an organization at a specific time."""
        ...

    async def get_previous_periods(
        self, db: AsyncSession, *, organization_id: UUID, limit: int = 6
    ) -> list[BillingPeriod]:
        """Get previous billing periods for an organization."""
        ...

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: BillingPeriod,
        obj_in: dict,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> BillingPeriod:
        """Update a billing period."""
        ...

    async def get_active_periods_in_range(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> list[BillingPeriod]:
        """Get all ACTIVE/GRACE periods that overlap with the given range."""
        ...


class BillingPeriodRepository(BillingPeriodRepositoryProtocol):
    """Delegates to the crud.billing_period singleton."""

    async def get(self, db: AsyncSession, *, id: UUID, ctx: BaseContext) -> Optional[BillingPeriod]:
        """Get a billing period by ID."""
        return await crud.billing_period.get(db, id=id, ctx=ctx)

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: BillingPeriodCreate,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> BillingPeriod:
        """Create a billing period."""
        return await crud.billing_period.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def get_current_period(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> Optional[BillingPeriod]:
        """Get the current active billing period for an organization."""
        return await crud.billing_period.get_current_period(db, organization_id=organization_id)

    async def get_current_period_at(
        self, db: AsyncSession, *, organization_id: UUID, at: datetime
    ) -> Optional[BillingPeriod]:
        """Get the active billing period for an organization at a specific time."""
        return await crud.billing_period.get_current_period_at(
            db, organization_id=organization_id, at=at
        )

    async def get_previous_periods(
        self, db: AsyncSession, *, organization_id: UUID, limit: int = 6
    ) -> list[BillingPeriod]:
        """Get previous billing periods for an organization."""
        return await crud.billing_period.get_previous_periods(
            db, organization_id=organization_id, limit=limit
        )

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: BillingPeriod,
        obj_in: dict,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> BillingPeriod:
        """Update a billing period."""
        return await crud.billing_period.update(db, db_obj=db_obj, obj_in=obj_in, ctx=ctx, uow=uow)

    async def get_active_periods_in_range(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> list[BillingPeriod]:
        """Get all ACTIVE/GRACE periods that overlap with the given range."""
        query = (
            select(BillingPeriod)
            .where(
                and_(
                    BillingPeriod.organization_id == organization_id,
                    BillingPeriod.period_start < range_end,
                    BillingPeriod.period_end > range_start,
                    BillingPeriod.status.in_(
                        [
                            BillingPeriodStatus.ACTIVE,
                            BillingPeriodStatus.GRACE,
                        ]
                    ),
                )
            )
            .order_by(BillingPeriod.period_start)
        )
        result = await db.execute(query)
        return list(result.scalars().all())


class WebhookEventRepositoryProtocol(Protocol):
    """Tracks processed Stripe webhook events for idempotency."""

    async def is_processed(self, db: AsyncSession, *, stripe_event_id: str) -> bool:
        """Check if a Stripe event has already been processed."""
        ...

    async def mark_processed(
        self, db: AsyncSession, *, stripe_event_id: str, event_type: str
    ) -> None:
        """Record that a Stripe event has been successfully processed."""
        ...


class WebhookEventRepository(WebhookEventRepositoryProtocol):
    """Manages processed webhook event records."""

    async def is_processed(self, db: AsyncSession, *, stripe_event_id: str) -> bool:
        """Check if a Stripe event has already been processed."""
        result = await db.execute(
            select(ProcessedWebhookEvent.id).where(
                ProcessedWebhookEvent.stripe_event_id == stripe_event_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def mark_processed(
        self, db: AsyncSession, *, stripe_event_id: str, event_type: str
    ) -> None:
        """Record that a Stripe event has been successfully processed."""
        db.add(
            ProcessedWebhookEvent(
                stripe_event_id=stripe_event_id,
                event_type=event_type,
            )
        )
        await db.flush()
