"""Null payment gateway for when Stripe is disabled.

Satisfies PaymentGatewayProtocol so the container can always be fully
constructed.

Infrastructure methods (create/delete customer, lookups, cleanup) return
sensible defaults so that calling code (e.g. organization_service) does not
need to know whether billing is enabled.

User-facing billing operations (checkout sessions, subscription mutations,
financial operations) raise BillingNotAvailableError — these require a real
payment provider and should fail clearly.

verify_webhook_signature raises ValueError, matching the Stripe adapter's
contract for invalid signatures.
"""

from typing import Any, Dict, Optional

from airweave.core.protocols.payment import PaymentGatewayProtocol
from airweave.domains.billing.exceptions import BillingNotAvailableError
from airweave.schemas.organization_billing import BillingPlan


class NullPaymentGateway(PaymentGatewayProtocol):
    """No-op payment gateway used when Stripe is disabled."""

    # ------------------------------------------------------------------
    # Infrastructure / lifecycle — silent no-ops
    # ------------------------------------------------------------------

    async def create_customer(
        self,
        email: str,
        name: str,
        metadata: Optional[Dict[str, str]] = None,
        test_clock: Optional[str] = None,
    ) -> Any:
        """No-op: return None so callers naturally skip billing."""
        return None

    async def delete_customer(self, customer_id: str) -> None:
        """No-op: nothing to clean up."""
        return None

    async def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> Any:
        """No-op: nothing to cancel."""
        return None

    # ------------------------------------------------------------------
    # Lookups / queries — return empty defaults
    # ------------------------------------------------------------------

    def get_price_for_plan(self, plan: BillingPlan) -> Optional[str]:
        """Return None — no prices configured."""
        return None

    def get_price_id_mapping(self) -> dict[str, BillingPlan]:
        """Return empty mapping."""
        return {}

    def extract_subscription_items(self, subscription: Any) -> list[str]:
        """Return empty list — no subscription items."""
        return []

    async def detect_payment_method(self, subscription: Any) -> tuple[bool, Optional[str]]:
        """Return (False, None) — no payment method."""
        return (False, None)

    async def get_customer_balance_cents(self, *, customer_id: str) -> int:
        """Return zero balance."""
        return 0

    async def get_subscription_coupon_id(self, *, subscription_id: str) -> Optional[str]:
        """Return None — no coupon."""
        return None

    # ------------------------------------------------------------------
    # User-facing billing operations — raise BillingNotAvailableError
    # ------------------------------------------------------------------

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, str]] = None,
        coupon_id: Optional[str] = None,
        default_payment_method: Optional[str] = None,
    ) -> Any:
        """Raise — requires real payment provider."""
        raise BillingNotAvailableError()

    async def get_subscription(self, subscription_id: str) -> Any:
        """Raise — requires real payment provider."""
        raise BillingNotAvailableError()

    async def update_subscription(
        self,
        subscription_id: str,
        price_id: Optional[str] = None,
        cancel_at_period_end: Optional[bool] = None,
        proration_behavior: str = "create_prorations",
        default_payment_method: Optional[str] = None,
    ) -> Any:
        """Raise — requires real payment provider."""
        raise BillingNotAvailableError()

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Raise — requires real payment provider."""
        raise BillingNotAvailableError()

    async def create_portal_session(self, customer_id: str, return_url: str) -> Any:
        """Raise — requires real payment provider."""
        raise BillingNotAvailableError()

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
        """Raise — requires real payment provider."""
        raise BillingNotAvailableError()

    async def create_or_get_yearly_coupon(
        self,
        *,
        percent_off: int,
        duration: str = "repeating",
        duration_in_months: int = 12,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Raise — requires real payment provider."""
        raise BillingNotAvailableError()

    async def apply_coupon_to_subscription(
        self,
        *,
        subscription_id: str,
        coupon_id: str,
    ) -> Any:
        """Raise — requires real payment provider."""
        raise BillingNotAvailableError()

    async def remove_subscription_discount(self, *, subscription_id: str) -> None:
        """Raise — requires real payment provider."""
        raise BillingNotAvailableError()

    async def credit_customer_balance(
        self,
        *,
        customer_id: str,
        amount_cents: int,
        currency: str = "usd",
        description: Optional[str] = None,
    ) -> Any:
        """Raise — requires real payment provider."""
        raise BillingNotAvailableError()

    # ------------------------------------------------------------------
    # Webhook — ValueError matches Stripe adapter contract
    # ------------------------------------------------------------------

    def verify_webhook_signature(self, payload: bytes, signature: str) -> Any:
        """Raise ValueError — billing is not enabled."""
        raise ValueError("Billing is not enabled")
