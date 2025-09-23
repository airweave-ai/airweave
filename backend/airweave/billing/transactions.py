"""Transactions for billing operations.

This module handles all database interactions for billing,
providing a clean interface between the service layer and CRUD operations.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.exceptions import InvalidStateError, NotFoundException
from airweave.db.unit_of_work import UnitOfWork
from airweave.models import OrganizationBilling
from airweave.schemas.billing_period import (
    BillingPeriodCreate,
    BillingPeriodStatus,
    BillingTransition,
)
from airweave.schemas.organization_billing import (
    BillingPlan,
    BillingStatus,
    OrganizationBillingCreate,
    OrganizationBillingUpdate,
)
from airweave.schemas.usage import UsageCreate


class BillingTransactions:
    """Static singleton class for all billing-related database operations."""

    async def get_billing_record(
        self,
        db: AsyncSession,
        organization_id: UUID,
    ) -> Optional[schemas.OrganizationBilling]:
        """Get billing record for an organization."""
        billing = await crud.organization_billing.get_by_organization(
            db, organization_id=organization_id
        )
        return (
            schemas.OrganizationBilling.model_validate(billing, from_attributes=True)
            if billing
            else None
        )

    async def get_billing_by_customer(
        self,
        db: AsyncSession,
        stripe_customer_id: str,
    ) -> Optional[schemas.OrganizationBilling]:
        """Get billing record by Stripe customer ID."""
        billing = await crud.organization_billing.get_by_stripe_customer(
            db, stripe_customer_id=stripe_customer_id
        )
        return (
            schemas.OrganizationBilling.model_validate(billing, from_attributes=True)
            if billing
            else None
        )

    async def get_billing_by_subscription(
        self,
        db: AsyncSession,
        stripe_subscription_id: str,
    ) -> Optional[OrganizationBilling]:
        """Get billing record by Stripe subscription ID.

        Returns the model directly for webhook processing.
        """
        return await crud.organization_billing.get_by_stripe_subscription(
            db, stripe_subscription_id=stripe_subscription_id
        )

    async def create_billing_record(
        self,
        db: AsyncSession,
        organization_id: UUID,
        stripe_customer_id: str,
        billing_email: str,
        plan: BillingPlan,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.OrganizationBilling:
        """Create initial billing record for an organization."""
        # Check if already exists
        existing = await crud.organization_billing.get_by_organization(
            db, organization_id=organization_id
        )
        if existing:
            raise InvalidStateError("Billing record already exists for organization")

        billing_create = OrganizationBillingCreate(
            organization_id=organization_id,
            stripe_customer_id=stripe_customer_id,
            billing_plan=plan,
            billing_status=BillingStatus.ACTIVE,
            billing_email=billing_email,
        )

        billing = await crud.organization_billing.create(
            db,
            obj_in=billing_create,
            ctx=ctx,
            uow=uow,
        )

        # Flush to ensure database fields are populated
        await db.flush()

        # Refresh the object to get database-generated fields
        await db.refresh(billing)

        return schemas.OrganizationBilling.model_validate(billing, from_attributes=True)

    async def update_billing_record(
        self,
        db: AsyncSession,
        billing_id: UUID,
        updates: OrganizationBillingUpdate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.OrganizationBilling:
        """Update a billing record."""
        billing_model = await crud.organization_billing.get(db, id=billing_id, ctx=ctx)
        if not billing_model:
            raise NotFoundException(f"Billing record {billing_id} not found")

        updated = await crud.organization_billing.update(
            db,
            db_obj=billing_model,
            obj_in=updates,
            ctx=ctx,
            uow=uow,
        )

        return schemas.OrganizationBilling.model_validate(updated, from_attributes=True)

    async def update_billing_by_org(
        self,
        db: AsyncSession,
        organization_id: UUID,
        updates: OrganizationBillingUpdate,
        ctx: ApiContext,
    ) -> schemas.OrganizationBilling:
        """Update billing record by organization ID."""
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=organization_id
        )
        if not billing_model:
            raise NotFoundException(f"No billing record for organization {organization_id}")

        updated = await crud.organization_billing.update(
            db,
            db_obj=billing_model,
            obj_in=updates,
            ctx=ctx,
        )

        return schemas.OrganizationBilling.model_validate(updated, from_attributes=True)

    # ------------------------------ Yearly Prepay ------------------------------ #

    async def record_yearly_prepay_started(
        self,
        db: AsyncSession,
        organization_id: UUID,
        *,
        amount_cents: int,
        started_at: datetime,
        expected_expires_at: datetime,
        coupon_id: Optional[str],
        payment_intent_id: Optional[str],
        ctx: ApiContext,
    ) -> schemas.OrganizationBilling:
        """Mark yearly prepay as started/pending in the billing record."""
        # Do not mark has_yearly_prepay yet; only after successful payment/finalization
        updates = OrganizationBillingUpdate(
            yearly_prepay_amount_cents=amount_cents,
            yearly_prepay_started_at=started_at,
            yearly_prepay_expires_at=expected_expires_at,
            yearly_prepay_coupon_id=coupon_id,
            yearly_prepay_payment_intent_id=payment_intent_id,
        )
        return await self.update_billing_by_org(db, organization_id, updates, ctx)

    async def record_yearly_prepay_finalized(
        self,
        db: AsyncSession,
        organization_id: UUID,
        *,
        coupon_id: str,
        payment_intent_id: str,
        expires_at: datetime,
        ctx: ApiContext,
    ) -> schemas.OrganizationBilling:
        """Finalize yearly prepay after successful payment and subscription setup."""
        updates = OrganizationBillingUpdate(
            has_yearly_prepay=True,
            yearly_prepay_coupon_id=coupon_id,
            yearly_prepay_payment_intent_id=payment_intent_id,
            yearly_prepay_expires_at=expires_at,
        )
        return await self.update_billing_by_org(db, organization_id, updates, ctx)

    async def create_billing_period(
        self,
        db: AsyncSession,
        organization_id: UUID,
        period_start: datetime,
        period_end: datetime,
        plan: BillingPlan,
        transition: BillingTransition,
        ctx: ApiContext,
        stripe_subscription_id: Optional[str] = None,
        previous_period_id: Optional[UUID] = None,
        status: BillingPeriodStatus = BillingPeriodStatus.ACTIVE,
    ) -> schemas.BillingPeriod:
        """Create a new billing period with usage record."""
        # Complete any active periods that would overlap with the new period
        # In test clock scenarios, we need to find periods that would be active
        # just before the new period starts
        from datetime import timedelta

        # Check for a period active just before the new period starts
        check_time = period_start - timedelta(seconds=1)
        current = await crud.billing_period.get_current_period_at(
            db, organization_id=organization_id, at=check_time
        )

        if current and current.status in [BillingPeriodStatus.ACTIVE, BillingPeriodStatus.GRACE]:
            db_period = await crud.billing_period.get(db, id=current.id, ctx=ctx)
            if db_period:
                # Only update if the new period actually starts after the current one
                if db_period.period_start < period_start:
                    await crud.billing_period.update(
                        db,
                        db_obj=db_period,
                        obj_in={
                            "status": BillingPeriodStatus.COMPLETED,
                            "period_end": period_start,  # Ensure continuity
                        },
                        ctx=ctx,
                    )
                    if not previous_period_id:
                        previous_period_id = db_period.id

        # Create new period
        period_create = BillingPeriodCreate(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
            plan=plan,
            status=status,
            created_from=transition,
            stripe_subscription_id=stripe_subscription_id,
            previous_period_id=previous_period_id,
        )

        period_id = None

        async with UnitOfWork(db) as uow:
            period = await crud.billing_period.create(db, obj_in=period_create, ctx=ctx, uow=uow)
            await db.flush()
            period_id = period.id

            # Create usage record
            usage_create = UsageCreate(
                organization_id=organization_id,
                billing_period_id=period.id,
            )
            await crud.usage.create(db, obj_in=usage_create, ctx=ctx, uow=uow)
            await uow.commit()

        # After commit, fetch the period fresh to avoid greenlet issues
        created_period = await crud.billing_period.get(db, id=period_id, ctx=ctx)
        if not created_period:
            raise InvalidStateError("Failed to create billing period")

        return schemas.BillingPeriod.model_validate(created_period, from_attributes=True)

    async def get_current_billing_period(
        self,
        db: AsyncSession,
        organization_id: UUID,
        at: Optional[datetime] = None,
    ) -> Optional[schemas.BillingPeriod]:
        """Get the current active billing period."""
        if at:
            period = await crud.billing_period.get_current_period_at(
                db, organization_id=organization_id, at=at
            )
        else:
            period = await crud.billing_period.get_current_period(
                db, organization_id=organization_id
            )

        return (
            schemas.BillingPeriod.model_validate(period, from_attributes=True) if period else None
        )

    async def get_previous_periods(
        self,
        db: AsyncSession,
        organization_id: UUID,
        limit: int = 1,
    ) -> List[schemas.BillingPeriod]:
        """Get previous billing periods."""
        periods = await crud.billing_period.get_previous_periods(
            db, organization_id=organization_id, limit=limit
        )
        return [schemas.BillingPeriod.model_validate(p, from_attributes=True) for p in periods]

    async def complete_billing_period(
        self,
        db: AsyncSession,
        period_id: UUID,
        status: BillingPeriodStatus,
        ctx: ApiContext,
    ) -> None:
        """Update a billing period's status."""
        period = await crud.billing_period.get(db, id=period_id, ctx=ctx)
        if period:
            await crud.billing_period.update(
                db,
                db_obj=period,
                obj_in={"status": status},
                ctx=ctx,
            )


billing_transactions = BillingTransactions()  # Singleton static instance
