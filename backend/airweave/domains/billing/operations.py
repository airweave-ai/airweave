"""Billing domain operations — write-side business logic.

These functions handle billing state mutations that involve real multi-step
business logic (overlap detection, transactional period+usage creation).
Simple CRUD wrappers are inlined at their call sites instead.
"""

from datetime import datetime, timedelta
from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.events.billing import BillingPeriodCreatedEvent
from airweave.core.logging import logger
from airweave.core.protocols.event_bus import EventBus
from airweave.core.protocols.payment import PaymentGatewayProtocol
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.billing.exceptions import BillingStateError
from airweave.domains.billing.repository import (
    BillingPeriodRepositoryProtocol,
    OrganizationBillingRepositoryProtocol,
)
from airweave.domains.usage.repository import UsageRepositoryProtocol
from airweave.models import Organization
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
        ctx: BaseContext,
        stripe_subscription_id: str,
        previous_period_id: Optional[UUID] = None,
        status: BillingPeriodStatus = BillingPeriodStatus.ACTIVE,
    ) -> schemas.BillingPeriod:
        """Create a new billing period with usage record."""
        ...

    async def create_billing_record(
        self,
        db: AsyncSession,
        organization: Organization,
        stripe_customer_id: str,
        billing_email: str,
        ctx: BaseContext,
        uow: UnitOfWork,
    ) -> schemas.OrganizationBilling:
        """Create initial billing record for an organization."""
        ...


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


class BillingOperations(BillingOperationsProtocol):
    """Billing write operations backed by repository layer."""

    def __init__(
        self,
        billing_repo: OrganizationBillingRepositoryProtocol,
        period_repo: BillingPeriodRepositoryProtocol,
        usage_repo: UsageRepositoryProtocol,
        payment_gateway: PaymentGatewayProtocol,
        event_bus: EventBus,
    ) -> None:
        """Initialize with required repository and payment dependencies."""
        self._billing_repo = billing_repo
        self._period_repo = period_repo
        self._usage_repo = usage_repo
        self._payment_gateway = payment_gateway
        self._event_bus = event_bus

    async def create_billing_record(
        self,
        db: AsyncSession,
        organization: Organization,
        stripe_customer_id: str,
        billing_email: str,
        ctx: BaseContext,
        uow: UnitOfWork,
    ) -> schemas.OrganizationBilling:
        """Create initial billing record for an organization.

        Handles both paid and free (developer) plans.
        """
        # SECURITY: Only self-serve plans allowed via user input; enterprise requires sales.
        # The billing record always starts as DEVELOPER. The real plan is set by
        # the customer.subscription.created webhook after Stripe Checkout completes.
        # org_metadata still stores the user's plan *intent* so the frontend knows
        # which checkout to redirect to.
        if organization.org_metadata:
            onboarding = organization.org_metadata.get("onboarding", {})
            plan_from_metadata = onboarding.get(
                "subscriptionPlan"
            ) or organization.org_metadata.get("plan")
            if plan_from_metadata and plan_from_metadata.lower() == "enterprise":
                ctx.logger.warning(
                    f"Blocked enterprise plan self-provisioning attempt for org "
                    f"{organization.id}. This may indicate abuse."
                )
                raise BillingStateError(
                    "Enterprise plan is only available via sales. "
                    "Please contact support or select a different plan."
                )

        selected_plan = BillingPlan.DEVELOPER

        existing = await self._billing_repo.get_by_org_id(db, organization_id=organization.id)
        if existing:
            raise BillingStateError("Billing record already exists for organization")

        billing_create = OrganizationBillingCreate(
            organization_id=organization.id,
            stripe_customer_id=stripe_customer_id,
            billing_plan=selected_plan,
            billing_status=BillingStatus.ACTIVE,
            billing_email=billing_email,
        )
        billing_model = await self._billing_repo.create(db, obj_in=billing_create, ctx=ctx, uow=uow)
        await db.flush()
        await db.refresh(billing_model)
        billing = schemas.OrganizationBilling.model_validate(billing_model, from_attributes=True)

        ctx.logger.info(f"Created billing record with plan {selected_plan}")

        # For developer plan, create $0 subscription for webhook-driven periods
        if selected_plan == BillingPlan.DEVELOPER:
            price_id = self._payment_gateway.get_price_for_plan(selected_plan)
            plan_str = selected_plan.value
            if price_id:
                try:
                    sub = await self._payment_gateway.create_subscription(
                        customer_id=stripe_customer_id,
                        price_id=price_id,
                        metadata={
                            "organization_id": str(organization.id),
                            "plan": plan_str,
                        },
                    )

                    await self._billing_repo.update(
                        db,
                        db_obj=billing_model,
                        obj_in=OrganizationBillingUpdate(
                            stripe_subscription_id=sub.id,
                        ),
                        ctx=ctx,
                    )

                    ctx.logger.info(f"Created $0 {plan_str} subscription {sub.id}")
                except Exception as e:
                    ctx.logger.warning(f"Failed to create {plan_str} subscription: {e}")
            else:
                ctx.logger.warning(
                    f"{selected_plan.value.title()} price ID not configured; "
                    f"{plan_str} plan will be local-only"
                )

        return billing

    async def create_billing_period(
        self,
        db: AsyncSession,
        organization_id: UUID,
        period_start: datetime,
        period_end: datetime,
        plan: BillingPlan,
        transition: BillingTransition,
        ctx: BaseContext,
        stripe_subscription_id: str,
        previous_period_id: Optional[UUID] = None,
        status: BillingPeriodStatus = BillingPeriodStatus.ACTIVE,
    ) -> schemas.BillingPeriod:
        """Create a new billing period with usage record.

        Resolves all overlapping active periods in the range before creating
        the new one: earlier periods are truncated/completed, later periods
        that start inside the new range are also completed.

        Creates the period and its usage record in a single UnitOfWork
        transaction.
        """
        overlapping = await self._period_repo.get_active_periods_in_range(
            db,
            organization_id=organization_id,
            range_start=period_start - timedelta(seconds=1),
            range_end=period_end,
        )

        async with UnitOfWork(db) as uow:
            for existing in overlapping:
                db_period = await self._period_repo.get(db, id=existing.id, ctx=ctx)
                if not db_period:
                    continue

                if db_period.period_start < period_start:
                    # Period starts before ours — truncate it at our start
                    await self._period_repo.update(
                        db,
                        db_obj=db_period,
                        obj_in={
                            "status": BillingPeriodStatus.COMPLETED,
                            "period_end": period_start,
                        },
                        ctx=ctx,
                        uow=uow,
                    )
                    if not previous_period_id:
                        previous_period_id = db_period.id
                    logger.info(
                        f"Completed earlier period {db_period.id} (truncated end to {period_start})"
                    )
                else:
                    # Period starts at or after ours — it's a forward overlap,
                    # complete it so the new period takes precedence
                    await self._period_repo.update(
                        db,
                        db_obj=db_period,
                        obj_in={"status": BillingPeriodStatus.COMPLETED},
                        ctx=ctx,
                        uow=uow,
                    )
                    logger.info(
                        f"Completed forward-overlapping period {db_period.id} "
                        f"(started {db_period.period_start})"
                    )

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

            period = await self._period_repo.create(db, obj_in=period_create, ctx=ctx, uow=uow)
            await db.flush()
            period_id = period.id

            usage_create = UsageCreate(
                organization_id=organization_id,
                billing_period_id=period.id,
            )
            await self._usage_repo.create(db, obj_in=usage_create, ctx=ctx, uow=uow)
            await uow.commit()

        created_period = await self._period_repo.get(db, id=period_id, ctx=ctx)
        if not created_period:
            raise BillingStateError("Failed to create billing period")

        await self._event_bus.publish(
            BillingPeriodCreatedEvent(
                organization_id=organization_id,
                billing_period_id=period_id,
                plan=plan.value,
                status=status.value,
                transition=transition.value,
            )
        )

        return schemas.BillingPeriod.model_validate(created_period, from_attributes=True)
