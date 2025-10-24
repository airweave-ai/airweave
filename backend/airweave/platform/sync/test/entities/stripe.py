"""Real Stripe entities captured from actual sync for testing."""

from datetime import datetime, timezone

from airweave.platform.entities.stripe import (
    StripeBalanceEntity,
    StripeBalanceTransactionEntity,
    StripeChargeEntity,
    StripeCustomerEntity,
    StripeEventEntity,
    StripeInvoiceEntity,
    StripePaymentIntentEntity,
    StripePaymentMethodEntity,
    StripePayoutEntity,
    StripeRefundEntity,
    StripeSubscriptionEntity,
)

# ============================================================================
# BALANCE ENTITIES
# ============================================================================

# Balance with negative available (pending payouts exceed available funds)
balance_negative_available = StripeBalanceEntity(
    entity_id="balance",
    breadcrumbs=[],
    name="Account Balance",
    created_at=None,
    updated_at=None,
    available=[{"amount": -8981, "currency": "eur", "source_types": {"card": -8981}}],
    pending=[{"amount": 161848, "currency": "eur", "source_types": {"card": 161848}}],
    instant_available=[{"amount": 152867, "currency": "eur", "source_types": {"card": 152867}}],
    connect_reserved=None,
    livemode=True,
)

# ============================================================================
# BALANCE TRANSACTION ENTITIES
# ============================================================================

# Refund transaction
balance_txn_refund = StripeBalanceTransactionEntity(
    entity_id="txn_1SJwjzGm1FpXlyE5djfHf4AJ",
    breadcrumbs=[],
    name="REFUND FOR PAYMENT (Subscription update)",
    created_at=datetime(2025, 10, 19, 13, 33, 42, tzinfo=timezone.utc),
    updated_at=None,
    amount=-7785,
    currency="eur",
    description="REFUND FOR PAYMENT (Subscription update)",
    fee=0,
    fee_details=[],
    net=-7785,
    reporting_category="refund",
    source="pyr_1SJwjyGm1FpXlyE5YTPJ8nGB",
    status="available",
    type="payment_refund",
)

# Large charge with detailed fee breakdown
balance_txn_large_charge = StripeBalanceTransactionEntity(
    entity_id="txn_3SJ2E4Gm1FpXlyE51I0WA5ws",
    breadcrumbs=[],
    name="Subscription update",
    created_at=datetime(2025, 10, 17, 1, 13, 2, tzinfo=timezone.utc),
    updated_at=None,
    amount=170842,
    currency="eur",
    description="Subscription update",
    fee=8994,
    fee_details=[
        {
            "amount": 3417,
            "application": None,
            "currency": "eur",
            "description": "Stripe currency conversion fee",
            "type": "stripe_fee",
        },
        {
            "amount": 5577,
            "application": None,
            "currency": "eur",
            "description": "Stripe processing fees",
            "type": "stripe_fee",
        },
    ],
    net=161848,
    reporting_category="charge",
    source="ch_3SJ2E4Gm1FpXlyE51Vz2wLut",
    status="pending",
    type="charge",
)

# Chargeback/dispute transaction with fees
balance_txn_chargeback = StripeBalanceTransactionEntity(
    entity_id="txn_1SFsEPGm1FpXlyE58ifXz308",
    breadcrumbs=[],
    name="Chargeback withdrawal for py_3SA33iGm1FpXlyE51Y9SzJEC",
    created_at=datetime(2025, 10, 8, 7, 56, 17, tzinfo=timezone.utc),
    updated_at=None,
    amount=-7481,
    currency="eur",
    description="Chargeback withdrawal for py_3SA33iGm1FpXlyE51Y9SzJEC",
    fee=2000,
    fee_details=[
        {
            "amount": 2000,
            "application": None,
            "currency": "eur",
            "description": "Dispute fee",
            "type": "stripe_fee",
        }
    ],
    net=-9481,
    reporting_category="dispute",
    source="du_1SFpvMGm1FpXlyE5t2kpNYJ8",
    status="available",
    type="adjustment",
)

# ============================================================================
# CHARGE ENTITIES
# ============================================================================

# Large successful charge with receipt
charge_large_paid = StripeChargeEntity(
    entity_id="ch_3SJ2E4Gm1FpXlyE51Vz2wLut",
    breadcrumbs=[],
    name="Subscription update",
    created_at=datetime(2025, 10, 17, 1, 13, 2, tzinfo=timezone.utc),
    updated_at=None,
    amount=200000,
    currency="usd",
    captured=True,
    paid=True,
    refunded=False,
    description="Subscription update",
    receipt_url="https://pay.stripe.com/receipts/invoices/CAcQARoXChVhY2N0XzFQR2o1eEdtMUZwWGx5RTUo_6LZxwYyBlsz-cq0-TosFt3uaqqkoPxUI888AUmObgnRl7w8qfV1a-zh34riB3ZSDGFScxVhhZAAjzs?s=ap",
    customer_id="cus_SJpIfxbYghJq2b",
    invoice_id="in_1SJ1GqGm1FpXlyE5xiVlHvsa",
    metadata={},
)

# Fully refunded charge
charge_refunded = StripeChargeEntity(
    entity_id="py_3SGxY4Gm1FpXlyE51ppXaLwc",
    breadcrumbs=[],
    name="Subscription update",
    created_at=datetime(2025, 10, 11, 7, 49, 7, tzinfo=timezone.utc),
    updated_at=None,
    amount=9075,
    currency="usd",
    captured=True,
    paid=True,
    refunded=True,
    description="Subscription update",
    receipt_url="https://pay.stripe.com/receipts/invoices/CAcQARoXChVhY2N0XzFQR2o1eEdtMUZwWGx5RTUo_6LZxwYyBh0eyUoxrTosFrz8b3DwwAbmHk74pl3qOWzCuLBft1ZUPeIgyJkg742fKxGbjhRwUSKU92w?s=ap",
    customer_id="cus_SeuZIvZOdqVpU6",
    invoice_id="in_1SGwbgGm1FpXlyE59K7UNSD0",
    metadata={},
)

# ============================================================================
# CUSTOMER ENTITIES
# ============================================================================

# Active customer with full details
customer_active = StripeCustomerEntity(
    entity_id="cus_SJpIfxbYghJq2b",
    breadcrumbs=[],
    name="Acme Corp",
    created_at=datetime(2025, 9, 15, 14, 22, 33, tzinfo=timezone.utc),
    updated_at=None,
    email="billing@acme-corp.com",
    phone="+1-555-0123",
    description="Enterprise customer - annual subscription",
    currency="usd",
    default_source="card_1SJ2E4Gm1FpXlyE5xyz123",
    delinquent=False,
    invoice_prefix="ACME",
    metadata={"account_id": "acc_12345", "plan": "enterprise", "seats": "50"},
)

# Delinquent customer with minimal details
customer_delinquent = StripeCustomerEntity(
    entity_id="cus_T4dvHMI2tNFS6U",
    breadcrumbs=[],
    name="startup@example.com",
    created_at=datetime(2024, 12, 1, 8, 15, 0, tzinfo=timezone.utc),
    updated_at=None,
    email="startup@example.com",
    phone=None,
    description=None,
    currency="eur",
    default_source=None,
    delinquent=True,
    invoice_prefix=None,
    metadata={},
)

# ============================================================================
# EVENT ENTITIES
# ============================================================================

# Charge succeeded event with full data
event_charge_succeeded = StripeEventEntity(
    entity_id="evt_1SJ2E4Gm1FpXlyE5abc123",
    breadcrumbs=[],
    name="charge.succeeded",
    created_at=datetime(2025, 10, 17, 1, 13, 3, tzinfo=timezone.utc),
    updated_at=None,
    event_type="charge.succeeded",
    api_version="2024-12-18.acacia",
    data={
        "object": {
            "id": "ch_3SJ2E4Gm1FpXlyE51Vz2wLut",
            "amount": 200000,
            "currency": "usd",
            "customer": "cus_SJpIfxbYghJq2b",
            "description": "Subscription update",
            "paid": True,
            "status": "succeeded",
        }
    },
    livemode=True,
    pending_webhooks=2,
    request={"id": "req_xyz789", "idempotency_key": "sub_update_abc123"},
)

# Customer updated event with previous attributes
event_customer_updated = StripeEventEntity(
    entity_id="evt_1SFsEPGm1FpXlyE5def456",
    breadcrumbs=[],
    name="customer.updated",
    created_at=datetime(2025, 10, 8, 10, 30, 15, tzinfo=timezone.utc),
    updated_at=None,
    event_type="customer.updated",
    api_version="2024-12-18.acacia",
    data={
        "object": {
            "id": "cus_T4dvHMI2tNFS6U",
            "email": "newemail@example.com",
            "delinquent": True,
        },
        "previous_attributes": {"email": "oldemail@example.com", "delinquent": False},
    },
    livemode=True,
    pending_webhooks=0,
    request=None,
)

# ============================================================================
# INVOICE ENTITIES
# ============================================================================

# Paid invoice with full details
invoice_paid = StripeInvoiceEntity(
    entity_id="in_1SJ1GqGm1FpXlyE5xiVlHvsa",
    breadcrumbs=[],
    name="ACME-2025-001",
    created_at=datetime(2025, 10, 17, 0, 30, 0, tzinfo=timezone.utc),
    updated_at=None,
    customer_id="cus_SJpIfxbYghJq2b",
    number="ACME-2025-001",
    status="paid",
    amount_due=200000,
    amount_paid=200000,
    amount_remaining=0,
    due_date=datetime(2025, 11, 1, 0, 0, 0, tzinfo=timezone.utc),
    paid=True,
    currency="usd",
    metadata={"contract_id": "CNT-2025-Q4", "department": "Engineering"},
)

# Open invoice with amount due
invoice_open = StripeInvoiceEntity(
    entity_id="in_1SGdl6Gm1FpXlyE5QxKdEDfg",
    breadcrumbs=[],
    name="INV-2025-042",
    created_at=datetime(2025, 10, 10, 15, 0, 0, tzinfo=timezone.utc),
    updated_at=None,
    customer_id="cus_SwZrYLsbDX62Dx",
    number="INV-2025-042",
    status="open",
    amount_due=8900,
    amount_paid=0,
    amount_remaining=8900,
    due_date=datetime(2025, 10, 25, 0, 0, 0, tzinfo=timezone.utc),
    paid=False,
    currency="usd",
    metadata={},
)

# ============================================================================
# PAYMENT INTENT ENTITIES
# ============================================================================

# Successful payment intent
payment_intent_succeeded = StripePaymentIntentEntity(
    entity_id="pi_3SJ2E4Gm1FpXlyE5abc123",
    breadcrumbs=[],
    name="Annual subscription payment",
    created_at=datetime(2025, 10, 17, 1, 12, 0, tzinfo=timezone.utc),
    updated_at=None,
    amount=200000,
    currency="usd",
    status="succeeded",
    description="Annual subscription payment",
    customer_id="cus_SJpIfxbYghJq2b",
    metadata={"subscription_id": "sub_abc123", "plan": "enterprise_annual"},
)

# Payment intent requiring action
payment_intent_requires_action = StripePaymentIntentEntity(
    entity_id="pi_3SGehrGm1FpXlyE5def456",
    breadcrumbs=[],
    name="Monthly payment - authentication required",
    created_at=datetime(2025, 10, 18, 15, 40, 0, tzinfo=timezone.utc),
    updated_at=None,
    amount=8900,
    currency="usd",
    status="requires_action",
    description="Monthly payment - authentication required",
    customer_id="cus_SwZrYLsbDX62Dx",
    metadata={"requires_3ds": "true", "retry_count": "1"},
)

# ============================================================================
# PAYMENT METHOD ENTITIES
# ============================================================================

# Visa card payment method
payment_method_visa = StripePaymentMethodEntity(
    entity_id="pm_1SJ2E4Gm1FpXlyE5card123",
    breadcrumbs=[],
    name="Visa ending in 4242",
    created_at=datetime(2025, 9, 15, 14, 20, 0, tzinfo=timezone.utc),
    updated_at=None,
    type="card",
    billing_details={
        "address": {
            "city": "San Francisco",
            "country": "US",
            "line1": "123 Market St",
            "line2": "Suite 400",
            "postal_code": "94102",
            "state": "CA",
        },
        "email": "billing@acme-corp.com",
        "name": "Acme Corp",
        "phone": "+1-555-0123",
    },
    customer_id="cus_SJpIfxbYghJq2b",
    card={
        "brand": "visa",
        "country": "US",
        "exp_month": 12,
        "exp_year": 2027,
        "fingerprint": "Xt5EWLLDS7FJjR1c",
        "funding": "credit",
        "last4": "4242",
        "networks": {"available": ["visa"], "preferred": None},
        "three_d_secure_usage": {"supported": True},
    },
    metadata={"primary_card": "true"},
)

# SEPA debit payment method
payment_method_sepa = StripePaymentMethodEntity(
    entity_id="pm_1SDaHJGm1FpXlyE5sepa456",
    breadcrumbs=[],
    name="SEPA Debit",
    created_at=datetime(2024, 12, 1, 8, 10, 0, tzinfo=timezone.utc),
    updated_at=None,
    type="sepa_debit",
    billing_details={
        "address": {"city": "Amsterdam", "country": "NL", "postal_code": "1012 AB"},
        "email": "finance@startup.nl",
        "name": "Startup B.V.",
    },
    customer_id="cus_T4dvHMI2tNFS6U",
    card=None,
    metadata={},
)

# ============================================================================
# PAYOUT ENTITIES
# ============================================================================

# Large payout
payout_large = StripePayoutEntity(
    entity_id="po_1S9xMaGm1FpXlyE5q88cfDi0",
    breadcrumbs=[],
    name="STRIPE PAYOUT",
    created_at=datetime(2025, 9, 22, 0, 12, 16, tzinfo=timezone.utc),
    updated_at=None,
    amount=158650,
    currency="eur",
    arrival_date=datetime(2025, 9, 24, 0, 0, 0, tzinfo=timezone.utc),
    description="STRIPE PAYOUT",
    destination="ba_1RoCitGm1FpXlyE5bank123",
    method="standard",
    status="paid",
    statement_descriptor="AIRWEAVE PAYOUT",
    metadata={},
)

# Instant payout
payout_instant = StripePayoutEntity(
    entity_id="po_1SFlLiGm1FpXlyE5nppsvz1w",
    breadcrumbs=[],
    name="Instant Payout",
    created_at=datetime(2025, 10, 8, 0, 35, 22, tzinfo=timezone.utc),
    updated_at=None,
    amount=7164,
    currency="eur",
    arrival_date=datetime(2025, 10, 8, 0, 35, 22, tzinfo=timezone.utc),
    description="Instant Payout",
    destination="ba_1SFlLiGm1FpXlyE5card789",
    method="instant",
    status="paid",
    statement_descriptor="AIRWEAVE INSTANT",
    metadata={"instant_fee_applied": "true"},
)

# ============================================================================
# REFUND ENTITIES
# ============================================================================

# Full refund
refund_full = StripeRefundEntity(
    entity_id="re_3RnoCVGm1FpXlyE505lpyMZx",
    breadcrumbs=[],
    name="Refund re_3RnoCVGm1FpXlyE505lpyMZx",
    created_at=datetime(2025, 8, 23, 15, 52, 24, tzinfo=timezone.utc),
    updated_at=None,
    amount=42654,
    currency="eur",
    status="succeeded",
    reason="requested_by_customer",
    receipt_number="1234-5678",
    charge_id="ch_3RnoCVGm1FpXlyE50dlPw6fC",
    payment_intent_id="pi_3RnoCVGm1FpXlyE5xyz789",
    metadata={"refund_reason": "Customer requested cancellation", "ticket_id": "SUP-1234"},
)

# Fraudulent refund
refund_fraud = StripeRefundEntity(
    entity_id="re_3Rz2yxGm1FpXlyE50fUrqsTD",
    breadcrumbs=[],
    name="Refund re_3Rz2yxGm1FpXlyE50fUrqsTD",
    created_at=datetime(2025, 8, 23, 15, 50, 32, tzinfo=timezone.utc),
    updated_at=None,
    amount=42654,
    currency="eur",
    status="succeeded",
    reason="fraudulent",
    receipt_number="1234-5679",
    charge_id="ch_3Rz2yxGm1FpXlyE50nfP5ghd",
    payment_intent_id="pi_3Rz2yxGm1FpXlyE5abc456",
    metadata={"fraud_score": "high", "flagged_by": "system"},
)

# ============================================================================
# SUBSCRIPTION ENTITIES
# ============================================================================

# Active subscription with current period
subscription_active = StripeSubscriptionEntity(
    entity_id="sub_1SJpIfxbYghJq2b",
    breadcrumbs=[],
    name="Subscription sub_1SJpIfxbYghJq2b",
    created_at=datetime(2025, 9, 15, 14, 22, 33, tzinfo=timezone.utc),
    updated_at=None,
    customer_id="cus_SJpIfxbYghJq2b",
    status="active",
    current_period_start=datetime(2025, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
    current_period_end=datetime(2025, 11, 1, 0, 0, 0, tzinfo=timezone.utc),
    cancel_at_period_end=False,
    canceled_at=None,
    metadata={"plan": "enterprise_annual", "seats": "50", "contract": "CNT-2025-Q4"},
)

# Canceled subscription
subscription_canceled = StripeSubscriptionEntity(
    entity_id="sub_1T4dvHMI2tNFS6U",
    breadcrumbs=[],
    name="Subscription sub_1T4dvHMI2tNFS6U",
    created_at=datetime(2024, 12, 1, 8, 15, 0, tzinfo=timezone.utc),
    updated_at=None,
    customer_id="cus_T4dvHMI2tNFS6U",
    status="canceled",
    current_period_start=datetime(2025, 9, 1, 0, 0, 0, tzinfo=timezone.utc),
    current_period_end=datetime(2025, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
    cancel_at_period_end=False,
    canceled_at=datetime(2025, 9, 15, 10, 30, 0, tzinfo=timezone.utc),
    metadata={"cancellation_reason": "downgraded_to_free", "churn_risk": "high"},
)

# All entities in one list
stripe_examples = [
    # Balance
    balance_negative_available,
    # Balance Transactions
    balance_txn_refund,
    balance_txn_large_charge,
    balance_txn_chargeback,
    # Charges
    charge_large_paid,
    charge_refunded,
    # Customers
    customer_active,
    customer_delinquent,
    # Events
    event_charge_succeeded,
    event_customer_updated,
    # Invoices
    invoice_paid,
    invoice_open,
    # Payment Intents
    payment_intent_succeeded,
    payment_intent_requires_action,
    # Payment Methods
    payment_method_visa,
    payment_method_sepa,
    # Payouts
    payout_large,
    payout_instant,
    # Refunds
    refund_full,
    refund_fraud,
    # Subscriptions
    subscription_active,
    subscription_canceled,
]
