"""Payment gateway protocol.

Cross-cutting infrastructure protocol for payment processing (Stripe, etc.).
All methods must be implemented by the same provider — the protocol is not split.

Direct consumers: BillingService, WebhookHandler, org_service, admin.py.
"""

from typing import Any, Dict, Optional, Protocol, runtime_checkable

from airweave.schemas.organization_billing import BillingPlan


@runtime_checkable
class PaymentGatewayProtocol(Protocol):
    """Protocol for payment gateway operations.

    Abstracts all payment provider interactions (customer management,
    subscriptions, checkout, portal, webhooks, coupons, balance).
    """

    # -------------------------------------------------------------------------
    # Price / plan mapping
    # -------------------------------------------------------------------------

    def get_price_id_mapping(self) -> dict[str, BillingPlan]:
        """Get reverse mapping from price IDs to plans."""
        ...

    def get_price_for_plan(self, plan: BillingPlan) -> Optional[str]:
        """Get payment provider price ID for a billing plan."""
        ...

    # -------------------------------------------------------------------------
    # Customer operations
    # -------------------------------------------------------------------------

    async def create_customer(
        self,
        email: str,
        name: str,
        metadata: Optional[Dict[str, str]] = None,
        test_clock: Optional[str] = None,
    ) -> Any:
        """Create a customer in the payment provider."""
        ...

    async def delete_customer(self, customer_id: str) -> None:
        """Delete a customer (for rollback). Best-effort."""
        ...

    # -------------------------------------------------------------------------
    # Subscription operations
    # -------------------------------------------------------------------------

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, str]] = None,
        coupon_id: Optional[str] = None,
        default_payment_method: Optional[str] = None,
    ) -> Any:
        """Create a subscription."""
        ...

    async def get_subscription(self, subscription_id: str) -> Any:
        """Retrieve a subscription."""
        ...

    async def update_subscription(
        self,
        subscription_id: str,
        price_id: Optional[str] = None,
        cancel_at_period_end: Optional[bool] = None,
        proration_behavior: str = "create_prorations",
        default_payment_method: Optional[str] = None,
    ) -> Any:
        """Update a subscription."""
        ...

    async def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> Any:
        """Cancel a subscription."""
        ...

    # -------------------------------------------------------------------------
    # Checkout operations
    # -------------------------------------------------------------------------

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Create a checkout session for subscription."""
        ...

    # -------------------------------------------------------------------------
    # Portal operations
    # -------------------------------------------------------------------------

    async def create_portal_session(self, customer_id: str, return_url: str) -> Any:
        """Create a customer portal session."""
        ...

    # -------------------------------------------------------------------------
    # Payment method operations
    # -------------------------------------------------------------------------

    async def detect_payment_method(self, subscription: Any) -> tuple[bool, Optional[str]]:
        """Detect if subscription has a payment method.

        Returns (has_payment_method, payment_method_id).
        """
        ...

    # -------------------------------------------------------------------------
    # Webhook operations
    # -------------------------------------------------------------------------

    def verify_webhook_signature(self, payload: bytes, signature: str) -> Any:
        """Verify and construct webhook event from payload and signature."""
        ...

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def extract_subscription_items(self, subscription: Any) -> list[str]:
        """Extract price IDs from subscription items."""
        ...

    # -------------------------------------------------------------------------
    # Yearly prepay
    # -------------------------------------------------------------------------

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
        """Create a one-time payment checkout session for yearly prepay."""
        ...

    async def get_customer_balance_cents(self, *, customer_id: str) -> int:
        """Return the customer's current account balance in cents."""
        ...

    async def get_subscription_coupon_id(self, *, subscription_id: str) -> Optional[str]:
        """Return active coupon id applied to the subscription, if any."""
        ...

    async def create_or_get_yearly_coupon(
        self,
        *,
        percent_off: int,
        duration: str = "repeating",
        duration_in_months: int = 12,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Create a reusable coupon for yearly prepay discount."""
        ...

    async def apply_coupon_to_subscription(
        self,
        *,
        subscription_id: str,
        coupon_id: str,
    ) -> Any:
        """Apply a coupon to an existing subscription."""
        ...

    async def remove_subscription_discount(self, *, subscription_id: str) -> None:
        """Remove any active discount/coupon from a subscription."""
        ...

    async def credit_customer_balance(
        self,
        *,
        customer_id: str,
        amount_cents: int,
        currency: str = "usd",
        description: Optional[str] = None,
    ) -> Any:
        """Credit customer's balance by the given amount (in cents)."""
        ...
