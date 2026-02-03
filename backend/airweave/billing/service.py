"""Main billing service orchestrator.

This module coordinates billing operations by orchestrating
between the business logic, repository, and Stripe client.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.billing.plan_logic import (
    ChangeType,
    PlanChangeContext,
    analyze_plan_change,
    compare_plans,
    compute_yearly_prepay_amount_cents,
    coupon_percent_off_for_yearly_prepay,
    get_plan_limits,
    is_paid_plan,
)
from airweave.billing.transactions import billing_transactions
from airweave.core.exceptions import InvalidStateError, NotFoundException
from airweave.core.logging import ContextualLogger, logger
from airweave.core.shared_models import AuthMethod
from airweave.db.unit_of_work import UnitOfWork
from airweave.integrations.stripe_client import stripe_client
from airweave.models import Organization
from airweave.schemas.organization_billing import (
    BillingPlan,
    BillingStatus,
    OrganizationBillingUpdate,
    SubscriptionInfo,
)


class BillingService:
    """Service for managing organization billing and subscriptions."""

    def _create_system_context(
        self,
        organization: schemas.Organization,
        source: str = "billing_service",
    ) -> ApiContext:
        """Create a system context for billing operations."""
        request_id = str(uuid4())
        return ApiContext(
            request_id=request_id,
            auth_method=AuthMethod.INTERNAL_SYSTEM,
            auth_subject_id=str(uuid4()),
            auth_subject_name=f"billing_{source}",
            organization=organization,
            user=None,
            logger=logger.with_context(
                request_id=request_id,
                organization_id=str(organization.id),
                auth_method=AuthMethod.INTERNAL_SYSTEM.value,
                source=source,
            ),
        )

    async def _get_organization(
        self, db: AsyncSession, organization_id: UUID
    ) -> schemas.Organization:
        """Get organization by ID."""
        org_model = await crud.organization.get(db, organization_id)
        if not org_model:
            raise NotFoundException(f"Organization {organization_id} not found")
        return schemas.Organization.model_validate(org_model, from_attributes=True)

    # Billing record management

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
                    raise InvalidStateError(
                        "Enterprise plan is only available via sales. "
                        "Please contact support or select a different plan."
                    )
                elif plan_lower in SELF_SERVE_PLANS:
                    selected_plan = BillingPlan(plan_lower)

        # Create billing record
        billing = await billing_transactions.create_billing_record(
            db=db,
            organization_id=organization.id,
            stripe_customer_id=stripe_customer_id,
            billing_email=billing_email,
            plan=selected_plan,
            ctx=ctx,
            uow=uow,
        )

        log.info(f"Created billing record for org {organization.id} with plan {selected_plan}")

        # For developer plan, create $0 subscription for webhook-driven periods
        # Note: Enterprise is handled via sales, not self-serve creation
        if selected_plan == BillingPlan.DEVELOPER and stripe_client:
            price_id = stripe_client.get_price_for_plan(selected_plan)
            plan_str = selected_plan.value
            if price_id:
                try:
                    sub = await stripe_client.create_subscription(
                        customer_id=stripe_customer_id,
                        price_id=price_id,
                        metadata={
                            "organization_id": str(organization.id),
                            "plan": plan_str,
                        },
                    )

                    await billing_transactions.update_billing_by_org(
                        db=db,
                        organization_id=organization.id,
                        updates=OrganizationBillingUpdate(
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

    # Subscription management
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
        if not stripe_client:
            raise InvalidStateError("Stripe is not enabled")

        new_price_id = stripe_client.get_price_for_plan(target_plan)
        if not new_price_id:
            raise InvalidStateError(f"Invalid plan: {target_plan.value}")

        if update_price_immediately:
            await stripe_client.update_subscription(
                subscription_id=billing.stripe_subscription_id,
                price_id=new_price_id,
                cancel_at_period_end=False,
                proration_behavior="create_prorations",
            )

        # Ensure a single yearly coupon (20%) is applied
        percent_off = coupon_percent_off_for_yearly_prepay(target_plan)
        idempotency_key = f"yearly:{ctx.organization.id}:{target_plan.value}"
        coupon = await stripe_client.create_or_get_yearly_coupon(
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
            current_coupon_id = await stripe_client.get_subscription_coupon_id(
                subscription_id=billing.stripe_subscription_id
            )
        except Exception:
            current_coupon_id = None
        if current_coupon_id and current_coupon_id != coupon.id:
            try:
                await stripe_client.remove_subscription_discount(
                    subscription_id=billing.stripe_subscription_id
                )
            except Exception:
                pass

        await stripe_client.apply_coupon_to_subscription(
            subscription_id=billing.stripe_subscription_id, coupon_id=coupon.id
        )

        # Compute credit based on remaining credit vs. yearly target
        target_year_amount = compute_yearly_prepay_amount_cents(target_plan)

        # Remaining credit = max(0, -balance)
        remaining_credit = 0
        try:
            balance = await stripe_client.get_customer_balance_cents(
                customer_id=billing.stripe_customer_id
            )
            if balance < 0:
                remaining_credit = -int(balance)
        except Exception:
            remaining_credit = 0

        credit_needed = max(0, int(target_year_amount) - int(remaining_credit))
        if credit_needed > 0:
            try:
                await stripe_client.credit_customer_balance(
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

        await billing_transactions.update_billing_by_org(
            db,
            ctx.organization.id,
            OrganizationBillingUpdate(
                billing_plan=target_plan,
                cancel_at_period_end=False,
                has_yearly_prepay=True,
                yearly_prepay_amount_cents=target_year_amount,  # Update to new plan's yearly amount
                yearly_prepay_expires_at=expires_at,
                yearly_prepay_started_at=started_at,
                yearly_prepay_coupon_id=coupon.id,
                # Update period to reflect yearly (not monthly) billing
                current_period_start=started_at,
                current_period_end=expires_at,
            ),
            ctx,
        )

        return f"Successfully upgraded to {target_plan.value} yearly"

    async def start_subscription_checkout(
        self,
        db: AsyncSession,
        plan: str,
        success_url: str,
        cancel_url: str,
        ctx: ApiContext,
    ) -> str:
        """Start a subscription checkout flow."""
        billing = await billing_transactions.get_billing_record(db, ctx.organization.id)
        if not billing:
            raise NotFoundException("No billing record found for organization")

        if not stripe_client:
            raise InvalidStateError("Stripe is not enabled")

        # Get price ID for plan
        billing_plan = BillingPlan(plan)

        # Block public Enterprise checkout
        if billing_plan == BillingPlan.ENTERPRISE:
            raise InvalidStateError(
                "Enterprise plan is only available via sales. Please contact support."
            )
        price_id = stripe_client.get_price_for_plan(billing_plan)
        if not price_id:
            raise InvalidStateError(f"Invalid plan: {plan}")

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

            raise InvalidStateError(f"Already has active {plan} subscription")

        # Create checkout session
        metadata = {
            "organization_id": str(ctx.organization.id),
            "plan": plan,
        }

        if billing.stripe_subscription_id and needs_checkout:
            metadata["previous_subscription_id"] = billing.stripe_subscription_id

        session = await stripe_client.create_checkout_session(
            customer_id=billing.stripe_customer_id,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )

        return session.url

    # ------------------------------ Yearly Prepay ------------------------------ #

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
        if not stripe_client:
            raise InvalidStateError("Stripe is not enabled")

        billing = await billing_transactions.get_billing_record(db, ctx.organization.id)
        if not billing:
            raise NotFoundException("No billing record found for organization")

        target_plan = BillingPlan(plan)
        if target_plan not in {BillingPlan.PRO, BillingPlan.TEAM}:
            raise InvalidStateError("Yearly prepay only supported for pro and team")

        amount_cents = compute_yearly_prepay_amount_cents(target_plan)
        percent_off = coupon_percent_off_for_yearly_prepay(target_plan)

        # Create/get coupon now to capture ID, but final application happens after payment
        # The coupon will apply 20% discount for exactly 12 months, then expire
        idempotency_key = f"yearly:{ctx.organization.id}:{target_plan.value}"
        coupon = await stripe_client.create_or_get_yearly_coupon(
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
        session = await stripe_client.create_prepay_checkout_session(
            customer_id=billing.stripe_customer_id,
            amount_cents=amount_cents,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )

        # Record prepay intent and coupon info (without marking as active yet)
        from datetime import timedelta

        expected_expires_at = datetime.utcnow() + timedelta(days=365)
        await billing_transactions.record_yearly_prepay_started(
            db,
            ctx.organization.id,
            amount_cents=amount_cents,
            started_at=datetime.utcnow(),
            expected_expires_at=expected_expires_at,
            coupon_id=coupon.id,
            payment_intent_id=getattr(session, "payment_intent", None),
            ctx=ctx,
        )

        return session.url

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
        billing = await billing_transactions.get_billing_record(db, ctx.organization.id)
        if not billing:
            raise NotFoundException("No billing record found")

        if not billing.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        if not stripe_client:
            raise InvalidStateError("Stripe is not enabled")

        target_plan = BillingPlan(new_plan)

        # Block public Enterprise upgrades/changes (allow only internal/system)
        if target_plan == BillingPlan.ENTERPRISE and ctx.auth_method != AuthMethod.INTERNAL_SYSTEM:
            raise InvalidStateError(
                "Enterprise plan is only available via sales. Please contact support."
            )

        # Handle YEARLY term transitions first
        if (period or "monthly").lower() == "yearly":
            # Only pro/team are supported for yearly
            if target_plan not in {BillingPlan.PRO, BillingPlan.TEAM}:
                raise InvalidStateError("Yearly billing only supported for pro and team")

            # Disallow lowering plan across yearly directly (e.g., team→pro yearly)
            change_type = compare_plans(billing.billing_plan, target_plan)
            if change_type == ChangeType.DOWNGRADE:
                raise InvalidStateError(
                    "Cannot downgrade directly to a lower yearly plan. "
                    "At year end you'll default to monthly; then switch to yearly."
                )

            # Ensure there is an active subscription to update
            if not billing.stripe_subscription_id:
                raise NotFoundException("No active subscription found")

            # Require payment method for crediting
            if not billing.payment_method_added:
                raise InvalidStateError(
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

            # Create new billing period for yearly commitment (resets usage)
            # This is fair since they're pre-paying for a full year
            # Note: The webhook handler will also create a period, but our repository
            # handles duplicates by completing the existing one first

            from airweave.schemas.billing_period import BillingTransition

            now = datetime.now(timezone.utc)

            # Check if we already have an active period for the target plan
            # This can happen if the webhook beats us to it
            current_period = await billing_transactions.get_current_billing_period(
                db, ctx.organization.id
            )

            # Only create if we don't have an active period for the target plan
            # or if the current period is for a different plan
            if not current_period or current_period.plan != target_plan:
                period_end = now + relativedelta(years=1)

                await billing_transactions.create_billing_period(
                    db,
                    organization_id=ctx.organization.id,
                    period_start=now,
                    period_end=period_end,
                    plan=target_plan,
                    transition=BillingTransition.UPGRADE,  # Yearly commitment is an upgrade
                    ctx=ctx,
                    stripe_subscription_id=billing.stripe_subscription_id,
                )

            return result

        # MONTHLY term transitions (default)

        # Special case: Team yearly → Team monthly (or Pro yearly → Pro monthly)
        # While this happens automatically, we still set pending_plan_change for UI consistency
        if billing.has_yearly_prepay and billing.billing_plan == target_plan:
            if not billing.yearly_prepay_expires_at:
                raise InvalidStateError("Yearly prepay expiry date not set")

            # Set as pending even though it's automatic - for UI consistency
            await billing_transactions.update_billing_by_org(
                db,
                ctx.organization.id,
                OrganizationBillingUpdate(
                    pending_plan_change=target_plan,
                    pending_plan_change_at=billing.yearly_prepay_expires_at,
                ),
                ctx,
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

        decision = analyze_plan_change(context)

        if not decision.allowed:
            if decision.requires_checkout:
                raise InvalidStateError(decision.message)
            raise InvalidStateError(decision.message)

        # Get new price ID
        new_price_id = stripe_client.get_price_for_plan(target_plan)
        if not new_price_id:
            raise InvalidStateError(f"Invalid plan: {new_plan}")

        # Special case: currently on yearly and requesting monthly change
        # - Upgrades (e.g., pro yearly → team monthly): remove discount and switch price immediately
        # - Downgrades (e.g., team yearly → pro monthly/developer): schedule for yearly expiry
        if billing.has_yearly_prepay:
            change_type = compare_plans(billing.billing_plan, target_plan)

            if change_type == ChangeType.UPGRADE:
                # Immediate: remove discount, change price now, keep credit window
                try:
                    await stripe_client.remove_subscription_discount(
                        subscription_id=billing.stripe_subscription_id
                    )
                except Exception:
                    pass

                await stripe_client.update_subscription(
                    subscription_id=billing.stripe_subscription_id,
                    price_id=new_price_id,
                    cancel_at_period_end=False,
                    proration_behavior="create_prorations",
                )

                # Update billing record - clear yearly flags since moving to monthly
                await billing_transactions.update_billing_by_org(
                    db,
                    ctx.organization.id,
                    OrganizationBillingUpdate(
                        billing_plan=target_plan,
                        cancel_at_period_end=False,
                        has_yearly_prepay=False,  # Moving to monthly, no longer yearly
                        yearly_prepay_started_at=None,
                        yearly_prepay_expires_at=None,
                        yearly_prepay_coupon_id=None,
                    ),
                    ctx,
                )

                # Create new billing period for the upgrade
                # This will automatically create usage records with correct limits

                from airweave.schemas.billing_period import BillingTransition

                now = datetime.now(timezone.utc)
                # Calculate period end (30 days for monthly)

                period_end = now + relativedelta(months=1)

                await billing_transactions.create_billing_period(
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
            await billing_transactions.update_billing_by_org(
                db,
                ctx.organization.id,
                OrganizationBillingUpdate(
                    pending_plan_change=target_plan,
                    pending_plan_change_at=billing.yearly_prepay_expires_at,
                ),
                ctx,
            )

            return (
                f"Subscription will be downgraded to {target_plan.value} "
                "at the end of the yearly period"
            )

        # Apply the change (standard monthly behavior)
        if decision.apply_immediately:
            # Immediate change (upgrade or reactivation)
            await stripe_client.update_subscription(
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

            await billing_transactions.update_billing_by_org(db, ctx.organization.id, updates, ctx)
        else:
            # Scheduled change (downgrade)
            await stripe_client.update_subscription(
                subscription_id=billing.stripe_subscription_id,
                price_id=new_price_id,
                proration_behavior="none",
            )

            updates = OrganizationBillingUpdate(
                pending_plan_change=target_plan,
                pending_plan_change_at=billing.current_period_end,
            )

            await billing_transactions.update_billing_by_org(db, ctx.organization.id, updates, ctx)

        return decision.message

    async def cancel_subscription(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Cancel subscription at period end."""
        billing = await billing_transactions.get_billing_record(db, ctx.organization.id)
        if not billing or not billing.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        if not stripe_client:
            raise InvalidStateError("Stripe is not enabled")

        # Cancel in Stripe
        await stripe_client.cancel_subscription(
            billing.stripe_subscription_id,
            at_period_end=True,
        )

        # Update local record
        await billing_transactions.update_billing_by_org(
            db,
            ctx.organization.id,
            OrganizationBillingUpdate(cancel_at_period_end=True),
            ctx,
        )

        return "Subscription will be canceled at the end of the current billing period"

    async def reactivate_subscription(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Reactivate a canceled subscription."""
        billing = await billing_transactions.get_billing_record(db, ctx.organization.id)
        if not billing or not billing.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        if not billing.cancel_at_period_end:
            raise InvalidStateError("Subscription is not set to cancel")

        if not stripe_client:
            raise InvalidStateError("Stripe is not enabled")

        # Reactivate in Stripe
        await stripe_client.update_subscription(
            subscription_id=billing.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        # Update local record
        await billing_transactions.update_billing_by_org(
            db,
            ctx.organization.id,
            OrganizationBillingUpdate(cancel_at_period_end=False),
            ctx,
        )

        return "Subscription reactivated successfully"

    async def cancel_pending_plan_change(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Cancel a pending plan change."""
        billing = await billing_transactions.get_billing_record(db, ctx.organization.id)
        if not billing or not billing.pending_plan_change:
            raise InvalidStateError("No pending plan change found")

        if not stripe_client:
            raise InvalidStateError("Stripe is not enabled")

        # Revert Stripe subscription to current plan
        current_price_id = stripe_client.get_price_for_plan(billing.billing_plan)
        if not current_price_id:
            raise InvalidStateError(f"Invalid current plan: {billing.billing_plan}")

        await stripe_client.update_subscription(
            subscription_id=billing.stripe_subscription_id,
            price_id=current_price_id,
            proration_behavior="none",
        )

        # Clear pending change
        await billing_transactions.update_billing_by_org(
            db,
            ctx.organization.id,
            OrganizationBillingUpdate(
                pending_plan_change=None,
                pending_plan_change_at=None,
            ),
            ctx,
        )

        return "Scheduled plan change has been canceled"

    async def create_customer_portal_session(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        return_url: str,
    ) -> str:
        """Create Stripe customer portal session."""
        billing = await billing_transactions.get_billing_record(db, ctx.organization.id)
        if not billing:
            raise NotFoundException("No billing record found")

        if not stripe_client:
            raise InvalidStateError("Stripe is not enabled")

        session = await stripe_client.create_portal_session(
            customer_id=billing.stripe_customer_id,
            return_url=return_url,
        )

        return session.url

    # Subscription information

    async def get_subscription_info(
        self,
        db: AsyncSession,
        organization_id: UUID,
        at: Optional[datetime] = None,
    ) -> SubscriptionInfo:
        """Get comprehensive subscription information."""
        billing = await billing_transactions.get_billing_record(db, organization_id)

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
        # Enterprise plans are managed separately (admin-created, $0 subscriptions)
        # and should never require payment method setup via the normal flow
        is_enterprise = billing.billing_plan == BillingPlan.ENTERPRISE
        is_paid = is_paid_plan(billing.billing_plan)
        needs_initial_setup = is_paid and not billing.stripe_subscription_id and not is_enterprise
        requires_payment_method = needs_initial_setup or in_grace_period or grace_period_expired

        # Update status if grace period expired
        if grace_period_expired and billing.billing_status != BillingStatus.PAST_DUE:
            org = await self._get_organization(db, organization_id)
            ctx = self._create_system_context(org, "get_subscription_info")
            await billing_transactions.update_billing_by_org(
                db,
                organization_id,
                OrganizationBillingUpdate(billing_status=BillingStatus.PAST_DUE),
                ctx,
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
            # Enterprise plans are always considered active (managed via admin, not Stripe checkout)
            has_active_subscription=bool(billing.stripe_subscription_id) or is_enterprise,
            in_trial=False,  # We don't track trials currently
            trial_ends_at=None,
            # Yearly prepay fields
            has_yearly_prepay=billing.has_yearly_prepay,
            yearly_prepay_started_at=billing.yearly_prepay_started_at,
            yearly_prepay_expires_at=billing.yearly_prepay_expires_at,
            yearly_prepay_amount_cents=billing.yearly_prepay_amount_cents,
            yearly_prepay_coupon_id=billing.yearly_prepay_coupon_id,
            yearly_prepay_payment_intent_id=billing.yearly_prepay_payment_intent_id,
        )


# Singleton instance
billing_service = BillingService()
