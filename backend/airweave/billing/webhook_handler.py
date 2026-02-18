"""Webhook processor for Stripe billing events.

This module handles incoming Stripe webhook events and delegates
to appropriate handlers using clean separation of concerns.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.billing.plan_logic import (
    PlanInferenceContext,
    compare_plans,
    determine_period_transition,
    infer_plan_from_webhook,
    should_create_new_period,
)
from airweave.billing.service import billing_service
from airweave.core.logging import ContextualLogger, logger
from airweave.core.shared_models import AuthMethod
from airweave.domains.billing.operations import BillingOperations
from airweave.domains.billing.repository import (
    BillingPeriodRepository,
    OrganizationBillingRepository,
)
from airweave.domains.organizations.repository import OrganizationRepository
from airweave.integrations.stripe_client import stripe_client
from airweave.schemas.billing_period import BillingPeriodStatus, BillingTransition
from airweave.schemas.organization_billing import (
    BillingPlan,
    BillingStatus,
    OrganizationBillingUpdate,
)

_billing_repo = OrganizationBillingRepository()
_period_repo = BillingPeriodRepository()
_billing_ops = BillingOperations()
_org_repo = OrganizationRepository()


class BillingWebhookProcessor:
    """Process Stripe webhook events for billing."""

    def __init__(self, db: AsyncSession):
        """Initialize webhook processor."""
        self.db = db

        # Event handler mapping
        self.handlers = {
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.payment_succeeded": self._handle_payment_succeeded,
            "invoice.paid": self._handle_payment_succeeded,  # $0 invoices
            "invoice.payment_failed": self._handle_payment_failed,
            "invoice.upcoming": self._handle_invoice_upcoming,
            "checkout.session.completed": self._handle_checkout_completed,
            "payment_intent.succeeded": self._handle_payment_intent_succeeded,
        }

    async def _create_context_logger(self, event: stripe.Event) -> ContextualLogger:
        """Create contextual logger with organization context."""
        organization_id = None

        try:
            event_object = event.data.object

            # Try metadata first
            if hasattr(event_object, "metadata") and event_object.metadata:
                org_id_str = event_object.metadata.get("organization_id")
                if org_id_str:
                    organization_id = UUID(org_id_str)

            # If not in metadata, lookup by customer/subscription
            if not organization_id:
                billing_model = None

                if hasattr(event_object, "id") and event.type.startswith("customer.subscription"):
                    billing_model = await _billing_repo.get_by_stripe_subscription_id(
                        self.db, stripe_subscription_id=event_object.id
                    )
                elif hasattr(event_object, "customer"):
                    billing_model = await _billing_repo.get_by_stripe_customer_id(
                        self.db, stripe_customer_id=event_object.customer
                    )
                elif hasattr(event_object, "subscription") and event_object.subscription:
                    billing_model = await _billing_repo.get_by_stripe_subscription_id(
                        self.db, stripe_subscription_id=event_object.subscription
                    )

                if billing_model:
                    organization_id = billing_model.organization_id

        except Exception as e:
            logger.error(f"Failed to get organization context: {e}")

        if organization_id:
            return logger.with_context(
                organization_id=str(organization_id),
                auth_method=AuthMethod.STRIPE_WEBHOOK.value,
                event_type=event.type,
                stripe_event_id=event.id,
            )

        return logger.with_context(
            auth_method=AuthMethod.STRIPE_WEBHOOK.value,
            event_type=event.type,
            stripe_event_id=event.id,
        )

    async def process_event(self, event: stripe.Event) -> None:
        """Process a Stripe webhook event."""
        log = await self._create_context_logger(event)

        handler = self.handlers.get(event.type)
        if handler:
            try:
                log.info(f"Processing webhook event: {event.type}")
                await handler(event, log)
            except Exception as e:
                log.error(f"Error handling {event.type}: {e}", exc_info=True)
                raise
        else:
            log.info(f"Unhandled webhook event type: {event.type}")

    # Event handlers

    async def _handle_subscription_created(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle new subscription creation."""
        subscription = event.data.object

        # Get organization from metadata
        org_id = subscription.metadata.get("organization_id")
        if not org_id:
            log.error(f"No organization_id in subscription {subscription.id} metadata")
            return

        # Get billing record
        billing = await _billing_repo.get_by_org_id(self.db, organization_id=UUID(org_id))
        if not billing:
            log.error(f"No billing record for organization {org_id}")
            return

        # Determine plan
        plan_str = subscription.metadata.get("plan", "pro")
        plan = BillingPlan(plan_str)

        # Create system context
        org = await _org_repo.get_by_id(
            self.db, organization_id=UUID(org_id), skip_access_validation=True
        )
        if not org:
            log.error(f"Organization {org_id} not found")
            return

        org_schema = schemas.Organization.model_validate(org, from_attributes=True)
        ctx = billing_service._create_system_context(org_schema, "stripe_webhook")

        # Detect payment method
        has_pm, pm_id = (
            await stripe_client.detect_payment_method(subscription)
            if stripe_client
            else (False, None)
        )

        # Update billing record
        updates = OrganizationBillingUpdate(
            stripe_subscription_id=subscription.id,
            billing_plan=plan,
            billing_status=BillingStatus.ACTIVE,
            current_period_start=datetime.utcfromtimestamp(subscription.current_period_start),
            current_period_end=datetime.utcfromtimestamp(subscription.current_period_end),
            grace_period_ends_at=None,
            payment_method_added=has_pm,
            payment_method_id=pm_id,
        )

        await _billing_repo.update(self.db, db_obj=billing, obj_in=updates, ctx=ctx)

        # Create first billing period
        await _billing_ops.create_billing_period(
            db=self.db,
            organization_id=UUID(org_id),
            period_start=datetime.utcfromtimestamp(subscription.current_period_start),
            period_end=datetime.utcfromtimestamp(subscription.current_period_end),
            plan=plan,
            transition=BillingTransition.INITIAL_SIGNUP,
            stripe_subscription_id=subscription.id,
            status=BillingPeriodStatus.ACTIVE,
            ctx=ctx,
        )

        log.info(f"Subscription created for org {org_id}: {plan}")

        # Notify Donke about paid subscription
        if plan != BillingPlan.DEVELOPER:
            await _notify_donke_subscription(
                org_schema, plan, UUID(org_id), is_yearly=False, log=log
            )
            # Send welcome email for Team plans
            await _send_team_welcome_email(
                self.db, org_schema, plan, UUID(org_id), is_yearly=False, log=log
            )

    async def _handle_subscription_updated(  # noqa: C901
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle subscription updates."""
        subscription = event.data.object
        previous_attributes = event.data.get("previous_attributes", {})

        # Get billing record
        billing = await _billing_repo.get_by_stripe_subscription_id(
            self.db, stripe_subscription_id=subscription.id
        )
        if not billing:
            log.error(f"No billing record for subscription {subscription.id}")
            return

        org_id = billing.organization_id

        # Create context
        org = await _org_repo.get_by_id(
            self.db, organization_id=org_id, skip_access_validation=True
        )
        if not org:
            log.error(f"Organization {org_id} not found")
            return

        org_schema = schemas.Organization.model_validate(org, from_attributes=True)
        ctx = billing_service._create_system_context(org_schema, "stripe_webhook")

        # Infer new plan
        is_renewal = "current_period_end" in previous_attributes
        items_changed = "items" in previous_attributes

        if stripe_client:
            price_ids = stripe_client.extract_subscription_items(subscription)
            price_mapping = stripe_client.get_price_id_mapping()
        else:
            price_ids = []
            price_mapping = {}

        # Only consider pending plan if it's time to apply it
        # For yearly plans, this means waiting until the yearly expires
        pending_to_apply = None
        if billing.pending_plan_change and billing.pending_plan_change_at:
            current_time = datetime.utcfromtimestamp(subscription.current_period_start)
            if current_time >= billing.pending_plan_change_at:
                pending_to_apply = billing.pending_plan_change
                log.info(f"Time to apply pending plan change: {pending_to_apply}")

        inference_context = PlanInferenceContext(
            current_plan=billing.billing_plan,
            pending_plan=pending_to_apply,  # Only set if it's time to apply
            is_renewal=is_renewal,
            items_changed=items_changed,
            subscription_items=price_ids,
        )

        inferred = infer_plan_from_webhook(inference_context, price_mapping)

        log.info(
            f"Inferred plan: {inferred.plan} (changed={inferred.changed}, reason={inferred.reason})"
        )

        # On renewal with a pending plan, ensure Stripe price switches accordingly
        # This is critical for applying downgrades that were scheduled for yearly expiry
        stripe_update_successful = False
        if is_renewal and inferred.changed and inferred.should_clear_pending and stripe_client:
            try:
                new_price_id = stripe_client.get_price_for_plan(inferred.plan)
                if new_price_id:
                    log.info(
                        f"Applying pending plan change on renewal: "
                        f"{billing.billing_plan} → {inferred.plan}"
                    )
                    await stripe_client.update_subscription(
                        subscription_id=subscription.id,
                        price_id=new_price_id,
                        proration_behavior="none",
                    )
                    stripe_update_successful = True

                    # Also need to ensure the discount is removed if transitioning from yearly
                    if billing.has_yearly_prepay:
                        try:
                            await stripe_client.remove_subscription_discount(
                                subscription_id=subscription.id
                            )
                            log.info("Removed yearly discount on plan change")
                        except Exception:
                            pass
            except Exception as e:
                log.error(f"Failed to switch subscription price on renewal: {e}")
                # If this is a test clock issue, we might still want to update the database
                # but only if it's a known test clock error
                if "test clock" in str(e).lower() and "advancement" in str(e).lower():
                    log.warning("Stripe update failed due to test clock - updating database anyway")
                    stripe_update_successful = True  # Allow DB update for test clock issues
                else:
                    # For real failures, don't update the database
                    log.error("Stripe update failed - skipping database update to prevent mismatch")
                    return

        # Determine if we should create a new period
        # Use the final plan (after considering Stripe update success) for period creation
        final_plan_for_period = inferred.plan
        if is_renewal and inferred.changed and inferred.should_clear_pending and stripe_client:
            if not stripe_update_successful:
                final_plan_for_period = billing.billing_plan

        change_type = compare_plans(billing.billing_plan, final_plan_for_period)
        if should_create_new_period(
            "renewal" if is_renewal else "immediate_change",
            final_plan_for_period != billing.billing_plan,  # Use actual change, not inferred
            change_type,
        ):
            transition = determine_period_transition(
                billing.billing_plan,
                final_plan_for_period,
                is_first_period=False,
            )

            # Use Stripe period start to locate the period that was active at that time
            # This ensures correct linkage under Stripe test clock advances
            at_dt = (
                datetime.utcfromtimestamp(subscription.current_period_start)
                if is_renewal
                else datetime.utcnow()
            )
            current_period = await _period_repo.get_current_period_at(
                self.db, organization_id=org_id, at=at_dt
            )

            await _billing_ops.create_billing_period(
                db=self.db,
                organization_id=org_id,
                period_start=(
                    datetime.utcfromtimestamp(subscription.current_period_start)
                    if is_renewal
                    else datetime.utcnow()
                ),
                period_end=datetime.utcfromtimestamp(subscription.current_period_end),
                plan=final_plan_for_period,
                transition=transition,
                stripe_subscription_id=subscription.id,
                previous_period_id=current_period.id if current_period else None,
                ctx=ctx,
            )

        # Update billing record
        has_pm, pm_id = (
            await stripe_client.detect_payment_method(subscription)
            if stripe_client
            else (False, None)
        )

        # If we tried to update Stripe but failed (except for test clock issues),
        # don't update the inferred plan to avoid mismatch
        final_plan = inferred.plan
        if is_renewal and inferred.changed and inferred.should_clear_pending and stripe_client:
            if not stripe_update_successful:
                # Stripe update failed - keep the old plan to stay in sync
                final_plan = billing.billing_plan
                log.warning(f"Keeping plan as {final_plan} due to Stripe update failure")

        updates = OrganizationBillingUpdate(
            billing_plan=final_plan,
            billing_status=BillingStatus(subscription.status),
            cancel_at_period_end=subscription.cancel_at_period_end,
            current_period_start=datetime.utcfromtimestamp(subscription.current_period_start),
            current_period_end=datetime.utcfromtimestamp(subscription.current_period_end),
            payment_method_added=has_pm,
        )

        if pm_id:
            updates.payment_method_id = pm_id

        # Update plan when appropriate (for any plan change, not just upgrades)
        if is_renewal or (items_changed and inferred.changed):
            updates.billing_plan = inferred.plan

        # Clear pending change on renewal
        if is_renewal and inferred.should_clear_pending:
            updates.pending_plan_change = None
            updates.pending_plan_change_at = None

        # Yearly prepay expiry handling: if we've passed the expiry window, clear the flag
        try:
            if billing.has_yearly_prepay:
                expiry = billing.yearly_prepay_expires_at
                # Check if the current renewal is happening after the yearly expiry
                # Use the subscription's current_period_start as the comparison time
                current_renewal_time = datetime.utcfromtimestamp(subscription.current_period_start)

                if expiry and current_renewal_time >= expiry:
                    log.info(
                        f"Yearly prepay expired for org {org_id}: "
                        f"renewal at {current_renewal_time} >= expiry {expiry}"
                    )
                    updates.has_yearly_prepay = False
                    # Also clear other yearly fields when expiry is reached
                    updates.yearly_prepay_expires_at = None
                    updates.yearly_prepay_started_at = None
                    updates.yearly_prepay_amount_cents = None
                    updates.yearly_prepay_coupon_id = None
                    updates.yearly_prepay_payment_intent_id = None
        except Exception as e:
            log.error(f"Error checking yearly prepay expiry: {e}")

        await _billing_repo.update(self.db, db_obj=billing, obj_in=updates, ctx=ctx)

        log.info(f"Subscription updated for org {org_id}")

    async def _handle_subscription_deleted(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle subscription deletion/cancellation."""
        subscription = event.data.object

        # Get billing record
        billing = await _billing_repo.get_by_stripe_subscription_id(
            self.db, stripe_subscription_id=subscription.id
        )
        if not billing:
            log.error(f"No billing record for subscription {subscription.id}")
            return

        org_id = billing.organization_id

        # Create context
        org = await _org_repo.get_by_id(
            self.db, organization_id=org_id, skip_access_validation=True
        )
        if not org:
            log.error(f"Organization {org_id} not found")
            return

        org_schema = schemas.Organization.model_validate(org, from_attributes=True)
        ctx = billing_service._create_system_context(org_schema, "stripe_webhook")

        # Check if actually deleted or just scheduled
        sub_status = getattr(subscription, "status", None)
        if sub_status == "canceled":
            # Actually deleted
            current_period = await _period_repo.get_current_period(self.db, organization_id=org_id)
            if current_period:
                await _period_repo.update(
                    self.db,
                    db_obj=current_period,
                    obj_in={"status": BillingPeriodStatus.COMPLETED},
                    ctx=ctx,
                )
                log.info(f"Completed final period {current_period.id} for org {org_id}")

            # Check for pending downgrade
            new_plan = billing.pending_plan_change or billing.billing_plan

            updates = OrganizationBillingUpdate(
                billing_status=BillingStatus.ACTIVE,
                billing_plan=new_plan,
                stripe_subscription_id=None,
                cancel_at_period_end=False,
                pending_plan_change=None,
                pending_plan_change_at=None,
            )

            await _billing_repo.update(self.db, db_obj=billing, obj_in=updates, ctx=ctx)

            log.info(f"Subscription fully canceled for org {org_id}")
        else:
            # Just scheduled to cancel
            updates = OrganizationBillingUpdate(cancel_at_period_end=True)
            await _billing_repo.update(self.db, db_obj=billing, obj_in=updates, ctx=ctx)
            log.info(f"Subscription scheduled to cancel for org {org_id}")

    async def _handle_payment_succeeded(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle successful payment."""
        invoice = event.data.object

        if not invoice.subscription:
            return  # One-time payment

        # Get billing record
        billing = await _billing_repo.get_by_stripe_customer_id(
            self.db, stripe_customer_id=invoice.customer
        )
        if not billing:
            log.error(f"No billing record for customer {invoice.customer}")
            return

        org_id = billing.organization_id

        # Create context
        org = await _org_repo.get_by_id(
            self.db, organization_id=org_id, skip_access_validation=True
        )
        if not org:
            return

        org_schema = schemas.Organization.model_validate(org, from_attributes=True)
        ctx = billing_service._create_system_context(org_schema, "stripe_webhook")

        # Update payment info
        updates = OrganizationBillingUpdate(
            last_payment_status="succeeded",
            last_payment_at=datetime.utcnow(),
        )

        # Clear past_due if needed
        if billing.billing_status == BillingStatus.PAST_DUE:
            updates.billing_status = BillingStatus.ACTIVE

        await _billing_repo.update(self.db, db_obj=billing, obj_in=updates, ctx=ctx)

        # Stamp the most recent ACTIVE/GRACE period with invoice details (best effort)
        try:
            period = await _period_repo.get_current_period(self.db, organization_id=org_id)
            if period and period.status in {BillingPeriodStatus.ACTIVE, BillingPeriodStatus.GRACE}:
                inv_paid_at = None
                try:
                    transitions = getattr(invoice, "status_transitions", None)
                    if transitions and isinstance(transitions, dict):
                        paid_at_ts = transitions.get("paid_at")
                        if paid_at_ts:
                            inv_paid_at = datetime.utcfromtimestamp(int(paid_at_ts))
                except Exception:
                    inv_paid_at = None

                await _period_repo.update(
                    self.db,
                    db_obj=period,
                    obj_in={
                        "stripe_invoice_id": getattr(invoice, "id", None),
                        "amount_cents": getattr(invoice, "amount_paid", None),
                        "currency": getattr(invoice, "currency", None),
                        "paid_at": inv_paid_at or datetime.utcnow(),
                    },
                    ctx=ctx,
                )
        except Exception:
            # Best effort; do not fail webhook
            pass

        log.info(f"Payment succeeded for org {org_id}")

    async def _handle_payment_failed(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle failed payment."""
        invoice = event.data.object

        if not invoice.subscription:
            return  # One-time payment

        # Get billing record
        billing = await _billing_repo.get_by_stripe_customer_id(
            self.db, stripe_customer_id=invoice.customer
        )
        if not billing:
            log.error(f"No billing record for customer {invoice.customer}")
            return

        org_id = billing.organization_id

        # Create context
        org = await _org_repo.get_by_id(
            self.db, organization_id=org_id, skip_access_validation=True
        )
        if not org:
            return

        org_schema = schemas.Organization.model_validate(org, from_attributes=True)
        ctx = billing_service._create_system_context(org_schema, "stripe_webhook")

        # Check if renewal failure
        if hasattr(invoice, "billing_reason") and invoice.billing_reason == "subscription_cycle":
            # Create grace period
            from datetime import timedelta

            current_period = await _period_repo.get_current_period(self.db, organization_id=org_id)
            if current_period:
                await _period_repo.update(
                    self.db,
                    db_obj=current_period,
                    obj_in={"status": BillingPeriodStatus.ENDED_UNPAID},
                    ctx=ctx,
                )

                grace_end = datetime.utcnow() + timedelta(days=7)
                await _billing_ops.create_billing_period(
                    db=self.db,
                    organization_id=org_id,
                    period_start=current_period.period_end,
                    period_end=grace_end,
                    plan=current_period.plan,
                    transition=BillingTransition.RENEWAL,
                    stripe_subscription_id=billing.stripe_subscription_id,
                    previous_period_id=current_period.id,
                    status=BillingPeriodStatus.GRACE,
                    ctx=ctx,
                )

                updates = OrganizationBillingUpdate(
                    last_payment_status="failed",
                    billing_status=BillingStatus.PAST_DUE,
                    grace_period_ends_at=grace_end,
                )
            else:
                updates = OrganizationBillingUpdate(
                    last_payment_status="failed",
                    billing_status=BillingStatus.PAST_DUE,
                )
        else:
            updates = OrganizationBillingUpdate(
                last_payment_status="failed",
                billing_status=BillingStatus.PAST_DUE,
            )

        await _billing_repo.update(self.db, db_obj=billing, obj_in=updates, ctx=ctx)

        log.warning(f"Payment failed for org {org_id}")

    async def _handle_invoice_upcoming(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle upcoming invoice notification."""
        invoice = event.data.object

        # Find organization
        billing = await _billing_repo.get_by_stripe_customer_id(
            self.db, stripe_customer_id=invoice.customer
        )

        if billing:
            log.info(
                f"Upcoming invoice for org {billing.organization_id}: "
                f"${invoice.amount_due / 100:.2f}"
            )
            # TODO: Send email notification if needed

    async def _handle_checkout_completed(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle checkout session completion."""
        session = event.data.object

        log.info(
            f"Checkout completed: {session.id}, "
            f"Customer: {session.customer}, "
            f"Mode: {getattr(session, 'mode', None)}, "
            f"Subscription: {getattr(session, 'subscription', None)}"
        )

        # If this is a yearly prepay payment (mode=payment), finalize yearly flow.
        if getattr(session, "mode", None) == "payment":
            await self._finalize_yearly_prepay(session, log)

        # For subscription mode, the subscription.created webhook will handle setup

    async def _handle_payment_intent_succeeded(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Optional handler for payment_intent.succeeded (not strictly needed)."""
        # No-op; checkout.session.completed covers our flow.
        return

    async def _finalize_yearly_prepay(  # noqa: C901
        self, session: Any, log: ContextualLogger
    ) -> None:
        """Finalize yearly prepay: credit balance, create subscription with coupon."""
        try:
            if not getattr(session, "metadata", None):
                return
            if session.metadata.get("type") != "yearly_prepay":
                return

            org_id_str = session.metadata.get("organization_id")
            plan_str = session.metadata.get("plan")
            coupon_id = session.metadata.get("coupon_id")
            payment_intent_id = getattr(session, "payment_intent", None)
            if not (org_id_str and plan_str and coupon_id and payment_intent_id):
                log.error("Missing metadata for yearly prepay finalization")
                return

            organization_id = UUID(org_id_str)

            # Hydrate context
            org = await _org_repo.get_by_id(
                self.db, organization_id=organization_id, skip_access_validation=True
            )
            if not org:
                log.error(f"Organization {organization_id} not found for prepay finalization")
                return
            org_schema = schemas.Organization.model_validate(org, from_attributes=True)
            ctx = billing_service._create_system_context(org_schema, "stripe_webhook")

            # Credit customer's balance by the captured amount
            billing = await _billing_repo.get_by_org_id(self.db, organization_id=organization_id)
            if not billing:
                log.error("Billing record missing for yearly prepay finalization")
                return

            try:
                pi = stripe.PaymentIntent.retrieve(payment_intent_id)
                amount_received = getattr(pi, "amount_received", None)
            except Exception:
                amount_received = None

            if amount_received and stripe_client:
                try:
                    await stripe_client.credit_customer_balance(
                        customer_id=billing.stripe_customer_id,
                        amount_cents=int(amount_received),
                        description=f"Yearly prepay credit ({plan_str})",
                    )
                except Exception as e:
                    log.warning(f"Failed to credit balance: {e}")

            # Update existing subscription or create new one
            if stripe_client:
                price_id = stripe_client.get_price_for_plan(BillingPlan(plan_str))
                if price_id:
                    if billing.stripe_subscription_id:
                        # Update existing subscription (e.g., Developer → Pro yearly)
                        # Apply the coupon to the existing subscription
                        try:
                            await stripe_client.apply_coupon_to_subscription(
                                subscription_id=billing.stripe_subscription_id,
                                coupon_id=coupon_id,
                            )
                        except Exception as e:
                            log.warning(f"Failed to apply coupon to subscription: {e}")

                        # Get the payment method from the payment intent and set as default
                        payment_method_id = None
                        try:
                            payment_intent_id = getattr(session, "payment_intent", None)
                            if payment_intent_id:
                                pi = stripe.PaymentIntent.retrieve(payment_intent_id)
                                payment_method_id = getattr(pi, "payment_method", None)
                        except Exception as e:
                            log.warning(f"Failed to get payment method from payment intent: {e}")

                        # Update the subscription to the new price with default payment method
                        update_params = {
                            "subscription_id": billing.stripe_subscription_id,
                            "price_id": price_id,
                            "cancel_at_period_end": False,
                            "proration_behavior": "create_prorations",
                        }
                        # Only set default_payment_method if we have a valid one
                        # For updates, it's OK to not have one since the subscription already exists
                        if payment_method_id:
                            update_params["default_payment_method"] = payment_method_id

                        sub = await stripe_client.update_subscription(**update_params)
                        log.info(
                            f"Updated existing subscription {billing.stripe_subscription_id} "
                            f"to {plan_str} yearly"
                        )
                    else:
                        # Create new subscription (no existing subscription)
                        # Get the payment method from the payment intent
                        payment_method_id = None
                        try:
                            payment_intent_id = getattr(session, "payment_intent", None)
                            if payment_intent_id:
                                pi = stripe.PaymentIntent.retrieve(payment_intent_id)
                                payment_method_id = getattr(pi, "payment_method", None)

                                # If we have a payment method, ensure it's attached to the customer
                                if payment_method_id:
                                    try:
                                        # Check if already attached by trying to retrieve it
                                        stripe.PaymentMethod.retrieve(payment_method_id)
                                        # Try to attach it if not already attached
                                        stripe.PaymentMethod.attach(
                                            payment_method_id, customer=billing.stripe_customer_id
                                        )
                                    except Exception as attach_err:
                                        log.debug(
                                            f"Payment method might already be attached:{attach_err}"
                                        )

                                    # Set as default payment method for the customer
                                    try:
                                        stripe.Customer.modify(
                                            billing.stripe_customer_id,
                                            invoice_settings={
                                                "default_payment_method": payment_method_id
                                            },
                                        )
                                    except Exception as set_default_err:
                                        log.warning(
                                            "Failed to set default payment method: "
                                            f"{set_default_err}"
                                        )
                        except Exception as e:
                            log.warning(f"Failed to get payment method from payment intent: {e}")

                        # If we still don't have a payment method, try to get the customer's default
                        if not payment_method_id:
                            try:
                                customer = stripe.Customer.retrieve(billing.stripe_customer_id)
                                if hasattr(customer, "invoice_settings"):
                                    invoice_settings = customer.invoice_settings
                                    if hasattr(invoice_settings, "default_payment_method"):
                                        payment_method_id = invoice_settings.default_payment_method
                            except Exception as e:
                                log.debug(f"No default payment method found on customer: {e}")

                        create_params = {
                            "customer_id": billing.stripe_customer_id,
                            "price_id": price_id,
                            "metadata": {
                                "organization_id": org_id_str,
                                "plan": plan_str,
                            },
                            "coupon_id": coupon_id,
                        }
                        # Only add default_payment_method if we have a valid one
                        if payment_method_id:
                            create_params["default_payment_method"] = payment_method_id

                        sub = await stripe_client.create_subscription(**create_params)
                        log.info(f"Created new subscription for {plan_str} yearly")

                    # Update DB: set subscription and finalize prepay window
                    from datetime import timedelta

                    # Derive expiry based on Stripe subscription start (respects test clock)
                    sub_start = datetime.utcfromtimestamp(sub.current_period_start)
                    expires_at = sub_start + timedelta(days=365)
                    # Check if subscription has payment method
                    has_pm, pm_id = (
                        await stripe_client.detect_payment_method(sub)
                        if stripe_client
                        else (False, None)
                    )

                    billing = await _billing_repo.update(
                        self.db,
                        db_obj=billing,
                        obj_in=OrganizationBillingUpdate(
                            stripe_subscription_id=sub.id,
                            billing_plan=BillingPlan(plan_str),
                            payment_method_added=True,  # They just paid, so they have a pm
                            payment_method_id=pm_id,
                        ),
                        ctx=ctx,
                    )
                    await _billing_repo.update(
                        self.db,
                        db_obj=billing,
                        obj_in=OrganizationBillingUpdate(
                            has_yearly_prepay=True,
                            yearly_prepay_coupon_id=coupon_id,
                            yearly_prepay_payment_intent_id=str(payment_intent_id),
                            yearly_prepay_expires_at=expires_at,
                        ),
                        ctx=ctx,
                    )

                    log.info(f"Yearly prepay finalized for org {organization_id}: sub {sub.id}")

                    # Notify Donke about yearly subscription
                    await _notify_donke_subscription(
                        org, BillingPlan(plan_str), organization_id, is_yearly=True, log=log
                    )
                    # Send welcome email for Team plans
                    await _send_team_welcome_email(
                        self.db,
                        org,
                        BillingPlan(plan_str),
                        organization_id,
                        is_yearly=True,
                        log=log,
                    )
        except Exception as e:
            log.error(f"Error finalizing yearly prepay: {e}", exc_info=True)
            raise


async def _notify_donke_subscription(
    org: schemas.Organization,
    plan: BillingPlan,
    org_id: UUID,
    is_yearly: bool,
    log: ContextualLogger,
) -> None:
    """Notify Donke about paid subscription (best-effort).

    Args:
        org: The organization schema
        plan: The billing plan
        org_id: Organization ID
        is_yearly: Whether this is a yearly subscription
        log: Contextual logger
    """
    import httpx

    from airweave.core.config import settings

    if not settings.DONKE_URL or not settings.DONKE_API_KEY:
        return

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.DONKE_URL}/api/notify-subscription?code={settings.DONKE_API_KEY}",
                headers={
                    "Content-Type": "application/json",
                },
                json={
                    "organization_name": org.name,
                    "plan": plan.value,
                    "organization_id": str(org_id),
                    "is_yearly": is_yearly,
                    "user_email": None,  # Could get from org owner if needed
                },
                timeout=5.0,
            )
            log.info(f"Notified Donke about subscription for {org_id}")
    except Exception as e:
        log.warning(f"Failed to notify Donke: {e}")


async def _send_team_welcome_email(
    db: AsyncSession,
    org: schemas.Organization,
    plan: BillingPlan,
    org_id: UUID,
    is_yearly: bool,
    log: ContextualLogger,
) -> None:
    """Send welcome email to Team plan subscribers via Donke (best-effort).

    Args:
        db: Database session
        org: The organization schema
        plan: The billing plan
        org_id: Organization ID
        is_yearly: Whether this is a yearly subscription
        log: Contextual logger
    """
    import httpx
    from sqlalchemy import select

    from airweave.core.config import settings
    from airweave.models.user import User
    from airweave.models.user_organization import UserOrganization

    # Only send for Team plans
    if plan != BillingPlan.TEAM:
        return

    if not settings.DONKE_URL or not settings.DONKE_API_KEY:
        return

    try:
        # Get organization owner to send email
        stmt = (
            select(User)
            .join(UserOrganization, User.id == UserOrganization.user_id)
            .where(
                UserOrganization.organization_id == org_id,
                UserOrganization.role == "owner",
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        owner = result.scalar_one_or_none()

        if not owner:
            log.warning(f"No owner found for organization {org_id}, skipping welcome email")
            return

        # Call Donke to send the welcome email
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.DONKE_URL}/api/send-team-welcome-email?code={settings.DONKE_API_KEY}",
                headers={
                    "Content-Type": "application/json",
                },
                json={
                    "organization_name": org.name,
                    "user_email": owner.email,
                    "user_name": owner.full_name or owner.email,
                    "plan": plan.value,
                    "is_yearly": is_yearly,
                },
                timeout=5.0,
            )
            log.info(f"Team welcome email sent via Donke for {org_id} to {owner.email}")
    except Exception as e:
        log.warning(f"Failed to send Team welcome email via Donke: {e}")
