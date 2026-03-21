"""Stripe entity schemas.

Based on the Stripe API reference (2024-12-18.acacia), we define entity schemas for
commonly used Stripe Core Resources: Customers, Invoices, Charges, Subscriptions,
Payment Intents, Balance, Balance Transactions, Events, Payouts, Payment Methods,
and Refunds.

These schemas follow the same style as other connectors (e.g., Asana, HubSpot, Todoist),
where each entity class inherits from our BaseEntity and adds relevant fields with
shared or per-resource metadata as needed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb


def _parse_stripe_ts(value: Any) -> Optional[datetime]:
    """Convert a Stripe unix timestamp (seconds) into a UTC datetime."""
    if value is None:
        return None
    try:
        return datetime.utcfromtimestamp(int(value))
    except (OSError, ValueError, TypeError):
        return None


class StripeBalanceEntity(BaseEntity):
    """Schema for Stripe Balance resource.

    https://stripe.com/docs/api/balance/balance_object
    """

    balance_id: str = AirweaveField(
        ..., description="Synthetic ID for the balance snapshot.", is_entity_id=True
    )
    balance_name: str = AirweaveField(
        ..., description="Display label for this balance snapshot.", embeddable=True, is_name=True
    )
    snapshot_time: datetime = AirweaveField(
        ..., description="Timestamp when the balance snapshot was taken.", is_created_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Dashboard URL for viewing the balance.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    available: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Funds that are available to be paid out, broken down by currency",
        embeddable=True,
    )
    pending: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Funds not yet available, broken down by currency",
        embeddable=True,
    )
    instant_available: Optional[List[Dict[str, Any]]] = AirweaveField(
        None,
        description="Funds available for Instant Payouts (if enabled)",
        embeddable=True,
    )
    connect_reserved: Optional[List[Dict[str, Any]]] = AirweaveField(
        None,
        description="Funds reserved for connected accounts (if using Connect)",
        embeddable=True,
    )
    livemode: bool = AirweaveField(
        False, description="Whether this balance is in live mode (vs test mode)", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Dashboard URL for the balance snapshot."""
        return self.web_url_value or ""


class StripeBalanceTransactionEntity(BaseEntity):
    """Schema for Stripe Balance Transaction resource.

    https://stripe.com/docs/api/balance_transactions
    """

    transaction_id: str = AirweaveField(
        ..., description="Stripe ID of the balance transaction.", is_entity_id=True
    )
    transaction_name: str = AirweaveField(
        ..., description="Display name of the transaction.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the transaction was created.", is_created_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Dashboard URL for viewing the transaction.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    amount: Optional[int] = AirweaveField(
        None, description="Gross amount of the transaction, in cents", embeddable=True
    )
    currency: Optional[str] = AirweaveField(
        None, description="Three-letter ISO currency code", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Text description of the transaction", embeddable=True
    )
    fee: Optional[int] = AirweaveField(
        None, description="Fees (in cents) taken from this transaction", embeddable=True
    )
    fee_details: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Detailed breakdown of fees (type, amount, application, etc.)",
        embeddable=False,
    )
    net: Optional[int] = AirweaveField(
        None, description="Net amount of the transaction, in cents", embeddable=True
    )
    reporting_category: Optional[str] = AirweaveField(
        None, description="Reporting category (e.g., 'charge', 'refund', etc.)", embeddable=True
    )
    source: Optional[str] = AirweaveField(
        None,
        description="ID of the charge or other object that caused this balance transaction",
        embeddable=False,
    )
    status: Optional[str] = AirweaveField(
        None,
        description="Status of the balance transaction (e.g., 'available', 'pending')",
        embeddable=True,
    )
    type: Optional[str] = AirweaveField(
        None, description="Transaction type (e.g., 'charge', 'refund', 'payout')", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Dashboard URL for the balance transaction."""
        return self.web_url_value or ""


class StripeChargeEntity(BaseEntity):
    """Schema for Stripe Charge entities.

    https://stripe.com/docs/api/charges
    """

    charge_id: str = AirweaveField(..., description="Stripe charge ID.", is_entity_id=True)
    charge_name: str = AirweaveField(
        ..., description="Display name of the charge.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the charge was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="Last activity timestamp for the charge.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Dashboard URL for the charge.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    amount: Optional[int] = AirweaveField(
        None, description="Amount charged in cents", embeddable=True
    )
    currency: Optional[str] = AirweaveField(
        None, description="Three-letter ISO currency code", embeddable=True
    )
    captured: bool = AirweaveField(
        False, description="Whether the charge was captured", embeddable=True
    )
    paid: bool = AirweaveField(False, description="Whether the charge was paid", embeddable=True)
    refunded: bool = AirweaveField(
        False, description="Whether the charge was refunded", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Arbitrary description of the charge", embeddable=True
    )
    receipt_url: Optional[str] = AirweaveField(
        None, description="URL to view this charge's receipt", embeddable=False
    )
    customer_id: Optional[str] = AirweaveField(
        None, description="ID of the Customer this charge belongs to", embeddable=False
    )
    invoice_id: Optional[str] = AirweaveField(
        None, description="ID of the Invoice this charge is linked to (if any)", embeddable=False
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Set of key-value pairs attached to the charge",
        embeddable=False,
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: Optional[str],
    ) -> StripeChargeEntity:
        """Build from a Stripe API charge object."""
        charge_id = data["id"]
        created_time = _parse_stripe_ts(data.get("created")) or datetime.utcnow()
        name = data.get("description") or f"Charge {charge_id}"

        customer_id = data.get("customer")
        breadcrumbs: List[Breadcrumb] = []
        if customer_id:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=customer_id,
                    name=f"Customer {customer_id}",
                    entity_type=StripeCustomerEntity.__name__,
                )
            )

        return cls(
            entity_id=charge_id,
            breadcrumbs=breadcrumbs,
            name=name,
            created_at=created_time,
            updated_at=created_time,
            charge_id=charge_id,
            charge_name=name,
            created_time=created_time,
            updated_time=created_time,
            web_url_value=web_url,
            amount=data.get("amount"),
            currency=data.get("currency"),
            captured=data.get("captured", False),
            paid=data.get("paid", False),
            refunded=data.get("refunded", False),
            description=data.get("description"),
            receipt_url=data.get("receipt_url"),
            customer_id=customer_id,
            invoice_id=data.get("invoice"),
            metadata=data.get("metadata", {}),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Dashboard URL for the charge."""
        return self.web_url_value or ""


class StripeCustomerEntity(BaseEntity):
    """Schema for Stripe Customer entities.

    https://stripe.com/docs/api/customers
    """

    customer_id: str = AirweaveField(..., description="Stripe customer ID.", is_entity_id=True)
    customer_name: str = AirweaveField(
        ..., description="Display name of the customer.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the customer was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="Timestamp of the latest update.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Dashboard URL for the customer.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    email: Optional[str] = AirweaveField(
        None, description="The customer's email address", embeddable=True
    )
    phone: Optional[str] = AirweaveField(
        None, description="The customer's phone number", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Arbitrary description of the customer", embeddable=True
    )
    currency: Optional[str] = AirweaveField(
        None,
        description="Preferred currency for the customer's recurring payments",
        embeddable=False,
    )
    default_source: Optional[str] = AirweaveField(
        None,
        description="ID of the default payment source (e.g. card) attached to this customer",
        embeddable=False,
    )
    delinquent: bool = AirweaveField(
        False, description="Whether the customer has any unpaid/overdue invoices", embeddable=True
    )
    invoice_prefix: Optional[str] = AirweaveField(
        None, description="Prefix for the customer's invoices", embeddable=False
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Set of key-value pairs attached to the customer",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Dashboard URL for the customer."""
        return self.web_url_value or ""


class StripeEventEntity(BaseEntity):
    """Schema for Stripe Event resource.

    https://stripe.com/docs/api/events
    """

    event_id: str = AirweaveField(..., description="Stripe event ID.", is_entity_id=True)
    event_name: str = AirweaveField(
        ..., description="Display name of the event.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the event was created.", is_created_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Dashboard URL for the event.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    event_type: Optional[str] = AirweaveField(
        None,
        description="The event's type (e.g., 'charge.succeeded', 'customer.created')",
        embeddable=True,
    )
    api_version: Optional[str] = AirweaveField(
        None, description="API version used to render event data", embeddable=False
    )
    data: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="The event payload. Typically includes 'object' and 'previous_attributes'.",
        embeddable=True,
    )
    livemode: bool = AirweaveField(
        False, description="Whether the event was triggered in live mode", embeddable=False
    )
    pending_webhooks: Optional[int] = AirweaveField(
        None, description="Number of webhooks yet to be delivered", embeddable=False
    )
    request: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Information on the request that created or triggered the event",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Dashboard URL for the event."""
        return self.web_url_value or ""


class StripeInvoiceEntity(BaseEntity):
    """Schema for Stripe Invoice entities.

    https://stripe.com/docs/api/invoices
    """

    invoice_id: str = AirweaveField(..., description="Stripe invoice ID.", is_entity_id=True)
    invoice_name: str = AirweaveField(
        ..., description="Display name of the invoice.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the invoice was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the invoice was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Dashboard URL for the invoice.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    customer_id: Optional[str] = AirweaveField(
        None, description="The ID of the customer this invoice belongs to", embeddable=False
    )
    number: Optional[str] = AirweaveField(
        None, description="A unique, user-facing reference for this invoice", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Invoice status (e.g., 'draft', 'open', 'paid', 'void')", embeddable=True
    )
    amount_due: Optional[int] = AirweaveField(
        None,
        description="Final amount due in cents (before any payment or credit)",
        embeddable=True,
    )
    amount_paid: Optional[int] = AirweaveField(
        None, description="Amount paid in cents", embeddable=True
    )
    amount_remaining: Optional[int] = AirweaveField(
        None, description="Amount remaining to be paid in cents", embeddable=True
    )
    due_date: Optional[datetime] = AirweaveField(
        None, description="Date on which payment is due (if applicable)", embeddable=True
    )
    paid: bool = AirweaveField(
        False, description="Whether the invoice has been fully paid", embeddable=True
    )
    currency: Optional[str] = AirweaveField(
        None, description="Three-letter ISO currency code (e.g. 'usd')", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Set of key-value pairs that can be attached to the invoice",
        embeddable=False,
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: Optional[str],
    ) -> StripeInvoiceEntity:
        """Build from a Stripe API invoice object."""
        invoice_id = data["id"]
        created_time = _parse_stripe_ts(data.get("created")) or datetime.utcnow()
        name = data.get("number") or f"Invoice {invoice_id}"
        due_date = _parse_stripe_ts(data.get("due_date"))

        customer_id = data.get("customer")
        breadcrumbs: List[Breadcrumb] = []
        if customer_id:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=customer_id,
                    name=f"Customer {customer_id}",
                    entity_type=StripeCustomerEntity.__name__,
                )
            )

        return cls(
            entity_id=invoice_id,
            breadcrumbs=breadcrumbs,
            name=name,
            created_at=created_time,
            updated_at=created_time,
            invoice_id=invoice_id,
            invoice_name=name,
            created_time=created_time,
            updated_time=created_time,
            web_url_value=web_url,
            customer_id=customer_id,
            number=data.get("number"),
            status=data.get("status"),
            amount_due=data.get("amount_due"),
            amount_paid=data.get("amount_paid"),
            amount_remaining=data.get("amount_remaining"),
            due_date=due_date,
            paid=data.get("paid", False),
            currency=data.get("currency"),
            metadata=data.get("metadata", {}),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Dashboard URL for the invoice."""
        return self.web_url_value or ""


class StripePaymentIntentEntity(BaseEntity):
    """Schema for Stripe PaymentIntent entities.

    https://stripe.com/docs/api/payment_intents
    """

    payment_intent_id: str = AirweaveField(
        ..., description="Stripe payment intent ID.", is_entity_id=True
    )
    payment_intent_name: str = AirweaveField(
        ..., description="Display name of the payment intent.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the payment intent was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="Last update timestamp for the payment intent.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Dashboard URL for the payment intent.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    amount: Optional[int] = AirweaveField(
        None,
        description="Amount in cents intended to be collected by this PaymentIntent",
        embeddable=True,
    )
    currency: Optional[str] = AirweaveField(
        None, description="Three-letter ISO currency code", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None,
        description="Status of the PaymentIntent (e.g. 'requires_payment_method', 'succeeded')",
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="Arbitrary description for the PaymentIntent", embeddable=True
    )
    customer_id: Optional[str] = AirweaveField(
        None, description="ID of the Customer this PaymentIntent is for (if any)", embeddable=False
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Set of key-value pairs attached to the PaymentIntent",
        embeddable=False,
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: Optional[str],
    ) -> StripePaymentIntentEntity:
        """Build from a Stripe API payment_intent object."""
        pi_id = data["id"]
        created_time = _parse_stripe_ts(data.get("created")) or datetime.utcnow()
        name = data.get("description") or f"Payment Intent {pi_id}"

        customer_id = data.get("customer")
        breadcrumbs: List[Breadcrumb] = []
        if customer_id:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=customer_id,
                    name=f"Customer {customer_id}",
                    entity_type=StripeCustomerEntity.__name__,
                )
            )

        return cls(
            entity_id=pi_id,
            breadcrumbs=breadcrumbs,
            name=name,
            created_at=created_time,
            updated_at=created_time,
            payment_intent_id=pi_id,
            payment_intent_name=name,
            created_time=created_time,
            updated_time=created_time,
            web_url_value=web_url,
            amount=data.get("amount"),
            currency=data.get("currency"),
            status=data.get("status"),
            description=data.get("description"),
            customer_id=customer_id,
            metadata=data.get("metadata", {}),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Dashboard URL for the payment intent."""
        return self.web_url_value or ""


class StripePaymentMethodEntity(BaseEntity):
    """Schema for Stripe PaymentMethod resource.

    https://stripe.com/docs/api/payment_methods
    """

    payment_method_id: str = AirweaveField(
        ..., description="Stripe payment method ID.", is_entity_id=True
    )
    payment_method_name: str = AirweaveField(
        ..., description="Display name of the payment method.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the payment method was created.", is_created_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Dashboard URL for the payment method.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    type: Optional[str] = AirweaveField(
        None, description="Type of the PaymentMethod (card, ideal, etc.)", embeddable=True
    )
    billing_details: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Billing information associated with the PaymentMethod",
        embeddable=True,
    )
    customer_id: Optional[str] = AirweaveField(
        None,
        description="ID of the Customer to which this PaymentMethod is saved (if any)",
        embeddable=False,
    )
    card: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description=(
            "If the PaymentMethod type is 'card', details about the card (brand, last4, etc.)"
        ),
        embeddable=True,
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Set of key-value pairs that can be attached to the PaymentMethod",
        embeddable=False,
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: Optional[str],
    ) -> StripePaymentMethodEntity:
        """Build from a Stripe API payment_method object."""
        pm_id = data["id"]
        created_time = _parse_stripe_ts(data.get("created")) or datetime.utcnow()
        name = data.get("type") or f"Payment Method {pm_id}"

        customer_id = data.get("customer")
        breadcrumbs: List[Breadcrumb] = []
        if customer_id:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=customer_id,
                    name=f"Customer {customer_id}",
                    entity_type=StripeCustomerEntity.__name__,
                )
            )

        return cls(
            entity_id=pm_id,
            breadcrumbs=breadcrumbs,
            name=name,
            created_at=created_time,
            updated_at=created_time,
            payment_method_id=pm_id,
            payment_method_name=name,
            created_time=created_time,
            web_url_value=web_url,
            type=data.get("type"),
            billing_details=data.get("billing_details", {}),
            customer_id=customer_id,
            card=data.get("card"),
            metadata=data.get("metadata", {}),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Dashboard URL for the payment method."""
        return self.web_url_value or ""


class StripePayoutEntity(BaseEntity):
    """Schema for Stripe Payout resource.

    https://stripe.com/docs/api/payouts
    """

    payout_id: str = AirweaveField(..., description="Stripe payout ID.", is_entity_id=True)
    payout_name: str = AirweaveField(
        ..., description="Display name of the payout.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the payout was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="Last update timestamp for the payout.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Dashboard URL for the payout.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    amount: Optional[int] = AirweaveField(
        None, description="Amount in cents to be transferred", embeddable=True
    )
    currency: Optional[str] = AirweaveField(
        None, description="Three-letter ISO currency code", embeddable=True
    )
    arrival_date: Optional[datetime] = AirweaveField(
        None, description="Date the payout is expected to arrive in the bank", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="An arbitrary string attached to the payout", embeddable=True
    )
    destination: Optional[str] = AirweaveField(
        None, description="ID of the bank account or card the payout was sent to", embeddable=False
    )
    method: Optional[str] = AirweaveField(
        None,
        description="The method used to send this payout (e.g., 'standard', 'instant')",
        embeddable=True,
    )
    status: Optional[str] = AirweaveField(
        None,
        description="Status of the payout (e.g., 'paid', 'pending', 'in_transit')",
        embeddable=True,
    )
    statement_descriptor: Optional[str] = AirweaveField(
        None,
        description="Extra information to be displayed on the user's bank statement",
        embeddable=True,
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Set of key-value pairs that can be attached to the payout",
        embeddable=False,
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: Optional[str],
    ) -> StripePayoutEntity:
        """Build from a Stripe API payout object."""
        payout_id = data["id"]
        created_time = _parse_stripe_ts(data.get("created")) or datetime.utcnow()
        name = data.get("description") or f"Payout {payout_id}"
        arrival_date = _parse_stripe_ts(data.get("arrival_date"))

        return cls(
            entity_id=payout_id,
            breadcrumbs=[],
            name=name,
            created_at=created_time,
            updated_at=created_time,
            payout_id=payout_id,
            payout_name=name,
            created_time=created_time,
            updated_time=created_time,
            web_url_value=web_url,
            amount=data.get("amount"),
            currency=data.get("currency"),
            arrival_date=arrival_date,
            description=data.get("description"),
            destination=data.get("destination"),
            method=data.get("method"),
            status=data.get("status"),
            statement_descriptor=data.get("statement_descriptor"),
            metadata=data.get("metadata", {}),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Dashboard URL for the payout."""
        return self.web_url_value or ""


class StripeRefundEntity(BaseEntity):
    """Schema for Stripe Refund resource.

    https://stripe.com/docs/api/refunds
    """

    refund_id: str = AirweaveField(..., description="Stripe refund ID.", is_entity_id=True)
    refund_name: str = AirweaveField(
        ..., description="Display name of the refund.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the refund was created.", is_created_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Dashboard URL for the refund.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    amount: Optional[int] = AirweaveField(
        None, description="Amount in cents refunded", embeddable=True
    )
    currency: Optional[str] = AirweaveField(
        None, description="Three-letter ISO currency code", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None,
        description="Status of the refund (e.g., 'pending', 'succeeded', 'failed')",
        embeddable=True,
    )
    reason: Optional[str] = AirweaveField(
        None,
        description="Reason for the refund (duplicate, fraudulent, requested_by_customer, etc.)",
        embeddable=True,
    )
    receipt_number: Optional[str] = AirweaveField(
        None,
        description="Transaction number that appears on email receipts issued for this refund",
        embeddable=False,
    )
    charge_id: Optional[str] = AirweaveField(
        None, description="ID of the charge being refunded", embeddable=False
    )
    payment_intent_id: Optional[str] = AirweaveField(
        None, description="ID of the PaymentIntent being refunded (if applicable)", embeddable=False
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Set of key-value pairs that can be attached to the refund",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Dashboard URL for the refund."""
        return self.web_url_value or ""


class StripeSubscriptionEntity(BaseEntity):
    """Schema for Stripe Subscription entities.

    https://stripe.com/docs/api/subscriptions
    """

    subscription_id: str = AirweaveField(
        ..., description="Stripe subscription ID.", is_entity_id=True
    )
    subscription_name: str = AirweaveField(
        ..., description="Display name of the subscription.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the subscription was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="Last update timestamp for the subscription.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Dashboard URL for the subscription.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    customer_id: Optional[str] = AirweaveField(
        None, description="The ID of the customer who owns this subscription", embeddable=False
    )
    status: Optional[str] = AirweaveField(
        None,
        description="Status of the subscription (e.g., 'active', 'past_due', 'canceled')",
        embeddable=True,
    )
    current_period_start: Optional[datetime] = AirweaveField(
        None,
        description="Start of the current billing period for this subscription",
        embeddable=True,
    )
    current_period_end: Optional[datetime] = AirweaveField(
        None,
        description="End of the current billing period for this subscription",
        embeddable=True,
    )
    cancel_at_period_end: bool = AirweaveField(
        False,
        description="Whether the subscription will cancel at the end of the current period",
        embeddable=True,
    )
    canceled_at: Optional[datetime] = AirweaveField(
        None, description="When the subscription was canceled (if any)", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Set of key-value pairs attached to the subscription",
        embeddable=False,
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: Optional[str],
    ) -> StripeSubscriptionEntity:
        """Build from a Stripe API subscription object."""
        sub_id = data["id"]
        created_time = _parse_stripe_ts(data.get("created")) or datetime.utcnow()
        name = f"Subscription {sub_id}"

        current_period_start = _parse_stripe_ts(data.get("current_period_start"))
        current_period_end = _parse_stripe_ts(data.get("current_period_end"))
        canceled_at = _parse_stripe_ts(data.get("canceled_at"))

        customer_id = data.get("customer")
        breadcrumbs: List[Breadcrumb] = []
        if customer_id:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=customer_id,
                    name=f"Customer {customer_id}",
                    entity_type=StripeCustomerEntity.__name__,
                )
            )

        return cls(
            entity_id=sub_id,
            breadcrumbs=breadcrumbs,
            name=name,
            created_at=created_time,
            updated_at=created_time,
            subscription_id=sub_id,
            subscription_name=name,
            created_time=created_time,
            updated_time=created_time,
            web_url_value=web_url,
            customer_id=customer_id,
            status=data.get("status"),
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            cancel_at_period_end=data.get("cancel_at_period_end", False),
            canceled_at=canceled_at,
            metadata=data.get("metadata", {}),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Dashboard URL for the subscription."""
        return self.web_url_value or ""
