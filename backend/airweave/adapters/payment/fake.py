"""Fake payment gateway for testing.

In-memory implementation of PaymentGatewayProtocol.
Records all calls for assertions. No external API calls.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

from airweave.core.protocols.payment import PaymentGatewayProtocol
from airweave.schemas.organization_billing import BillingPlan


class FakePaymentGateway(PaymentGatewayProtocol):
    """Test implementation of PaymentGatewayProtocol.

    Usage::

        fake = FakePaymentGateway()
        customer = await fake.create_customer("a@b.com", "Org")
        assert fake.call_count("create_customer") == 1
    """

    def __init__(
        self,
        price_ids: Optional[dict[BillingPlan, str]] = None,
        should_raise: Optional[Exception] = None,
    ) -> None:
        """Initialize with optional price IDs and error injection."""
        self._price_ids = price_ids or {
            BillingPlan.DEVELOPER: "price_dev",
            BillingPlan.PRO: "price_pro",
            BillingPlan.TEAM: "price_team",
            BillingPlan.ENTERPRISE: "price_ent",
        }
        self._should_raise = should_raise
        self._calls: list[tuple[str, tuple, dict]] = []

        # In-memory state
        self._customers: dict[str, dict] = {}
        self._subscriptions: dict[str, dict] = {}
        self._coupons: dict[str, dict] = {}
        self._balances: dict[str, int] = {}  # customer_id -> balance cents

    def _record(self, method: str, *args: Any, **kwargs: Any) -> None:
        self._calls.append((method, args, kwargs))
        if self._should_raise:
            raise self._should_raise

    # ---- Test helpers ----

    def call_count(self, method: str) -> int:
        """Number of times a method was called."""
        return sum(1 for name, _, _ in self._calls if name == method)

    def calls_for(self, method: str) -> list[tuple[tuple, dict]]:
        """Return (args, kwargs) for each call to *method*."""
        return [(a, k) for name, a, k in self._calls if name == method]

    def clear(self) -> None:
        """Reset all recorded state."""
        self._calls.clear()
        self._customers.clear()
        self._subscriptions.clear()
        self._coupons.clear()
        self._balances.clear()

    # ---- Price / plan mapping ----

    def get_price_id_mapping(self) -> dict[str, BillingPlan]:
        """Return reverse mapping from price IDs to plans."""
        return {pid: plan for plan, pid in self._price_ids.items() if pid}

    def get_price_for_plan(self, plan: BillingPlan) -> Optional[str]:
        """Return fake price ID for a plan."""
        return self._price_ids.get(plan)

    # ---- Customer operations ----

    async def create_customer(
        self,
        email: str,
        name: str,
        metadata: Optional[Dict[str, str]] = None,
        test_clock: Optional[str] = None,
    ) -> Any:
        """Create a fake customer in memory."""
        self._record("create_customer", email, name, metadata=metadata)
        cid = f"cus_{uuid4().hex[:14]}"
        obj = _obj(id=cid, email=email, name=name, metadata=metadata or {})
        self._customers[cid] = obj
        return obj

    async def delete_customer(self, customer_id: str) -> None:
        """Delete a fake customer from memory."""
        self._record("delete_customer", customer_id)
        self._customers.pop(customer_id, None)

    # ---- Subscription operations ----

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, str]] = None,
        coupon_id: Optional[str] = None,
        default_payment_method: Optional[str] = None,
    ) -> Any:
        """Create a fake subscription in memory."""
        self._record("create_subscription", customer_id, price_id, metadata=metadata)
        sid = f"sub_{uuid4().hex[:14]}"
        obj = _obj(
            id=sid,
            customer=customer_id,
            status="active",
            cancel_at_period_end=False,
            current_period_start=0,
            current_period_end=0,
            items=_obj(data=[_obj(id=f"si_{uuid4().hex[:8]}", price=_obj(id=price_id))]),
            default_payment_method=default_payment_method,
            metadata=metadata or {},
        )
        self._subscriptions[sid] = obj
        return obj

    async def get_subscription(self, subscription_id: str) -> Any:
        """Retrieve a fake subscription from memory."""
        self._record("get_subscription", subscription_id)
        sub = self._subscriptions.get(subscription_id)
        if sub is None:
            sub = _obj(
                id=subscription_id,
                status="active",
                items=_obj(data=[]),
                cancel_at_period_end=False,
            )
        return sub

    async def update_subscription(
        self,
        subscription_id: str,
        price_id: Optional[str] = None,
        cancel_at_period_end: Optional[bool] = None,
        proration_behavior: str = "create_prorations",
        default_payment_method: Optional[str] = None,
    ) -> Any:
        """Update a fake subscription in memory."""
        self._record(
            "update_subscription",
            subscription_id,
            price_id=price_id,
            cancel_at_period_end=cancel_at_period_end,
        )
        sub = self._subscriptions.get(subscription_id, _obj(id=subscription_id))
        if cancel_at_period_end is not None:
            sub.cancel_at_period_end = cancel_at_period_end
        return sub

    async def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> Any:
        """Cancel a fake subscription."""
        self._record("cancel_subscription", subscription_id, at_period_end=at_period_end)
        sub = self._subscriptions.get(subscription_id, _obj(id=subscription_id))
        if at_period_end:
            sub.cancel_at_period_end = True
        else:
            self._subscriptions.pop(subscription_id, None)
        return sub

    # ---- Checkout operations ----

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Return a fake checkout session URL."""
        self._record("create_checkout_session", customer_id, price_id)
        return _obj(id=f"cs_{uuid4().hex[:14]}", url="https://checkout.fake/session")

    # ---- Portal operations ----

    async def create_portal_session(self, customer_id: str, return_url: str) -> Any:
        """Return a fake portal session URL."""
        self._record("create_portal_session", customer_id)
        return _obj(url="https://portal.fake/session")

    # ---- Payment method operations ----

    async def detect_payment_method(self, subscription: Any) -> tuple[bool, Optional[str]]:
        """Detect payment method from fake subscription."""
        self._record("detect_payment_method")
        pm = getattr(subscription, "default_payment_method", None)
        if pm:
            pm_id = pm.get("id") if isinstance(pm, dict) else pm
            if pm_id:
                return True, pm_id
        return False, None

    # ---- Webhook operations ----

    def verify_webhook_signature(self, payload: bytes, signature: str) -> Any:
        """Return a fake webhook event."""
        self._record("verify_webhook_signature")
        return _obj(type="test.event", id="evt_fake", data=_obj(object={}))

    # ---- Helpers ----

    def extract_subscription_items(self, subscription: Any) -> list[str]:
        """Extract price IDs from fake subscription items."""
        self._record("extract_subscription_items")
        try:
            items_data = subscription.items.data or []
            return [item.price.id for item in items_data]
        except Exception:
            return []

    # ---- Yearly prepay ----

    async def create_prepay_checkout_session(
        self,
        *,
        customer_id: str,
        amount_cents: int,
        currency: str = "usd",
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Return a fake prepay checkout session."""
        self._record("create_prepay_checkout_session", customer_id, amount_cents)
        return _obj(
            id=f"cs_{uuid4().hex[:14]}",
            url="https://checkout.fake/prepay",
            payment_intent=f"pi_{uuid4().hex[:14]}",
        )

    async def get_customer_balance_cents(self, *, customer_id: str) -> int:
        """Return fake customer balance."""
        self._record("get_customer_balance_cents", customer_id)
        return self._balances.get(customer_id, 0)

    async def get_subscription_coupon_id(self, *, subscription_id: str) -> Optional[str]:
        """Return None — no coupon on fake subscriptions."""
        self._record("get_subscription_coupon_id", subscription_id)
        return None

    async def create_or_get_yearly_coupon(
        self,
        *,
        percent_off: int,
        duration: str = "repeating",
        duration_in_months: int = 12,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Create a fake yearly coupon."""
        self._record("create_or_get_yearly_coupon", percent_off=percent_off)
        cid = f"coupon_{uuid4().hex[:8]}"
        obj = _obj(id=cid, percent_off=percent_off)
        self._coupons[cid] = obj
        return obj

    async def apply_coupon_to_subscription(
        self,
        *,
        subscription_id: str,
        coupon_id: str,
    ) -> Any:
        """Apply a fake coupon to a subscription."""
        self._record("apply_coupon_to_subscription", subscription_id, coupon_id)
        return self._subscriptions.get(subscription_id, _obj(id=subscription_id))

    async def remove_subscription_discount(self, *, subscription_id: str) -> None:
        """Remove discount from fake subscription."""
        self._record("remove_subscription_discount", subscription_id)

    async def credit_customer_balance(
        self,
        *,
        customer_id: str,
        amount_cents: int,
        currency: str = "usd",
        description: Optional[str] = None,
    ) -> Any:
        """Credit fake customer balance."""
        self._record("credit_customer_balance", customer_id, amount_cents)
        current = self._balances.get(customer_id, 0)
        self._balances[customer_id] = current - amount_cents  # Stripe credits are negative
        return _obj(amount=-amount_cents)


class _obj:
    """Tiny attribute-bag to emulate Stripe object shapes in tests."""

    def __init__(self, **kwargs: Any):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def get(self, key: str, default: Any = None) -> Any:
        """Get attribute by key with default."""
        return getattr(self, key, default)
