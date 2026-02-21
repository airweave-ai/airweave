"""Stripe payment gateway adapter.

Implements PaymentGatewayProtocol by wrapping the Stripe API.
Moved from integrations/stripe_client.py.
"""

from typing import Any, Dict, Optional

import stripe
from stripe.error import StripeError

from airweave.core.config import settings
from airweave.core.exceptions import ExternalServiceError
from airweave.core.protocols.payment import PaymentGatewayProtocol
from airweave.schemas.organization_billing import BillingPlan


class StripePaymentGateway(PaymentGatewayProtocol):
    """Stripe implementation of PaymentGatewayProtocol."""

    def __init__(self):
        """Initialize Stripe client."""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        # Price ID configuration
        self.price_ids = {
            BillingPlan.DEVELOPER: settings.STRIPE_DEVELOPER_MONTHLY,
            BillingPlan.PRO: settings.STRIPE_PRO_MONTHLY,
            BillingPlan.TEAM: settings.STRIPE_TEAM_MONTHLY,
            BillingPlan.ENTERPRISE: settings.STRIPE_ENTERPRISE_MONTHLY,
        }

    def get_price_id_mapping(self) -> dict[str, BillingPlan]:
        """Get reverse mapping from price IDs to plans."""
        return {price_id: plan for plan, price_id in self.price_ids.items() if price_id}

    def get_price_for_plan(self, plan: BillingPlan) -> Optional[str]:
        """Get Stripe price ID for a billing plan."""
        return self.price_ids.get(plan)

    def _sanitize_text(self, text: str) -> str:
        """Sanitize text for Stripe API (ASCII-only)."""
        if not text:
            return text

        try:
            return text.encode("ascii", "replace").decode("ascii")
        except Exception:
            return "".join(char for char in text if ord(char) < 128)

    def _clean_metadata(self, metadata: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Clean metadata values for Stripe."""
        if not metadata:
            return {}

        return {
            self._sanitize_text(str(key)): self._sanitize_text(str(value))
            for key, value in metadata.items()
        }

    # Customer operations

    async def create_customer(
        self,
        email: str,
        name: str,
        metadata: Optional[Dict[str, str]] = None,
        test_clock: Optional[str] = None,
    ) -> stripe.Customer:
        """Create a Stripe customer."""
        try:
            params: Dict[str, Any] = {
                "email": self._sanitize_text(email),
                "name": self._sanitize_text(name),
                "metadata": self._clean_metadata(metadata),
            }
            if test_clock:
                params["test_clock"] = test_clock

            return await stripe.Customer.create_async(**params)
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to create customer: {str(e)}",
            ) from e

    async def delete_customer(self, customer_id: str) -> None:
        """Delete a Stripe customer (for rollback)."""
        try:
            await stripe.Customer.delete_async(customer_id)
        except StripeError:
            # Don't raise on cleanup failures
            pass

    # Subscription operations

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, str]] = None,
        coupon_id: Optional[str] = None,
        default_payment_method: Optional[str] = None,
    ) -> stripe.Subscription:
        """Create a subscription directly (no checkout)."""
        try:
            params: Dict[str, Any] = {
                "customer": customer_id,
                "items": [{"price": price_id}],
                "metadata": self._clean_metadata(metadata),
            }
            if coupon_id:
                params["coupon"] = coupon_id
            if default_payment_method:
                params["default_payment_method"] = default_payment_method

            return await stripe.Subscription.create_async(**params)
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to create subscription: {str(e)}",
            ) from e

    async def get_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Retrieve a subscription."""
        try:
            return await stripe.Subscription.retrieve_async(subscription_id)
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to retrieve subscription: {str(e)}",
            ) from e

    async def update_subscription(
        self,
        subscription_id: str,
        price_id: Optional[str] = None,
        cancel_at_period_end: Optional[bool] = None,
        proration_behavior: str = "create_prorations",
        default_payment_method: Optional[str] = None,
    ) -> stripe.Subscription:
        """Update a subscription."""
        try:
            update_params: Dict[str, Any] = {
                "proration_behavior": proration_behavior,
            }

            # Handle price change
            if price_id:
                subscription = await self.get_subscription(subscription_id)
                items_data = subscription.get("items", {}).get("data", [])
                if not items_data:
                    raise ExternalServiceError(
                        service_name="Stripe",
                        message=f"Subscription {subscription_id} has no items",
                    )

                item_id = items_data[0]["id"]
                update_params["items"] = [{"id": item_id, "price": price_id}]

            # Handle cancellation flag
            if cancel_at_period_end is not None:
                update_params["cancel_at_period_end"] = cancel_at_period_end

            # Handle default payment method
            if default_payment_method:
                update_params["default_payment_method"] = default_payment_method

            return await stripe.Subscription.modify_async(subscription_id, **update_params)
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to update subscription: {str(e)}",
            ) from e

    async def cancel_subscription(
        self, subscription_id: str, at_period_end: bool = True
    ) -> stripe.Subscription:
        """Cancel a subscription."""
        try:
            if at_period_end:
                return await stripe.Subscription.modify_async(
                    subscription_id, cancel_at_period_end=True
                )
            else:
                return await stripe.Subscription.delete_async(subscription_id)
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to cancel subscription: {str(e)}",
            ) from e

    # Checkout operations

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> stripe.checkout.Session:
        """Create a checkout session."""
        try:
            clean_metadata = self._clean_metadata(metadata)

            return await stripe.checkout.Session.create_async(
                customer=customer_id,
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=self._sanitize_text(success_url),
                cancel_url=self._sanitize_text(cancel_url),
                metadata=clean_metadata,
                allow_promotion_codes=True,
                billing_address_collection="required",
                customer_update={
                    "address": "auto",
                    "name": "auto",
                },
                subscription_data={
                    "metadata": clean_metadata,
                },
            )
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to create checkout session: {str(e)}",
            ) from e

    # Portal operations

    async def create_portal_session(
        self, customer_id: str, return_url: str
    ) -> stripe.billing_portal.Session:
        """Create a customer portal session."""
        try:
            return await stripe.billing_portal.Session.create_async(
                customer=customer_id,
                return_url=self._sanitize_text(return_url),
            )
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to create portal session: {str(e)}",
            ) from e

    # Payment method operations

    async def detect_payment_method(
        self, subscription: stripe.Subscription
    ) -> tuple[bool, Optional[str]]:
        """Detect if subscription has a payment method.

        Returns:
            Tuple of (has_payment_method, payment_method_id)
        """
        # Check subscription-level payment method
        pm = getattr(subscription, "default_payment_method", None)
        pm_id = pm.get("id") if isinstance(pm, dict) else pm
        if pm_id:
            return True, pm_id

        # Check customer-level payment method
        try:
            customer_id = getattr(subscription, "customer", None)
            if customer_id:
                customer = await stripe.Customer.retrieve_async(customer_id)

                # Check invoice settings
                inv_settings = getattr(customer, "invoice_settings", {})
                inv_pm = getattr(inv_settings, "default_payment_method", None)
                inv_pm_id = inv_pm.get("id") if isinstance(inv_pm, dict) else inv_pm
                if inv_pm_id:
                    return True, inv_pm_id

                # Check legacy default source
                default_source = getattr(customer, "default_source", None)
                if default_source:
                    return True, default_source
        except Exception:
            pass

        return False, None

    # Webhook operations

    def verify_webhook_signature(self, payload: bytes, signature: str) -> stripe.Event:
        """Verify and construct webhook event."""
        try:
            return stripe.Webhook.construct_event(payload, signature, self.webhook_secret)
        except ValueError as e:
            raise ValueError(f"Invalid webhook payload: {e}") from e
        except stripe.error.SignatureVerificationError as e:
            raise ValueError(f"Invalid webhook signature: {e}") from e

    # Helper methods

    def extract_subscription_items(self, subscription: Any) -> list[str]:
        """Extract price IDs from subscription items."""
        price_ids = []

        try:
            # Handle both dict and object formats
            if hasattr(subscription, "items") and hasattr(subscription.items, "data"):
                items_data = subscription.items.data or []
            elif isinstance(subscription, dict):
                items_data = (subscription.get("items") or {}).get("data") or []
            else:
                return price_ids

            for item in items_data:
                price_obj = None
                if hasattr(item, "price"):
                    price_obj = item.price
                elif isinstance(item, dict):
                    price_obj = item.get("price")

                if hasattr(price_obj, "id"):
                    price_ids.append(price_obj.id)
                elif isinstance(price_obj, dict) and "id" in price_obj:
                    price_ids.append(price_obj["id"])
        except Exception:
            pass

        return price_ids

    # --------------------------- Yearly Prepay Helpers --------------------------- #

    async def create_prepay_checkout_session(
        self,
        *,
        customer_id: str,
        amount_cents: int,
        currency: str = "usd",
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> stripe.checkout.Session:
        """Create a one-time payment checkout session for yearly prepay credit."""
        try:
            clean_metadata = self._clean_metadata(metadata)
            return await stripe.checkout.Session.create_async(
                customer=customer_id,
                mode="payment",
                success_url=self._sanitize_text(success_url),
                cancel_url=self._sanitize_text(cancel_url),
                line_items=[
                    {
                        "price_data": {
                            "currency": currency,
                            "product_data": {"name": "Yearly prepay credit"},
                            "unit_amount": int(amount_cents),
                        },
                        "quantity": 1,
                    }
                ],
                payment_intent_data={
                    "setup_future_usage": "off_session",
                },
                metadata=clean_metadata,
            )
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to create prepay checkout session: {str(e)}",
            ) from e

    async def get_customer_balance_cents(self, *, customer_id: str) -> int:
        """Return the customer's current account balance in cents."""
        try:
            customer = await stripe.Customer.retrieve_async(customer_id)
            balance = getattr(customer, "balance", 0) or 0
            return int(balance)
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to retrieve customer balance: {str(e)}",
            ) from e

    async def get_subscription_coupon_id(self, *, subscription_id: str) -> Optional[str]:
        """Return active coupon id applied to the subscription, if any."""
        try:
            sub = await stripe.Subscription.retrieve_async(subscription_id)
            coupon_id: Optional[str] = None
            try:
                discount = getattr(sub, "discount", None)
                if discount is not None:
                    coupon = getattr(discount, "coupon", None)
                    if coupon is not None:
                        cid = getattr(coupon, "id", None)
                        if cid:
                            coupon_id = str(cid)
                # dict-like fallback
                if coupon_id is None and isinstance(sub, dict):
                    d = sub.get("discount")
                    if isinstance(d, dict):
                        c = d.get("coupon")
                        if isinstance(c, dict):
                            cid2 = c.get("id")
                            if cid2:
                                coupon_id = str(cid2)
            except Exception:
                coupon_id = None
            return coupon_id
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to retrieve subscription coupon: {str(e)}",
            ) from e

    async def create_or_get_yearly_coupon(
        self,
        *,
        percent_off: int,
        duration: str = "repeating",
        duration_in_months: int = 12,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> stripe.Coupon:
        """Create a reusable coupon for yearly prepay discount or retrieve by metadata key."""
        try:
            if idempotency_key:
                try:
                    coupons = await stripe.Coupon.search_async(
                        query=f"metadata['idempotency_key']:'{idempotency_key}'"
                    )
                    if getattr(coupons, "data", []):
                        return coupons.data[0]
                except Exception:
                    pass

            params: Dict[str, Any] = {
                "percent_off": percent_off,
                "duration": duration,
                "metadata": (
                    self._clean_metadata({"idempotency_key": idempotency_key or ""})
                    if idempotency_key
                    else self._clean_metadata(metadata)
                ),
            }

            if duration == "repeating":
                params["duration_in_months"] = duration_in_months

            return await stripe.Coupon.create_async(**params)
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to create yearly coupon: {str(e)}",
            ) from e

    async def apply_coupon_to_subscription(
        self,
        *,
        subscription_id: str,
        coupon_id: str,
    ) -> stripe.Subscription:
        """Apply a coupon to an existing subscription."""
        try:
            return await stripe.Subscription.modify_async(
                subscription_id,
                coupon=coupon_id,
            )
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to apply coupon to subscription: {str(e)}",
            ) from e

    async def remove_subscription_discount(self, *, subscription_id: str) -> None:
        """Remove any active discount/coupon from a subscription."""
        try:
            await stripe.Subscription.delete_discount_async(subscription_id)
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to remove subscription discount: {str(e)}",
            ) from e

    async def credit_customer_balance(
        self,
        *,
        customer_id: str,
        amount_cents: int,
        currency: str = "usd",
        description: Optional[str] = None,
    ) -> Any:
        """Credit customer's balance by the given amount (in cents)."""
        try:
            return await stripe.Customer.create_balance_transaction_async(
                customer_id,
                amount=-int(amount_cents),
                currency=currency,
                description=self._sanitize_text(description or "Yearly prepay credit"),
            )
        except StripeError as e:
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to credit customer balance: {str(e)}",
            ) from e
