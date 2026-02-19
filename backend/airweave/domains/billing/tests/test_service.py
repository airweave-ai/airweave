"""Unit tests for BillingService.

All external dependencies are fakes — no patching of module-level singletons.
"""

from datetime import datetime, timedelta, timezone

import pytest

from airweave.adapters.payment.null import NullPaymentGateway
from airweave.core.shared_models import AuthMethod
from airweave.domains.billing.exceptions import (
    BillingNotAvailableError,
    BillingNotFoundError,
    BillingStateError,
)
from airweave.domains.billing.tests.conftest import (
    DEFAULT_ORG_ID,
    _make_billing_model,
    _make_ctx,
    _make_period_model,
    _make_service,
)
from airweave.schemas.organization_billing import BillingPlan, BillingStatus


# ===========================================================================
# get_subscription_info
# ===========================================================================


class TestGetSubscriptionInfo:
    @pytest.mark.asyncio
    async def test_no_billing_record_returns_defaults(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()

        info = await svc.get_subscription_info(db, ctx)

        assert info.plan == BillingPlan.PRO
        assert info.has_active_subscription is False
        assert info.payment_method_added is False

    @pytest.mark.asyncio
    async def test_active_pro_subscription(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        info = await svc.get_subscription_info(db, ctx)

        assert info.plan == BillingPlan.PRO
        assert info.has_active_subscription is True
        assert info.payment_method_added is True
        assert info.cancel_at_period_end is False
        assert "max_entities" in info.limits

    @pytest.mark.asyncio
    async def test_grace_period_active(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(
            grace_period_ends_at=datetime.utcnow() + timedelta(days=3),
        )
        br.seed(DEFAULT_ORG_ID, billing)

        info = await svc.get_subscription_info(db, ctx)

        assert info.in_grace_period is True
        assert info.requires_payment_method is True

    @pytest.mark.asyncio
    async def test_grace_period_expired_updates_status(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(
            grace_period_ends_at=datetime.utcnow() - timedelta(days=1),
            billing_status=BillingStatus.ACTIVE.value,
        )
        br.seed(DEFAULT_ORG_ID, billing)

        info = await svc.get_subscription_info(db, ctx)

        assert info.requires_payment_method is True
        # billing model should be updated to PAST_DUE
        assert billing.billing_status == BillingStatus.PAST_DUE.value

    @pytest.mark.asyncio
    async def test_enterprise_without_subscription_is_active(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(
            billing_plan=BillingPlan.ENTERPRISE.value,
            stripe_subscription_id=None,
        )
        br.seed(DEFAULT_ORG_ID, billing)

        info = await svc.get_subscription_info(db, ctx)

        assert info.has_active_subscription is True
        assert info.plan == BillingPlan.ENTERPRISE


# ===========================================================================
# start_subscription_checkout
# ===========================================================================


class TestStartSubscriptionCheckout:
    @pytest.mark.asyncio
    async def test_no_billing_record_raises(self, db, ctx):
        svc, *_ = _make_service()

        with pytest.raises(BillingNotFoundError):
            await svc.start_subscription_checkout(db, "pro", "https://ok", "https://cancel", ctx)

    @pytest.mark.asyncio
    async def test_enterprise_plan_blocked(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        with pytest.raises(BillingStateError, match="Enterprise"):
            await svc.start_subscription_checkout(
                db, "enterprise", "https://ok", "https://cancel", ctx
            )

    @pytest.mark.asyncio
    async def test_no_price_id_raises(self, db, ctx):
        from airweave.adapters.payment.fake import FakePaymentGateway

        gw = FakePaymentGateway()
        gw._price_ids = {}  # Clear after init to avoid falsy-dict default fallback
        svc, gw, br, pr, bo, org = _make_service(payment_gateway=gw)
        billing = _make_billing_model(
            stripe_subscription_id=None,
            payment_method_added=False,
        )
        br.seed(DEFAULT_ORG_ID, billing)

        with pytest.raises(BillingStateError, match="Invalid plan"):
            await svc.start_subscription_checkout(db, "pro", "https://ok", "https://cancel", ctx)

    @pytest.mark.asyncio
    async def test_creates_checkout_session(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(
            stripe_subscription_id=None,
            payment_method_added=False,
        )
        br.seed(DEFAULT_ORG_ID, billing)

        url = await svc.start_subscription_checkout(
            db, "pro", "https://ok", "https://cancel", ctx
        )

        assert url == "https://checkout.fake/session"
        assert gw.call_count("create_checkout_session") == 1

    @pytest.mark.asyncio
    async def test_existing_sub_with_pm_delegates_to_update(self, db, ctx):
        """If org has a subscription and payment method, should update instead of checkout."""
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(billing_plan=BillingPlan.DEVELOPER.value)
        br.seed(DEFAULT_ORG_ID, billing)

        result = await svc.start_subscription_checkout(
            db, "pro", "https://ok", "https://cancel", ctx
        )

        # Should have called update_subscription (not create_checkout_session)
        assert gw.call_count("create_checkout_session") == 0
        assert gw.call_count("update_subscription") == 1

    @pytest.mark.asyncio
    async def test_canceled_sub_reactivates(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(cancel_at_period_end=True)
        br.seed(DEFAULT_ORG_ID, billing)

        result = await svc.start_subscription_checkout(
            db, "pro", "https://ok", "https://cancel", ctx
        )

        assert gw.call_count("update_subscription") == 1


# ===========================================================================
# update_subscription_plan
# ===========================================================================


class TestUpdateSubscriptionPlan:
    @pytest.mark.asyncio
    async def test_no_billing_raises(self, db, ctx):
        svc, *_ = _make_service()

        with pytest.raises(BillingNotFoundError):
            await svc.update_subscription_plan(db, ctx, "pro")

    @pytest.mark.asyncio
    async def test_no_subscription_raises(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(stripe_subscription_id=None)
        br.seed(DEFAULT_ORG_ID, billing)

        with pytest.raises(BillingNotFoundError, match="No active subscription"):
            await svc.update_subscription_plan(db, ctx, "pro")

    @pytest.mark.asyncio
    async def test_enterprise_target_blocked_for_user_auth(self, db):
        ctx = _make_ctx(auth_method=AuthMethod.AUTH0)
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        with pytest.raises(BillingStateError, match="Enterprise"):
            await svc.update_subscription_plan(db, ctx, "enterprise")

    @pytest.mark.asyncio
    async def test_upgrade_dev_to_pro(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(billing_plan=BillingPlan.DEVELOPER.value)
        br.seed(DEFAULT_ORG_ID, billing)

        result = await svc.update_subscription_plan(db, ctx, "pro")

        assert "upgraded" in result.lower() or "pro" in result.lower()
        assert gw.call_count("update_subscription") == 1
        # cancel_at_period_end should be cleared
        assert billing.cancel_at_period_end is False

    @pytest.mark.asyncio
    async def test_downgrade_team_to_pro(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(billing_plan=BillingPlan.TEAM.value)
        br.seed(DEFAULT_ORG_ID, billing)

        result = await svc.update_subscription_plan(db, ctx, "pro")

        assert "downgraded" in result.lower() or "end of" in result.lower()
        # Should set pending plan change
        assert billing.pending_plan_change == BillingPlan.PRO

    @pytest.mark.asyncio
    async def test_same_plan_raises(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model()  # defaults to PRO
        br.seed(DEFAULT_ORG_ID, billing)

        with pytest.raises(BillingStateError, match="Already on"):
            await svc.update_subscription_plan(db, ctx, "pro")

    @pytest.mark.asyncio
    async def test_upgrade_without_pm_raises(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(
            billing_plan=BillingPlan.DEVELOPER.value,
            payment_method_added=False,
        )
        br.seed(DEFAULT_ORG_ID, billing)

        with pytest.raises(BillingStateError, match="Payment method required"):
            await svc.update_subscription_plan(db, ctx, "pro")

    @pytest.mark.asyncio
    async def test_yearly_upgrade_pro_to_team(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(
            billing_plan=BillingPlan.PRO.value,
            has_yearly_prepay=False,
        )
        br.seed(DEFAULT_ORG_ID, billing)

        result = await svc.update_subscription_plan(db, ctx, "team", period="yearly")

        assert "team" in result.lower()
        # Should have created coupon and updated subscription
        assert gw.call_count("create_or_get_yearly_coupon") == 1
        assert gw.call_count("update_subscription") == 1

    @pytest.mark.asyncio
    async def test_yearly_downgrade_raises(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(billing_plan=BillingPlan.TEAM.value)
        br.seed(DEFAULT_ORG_ID, billing)

        with pytest.raises(BillingStateError, match="Cannot downgrade directly"):
            await svc.update_subscription_plan(db, ctx, "pro", period="yearly")

    @pytest.mark.asyncio
    async def test_yearly_same_plan_to_monthly_schedules(self, db, ctx):
        expires = datetime.now(timezone.utc) + timedelta(days=200)
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(
            has_yearly_prepay=True,
            yearly_prepay_expires_at=expires,
        )
        br.seed(DEFAULT_ORG_ID, billing)

        result = await svc.update_subscription_plan(db, ctx, "pro")

        assert "scheduled" in result.lower() or "yearly" in result.lower()
        assert billing.pending_plan_change == BillingPlan.PRO
        assert billing.pending_plan_change_at == expires


# ===========================================================================
# cancel_subscription
# ===========================================================================


class TestCancelSubscription:
    @pytest.mark.asyncio
    async def test_no_billing_raises(self, db, ctx):
        svc, *_ = _make_service()

        with pytest.raises(BillingNotFoundError):
            await svc.cancel_subscription(db, ctx)

    @pytest.mark.asyncio
    async def test_active_subscription_cancels(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        result = await svc.cancel_subscription(db, ctx)

        assert "canceled" in result.lower()
        assert billing.cancel_at_period_end is True
        assert gw.call_count("cancel_subscription") == 1

    @pytest.mark.asyncio
    async def test_cancel_calls_gateway_with_correct_args(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(stripe_subscription_id="sub_xyz")
        br.seed(DEFAULT_ORG_ID, billing)

        await svc.cancel_subscription(db, ctx)

        calls = gw.calls_for("cancel_subscription")
        assert len(calls) == 1
        args, kwargs = calls[0]
        assert args[0] == "sub_xyz"
        assert kwargs.get("at_period_end") is True


# ===========================================================================
# reactivate_subscription
# ===========================================================================


class TestReactivateSubscription:
    @pytest.mark.asyncio
    async def test_no_billing_raises(self, db, ctx):
        svc, *_ = _make_service()

        with pytest.raises(BillingNotFoundError):
            await svc.reactivate_subscription(db, ctx)

    @pytest.mark.asyncio
    async def test_not_canceling_raises(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(cancel_at_period_end=False)
        br.seed(DEFAULT_ORG_ID, billing)

        with pytest.raises(BillingStateError, match="not set to cancel"):
            await svc.reactivate_subscription(db, ctx)

    @pytest.mark.asyncio
    async def test_reactivation_succeeds(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(cancel_at_period_end=True)
        br.seed(DEFAULT_ORG_ID, billing)

        result = await svc.reactivate_subscription(db, ctx)

        assert "reactivated" in result.lower()
        assert billing.cancel_at_period_end is False
        assert gw.call_count("update_subscription") == 1


# ===========================================================================
# cancel_pending_plan_change
# ===========================================================================


class TestCancelPendingPlanChange:
    @pytest.mark.asyncio
    async def test_no_pending_raises(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(pending_plan_change=None)
        br.seed(DEFAULT_ORG_ID, billing)

        with pytest.raises(BillingStateError, match="No pending plan change"):
            await svc.cancel_pending_plan_change(db, ctx)

    @pytest.mark.asyncio
    async def test_clears_pending_change(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model(
            pending_plan_change=BillingPlan.DEVELOPER,
            pending_plan_change_at=datetime.utcnow() + timedelta(days=15),
        )
        br.seed(DEFAULT_ORG_ID, billing)

        result = await svc.cancel_pending_plan_change(db, ctx)

        assert "canceled" in result.lower()
        assert billing.pending_plan_change is None
        assert billing.pending_plan_change_at is None
        # Should revert Stripe to current plan
        assert gw.call_count("update_subscription") == 1


# ===========================================================================
# create_customer_portal_session
# ===========================================================================


class TestCreateCustomerPortalSession:
    @pytest.mark.asyncio
    async def test_no_billing_raises(self, db, ctx):
        svc, *_ = _make_service()

        with pytest.raises(BillingNotFoundError):
            await svc.create_customer_portal_session(db, ctx, "https://return")

    @pytest.mark.asyncio
    async def test_returns_portal_url(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        url = await svc.create_customer_portal_session(db, ctx, "https://return")

        assert url == "https://portal.fake/session"
        assert gw.call_count("create_portal_session") == 1


# ===========================================================================
# start_yearly_prepay_checkout
# ===========================================================================


class TestStartYearlyPrepayCheckout:
    @pytest.mark.asyncio
    async def test_no_billing_raises(self, db, ctx):
        svc, *_ = _make_service()

        with pytest.raises(BillingNotFoundError):
            await svc.start_yearly_prepay_checkout(
                db, plan="pro", success_url="https://ok", cancel_url="https://cancel", ctx=ctx
            )

    @pytest.mark.asyncio
    async def test_developer_plan_raises(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        with pytest.raises(BillingStateError, match="only supported for pro and team"):
            await svc.start_yearly_prepay_checkout(
                db, plan="developer", success_url="https://ok", cancel_url="https://cancel", ctx=ctx
            )

    @pytest.mark.asyncio
    async def test_pro_yearly_prepay_checkout(self, db, ctx):
        svc, gw, br, pr, bo, org = _make_service()
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)

        url = await svc.start_yearly_prepay_checkout(
            db, plan="pro", success_url="https://ok", cancel_url="https://cancel", ctx=ctx
        )

        assert url == "https://checkout.fake/prepay"
        assert gw.call_count("create_or_get_yearly_coupon") == 1
        assert gw.call_count("create_prepay_checkout_session") == 1
        # DB should be updated with prepay intent info
        assert billing.yearly_prepay_amount_cents is not None
        assert billing.yearly_prepay_coupon_id is not None


# ===========================================================================
# NullPaymentGateway behavior (Stripe disabled)
# ===========================================================================


class TestNullGatewayBehavior:
    """Service behavior when NullPaymentGateway is injected (STRIPE_ENABLED=false).

    NullPaymentGateway returns None/empty from lookups and raises
    BillingNotAvailableError from user-facing operations.
    """

    # -- get_price_for_plan → None → BillingStateError --

    @pytest.mark.asyncio
    async def test_checkout_raises_when_no_price_ids(self, db, ctx):
        svc, _, br, *_ = _make_service(payment_gateway=NullPaymentGateway())
        br.seed(DEFAULT_ORG_ID, _make_billing_model())

        with pytest.raises(BillingStateError, match="Invalid plan"):
            await svc.start_subscription_checkout(
                db, "pro", "https://ok", "https://cancel", ctx
            )

    @pytest.mark.asyncio
    async def test_update_plan_raises_when_no_price_ids(self, db, ctx):
        svc, _, br, *_ = _make_service(payment_gateway=NullPaymentGateway())
        br.seed(
            DEFAULT_ORG_ID,
            _make_billing_model(billing_plan=BillingPlan.DEVELOPER.value),
        )

        with pytest.raises(BillingStateError, match="Invalid plan"):
            await svc.update_subscription_plan(db, ctx, "pro")

    @pytest.mark.asyncio
    async def test_cancel_pending_raises_when_no_price_ids(self, db, ctx):
        svc, _, br, *_ = _make_service(payment_gateway=NullPaymentGateway())
        br.seed(
            DEFAULT_ORG_ID,
            _make_billing_model(pending_plan_change=BillingPlan.DEVELOPER),
        )

        with pytest.raises(BillingStateError, match="Invalid current plan"):
            await svc.cancel_pending_plan_change(db, ctx)

    # -- User-facing gateway methods raise BillingNotAvailableError --

    @pytest.mark.asyncio
    async def test_reactivate_raises_not_available(self, db, ctx):
        svc, _, br, *_ = _make_service(payment_gateway=NullPaymentGateway())
        br.seed(DEFAULT_ORG_ID, _make_billing_model(cancel_at_period_end=True))

        with pytest.raises(BillingNotAvailableError):
            await svc.reactivate_subscription(db, ctx)

    @pytest.mark.asyncio
    async def test_portal_session_raises_not_available(self, db, ctx):
        svc, _, br, *_ = _make_service(payment_gateway=NullPaymentGateway())
        br.seed(DEFAULT_ORG_ID, _make_billing_model())

        with pytest.raises(BillingNotAvailableError):
            await svc.create_customer_portal_session(db, ctx, "https://return")

    @pytest.mark.asyncio
    async def test_yearly_prepay_raises_not_available(self, db, ctx):
        svc, _, br, *_ = _make_service(payment_gateway=NullPaymentGateway())
        br.seed(DEFAULT_ORG_ID, _make_billing_model())

        with pytest.raises(BillingNotAvailableError):
            await svc.start_yearly_prepay_checkout(
                db, plan="pro", success_url="https://ok", cancel_url="https://cancel", ctx=ctx
            )

    # -- Infrastructure no-ops still work --

    @pytest.mark.asyncio
    async def test_cancel_subscription_succeeds(self, db, ctx):
        """NullPaymentGateway.cancel_subscription is a silent no-op."""
        svc, _, br, *_ = _make_service(payment_gateway=NullPaymentGateway())
        br.seed(DEFAULT_ORG_ID, _make_billing_model())

        result = await svc.cancel_subscription(db, ctx)

        assert "canceled" in result.lower()
        updated = await br.get_by_org_id(db, organization_id=DEFAULT_ORG_ID)
        assert updated.cancel_at_period_end is True

    @pytest.mark.asyncio
    async def test_get_subscription_info_works(self, db, ctx):
        """get_subscription_info makes no user-facing gateway calls."""
        svc, _, br, *_ = _make_service(payment_gateway=NullPaymentGateway())
        br.seed(DEFAULT_ORG_ID, _make_billing_model())

        info = await svc.get_subscription_info(db, ctx)

        assert info.plan == BillingPlan.PRO
        assert info.has_active_subscription is True
