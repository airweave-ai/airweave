"""Main billing service orchestrator.

This module coordinates billing operations by orchestrating
between the business logic, repository, and payment gateway.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.protocols.payment import PaymentGatewayProtocol
from airweave.domains.billing.exceptions import (
    BillingNotFoundError,
    BillingStateError,
    wrap_gateway_errors,
)
from airweave.domains.billing.operations import BillingOperationsProtocol
from airweave.domains.billing.protocols import BillingServiceProtocol
from airweave.domains.billing.repository import (
    BillingPeriodRepositoryProtocol,
    OrganizationBillingRepositoryProtocol,
)
from airweave.domains.billing.types import (
    ChangeType,
    PlanChangeContext,
    PlanChangeDecision,
    compare_plans,
    compute_yearly_prepay_amount_cents,
    coupon_percent_off_for_yearly_prepay,
    get_plan_limits,
    is_paid_plan,
)
from airweave.domains.organizations.repository import OrganizationRepositoryProtocol
from airweave.schemas.organization_billing import (
    BillingPlan,
    BillingStatus,
    OrganizationBillingUpdate,
    SubscriptionInfo,
)


class BillingService(BillingServiceProtocol):
    """Service for managing organization billing and subscriptions."""

    def __init__(
        self,
        payment_gateway: PaymentGatewayProtocol,
        billing_repo: OrganizationBillingRepositoryProtocol,
        period_repo: BillingPeriodRepositoryProtocol,
        billing_ops: BillingOperationsProtocol,
        org_repo: OrganizationRepositoryProtocol,
    ) -> None:
        """Initialize with all required dependencies."""
        self._payment_gateway = payment_gateway
        self._billing_repo = billing_repo
        self._period_repo = period_repo
        self._billing_ops = billing_ops
        self._org_repo = org_repo

    @staticmethod
    def _analyze_plan_change(context: PlanChangeContext) -> PlanChangeDecision:
        """Analyze a plan change request and determine the appropriate action."""
        # Special case: reactivating a canceled subscription
        if context.is_canceling and context.current_plan == context.target_plan:
            return PlanChangeDecision(
                allowed=True,
                change_type=ChangeType.REACTIVATION,
                requires_checkout=False,
                apply_immediately=True,
                message="Subscription reactivated successfully",
                new_plan=context.current_plan,
            )

        change_type = compare_plans(context.current_plan, context.target_plan)

        # Same plan, no change needed
        if change_type == ChangeType.SAME:
            return PlanChangeDecision(
                allowed=False,
                change_type=change_type,
                requires_checkout=False,
                apply_immediately=False,
                message=f"Already on {context.target_plan} plan",
                new_plan=context.current_plan,
            )

        # Check if payment method is required
        target_is_paid = is_paid_plan(context.target_plan)
        needs_payment_method = target_is_paid and not context.has_payment_method

        if needs_payment_method:
            return PlanChangeDecision(
                allowed=False,
                change_type=change_type,
                requires_checkout=True,
                apply_immediately=False,
                message="Payment method required for upgrade; use checkout-session",
                new_plan=context.current_plan,
            )

        # Upgrade: apply immediately with proration
        if change_type == ChangeType.UPGRADE:
            return PlanChangeDecision(
                allowed=True,
                change_type=change_type,
                requires_checkout=False,
                apply_immediately=True,
                message=f"Successfully upgraded to {context.target_plan} plan",
                new_plan=context.target_plan,
                clear_pending=True,
            )

        # Downgrade: schedule for end of period
        if change_type == ChangeType.DOWNGRADE:
            return PlanChangeDecision(
                allowed=True,
                change_type=change_type,
                requires_checkout=False,
                apply_immediately=False,
                message=f"Subscription will be downgraded to {context.target_plan} "
                "at the end of the current billing period",
                new_plan=context.current_plan,  # Keep current plan until period end
            )

        return PlanChangeDecision(
            allowed=False,
            change_type=change_type,
            requires_checkout=False,
            apply_immediately=False,
            message="Invalid plan change",
            new_plan=context.current_plan,
        )

    async def _get_organization(
        self, db: AsyncSession, organization_id: UUID
    ) -> schemas.Organization:
        """Get organization by ID."""
        org_model = await self._org_repo.get_by_id(db, organization_id=organization_id)
        if not org_model:
            raise BillingNotFoundError(f"Organization {organization_id} not found")
        return schemas.Organization.model_validate(org_model, from_attributes=True)

    # ------------------------------ Helpers (internal) ------------------------------ #

    async def _apply_yearly_coupon_and_credit(  # noqa: C901
        self,
        *,
        billing: schemas.OrganizationBilling,
        target_plan: BillingPlan,
        ctx: ApiContext,
        db: AsyncSession,
        update_price_immediately: bool,
    ) -> str:
        """Apply yearly 20% coupon and credit based on remaining balance.

        - Ensures only one active 20% coupon remains (removes existing if different)
        - Credits balance for whole-year amount (or difference for plan upgrade)
        - Optionally updates subscription price immediately
        - Updates DB yearly fields preserving/setting expiry
        """
        new_price_id = self._payment_gateway.get_price_for_plan(target_plan)
        if not new_price_id:
            raise BillingStateError(f"Invalid plan: {target_plan.value}")

        if update_price_immediately:
            await self._payment_gateway.update_subscription(
                subscription_id=billing.stripe_subscription_id,
                price_id=new_price_id,
                cancel_at_period_end=False,
                proration_behavior="create_prorations",
            )

        # Ensure a single yearly coupon (20%) is applied
        percent_off = coupon_percent_off_for_yearly_prepay(target_plan)
        idempotency_key = f"yearly:{ctx.organization.id}:{target_plan.value}"
        coupon = await self._payment_gateway.create_or_get_yearly_coupon(
            percent_off=percent_off,
            duration="repeating",
            duration_in_months=12,
            idempotency_key=idempotency_key,
            metadata={
                "organization_id": str(ctx.organization.id),
                "plan": target_plan.value,
                "type": "yearly_prepay",
            },
        )

        # If a different coupon exists, replace it
        try:
            current_coupon_id = await self._payment_gateway.get_subscription_coupon_id(
                subscription_id=billing.stripe_subscription_id
            )
        except Exception:
            current_coupon_id = None
        if current_coupon_id and current_coupon_id != coupon.id:
            try:
                await self._payment_gateway.remove_subscription_discount(
                    subscription_id=billing.stripe_subscription_id
                )
            except Exception:
                pass

        await self._payment_gateway.apply_coupon_to_subscription(
            subscription_id=billing.stripe_subscription_id, coupon_id=coupon.id
        )

        # Compute credit based on remaining credit vs. yearly target
        target_year_amount = compute_yearly_prepay_amount_cents(target_plan)

        # Remaining credit = max(0, -balance)
        remaining_credit = 0
        try:
            balance = await self._payment_gateway.get_customer_balance_cents(
                customer_id=billing.stripe_customer_id
            )
            if balance < 0:
                remaining_credit = -int(balance)
        except Exception:
            remaining_credit = 0

        credit_needed = max(0, int(target_year_amount) - int(remaining_credit))
        if credit_needed > 0:
            try:
                await self._payment_gateway.credit_customer_balance(
                    customer_id=billing.stripe_customer_id,
                    amount_cents=int(credit_needed),
                    description=f"Yearly prepay credit ({target_plan.value})",
                )
            except Exception:
                pass

        now = datetime.now(timezone.utc)
        expires_at = billing.yearly_prepay_expires_at
        if not billing.has_yearly_prepay or not expires_at:
            expires_at = now + timedelta(days=365)

        started_at = billing.yearly_prepay_started_at or now

        billing_model = await self._billing_repo.get_by_org_id(
            db, organization_id=ctx.organization.id
        )
        await self._billing_repo.update(
            db,
            db_obj=billing_model,
            obj_in=OrganizationBillingUpdate(
                billing_plan=target_plan,
                cancel_at_period_end=False,
                has_yearly_prepay=True,
                yearly_prepay_amount_cents=target_year_amount,
                yearly_prepay_expires_at=expires_at,
                yearly_prepay_started_at=started_at,
                yearly_prepay_coupon_id=coupon.id,
                current_period_start=started_at,
                current_period_end=expires_at,
            ),
            ctx=ctx,
        )

        return f"Successfully upgraded to {target_plan.value} yearly"

    @wrap_gateway_errors
    async def start_subscription_checkout(
        self,
        db: AsyncSession,
        plan: str,
        success_url: str,
        cancel_url: str,
        ctx: ApiContext,
    ) -> str:
        """Start a subscription checkout flow."""
        billing = await self._billing_repo.get_by_org_id(db, organization_id=ctx.organization.id)
        if not billing:
            raise BillingNotFoundError("No billing record found for organization")

        # Get price ID for plan
        billing_plan = BillingPlan(plan)

        # Block public Enterprise checkout
        if billing_plan == BillingPlan.ENTERPRISE:
            raise BillingStateError(
                "Enterprise plan is only available via sales. Please contact support."
            )
        price_id = self._payment_gateway.get_price_for_plan(billing_plan)
        if not price_id:
            raise BillingStateError(f"Invalid plan: {plan}")

        # Check if checkout is needed
        is_target_paid = is_paid_plan(billing_plan)
        needs_checkout = is_target_paid and not billing.payment_method_added

        # If has subscription and doesn't need checkout, update instead
        if billing.stripe_subscription_id and not needs_checkout:
            if billing.billing_plan != billing_plan:
                ctx.logger.info(f"Updating existing subscription to {plan}")
                return await self.update_subscription_plan(db, ctx, plan)

            if billing.cancel_at_period_end:
                ctx.logger.info(f"Reactivating canceled {plan} subscription")
                return await self.update_subscription_plan(db, ctx, plan)

            raise BillingStateError(f"Already has active {plan} subscription")

        # Create checkout session
        metadata = {
            "organization_id": str(ctx.organization.id),
            "plan": plan,
        }

        if billing.stripe_subscription_id and needs_checkout:
            metadata["previous_subscription_id"] = billing.stripe_subscription_id

        session = await self._payment_gateway.create_checkout_session(
            customer_id=billing.stripe_customer_id,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )

        return session.url

    # ------------------------------ Yearly Prepay ------------------------------ #

    @wrap_gateway_errors
    async def start_yearly_prepay_checkout(
        self,
        db: AsyncSession,
        *,
        plan: str,
        success_url: str,
        cancel_url: str,
        ctx: ApiContext,
    ) -> str:
        """Start a yearly prepay checkout flow for organizations without a subscription.

        Flow:
        - Compute yearly amount (20% discount)
        - Create a one-time Payment checkout session for the amount
        - Create (or ensure) a coupon for 20% off
        - Record pending prepay intent in DB
        - Webhook will finalize: credit balance, create subscription with coupon, update DB
        """
        billing = await self._billing_repo.get_by_org_id(db, organization_id=ctx.organization.id)
        if not billing:
            raise BillingNotFoundError("No billing record found for organization")

        target_plan = BillingPlan(plan)
        if target_plan not in {BillingPlan.PRO, BillingPlan.TEAM}:
            raise BillingStateError("Yearly prepay only supported for pro and team")

        amount_cents = compute_yearly_prepay_amount_cents(target_plan)
        percent_off = coupon_percent_off_for_yearly_prepay(target_plan)

        # Create/get coupon now to capture ID, but final application happens after payment
        idempotency_key = f"yearly:{ctx.organization.id}:{target_plan.value}"
        coupon = await self._payment_gateway.create_or_get_yearly_coupon(
            percent_off=percent_off,
            duration="repeating",
            duration_in_months=12,
            idempotency_key=idempotency_key,
            metadata={
                "organization_id": str(ctx.organization.id),
                "plan": target_plan.value,
                "type": "yearly_prepay",
            },
        )

        # Create payment checkout session
        metadata = {
            "organization_id": str(ctx.organization.id),
            "plan": target_plan.value,
            "type": "yearly_prepay",
            "coupon_id": coupon.id,
        }
        session = await self._payment_gateway.create_prepay_checkout_session(
            customer_id=billing.stripe_customer_id,
            amount_cents=amount_cents,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )

        # Record prepay intent and coupon info (without marking as active yet)
        expected_expires_at = datetime.utcnow() + timedelta(days=365)
        updates = OrganizationBillingUpdate(
            yearly_prepay_amount_cents=amount_cents,
            yearly_prepay_started_at=datetime.utcnow(),
            yearly_prepay_expires_at=expected_expires_at,
            yearly_prepay_coupon_id=coupon.id,
            yearly_prepay_payment_intent_id=getattr(session, "payment_intent", None),
        )
        await self._billing_repo.update(db, db_obj=billing, obj_in=updates, ctx=ctx)

        return session.url

    @wrap_gateway_errors
    async def update_subscription_plan(  # noqa: C901
        self,
        db: AsyncSession,
        ctx: ApiContext,
        new_plan: str,
        period: str = "monthly",
    ) -> str:
        """Update subscription to a new plan and optionally term (monthly/yearly).

        Rules:
        - Upgrades happen immediately
        - Downgrades are scheduled for end of the current period
        - With yearly prepay active, "period end" is yearly_prepay_expires_at
        - Yearly upgrades add credit and apply 12-month 20% coupon
        - Yearly downgrades are scheduled for after yearly expiry (no Stripe change yet)
        """
        billing = await self._billing_repo.get_by_org_id(db, organization_id=ctx.organization.id)
        if not billing:
            raise BillingNotFoundError("No billing record found")

        if not billing.stripe_subscription_id:
            raise BillingNotFoundError("No active subscription found")

        target_plan = BillingPlan(new_plan)

        # Block public Enterprise upgrades/changes (allow only internal/system)
        from airweave.core.shared_models import AuthMethod

        if target_plan == BillingPlan.ENTERPRISE and ctx.auth_method != AuthMethod.INTERNAL_SYSTEM:
            raise BillingStateError(
                "Enterprise plan is only available via sales. Please contact support."
            )

        # Handle YEARLY term transitions first
        if (period or "monthly").lower() == "yearly":
            # Only pro/team are supported for yearly
            if target_plan not in {BillingPlan.PRO, BillingPlan.TEAM}:
                raise BillingStateError("Yearly billing only supported for pro and team")

            # Disallow lowering plan across yearly directly (e.g., team->pro yearly)
            change_type = compare_plans(billing.billing_plan, target_plan)
            if change_type == ChangeType.DOWNGRADE:
                raise BillingStateError(
                    "Cannot downgrade directly to a lower yearly plan. "
                    "At year end you'll default to monthly; then switch to yearly."
                )

            # Ensure there is an active subscription to update
            if not billing.stripe_subscription_id:
                raise BillingNotFoundError("No active subscription found")

            # Require payment method for crediting
            if not billing.payment_method_added:
                raise BillingStateError(
                    "Payment method required for yearly upgrade; "
                    "use /billing/yearly/checkout-session"
                )

            # Apply yearly logic via helper (handles coupon, credit, price, DB fields)
            update_price = target_plan != billing.billing_plan
            result = await self._apply_yearly_coupon_and_credit(
                billing=billing,
                target_plan=target_plan,
                ctx=ctx,
                db=db,
                update_price_immediately=update_price,
            )

            from airweave.schemas.billing_period import BillingTransition

            now = datetime.now(timezone.utc)

            current_period = await self._period_repo.get_current_period(
                db, organization_id=ctx.organization.id
            )

            if not current_period or current_period.plan != target_plan:
                period_end = now + relativedelta(years=1)

                await self._billing_ops.create_billing_period(
                    db,
                    organization_id=ctx.organization.id,
                    period_start=now,
                    period_end=period_end,
                    plan=target_plan,
                    transition=BillingTransition.UPGRADE,
                    ctx=ctx,
                    stripe_subscription_id=billing.stripe_subscription_id,
                )

            return result

        # MONTHLY term transitions (default)

        # Special case: Team yearly -> Team monthly (or Pro yearly -> Pro monthly)
        if billing.has_yearly_prepay and billing.billing_plan == target_plan:
            if not billing.yearly_prepay_expires_at:
                raise BillingStateError("Yearly prepay expiry date not set")

            await self._billing_repo.update(
                db,
                db_obj=billing,
                obj_in=OrganizationBillingUpdate(
                    pending_plan_change=target_plan,
                    pending_plan_change_at=billing.yearly_prepay_expires_at,
                ),
                ctx=ctx,
            )

            return (
                f"Plan change to {target_plan.value} monthly scheduled for "
                f"{billing.yearly_prepay_expires_at.strftime('%B %d, %Y')} "
                "(when your yearly discount expires)"
            )

        # Analyze the plan change
        context = PlanChangeContext(
            current_plan=billing.billing_plan,
            target_plan=target_plan,
            has_payment_method=billing.payment_method_added,
            is_canceling=billing.cancel_at_period_end,
            pending_plan=billing.pending_plan_change,
            current_period_end=billing.current_period_end,
        )

        decision = self._analyze_plan_change(context)

        if not decision.allowed:
            if decision.requires_checkout:
                raise BillingStateError(decision.message)
            raise BillingStateError(decision.message)

        # Get new price ID
        new_price_id = self._payment_gateway.get_price_for_plan(target_plan)
        if not new_price_id:
            raise BillingStateError(f"Invalid plan: {new_plan}")

        # Special case: currently on yearly and requesting monthly change
        if billing.has_yearly_prepay:
            change_type = compare_plans(billing.billing_plan, target_plan)

            if change_type == ChangeType.UPGRADE:
                # Immediate: remove discount, change price now, keep credit window
                try:
                    await self._payment_gateway.remove_subscription_discount(
                        subscription_id=billing.stripe_subscription_id
                    )
                except Exception:
                    pass

                await self._payment_gateway.update_subscription(
                    subscription_id=billing.stripe_subscription_id,
                    price_id=new_price_id,
                    cancel_at_period_end=False,
                    proration_behavior="create_prorations",
                )

                # Update billing record - clear yearly flags since moving to monthly
                await self._billing_repo.update(
                    db,
                    db_obj=billing,
                    obj_in=OrganizationBillingUpdate(
                        billing_plan=target_plan,
                        cancel_at_period_end=False,
                        has_yearly_prepay=False,
                        yearly_prepay_started_at=None,
                        yearly_prepay_expires_at=None,
                        yearly_prepay_coupon_id=None,
                    ),
                    ctx=ctx,
                )

                from airweave.schemas.billing_period import BillingTransition

                now = datetime.now(timezone.utc)
                period_end = now + relativedelta(months=1)

                await self._billing_ops.create_billing_period(
                    db,
                    organization_id=ctx.organization.id,
                    period_start=now,
                    period_end=period_end,
                    plan=target_plan,
                    transition=BillingTransition.UPGRADE,
                    ctx=ctx,
                    stripe_subscription_id=billing.stripe_subscription_id,
                )

                return f"Successfully upgraded to {target_plan.value} plan"

            # Downgrades: schedule for yearly expiry
            await self._billing_repo.update(
                db,
                db_obj=billing,
                obj_in=OrganizationBillingUpdate(
                    pending_plan_change=target_plan,
                    pending_plan_change_at=billing.yearly_prepay_expires_at,
                ),
                ctx=ctx,
            )

            return (
                f"Subscription will be downgraded to {target_plan.value} "
                "at the end of the yearly period"
            )

        # Apply the change (standard monthly behavior)
        if decision.apply_immediately:
            # Immediate change (upgrade or reactivation)
            await self._payment_gateway.update_subscription(
                subscription_id=billing.stripe_subscription_id,
                price_id=new_price_id if decision.new_plan != billing.billing_plan else None,
                cancel_at_period_end=False,
                proration_behavior="create_prorations",
            )

            updates = OrganizationBillingUpdate(
                cancel_at_period_end=False,
            )

            if decision.clear_pending:
                updates.pending_plan_change = None
                updates.pending_plan_change_at = None

            await self._billing_repo.update(db, db_obj=billing, obj_in=updates, ctx=ctx)
        else:
            # Scheduled change (downgrade)
            await self._payment_gateway.update_subscription(
                subscription_id=billing.stripe_subscription_id,
                price_id=new_price_id,
                proration_behavior="none",
            )

            updates = OrganizationBillingUpdate(
                pending_plan_change=target_plan,
                pending_plan_change_at=billing.current_period_end,
            )

            await self._billing_repo.update(db, db_obj=billing, obj_in=updates, ctx=ctx)

        return decision.message

    @wrap_gateway_errors
    async def cancel_subscription(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Cancel subscription at period end."""
        billing = await self._billing_repo.get_by_org_id(db, organization_id=ctx.organization.id)
        if not billing or not billing.stripe_subscription_id:
            raise BillingNotFoundError("No active subscription found")

        # Cancel in Stripe
        await self._payment_gateway.cancel_subscription(
            billing.stripe_subscription_id,
            at_period_end=True,
        )

        # Update local record
        await self._billing_repo.update(
            db,
            db_obj=billing,
            obj_in=OrganizationBillingUpdate(cancel_at_period_end=True),
            ctx=ctx,
        )

        return "Subscription will be canceled at the end of the current billing period"

    @wrap_gateway_errors
    async def reactivate_subscription(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Reactivate a canceled subscription."""
        billing = await self._billing_repo.get_by_org_id(db, organization_id=ctx.organization.id)
        if not billing or not billing.stripe_subscription_id:
            raise BillingNotFoundError("No active subscription found")

        if not billing.cancel_at_period_end:
            raise BillingStateError("Subscription is not set to cancel")

        # Reactivate in Stripe
        await self._payment_gateway.update_subscription(
            subscription_id=billing.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        # Update local record
        await self._billing_repo.update(
            db,
            db_obj=billing,
            obj_in=OrganizationBillingUpdate(cancel_at_period_end=False),
            ctx=ctx,
        )

        return "Subscription reactivated successfully"

    @wrap_gateway_errors
    async def cancel_pending_plan_change(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Cancel a pending plan change."""
        billing = await self._billing_repo.get_by_org_id(db, organization_id=ctx.organization.id)
        if not billing or not billing.pending_plan_change:
            raise BillingStateError("No pending plan change found")

        # Revert Stripe subscription to current plan
        current_price_id = self._payment_gateway.get_price_for_plan(billing.billing_plan)
        if not current_price_id:
            raise BillingStateError(f"Invalid current plan: {billing.billing_plan}")

        await self._payment_gateway.update_subscription(
            subscription_id=billing.stripe_subscription_id,
            price_id=current_price_id,
            proration_behavior="none",
        )

        # Clear pending change
        await self._billing_repo.update(
            db,
            db_obj=billing,
            obj_in=OrganizationBillingUpdate(
                pending_plan_change=None,
                pending_plan_change_at=None,
            ),
            ctx=ctx,
        )

        return "Scheduled plan change has been canceled"

    @wrap_gateway_errors
    async def create_customer_portal_session(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        return_url: str,
    ) -> str:
        """Create Stripe customer portal session."""
        billing = await self._billing_repo.get_by_org_id(db, organization_id=ctx.organization.id)
        if not billing:
            raise BillingNotFoundError("No billing record found")

        session = await self._payment_gateway.create_portal_session(
            customer_id=billing.stripe_customer_id,
            return_url=return_url,
        )

        return session.url

    # Subscription information

    @wrap_gateway_errors
    async def get_subscription_info(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        at: Optional[datetime] = None,
    ) -> SubscriptionInfo:
        """Get comprehensive subscription information."""
        organization_id = ctx.organization.id
        billing = await self._billing_repo.get_by_org_id(db, organization_id=organization_id)

        if not billing:
            # Return free/OSS tier info
            return SubscriptionInfo(
                plan=BillingPlan.PRO,
                status=BillingStatus.ACTIVE,
                cancel_at_period_end=False,
                current_period_start=None,
                current_period_end=None,
                pending_plan_change=None,
                pending_plan_change_at=None,
                limits=get_plan_limits(BillingPlan.PRO),
                payment_method_added=False,
                in_grace_period=False,
                requires_payment_method=False,
                is_oss=False,
                has_active_subscription=False,
                in_trial=False,
                trial_ends_at=None,
                grace_period_ends_at=None,
                # Yearly prepay defaults
                has_yearly_prepay=False,
                yearly_prepay_started_at=None,
                yearly_prepay_expires_at=None,
                yearly_prepay_amount_cents=None,
                yearly_prepay_coupon_id=None,
                yearly_prepay_payment_intent_id=None,
            )

        # Check grace period
        in_grace_period = (
            billing.grace_period_ends_at is not None
            and datetime.utcnow() < billing.grace_period_ends_at
            and billing.stripe_subscription_id is not None
        )

        grace_period_expired = (
            billing.grace_period_ends_at is not None
            and datetime.utcnow() >= billing.grace_period_ends_at
            and billing.stripe_subscription_id is not None
        )

        # Check if needs setup
        is_enterprise = billing.billing_plan == BillingPlan.ENTERPRISE
        is_paid = is_paid_plan(billing.billing_plan)
        needs_initial_setup = is_paid and not billing.stripe_subscription_id and not is_enterprise
        requires_payment_method = needs_initial_setup or in_grace_period or grace_period_expired

        # Update status if grace period expired
        if grace_period_expired and billing.billing_status != BillingStatus.PAST_DUE:
            await self._billing_repo.update(
                db,
                db_obj=billing,
                obj_in=OrganizationBillingUpdate(billing_status=BillingStatus.PAST_DUE),
                ctx=ctx,
            )

        return SubscriptionInfo(
            plan=billing.billing_plan,
            status=billing.billing_status,
            cancel_at_period_end=billing.cancel_at_period_end,
            current_period_start=billing.current_period_start,
            current_period_end=billing.current_period_end,
            pending_plan_change=billing.pending_plan_change,
            pending_plan_change_at=billing.pending_plan_change_at,
            limits=get_plan_limits(billing.billing_plan),
            payment_method_added=billing.payment_method_added,
            in_grace_period=in_grace_period,
            grace_period_ends_at=billing.grace_period_ends_at,
            requires_payment_method=requires_payment_method,
            is_oss=False,
            has_active_subscription=bool(billing.stripe_subscription_id) or is_enterprise,
            in_trial=False,
            trial_ends_at=None,
            # Yearly prepay fields
            has_yearly_prepay=billing.has_yearly_prepay,
            yearly_prepay_started_at=billing.yearly_prepay_started_at,
            yearly_prepay_expires_at=billing.yearly_prepay_expires_at,
            yearly_prepay_amount_cents=billing.yearly_prepay_amount_cents,
            yearly_prepay_coupon_id=billing.yearly_prepay_coupon_id,
            yearly_prepay_payment_intent_id=billing.yearly_prepay_payment_intent_id,
        )
