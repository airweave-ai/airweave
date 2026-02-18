"""Billing domain operations — write-side business logic.

These functions handle billing state mutations that involve real multi-step
business logic (overlap detection, transactional period+usage creation).
Simple CRUD wrappers are inlined at their call sites instead.
"""

from datetime import datetime, timedelta
from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.exceptions import InvalidStateError
from airweave.db.unit_of_work import UnitOfWork
from airweave.schemas.billing_period import (
    BillingPeriodCreate,
    BillingPeriodStatus,
    BillingTransition,
)
from airweave.schemas.organization_billing import BillingPlan
from airweave.schemas.usage import UsageCreate

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class BillingOperationsProtocol(Protocol):
    """Write-side billing operations used by service and webhook handler."""

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
        ...


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


class BillingOperations(BillingOperationsProtocol):
    """Billing write operations backed by crud layer."""

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
        """Create a new billing period with usage record.

        Automatically completes any overlapping active periods before creating
        the new one. Creates the period and its usage record in a single
        UnitOfWork transaction.
        """
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
                            "period_end": period_start,
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
