"""Unit tests for BillingWebhookProcessor.

Static helper tests (pure logic) and handler tests (async with fakes).
Handlers are called directly to bypass _resolve_event_context.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pytest

from airweave.adapters.payment.fake import _obj
from airweave.adapters.payment.null import NullPaymentGateway
from airweave.domains.billing.tests.conftest import (
    DEFAULT_ORG_ID,
    _make_billing_model,
    _make_ctx,
    _make_invoice_obj,
    _make_org_model,
    _make_period_model,
    _make_stripe_event,
    _make_subscription_obj,
    _make_webhook_processor,
)
from airweave.domains.billing.types import ChangeType, InferredPlan, PlanInferenceContext
from airweave.domains.billing.webhook_processor import BillingWebhookProcessor
from airweave.schemas.billing_period import BillingPeriodStatus, BillingTransition
from airweave.schemas.organization_billing import BillingPlan, BillingStatus


# ===========================================================================
# _infer_plan_from_webhook (static, pure)
# ===========================================================================


@dataclass
class InferCase:
    label: str
    context: PlanInferenceContext
    price_mapping: dict[str, BillingPlan]
    expected_plan: BillingPlan
    expected_changed: bool
    expected_reason: str
    expected_clear_pending: bool = False


PRICE_MAP = {
    "price_dev": BillingPlan.DEVELOPER,
    "price_pro": BillingPlan.PRO,
    "price_team": BillingPlan.TEAM,
}

INFER_CASES = [
    InferCase(
        label="renewal_with_pending",
        context=PlanInferenceContext(
            current_plan=BillingPlan.PRO,
            pending_plan=BillingPlan.DEVELOPER,
            is_renewal=True,
            items_changed=False,
            subscription_items=["price_pro"],
        ),
        price_mapping=PRICE_MAP,
        expected_plan=BillingPlan.DEVELOPER,
        expected_changed=True,
        expected_reason="renewal_with_pending_change",
        expected_clear_pending=True,
    ),
    InferCase(
        label="renewal_no_pending_single_item",
        context=PlanInferenceContext(
            current_plan=BillingPlan.PRO,
            pending_plan=None,
            is_renewal=True,
            items_changed=False,
            subscription_items=["price_team"],
        ),
        price_mapping=PRICE_MAP,
        expected_plan=BillingPlan.TEAM,
        expected_changed=True,
        expected_reason="renewal_single_plan",
    ),
    InferCase(
        label="renewal_no_pending_no_items",
        context=PlanInferenceContext(
            current_plan=BillingPlan.PRO,
            pending_plan=None,
            is_renewal=True,
            items_changed=False,
            subscription_items=[],
        ),
        price_mapping=PRICE_MAP,
        expected_plan=BillingPlan.PRO,
        expected_changed=False,
        expected_reason="renewal_keep_current",
    ),
    InferCase(
        label="items_change_single_plan",
        context=PlanInferenceContext(
            current_plan=BillingPlan.PRO,
            pending_plan=None,
            is_renewal=False,
            items_changed=True,
            subscription_items=["price_team"],
        ),
        price_mapping=PRICE_MAP,
        expected_plan=BillingPlan.TEAM,
        expected_changed=True,
        expected_reason="items_change_single_plan",
    ),
    InferCase(
        label="items_change_ambiguous",
        context=PlanInferenceContext(
            current_plan=BillingPlan.PRO,
            pending_plan=None,
            is_renewal=False,
            items_changed=True,
            subscription_items=["price_dev", "price_team"],  # Two plans different from current
        ),
        price_mapping=PRICE_MAP,
        expected_plan=BillingPlan.PRO,
        expected_changed=False,
        expected_reason="items_change_ambiguous",
    ),
    InferCase(
        label="no_relevant_changes",
        context=PlanInferenceContext(
            current_plan=BillingPlan.PRO,
            pending_plan=None,
            is_renewal=False,
            items_changed=False,
            subscription_items=["price_pro"],
        ),
        price_mapping=PRICE_MAP,
        expected_plan=BillingPlan.PRO,
        expected_changed=False,
        expected_reason="no_relevant_changes",
    ),
    InferCase(
        label="items_change_different_plan",
        context=PlanInferenceContext(
            current_plan=BillingPlan.PRO,
            pending_plan=None,
            is_renewal=False,
            items_changed=True,
            subscription_items=["price_pro", "price_dev"],
        ),
        price_mapping=PRICE_MAP,
        expected_plan=BillingPlan.DEVELOPER,
        expected_changed=True,
        expected_reason="items_change_different_plan",
    ),
    InferCase(
        label="renewal_pending_same_as_current",
        context=PlanInferenceContext(
            current_plan=BillingPlan.PRO,
            pending_plan=BillingPlan.PRO,
            is_renewal=True,
            items_changed=False,
            subscription_items=["price_pro"],
        ),
        price_mapping=PRICE_MAP,
        expected_plan=BillingPlan.PRO,
        expected_changed=False,
        expected_reason="renewal_with_pending_change",
        expected_clear_pending=True,
    ),
]


@pytest.mark.parametrize("case", INFER_CASES, ids=lambda c: c.label)
def test_infer_plan_from_webhook(case: InferCase):
    result = BillingWebhookProcessor._infer_plan_from_webhook(case.context, case.price_mapping)

    assert result.plan == case.expected_plan
    assert result.changed == case.expected_changed
    assert result.reason == case.expected_reason
    assert result.should_clear_pending == case.expected_clear_pending


# ===========================================================================
# _determine_period_transition (static, pure)
# ===========================================================================


@dataclass
class TransitionCase:
    label: str
    old: BillingPlan
    new: BillingPlan
    is_first: bool
    expected: str


TRANSITION_CASES = [
    TransitionCase("first_period", BillingPlan.PRO, BillingPlan.PRO, True, BillingTransition.INITIAL_SIGNUP),
    TransitionCase("upgrade", BillingPlan.DEVELOPER, BillingPlan.PRO, False, BillingTransition.UPGRADE),
    TransitionCase("downgrade", BillingPlan.TEAM, BillingPlan.PRO, False, BillingTransition.DOWNGRADE),
    TransitionCase("same_renewal", BillingPlan.PRO, BillingPlan.PRO, False, BillingTransition.RENEWAL),
]


@pytest.mark.parametrize("case", TRANSITION_CASES, ids=lambda c: c.label)
def test_determine_period_transition(case: TransitionCase):
    result = BillingWebhookProcessor._determine_period_transition(case.old, case.new, case.is_first)
    assert result == case.expected


# ===========================================================================
# _should_create_new_period (static, pure)
# ===========================================================================


@dataclass
class NewPeriodCase:
    label: str
    event_type: str
    plan_changed: bool
    change_type: ChangeType
    expected: bool


NEW_PERIOD_CASES = [
    NewPeriodCase("renewal", "renewal", False, ChangeType.SAME, True),
    NewPeriodCase("immediate_upgrade", "immediate_change", True, ChangeType.UPGRADE, True),
    NewPeriodCase("immediate_downgrade", "immediate_change", True, ChangeType.DOWNGRADE, False),
    NewPeriodCase("immediate_same", "immediate_change", False, ChangeType.SAME, False),
]


@pytest.mark.parametrize("case", NEW_PERIOD_CASES, ids=lambda c: c.label)
def test_should_create_new_period(case: NewPeriodCase):
    result = BillingWebhookProcessor._should_create_new_period(
        case.event_type, case.plan_changed, case.change_type
    )
    assert result == case.expected


# ===========================================================================
# _handle_subscription_created
# ===========================================================================


class TestHandleSubscriptionCreated:
    @pytest.mark.asyncio
    async def test_no_ctx_returns_early(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)
        sub = _make_subscription_obj()
        event = _make_stripe_event("customer.subscription.created", sub)
        log = _make_ctx().logger

        await proc._handle_subscription_created(db, event, None, log)

        # No billing ops should be called
        assert len(bo._calls) == 0

    @pytest.mark.asyncio
    async def test_no_billing_record_returns_early(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        sub = _make_subscription_obj()
        event = _make_stripe_event("customer.subscription.created", sub)

        await proc._handle_subscription_created(db, event, ctx, ctx.logger)

        assert len(bo._calls) == 0

    @pytest.mark.asyncio
    async def test_happy_path_pro(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        sub = _make_subscription_obj(metadata={"organization_id": str(DEFAULT_ORG_ID), "plan": "pro"})
        event = _make_stripe_event("customer.subscription.created", sub)

        await proc._handle_subscription_created(db, event, ctx, ctx.logger)

        # Billing record updated
        assert billing.stripe_subscription_id == "sub_test"
        assert billing.billing_plan == BillingPlan.PRO.value
        assert billing.billing_status == BillingStatus.ACTIVE.value
        # Billing period created
        assert len(bo._periods) == 1
        assert bo._periods[0]["plan"] == BillingPlan.PRO
        assert bo._periods[0]["transition"] == BillingTransition.INITIAL_SIGNUP

    @pytest.mark.asyncio
    async def test_developer_plan(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model(billing_plan=BillingPlan.DEVELOPER.value)
        br.seed(DEFAULT_ORG_ID, billing)

        sub = _make_subscription_obj(
            metadata={"organization_id": str(DEFAULT_ORG_ID), "plan": "developer"}
        )
        event = _make_stripe_event("customer.subscription.created", sub)

        await proc._handle_subscription_created(db, event, ctx, ctx.logger)

        assert billing.billing_plan == BillingPlan.DEVELOPER.value
        assert len(bo._periods) == 1
        assert bo._periods[0]["plan"] == BillingPlan.DEVELOPER

    @pytest.mark.asyncio
    async def test_payment_method_detected(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model(payment_method_added=False, payment_method_id=None)
        br.seed(DEFAULT_ORG_ID, billing)

        sub = _make_subscription_obj(default_payment_method="pm_xyz")
        event = _make_stripe_event("customer.subscription.created", sub)

        await proc._handle_subscription_created(db, event, ctx, ctx.logger)

        assert billing.payment_method_added is True
        assert billing.payment_method_id == "pm_xyz"


# ===========================================================================
# _handle_subscription_updated
# ===========================================================================


class TestHandleSubscriptionUpdated:
    @pytest.mark.asyncio
    async def test_no_billing_returns_early(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        sub = _make_subscription_obj()
        event = _make_stripe_event("customer.subscription.updated", sub)

        await proc._handle_subscription_updated(db, event, ctx, ctx.logger)

        # No updates should happen
        assert len(bo._periods) == 0

    @pytest.mark.asyncio
    async def test_renewal_creates_period(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        now_ts = int(time.time())
        sub = _make_subscription_obj(
            current_period_start=now_ts,
            current_period_end=now_ts + 30 * 86400,
        )
        # Renewal is detected via previous_attributes containing current_period_end
        event = _make_stripe_event(
            "customer.subscription.updated",
            sub,
            previous_attributes={"current_period_end": now_ts - 30 * 86400},
        )

        await proc._handle_subscription_updated(db, event, ctx, ctx.logger)

        # Should create a new period (renewal)
        assert len(bo._periods) == 1
        assert bo._periods[0]["transition"] == BillingTransition.RENEWAL

    @pytest.mark.asyncio
    async def test_no_relevant_changes_updates_billing_only(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        sub = _make_subscription_obj()
        event = _make_stripe_event(
            "customer.subscription.updated",
            sub,
            previous_attributes={},
        )

        await proc._handle_subscription_updated(db, event, ctx, ctx.logger)

        # No new period
        assert len(bo._periods) == 0
        # Billing record should still be updated (dates, status)
        update_calls = [c for c in br._calls if c[0] == "update"]
        assert len(update_calls) >= 1

    @pytest.mark.asyncio
    async def test_cancel_at_period_end_recorded(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model(cancel_at_period_end=False)
        br.seed(DEFAULT_ORG_ID, billing)

        sub = _make_subscription_obj(cancel_at_period_end=True)
        event = _make_stripe_event(
            "customer.subscription.updated",
            sub,
            previous_attributes={},
        )

        await proc._handle_subscription_updated(db, event, ctx, ctx.logger)

        assert billing.cancel_at_period_end is True

    @pytest.mark.asyncio
    async def test_yearly_prepay_expiry_clears_fields(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        # Billing with yearly prepay that has expired
        billing = _make_billing_model(
            has_yearly_prepay=True,
            yearly_prepay_expires_at=datetime.utcnow() - timedelta(days=1),
            yearly_prepay_started_at=datetime.utcnow() - timedelta(days=366),
            yearly_prepay_coupon_id="coupon_test",
        )
        br.seed(DEFAULT_ORG_ID, billing)

        now_ts = int(time.time())
        sub = _make_subscription_obj(
            current_period_start=now_ts,
            current_period_end=now_ts + 30 * 86400,
        )
        # Renewal event
        event = _make_stripe_event(
            "customer.subscription.updated",
            sub,
            previous_attributes={"current_period_end": now_ts - 30 * 86400},
        )

        await proc._handle_subscription_updated(db, event, ctx, ctx.logger)

        # Yearly fields should be cleared
        assert billing.has_yearly_prepay is False
        assert billing.yearly_prepay_expires_at is None
        assert billing.yearly_prepay_coupon_id is None


# ===========================================================================
# _handle_subscription_deleted
# ===========================================================================


class TestHandleSubscriptionDeleted:
    @pytest.mark.asyncio
    async def test_no_billing_returns_early(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        sub = _make_subscription_obj(status="canceled")
        event = _make_stripe_event("customer.subscription.deleted", sub)

        await proc._handle_subscription_deleted(db, event, ctx, ctx.logger)

        # No updates
        update_calls = [c for c in br._calls if c[0] == "update"]
        assert len(update_calls) == 0

    @pytest.mark.asyncio
    async def test_canceled_clears_subscription(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)
        period = _make_period_model()
        pr.seed(period)

        sub = _make_subscription_obj(status="canceled")
        event = _make_stripe_event("customer.subscription.deleted", sub)

        await proc._handle_subscription_deleted(db, event, ctx, ctx.logger)

        assert billing.stripe_subscription_id is None
        assert billing.cancel_at_period_end is False

    @pytest.mark.asyncio
    async def test_scheduled_cancel_sets_flag(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model(cancel_at_period_end=False)
        br.seed(DEFAULT_ORG_ID, billing)

        sub = _make_subscription_obj(status="active")
        event = _make_stripe_event("customer.subscription.deleted", sub)

        await proc._handle_subscription_deleted(db, event, ctx, ctx.logger)

        assert billing.cancel_at_period_end is True

    @pytest.mark.asyncio
    async def test_pending_downgrade_applies_on_cancel(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model(
            pending_plan_change=BillingPlan.DEVELOPER,
            pending_plan_change_at=datetime.utcnow(),
        )
        br.seed(DEFAULT_ORG_ID, billing)
        period = _make_period_model()
        pr.seed(period)

        sub = _make_subscription_obj(status="canceled")
        event = _make_stripe_event("customer.subscription.deleted", sub)

        await proc._handle_subscription_deleted(db, event, ctx, ctx.logger)

        assert billing.billing_plan == BillingPlan.DEVELOPER.value
        assert billing.pending_plan_change is None


# ===========================================================================
# _handle_payment_succeeded
# ===========================================================================


class TestHandlePaymentSucceeded:
    @pytest.mark.asyncio
    async def test_no_subscription_returns_early(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        invoice = _make_invoice_obj(subscription=None)
        event = _make_stripe_event("invoice.payment_succeeded", invoice)

        await proc._handle_payment_succeeded(db, event, ctx, ctx.logger)

        update_calls = [c for c in br._calls if c[0] == "update"]
        assert len(update_calls) == 0

    @pytest.mark.asyncio
    async def test_no_billing_returns_early(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        invoice = _make_invoice_obj()
        event = _make_stripe_event("invoice.payment_succeeded", invoice)

        await proc._handle_payment_succeeded(db, event, ctx, ctx.logger)

        update_calls = [c for c in br._calls if c[0] == "update"]
        assert len(update_calls) == 0

    @pytest.mark.asyncio
    async def test_happy_path_updates_payment_status(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)
        period = _make_period_model()
        pr.seed(period)

        invoice = _make_invoice_obj()
        event = _make_stripe_event("invoice.payment_succeeded", invoice)

        await proc._handle_payment_succeeded(db, event, ctx, ctx.logger)

        assert billing.last_payment_status == "succeeded"
        assert billing.last_payment_at is not None

    @pytest.mark.asyncio
    async def test_past_due_updated_to_active(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model(billing_status=BillingStatus.PAST_DUE.value)
        br.seed(DEFAULT_ORG_ID, billing)

        invoice = _make_invoice_obj()
        event = _make_stripe_event("invoice.payment_succeeded", invoice)

        await proc._handle_payment_succeeded(db, event, ctx, ctx.logger)

        assert billing.billing_status == BillingStatus.ACTIVE.value


# ===========================================================================
# _handle_payment_failed
# ===========================================================================


class TestHandlePaymentFailed:
    @pytest.mark.asyncio
    async def test_no_subscription_returns_early(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        invoice = _make_invoice_obj(subscription=None)
        event = _make_stripe_event("invoice.payment_failed", invoice)

        await proc._handle_payment_failed(db, event, ctx, ctx.logger)

        update_calls = [c for c in br._calls if c[0] == "update"]
        assert len(update_calls) == 0

    @pytest.mark.asyncio
    async def test_no_billing_returns_early(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        invoice = _make_invoice_obj()
        event = _make_stripe_event("invoice.payment_failed", invoice)

        await proc._handle_payment_failed(db, event, ctx, ctx.logger)

        update_calls = [c for c in br._calls if c[0] == "update"]
        assert len(update_calls) == 0

    @pytest.mark.asyncio
    async def test_renewal_failure_creates_grace_period(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)
        period = _make_period_model()
        pr.seed(period)

        invoice = _make_invoice_obj(billing_reason="subscription_cycle")
        event = _make_stripe_event("invoice.payment_failed", invoice)

        await proc._handle_payment_failed(db, event, ctx, ctx.logger)

        assert billing.billing_status == BillingStatus.PAST_DUE.value
        assert billing.last_payment_status == "failed"
        assert billing.grace_period_ends_at is not None
        # Grace period billing period should be created
        assert len(bo._periods) == 1
        assert bo._periods[0]["status"] == BillingPeriodStatus.GRACE

    @pytest.mark.asyncio
    async def test_non_renewal_failure_sets_past_due(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        invoice = _make_invoice_obj()
        event = _make_stripe_event("invoice.payment_failed", invoice)

        await proc._handle_payment_failed(db, event, ctx, ctx.logger)

        assert billing.billing_status == BillingStatus.PAST_DUE.value
        assert billing.last_payment_status == "failed"
        # No grace period created for non-renewal failures
        assert len(bo._periods) == 0


# ===========================================================================
# _handle_checkout_completed
# ===========================================================================


class TestHandleCheckoutCompleted:
    @pytest.mark.asyncio
    async def test_subscription_mode_noop(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()

        session = _obj(
            id="cs_test",
            customer="cus_test",
            mode="subscription",
            subscription="sub_test",
            metadata={},
        )
        event = _make_stripe_event("checkout.session.completed", session)

        await proc._handle_checkout_completed(db, event, ctx, ctx.logger)

        # No billing ops should be called for subscription mode
        assert len(bo._periods) == 0


# ===========================================================================
# _handle_invoice_upcoming
# ===========================================================================


class TestHandleInvoiceUpcoming:
    @pytest.mark.asyncio
    async def test_logs_upcoming(self, db):
        proc, gw, br, pr, bo, org = _make_webhook_processor()
        ctx = _make_ctx()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        invoice = _make_invoice_obj(amount_due=2000)
        event = _make_stripe_event("invoice.upcoming", invoice)

        # Should not raise — just logs
        await proc._handle_invoice_upcoming(db, event, ctx, ctx.logger)


# ===========================================================================
# NullPaymentGateway behavior (Stripe disabled)
# ===========================================================================


class TestNullGatewayWebhookBehavior:
    """Webhook processor behavior when NullPaymentGateway is injected."""

    @pytest.mark.asyncio
    async def test_handle_webhook_raises_on_verify(self, db):
        """NullPaymentGateway.verify_webhook_signature raises ValueError."""
        proc, *_ = _make_webhook_processor(payment_gateway=NullPaymentGateway())

        with pytest.raises(ValueError, match="Billing is not enabled"):
            await proc.process_webhook(db, b"payload", "sig_header")

    def test_infer_plan_with_empty_mapping_keeps_current(self):
        """Empty price mapping (from NullPaymentGateway) → falls back to current plan."""
        context = PlanInferenceContext(
            current_plan=BillingPlan.PRO,
            pending_plan=None,
            is_renewal=True,
            items_changed=False,
            subscription_items=["price_pro"],
        )

        result = BillingWebhookProcessor._infer_plan_from_webhook(context, {})

        assert result.plan == BillingPlan.PRO
        assert result.changed is False

    @pytest.mark.asyncio
    async def test_subscription_created_no_payment_method_detected(self, db):
        """NullPaymentGateway.detect_payment_method returns (False, None)."""
        proc, _, br, pr, bo, org = _make_webhook_processor(
            payment_gateway=NullPaymentGateway()
        )
        ctx = _make_ctx()
        billing = _make_billing_model(payment_method_added=False, payment_method_id=None)
        br.seed(DEFAULT_ORG_ID, billing)

        sub = _make_subscription_obj(default_payment_method="pm_xyz")
        event = _make_stripe_event("customer.subscription.created", sub)

        await proc._handle_subscription_created(db, event, ctx, ctx.logger)

        # NullPaymentGateway always returns (False, None) for detect_payment_method
        assert billing.payment_method_added is False
        assert billing.payment_method_id is None

    @pytest.mark.asyncio
    async def test_subscription_updated_empty_items_keeps_plan(self, db):
        """NullPaymentGateway returns empty items and mapping → plan unchanged."""
        proc, _, br, pr, bo, org = _make_webhook_processor(
            payment_gateway=NullPaymentGateway()
        )
        ctx = _make_ctx()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        now_ts = int(time.time())
        sub = _make_subscription_obj(
            current_period_start=now_ts,
            current_period_end=now_ts + 30 * 86400,
        )
        event = _make_stripe_event(
            "customer.subscription.updated",
            sub,
            previous_attributes={"current_period_end": now_ts - 30 * 86400},
        )

        await proc._handle_subscription_updated(db, event, ctx, ctx.logger)

        # Plan should be unchanged (NullPaymentGateway returns empty mapping)
        assert billing.billing_plan == BillingPlan.PRO.value
