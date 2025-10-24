"""Stripe entity schemas.

Based on the Stripe API reference (2024-12-18.acacia), we define entity schemas for
commonly used Stripe Core Resources: Customers, Invoices, Charges, Subscriptions,
Payment Intents, Balance, Balance Transactions, Events, Payouts, Payment Methods,
and Refunds.

These schemas follow the same style as other connectors (e.g., Asana, HubSpot, Todoist),
where each entity class inherits from our BaseEntity and adds relevant fields with
shared or per-resource metadata as needed.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class StripeBalanceEntity(BaseEntity):
    """Schema for Stripe Balance resource.

    https://stripe.com/docs/api/balance/balance_object
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id ("balance" - single resource)
    # - breadcrumbs (empty - balance is top-level)
    # - name ("Account Balance")
    # - created_at (None - balance is a snapshot, not created)
    # - updated_at (None - balance is a snapshot, not updated)

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


class StripeBalanceTransactionEntity(BaseEntity):
    """Schema for Stripe Balance Transaction resource.

    https://stripe.com/docs/api/balance_transactions
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (transaction ID)
    # - breadcrumbs (empty - transactions are top-level)
    # - name (from description or "Transaction {id}")
    # - created_at (from created timestamp)
    # - updated_at (None - transactions don't update)

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


class StripeChargeEntity(BaseEntity):
    """Schema for Stripe Charge entities.

    https://stripe.com/docs/api/charges
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (charge ID)
    # - breadcrumbs (empty - charges are top-level)
    # - name (from description or "Charge {id}")
    # - created_at (from created timestamp)
    # - updated_at (None - charges don't update)

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


class StripeCustomerEntity(BaseEntity):
    """Schema for Stripe Customer entities.

    https://stripe.com/docs/api/customers
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (customer ID)
    # - breadcrumbs (empty - customers are top-level)
    # - name (from name field or email)
    # - created_at (from created timestamp)
    # - updated_at (None - customers don't have update timestamp)

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


class StripeEventEntity(BaseEntity):
    """Schema for Stripe Event resource.

    https://stripe.com/docs/api/events
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (event ID)
    # - breadcrumbs (empty - events are top-level)
    # - name (from event_type)
    # - created_at (from created timestamp)
    # - updated_at (None - events don't update)

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


class StripeInvoiceEntity(BaseEntity):
    """Schema for Stripe Invoice entities.

    https://stripe.com/docs/api/invoices
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (invoice ID)
    # - breadcrumbs (empty - invoices are top-level)
    # - name (from number or "Invoice {id}")
    # - created_at (from created timestamp)
    # - updated_at (None - invoices don't have update timestamp)

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


class StripePaymentIntentEntity(BaseEntity):
    """Schema for Stripe PaymentIntent entities.

    https://stripe.com/docs/api/payment_intents
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (payment intent ID)
    # - breadcrumbs (empty - payment intents are top-level)
    # - name (from description or "Payment Intent {id}")
    # - created_at (from created timestamp)
    # - updated_at (None - payment intents don't have update timestamp)

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


class StripePaymentMethodEntity(BaseEntity):
    """Schema for Stripe PaymentMethod resource.

    https://stripe.com/docs/api/payment_methods
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (payment method ID)
    # - breadcrumbs (empty - payment methods are top-level)
    # - name (from type or "Payment Method {id}")
    # - created_at (from created timestamp)
    # - updated_at (None - payment methods don't have update timestamp)

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


class StripePayoutEntity(BaseEntity):
    """Schema for Stripe Payout resource.

    https://stripe.com/docs/api/payouts
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (payout ID)
    # - breadcrumbs (empty - payouts are top-level)
    # - name (from description or "Payout {id}")
    # - created_at (from created timestamp)
    # - updated_at (None - payouts don't have update timestamp)

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


class StripeRefundEntity(BaseEntity):
    """Schema for Stripe Refund resource.

    https://stripe.com/docs/api/refunds
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (refund ID)
    # - breadcrumbs (empty - refunds are top-level)
    # - name ("Refund {id}")
    # - created_at (from created timestamp)
    # - updated_at (None - refunds don't have update timestamp)

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


class StripeSubscriptionEntity(BaseEntity):
    """Schema for Stripe Subscription entities.

    https://stripe.com/docs/api/subscriptions
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (subscription ID)
    # - breadcrumbs (empty - subscriptions are top-level)
    # - name ("Subscription {id}")
    # - created_at (from created timestamp)
    # - updated_at (None - subscriptions don't have update timestamp)

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
