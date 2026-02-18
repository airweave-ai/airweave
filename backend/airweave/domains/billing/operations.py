"""Billing domain operations — write-side business logic.

These functions handle billing state mutations that involve real multi-step
business logic (overlap detection, transactional period+usage creation).
Simple CRUD wrappers are inlined at their call sites instead.
"""

from datetime import datetime, timedelta
from typing import Any, Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.logging import ContextualLogger, logger
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.billing.exceptions import BillingStateError
from airweave.domains.billing.repository import OrganizationBillingRepositoryProtocol
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
        ctx: ApiContext,
        stripe_subscription_id: Optional[str] = None,
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
        ctx: ApiContext,
        uow: UnitOfWork,
        contextual_logger: Optional[ContextualLogger] = None,
    ) -> schemas.OrganizationBilling:
        """Create initial billing record for an organization."""
        ...


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


class BillingOperations(BillingOperationsProtocol):
    """Billing write operations backed by crud layer."""

    def __init__(
        self,
        billing_repo: Optional["OrganizationBillingRepositoryProtocol"] = None,
        payment_gateway: Optional[Any] = None,
    ) -> None:
        """Initialize with optional billing repo and payment gateway."""
        self._billing_repo = billing_repo
        self._payment_gateway = payment_gateway

    async def create_billing_record(
        self,
        db: AsyncSession,
        organization: Organization,
        stripe_customer_id: str,
        billing_email: str,
        ctx: ApiContext,
        uow: UnitOfWork,
        contextual_logger: Optional[ContextualLogger] = None,
    ) -> schemas.OrganizationBilling:
        """Create initial billing record for an organization.

        Handles both paid and free (developer) plans.
        """
        from airweave.domains.billing.repository import OrganizationBillingRepository

        billing_repo = self._billing_repo or OrganizationBillingRepository()
        log = contextual_logger or logger

        # Extract plan from organization metadata
        # SECURITY: Only self-serve plans allowed via user input;
        # enterprise requires sales
        SELF_SERVE_PLANS = ["developer", "pro", "team"]

        selected_plan = BillingPlan.PRO  # Default
        if hasattr(organization, "org_metadata") and organization.org_metadata:
            # Check for plan in onboarding metadata (from test/frontend)
            onboarding = organization.org_metadata.get("onboarding", {})
            subscription_plan = onboarding.get("subscriptionPlan")
            # Also check direct plan field for backwards compatibility
            direct_plan = organization.org_metadata.get("plan")

            plan_from_metadata = subscription_plan or direct_plan
            if plan_from_metadata:
                plan_lower = plan_from_metadata.lower()
                if plan_lower == "enterprise":
                    log.warning(
                        f"Blocked enterprise plan self-provisioning attempt for org "
                        f"{organization.id}. This may indicate abuse."
                    )
                    raise BillingStateError(
                        "Enterprise plan is only available via sales. "
                        "Please contact support or select a different plan."
                    )
                elif plan_lower in SELF_SERVE_PLANS:
                    selected_plan = BillingPlan(plan_lower)

        # Create billing record
        existing = await billing_repo.get_by_org_id(db, organization_id=organization.id)
        if existing:
            raise BillingStateError("Billing record already exists for organization")

        billing_create = OrganizationBillingCreate(
            organization_id=organization.id,
            stripe_customer_id=stripe_customer_id,
            billing_plan=selected_plan,
            billing_status=BillingStatus.ACTIVE,
            billing_email=billing_email,
        )
        billing_model = await billing_repo.create(db, obj_in=billing_create, ctx=ctx, uow=uow)
        await db.flush()
        await db.refresh(billing_model)
        billing = schemas.OrganizationBilling.model_validate(billing_model, from_attributes=True)

        log.info(f"Created billing record for org {organization.id} with plan {selected_plan}")

        # For developer plan, create $0 subscription for webhook-driven periods
        # Note: Enterprise is handled via sales, not self-serve creation
        if selected_plan == BillingPlan.DEVELOPER and self._payment_gateway:
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

                    await billing_repo.update(
                        db,
                        db_obj=billing_model,
                        obj_in=OrganizationBillingUpdate(
                            stripe_subscription_id=sub.id,
                        ),
                        ctx=ctx,
                    )

                    log.info(
                        f"Created $0 {plan_str} subscription {sub.id} for org {organization.id}"
                    )
                except Exception as e:
                    log.warning(f"Failed to create {plan_str} subscription: {e}")
            else:
                log.warning(
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
            raise BillingStateError("Failed to create billing period")

        return schemas.BillingPeriod.model_validate(created_period, from_attributes=True)
