"""Stripe source implementation.

We retrieve data from the Stripe API for the following core resources:
- Balance
- Balance Transactions
- Charges
- Customers
- Events
- Invoices
- Payment Intents
- Payment Methods
- Payouts
- Refunds
- Subscriptions

Then, we yield them as entities using the respective entity schemas defined in entities/stripe.py.
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import StripeAuthConfig
from airweave.platform.configs.config import StripeConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
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
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="Stripe",
    short_name="stripe",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class=StripeAuthConfig,
    config_class=StripeConfig,
    labels=["Payment"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class StripeSource(BaseSource):
    """Stripe source connector integrates with the Stripe API to extract payment and financial data.

    Synchronizes comprehensive data from your Stripe account.

    It provides access to all major Stripe resources
    including transactions, customers, subscriptions, and account analytics.
    """

    @classmethod
    async def create(
        cls, stripe_auth_config: StripeAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "StripeSource":
        """Create a new Stripe source instance."""
        instance = cls()
        instance.api_key = stripe_auth_config.api_key
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> dict:
        """Make an authenticated GET request to the Stripe API.

        The `url` should be a fully qualified endpoint (e.g., 'https://api.stripe.com/v1/customers').

        Stripe uses Basic authentication with the API key as the username and no password.
        See: https://docs.stripe.com/api/authentication
        """
        # Use Basic authentication with the API key as the username and no password
        auth = httpx.BasicAuth(username=self.api_key, password="")
        # Use a per-request timeout generous enough for Stripe pagination, but bounded
        response = await client.get(url, auth=auth, timeout=20.0)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _parse_unix_timestamp(value: Optional[int]) -> Optional[datetime]:
        """Convert a unix timestamp (seconds) into a UTC datetime."""
        if value is None:
            return None
        try:
            return datetime.utcfromtimestamp(value)
        except (OSError, ValueError):
            return None

    def _dashboard_base(self, livemode: Optional[bool]) -> str:
        """Return the base Stripe dashboard URL for live/test mode."""
        prefix = "" if livemode else "test/"
        return f"https://dashboard.stripe.com/{prefix}"

    def _build_dashboard_url(
        self,
        resource: str,
        record_id: Optional[str],
        livemode: Optional[bool],
        trailing: Optional[str] = None,
    ) -> Optional[str]:
        """Construct a Stripe dashboard URL for a resource."""
        base = self._dashboard_base(livemode)
        segments = [resource]
        if record_id:
            segments.append(record_id)
        if trailing:
            segments.append(trailing)
        path = "/".join(seg for seg in segments if seg)
        return f"{base}{path}"

    async def _generate_balance_entity(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[StripeBalanceEntity, None]:
        """Retrieve the current account balance (single object) from.

        GET https://api.stripe.com/v1/balance
        Yields exactly one StripeBalanceEntity if successful.
        """
        url = "https://api.stripe.com/v1/balance"
        data = await self._get_with_auth(client, url)

        snapshot_time = datetime.utcnow()
        livemode = data.get("livemode", False)
        web_url = self._build_dashboard_url("balance", None, livemode)

        # Create the entity with the raw data structures from Stripe
        # This avoids any issues with nested dictionaries like source_types
        # We don't manually extract nested fields but pass them directly as they are
        yield StripeBalanceEntity(
            # Base fields
            entity_id="balance",
            breadcrumbs=[],
            name="Account Balance",
            created_at=snapshot_time,
            updated_at=snapshot_time,
            # API fields
            balance_id="balance",
            balance_name="Account Balance",
            snapshot_time=snapshot_time,
            web_url_value=web_url,
            available=data.get("available", []),
            pending=data.get("pending", []),
            instant_available=data.get("instant_available"),
            connect_reserved=data.get("connect_reserved"),
            livemode=livemode,
        )

    async def _generate_balance_transaction_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[StripeBalanceTransactionEntity, None]:
        """Retrieve balance transactions in a paginated loop from.

        GET https://api.stripe.com/v1/balance_transactions
        Yields StripeBalanceTransactionEntity objects.
        """
        base_url = "https://api.stripe.com/v1/balance_transactions?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for txn in data.get("data", []):
                # Convert unix timestamp to datetime
                created_time = self._parse_unix_timestamp(txn.get("created")) or datetime.utcnow()

                # Create name from description or fallback
                transaction_id = txn["id"]
                name = txn.get("description") or f"Transaction {transaction_id}"
                web_url = self._build_dashboard_url(
                    "balance/history", transaction_id, txn.get("livemode")
                )

                yield StripeBalanceTransactionEntity(
                    # Base fields
                    entity_id=transaction_id,
                    breadcrumbs=[],
                    name=name,
                    created_at=created_time,
                    updated_at=None,  # Transactions don't update
                    # API fields
                    transaction_id=transaction_id,
                    transaction_name=name,
                    created_time=created_time,
                    web_url_value=web_url,
                    amount=txn.get("amount"),
                    currency=txn.get("currency"),
                    description=txn.get("description"),
                    fee=txn.get("fee"),
                    fee_details=txn.get("fee_details", []),
                    net=txn.get("net"),
                    reporting_category=txn.get("reporting_category"),
                    source=txn.get("source"),
                    status=txn.get("status"),
                    type=txn.get("type"),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_charge_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[StripeChargeEntity, None]:
        """Retrieve a list of charges.

          GET https://api.stripe.com/v1/charges
        Paginated, yields StripeChargeEntity objects.
        """
        base_url = "https://api.stripe.com/v1/charges?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for charge in data.get("data", []):
                # Convert unix timestamp to datetime
                created_time = (
                    self._parse_unix_timestamp(charge.get("created")) or datetime.utcnow()
                )

                # Create name from description or fallback
                charge_id = charge["id"]
                name = charge.get("description") or f"Charge {charge_id}"
                web_url = self._build_dashboard_url("payments", charge_id, charge.get("livemode"))
                customer_id = charge.get("customer")
                breadcrumbs: list[Breadcrumb] = []
                if customer_id:
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=customer_id,
                            name=f"Customer {customer_id}",
                            entity_type=StripeCustomerEntity.__name__,
                        )
                    )

                yield StripeChargeEntity(
                    # Base fields
                    entity_id=charge_id,
                    breadcrumbs=breadcrumbs,
                    name=name,
                    created_at=created_time,
                    updated_at=created_time,
                    # API fields
                    charge_id=charge_id,
                    charge_name=name,
                    created_time=created_time,
                    updated_time=created_time,
                    web_url_value=web_url,
                    amount=charge.get("amount"),
                    currency=charge.get("currency"),
                    captured=charge.get("captured", False),
                    paid=charge.get("paid", False),
                    refunded=charge.get("refunded", False),
                    description=charge.get("description"),
                    receipt_url=charge.get("receipt_url"),
                    customer_id=charge.get("customer"),
                    invoice_id=charge.get("invoice"),
                    metadata=charge.get("metadata", {}),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_customer_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[StripeCustomerEntity, None]:
        """Retrieve a list of customers.

        GET https://api.stripe.com/v1/customers
        Paginated, yields StripeCustomerEntity objects.
        """
        base_url = "https://api.stripe.com/v1/customers?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for cust in data.get("data", []):
                # Convert unix timestamp to datetime
                created_time = self._parse_unix_timestamp(cust.get("created")) or datetime.utcnow()

                # Create name from name field or email
                customer_id = cust["id"]
                name = cust.get("name") or cust.get("email") or f"Customer {customer_id}"
                web_url = self._build_dashboard_url("customers", customer_id, cust.get("livemode"))

                yield StripeCustomerEntity(
                    # Base fields
                    entity_id=customer_id,
                    breadcrumbs=[],
                    name=name,
                    created_at=created_time,
                    updated_at=created_time,
                    # API fields
                    customer_id=customer_id,
                    customer_name=name,
                    created_time=created_time,
                    updated_time=created_time,
                    web_url_value=web_url,
                    email=cust.get("email"),
                    phone=cust.get("phone"),
                    description=cust.get("description"),
                    currency=cust.get("currency"),
                    default_source=cust.get("default_source"),
                    delinquent=cust.get("delinquent", False),
                    invoice_prefix=cust.get("invoice_prefix"),
                    metadata=cust.get("metadata", {}),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_event_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[StripeEventEntity, None]:
        """Retrieve a list of events.

        GET https://api.stripe.com/v1/events
        Paginated, yields StripeEventEntity objects.
        """
        base_url = "https://api.stripe.com/v1/events?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for evt in data.get("data", []):
                # Convert unix timestamp to datetime
                created_time = self._parse_unix_timestamp(evt.get("created")) or datetime.utcnow()

                # Create name from event type
                event_id = evt["id"]
                name = evt.get("type") or f"Event {event_id}"
                web_url = self._build_dashboard_url("events", event_id, evt.get("livemode"))

                yield StripeEventEntity(
                    # Base fields
                    entity_id=event_id,
                    breadcrumbs=[],
                    name=name,
                    created_at=created_time,
                    updated_at=created_time,
                    # API fields
                    event_id=event_id,
                    event_name=name,
                    created_time=created_time,
                    web_url_value=web_url,
                    event_type=evt.get("type"),
                    api_version=evt.get("api_version"),
                    data=evt.get("data", {}),
                    livemode=evt.get("livemode", False),
                    pending_webhooks=evt.get("pending_webhooks"),
                    request=evt.get("request"),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_invoice_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[StripeInvoiceEntity, None]:
        """Retrieve a list of invoices.

        GET https://api.stripe.com/v1/invoices
        Paginated, yields StripeInvoiceEntity objects.
        """
        base_url = "https://api.stripe.com/v1/invoices?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for inv in data.get("data", []):
                # Convert unix timestamps to datetime
                created_time = self._parse_unix_timestamp(inv.get("created")) or datetime.utcnow()

                due_date_timestamp = inv.get("due_date")
                due_date = (
                    datetime.utcfromtimestamp(due_date_timestamp) if due_date_timestamp else None
                )

                # Create name from number or fallback
                invoice_id = inv["id"]
                name = inv.get("number") or f"Invoice {invoice_id}"
                web_url = self._build_dashboard_url("invoices", invoice_id, inv.get("livemode"))
                customer_id = inv.get("customer")
                breadcrumbs: List[Breadcrumb] = []
                if customer_id:
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=customer_id,
                            name=f"Customer {customer_id}",
                            entity_type=StripeCustomerEntity.__name__,
                        )
                    )

                yield StripeInvoiceEntity(
                    # Base fields
                    entity_id=invoice_id,
                    breadcrumbs=breadcrumbs,
                    name=name,
                    created_at=created_time,
                    updated_at=created_time,
                    # API fields
                    invoice_id=invoice_id,
                    invoice_name=name,
                    created_time=created_time,
                    updated_time=created_time,
                    web_url_value=web_url,
                    customer_id=inv.get("customer"),
                    number=inv.get("number"),
                    status=inv.get("status"),
                    amount_due=inv.get("amount_due"),
                    amount_paid=inv.get("amount_paid"),
                    amount_remaining=inv.get("amount_remaining"),
                    due_date=due_date,
                    paid=inv.get("paid", False),
                    currency=inv.get("currency"),
                    metadata=inv.get("metadata", {}),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_payment_intent_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[StripePaymentIntentEntity, None]:
        """Retrieve a list of payment intents.

        GET https://api.stripe.com/v1/payment_intents
        Paginated, yields StripePaymentIntentEntity objects.
        """
        base_url = "https://api.stripe.com/v1/payment_intents?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for pi in data.get("data", []):
                # Convert unix timestamp to datetime
                created_time = self._parse_unix_timestamp(pi.get("created")) or datetime.utcnow()

                # Create name from description or fallback
                payment_intent_id = pi["id"]
                name = pi.get("description") or f"Payment Intent {payment_intent_id}"
                web_url = self._build_dashboard_url(
                    "payments", payment_intent_id, pi.get("livemode")
                )
                customer_id = pi.get("customer")
                breadcrumbs: List[Breadcrumb] = []
                if customer_id:
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=customer_id,
                            name=f"Customer {customer_id}",
                            entity_type=StripeCustomerEntity.__name__,
                        )
                    )

                yield StripePaymentIntentEntity(
                    # Base fields
                    entity_id=payment_intent_id,
                    breadcrumbs=breadcrumbs,
                    name=name,
                    created_at=created_time,
                    updated_at=created_time,
                    # API fields
                    payment_intent_id=payment_intent_id,
                    payment_intent_name=name,
                    created_time=created_time,
                    updated_time=created_time,
                    web_url_value=web_url,
                    amount=pi.get("amount"),
                    currency=pi.get("currency"),
                    status=pi.get("status"),
                    description=pi.get("description"),
                    customer_id=pi.get("customer"),
                    metadata=pi.get("metadata", {}),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_payment_method_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[StripePaymentMethodEntity, None]:
        """Retrieve a list of payment methods for the account or for a specific customer.

        The typical GET is: https://api.stripe.com/v1/payment_methods?customer=<id>&type=<type>
        For demonstration, we'll assume you pass a type of 'card' for all of them.
        Paginated, yields StripePaymentMethodEntity objects.
        """
        # Adjust as needed to retrieve the correct PaymentMethods.
        base_url = "https://api.stripe.com/v1/payment_methods?limit=100&type=card"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for pm in data.get("data", []):
                # Convert unix timestamp to datetime
                created_time = self._parse_unix_timestamp(pm.get("created")) or datetime.utcnow()

                # Create name from type
                payment_method_id = pm["id"]
                name = pm.get("type") or f"Payment Method {payment_method_id}"
                web_url = self._build_dashboard_url(
                    "payment_methods", payment_method_id, pm.get("livemode")
                )
                customer_id = pm.get("customer")
                breadcrumbs: List[Breadcrumb] = []
                if customer_id:
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=customer_id,
                            name=f"Customer {customer_id}",
                            entity_type=StripeCustomerEntity.__name__,
                        )
                    )

                yield StripePaymentMethodEntity(
                    # Base fields
                    entity_id=payment_method_id,
                    breadcrumbs=breadcrumbs,
                    name=name,
                    created_at=created_time,
                    updated_at=created_time,
                    # API fields
                    payment_method_id=payment_method_id,
                    payment_method_name=name,
                    created_time=created_time,
                    web_url_value=web_url,
                    type=pm.get("type"),
                    billing_details=pm.get("billing_details", {}),
                    customer_id=pm.get("customer"),
                    card=pm.get("card"),
                    metadata=pm.get("metadata", {}),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_payout_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[StripePayoutEntity, None]:
        """Retrieve a list of payouts.

        GET https://api.stripe.com/v1/payouts
        Paginated, yields StripePayoutEntity objects.
        """
        base_url = "https://api.stripe.com/v1/payouts?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for payout in data.get("data", []):
                # Convert unix timestamps to datetime
                created_time = (
                    self._parse_unix_timestamp(payout.get("created")) or datetime.utcnow()
                )

                arrival_date_timestamp = payout.get("arrival_date")
                arrival_date = (
                    datetime.utcfromtimestamp(arrival_date_timestamp)
                    if arrival_date_timestamp
                    else None
                )

                # Create name from description or fallback
                payout_id = payout["id"]
                name = payout.get("description") or f"Payout {payout_id}"
                web_url = self._build_dashboard_url("payouts", payout_id, payout.get("livemode"))

                yield StripePayoutEntity(
                    # Base fields
                    entity_id=payout_id,
                    breadcrumbs=[],
                    name=name,
                    created_at=created_time,
                    updated_at=created_time,
                    # API fields
                    payout_id=payout_id,
                    payout_name=name,
                    created_time=created_time,
                    updated_time=created_time,
                    web_url_value=web_url,
                    amount=payout.get("amount"),
                    currency=payout.get("currency"),
                    arrival_date=arrival_date,
                    description=payout.get("description"),
                    destination=payout.get("destination"),
                    method=payout.get("method"),
                    status=payout.get("status"),
                    statement_descriptor=payout.get("statement_descriptor"),
                    metadata=payout.get("metadata", {}),
                )
            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_refund_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[StripeRefundEntity, None]:
        """Retrieve a list of refunds.

        GET https://api.stripe.com/v1/refunds
        Paginated, yields StripeRefundEntity objects.
        """
        base_url = "https://api.stripe.com/v1/refunds?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for refund in data.get("data", []):
                # Convert unix timestamp to datetime
                created_time = (
                    self._parse_unix_timestamp(refund.get("created")) or datetime.utcnow()
                )

                # Create name
                refund_id = refund["id"]
                name = f"Refund {refund_id}"
                web_url = self._build_dashboard_url("refunds", refund_id, refund.get("livemode"))

                yield StripeRefundEntity(
                    # Base fields
                    entity_id=refund_id,
                    breadcrumbs=[],
                    name=name,
                    created_at=created_time,
                    updated_at=created_time,
                    # API fields
                    refund_id=refund_id,
                    refund_name=name,
                    created_time=created_time,
                    web_url_value=web_url,
                    amount=refund.get("amount"),
                    currency=refund.get("currency"),
                    status=refund.get("status"),
                    reason=refund.get("reason"),
                    receipt_number=refund.get("receipt_number"),
                    charge_id=refund.get("charge"),
                    payment_intent_id=refund.get("payment_intent"),
                    metadata=refund.get("metadata", {}),
                )
            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_subscription_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[StripeSubscriptionEntity, None]:
        """Retrieve a list of subscriptions.

        GET https://api.stripe.com/v1/subscriptions
        Paginated, yields StripeSubscriptionEntity objects.
        """
        base_url = "https://api.stripe.com/v1/subscriptions?limit=100"
        url = base_url

        while url:
            data = await self._get_with_auth(client, url)
            for sub in data.get("data", []):
                # Convert unix timestamps to datetime
                created_time = self._parse_unix_timestamp(sub.get("created")) or datetime.utcnow()

                current_period_start_timestamp = sub.get("current_period_start")
                current_period_start = (
                    datetime.utcfromtimestamp(current_period_start_timestamp)
                    if current_period_start_timestamp
                    else None
                )

                current_period_end_timestamp = sub.get("current_period_end")
                current_period_end = (
                    datetime.utcfromtimestamp(current_period_end_timestamp)
                    if current_period_end_timestamp
                    else None
                )

                canceled_at_timestamp = sub.get("canceled_at")
                canceled_at = (
                    datetime.utcfromtimestamp(canceled_at_timestamp)
                    if canceled_at_timestamp
                    else None
                )

                # Create name
                subscription_id = sub["id"]
                name = f"Subscription {subscription_id}"
                web_url = self._build_dashboard_url(
                    "subscriptions", subscription_id, sub.get("livemode")
                )
                customer_id = sub.get("customer")
                breadcrumbs: List[Breadcrumb] = []
                if customer_id:
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=customer_id,
                            name=f"Customer {customer_id}",
                            entity_type=StripeCustomerEntity.__name__,
                        )
                    )

                yield StripeSubscriptionEntity(
                    # Base fields
                    entity_id=subscription_id,
                    breadcrumbs=breadcrumbs,
                    name=name,
                    created_at=created_time,
                    updated_at=created_time,
                    # API fields
                    subscription_id=subscription_id,
                    subscription_name=name,
                    created_time=created_time,
                    updated_time=created_time,
                    web_url_value=web_url,
                    customer_id=sub.get("customer"),
                    status=sub.get("status"),
                    current_period_start=current_period_start,
                    current_period_end=current_period_end,
                    cancel_at_period_end=sub.get("cancel_at_period_end", False),
                    canceled_at=canceled_at,
                    metadata=sub.get("metadata", {}),
                )

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        """Generate all Stripe entities.

        - Balance
        - Balance Transactions
        - Charges
        - Customers
        - Events
        - Invoices
        - Payment Intents
        - Payment Methods
        - Payouts
        - Refunds
        - Subscriptions
        """
        # Slightly higher default timeout to accommodate Stripe pagination bursts
        async with self.http_client(timeout=20.0) as client:
            # 1) Single Balance resource
            async for balance_entity in self._generate_balance_entity(client):
                yield balance_entity

            # 2) Balance Transactions
            async for txn_entity in self._generate_balance_transaction_entities(client):
                yield txn_entity

            # 3) Charges
            async for charge_entity in self._generate_charge_entities(client):
                yield charge_entity

            # 4) Customers
            async for customer_entity in self._generate_customer_entities(client):
                yield customer_entity

            # 5) Events
            async for event_entity in self._generate_event_entities(client):
                yield event_entity

            # 6) Invoices
            async for invoice_entity in self._generate_invoice_entities(client):
                yield invoice_entity

            # 7) Payment Intents
            async for pi_entity in self._generate_payment_intent_entities(client):
                yield pi_entity

            # 8) Payment Methods
            async for pm_entity in self._generate_payment_method_entities(client):
                yield pm_entity

            # 9) Payouts
            async for payout_entity in self._generate_payout_entities(client):
                yield payout_entity

            # 10) Refunds
            async for refund_entity in self._generate_refund_entities(client):
                yield refund_entity

            # 11) Subscriptions
            async for sub_entity in self._generate_subscription_entities(client):
                yield sub_entity

    async def validate(self) -> bool:
        """Verify Stripe API key by pinging a lightweight endpoint (/v1/balance)."""
        if not getattr(self, "api_key", None):
            self.logger.error("Stripe validation failed: missing API key.")
            return False
        try:
            async with self.http_client(timeout=10.0) as client:
                # Reuse the authenticated helper for consistency
                await self._get_with_auth(client, "https://api.stripe.com/v1/balance")
                return True
        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"Stripe validation failed: HTTP {e.response.status_code} - {e.response.text[:200]}"
            )
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during Stripe validation: {e}")
            return False
