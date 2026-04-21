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

from __future__ import annotations

import base64
from datetime import datetime
from typing import TYPE_CHECKING, AsyncGenerator, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import AuthProviderKind, SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import StripeAuthConfig
from airweave.platform.configs.config import StripeConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
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
    _parse_stripe_ts,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup

_parse_unix_timestamp = _parse_stripe_ts


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
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: StripeConfig,
    ) -> StripeSource:
        """Create a new Stripe source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if auth.provider_kind == AuthProviderKind.CREDENTIAL:
            instance._api_key = auth.credentials.api_key
        else:
            instance._api_key = await auth.get_token()
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str) -> dict:
        """Make an authenticated GET request to the Stripe API.

        Stripe uses Basic authentication with the API key as the username and no password.
        See: https://docs.stripe.com/api/authentication
        """
        auth_str = base64.b64encode(f"{self._api_key}:".encode()).decode()
        headers = {"Authorization": f"Basic {auth_str}"}
        response = await self.http_client.get(url, headers=headers, timeout=20.0)
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

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

    async def _generate_balance_entity(self) -> AsyncGenerator[StripeBalanceEntity, None]:
        """Retrieve the current account balance (single object) from.

        GET https://api.stripe.com/v1/balance
        Yields exactly one StripeBalanceEntity if successful.
        """
        url = "https://api.stripe.com/v1/balance"
        data = await self._get(url)

        snapshot_time = datetime.utcnow()
        livemode = data.get("livemode", False)
        web_url = self._build_dashboard_url("balance", None, livemode)

        yield StripeBalanceEntity(
            entity_id="balance",
            breadcrumbs=[],
            name="Account Balance",
            created_at=snapshot_time,
            updated_at=snapshot_time,
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
        self,
    ) -> AsyncGenerator[StripeBalanceTransactionEntity, None]:
        """Retrieve balance transactions in a paginated loop from.

        GET https://api.stripe.com/v1/balance_transactions
        Yields StripeBalanceTransactionEntity objects.
        """
        base_url = "https://api.stripe.com/v1/balance_transactions?limit=100"
        url = base_url

        while url:
            data = await self._get(url)
            for txn in data.get("data", []):
                created_time = _parse_unix_timestamp(txn.get("created")) or datetime.utcnow()

                transaction_id = txn["id"]
                name = txn.get("description") or f"Transaction {transaction_id}"
                web_url = self._build_dashboard_url(
                    "balance/history", transaction_id, txn.get("livemode")
                )

                yield StripeBalanceTransactionEntity(
                    entity_id=transaction_id,
                    breadcrumbs=[],
                    name=name,
                    created_at=created_time,
                    updated_at=None,
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

    async def _generate_charge_entities(self) -> AsyncGenerator[StripeChargeEntity, None]:
        """Retrieve a list of charges.

          GET https://api.stripe.com/v1/charges
        Paginated, yields StripeChargeEntity objects.
        """
        base_url = "https://api.stripe.com/v1/charges?limit=100"
        url = base_url

        while url:
            data = await self._get(url)
            for charge in data.get("data", []):
                web_url = self._build_dashboard_url(
                    "payments", charge["id"], charge.get("livemode")
                )
                yield StripeChargeEntity.from_api(charge, web_url=web_url)

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_customer_entities(self) -> AsyncGenerator[StripeCustomerEntity, None]:
        """Retrieve a list of customers.

        GET https://api.stripe.com/v1/customers
        Paginated, yields StripeCustomerEntity objects.
        """
        base_url = "https://api.stripe.com/v1/customers?limit=100"
        url = base_url

        while url:
            data = await self._get(url)
            for cust in data.get("data", []):
                created_time = _parse_unix_timestamp(cust.get("created")) or datetime.utcnow()

                customer_id = cust["id"]
                name = cust.get("name") or cust.get("email") or f"Customer {customer_id}"
                web_url = self._build_dashboard_url("customers", customer_id, cust.get("livemode"))

                yield StripeCustomerEntity(
                    entity_id=customer_id,
                    breadcrumbs=[],
                    name=name,
                    created_at=created_time,
                    updated_at=created_time,
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

    async def _generate_event_entities(self) -> AsyncGenerator[StripeEventEntity, None]:
        """Retrieve a list of events.

        GET https://api.stripe.com/v1/events
        Paginated, yields StripeEventEntity objects.
        """
        base_url = "https://api.stripe.com/v1/events?limit=100"
        url = base_url

        while url:
            data = await self._get(url)
            for evt in data.get("data", []):
                created_time = _parse_unix_timestamp(evt.get("created")) or datetime.utcnow()

                event_id = evt["id"]
                name = evt.get("type") or f"Event {event_id}"
                web_url = self._build_dashboard_url("events", event_id, evt.get("livemode"))

                yield StripeEventEntity(
                    entity_id=event_id,
                    breadcrumbs=[],
                    name=name,
                    created_at=created_time,
                    updated_at=created_time,
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

    async def _generate_invoice_entities(self) -> AsyncGenerator[StripeInvoiceEntity, None]:
        """Retrieve a list of invoices.

        GET https://api.stripe.com/v1/invoices
        Paginated, yields StripeInvoiceEntity objects.
        """
        base_url = "https://api.stripe.com/v1/invoices?limit=100"
        url = base_url

        while url:
            data = await self._get(url)
            for inv in data.get("data", []):
                web_url = self._build_dashboard_url("invoices", inv["id"], inv.get("livemode"))
                yield StripeInvoiceEntity.from_api(inv, web_url=web_url)

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_payment_intent_entities(
        self,
    ) -> AsyncGenerator[StripePaymentIntentEntity, None]:
        """Retrieve a list of payment intents.

        GET https://api.stripe.com/v1/payment_intents
        Paginated, yields StripePaymentIntentEntity objects.
        """
        base_url = "https://api.stripe.com/v1/payment_intents?limit=100"
        url = base_url

        while url:
            data = await self._get(url)
            for pi in data.get("data", []):
                web_url = self._build_dashboard_url("payments", pi["id"], pi.get("livemode"))
                yield StripePaymentIntentEntity.from_api(pi, web_url=web_url)

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_payment_method_entities(
        self,
    ) -> AsyncGenerator[StripePaymentMethodEntity, None]:
        """Retrieve a list of payment methods for the account or for a specific customer.

        The typical GET is: https://api.stripe.com/v1/payment_methods?customer=<id>&type=<type>
        For demonstration, we'll assume you pass a type of 'card' for all of them.
        Paginated, yields StripePaymentMethodEntity objects.
        """
        base_url = "https://api.stripe.com/v1/payment_methods?limit=100&type=card"
        url = base_url

        while url:
            data = await self._get(url)
            for pm in data.get("data", []):
                web_url = self._build_dashboard_url("payment_methods", pm["id"], pm.get("livemode"))
                yield StripePaymentMethodEntity.from_api(pm, web_url=web_url)

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_payout_entities(self) -> AsyncGenerator[StripePayoutEntity, None]:
        """Retrieve a list of payouts.

        GET https://api.stripe.com/v1/payouts
        Paginated, yields StripePayoutEntity objects.
        """
        base_url = "https://api.stripe.com/v1/payouts?limit=100"
        url = base_url

        while url:
            data = await self._get(url)
            for payout in data.get("data", []):
                web_url = self._build_dashboard_url("payouts", payout["id"], payout.get("livemode"))
                yield StripePayoutEntity.from_api(payout, web_url=web_url)
            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def _generate_refund_entities(self) -> AsyncGenerator[StripeRefundEntity, None]:
        """Retrieve a list of refunds.

        GET https://api.stripe.com/v1/refunds
        Paginated, yields StripeRefundEntity objects.
        """
        base_url = "https://api.stripe.com/v1/refunds?limit=100"
        url = base_url

        while url:
            data = await self._get(url)
            for refund in data.get("data", []):
                created_time = _parse_unix_timestamp(refund.get("created")) or datetime.utcnow()

                refund_id = refund["id"]
                name = f"Refund {refund_id}"
                web_url = self._build_dashboard_url("refunds", refund_id, refund.get("livemode"))

                yield StripeRefundEntity(
                    entity_id=refund_id,
                    breadcrumbs=[],
                    name=name,
                    created_at=created_time,
                    updated_at=created_time,
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
        self,
    ) -> AsyncGenerator[StripeSubscriptionEntity, None]:
        """Retrieve a list of subscriptions.

        GET https://api.stripe.com/v1/subscriptions
        Paginated, yields StripeSubscriptionEntity objects.
        """
        base_url = "https://api.stripe.com/v1/subscriptions?limit=100"
        url = base_url

        while url:
            data = await self._get(url)
            for sub in data.get("data", []):
                web_url = self._build_dashboard_url("subscriptions", sub["id"], sub.get("livemode"))
                yield StripeSubscriptionEntity.from_api(sub, web_url=web_url)

            has_more = data.get("has_more")
            if not has_more:
                url = None
            else:
                last_id = data["data"][-1]["id"]
                url = f"{base_url}&starting_after={last_id}"

    async def generate_entities(  # noqa: C901
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
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
        async for balance_entity in self._generate_balance_entity():
            yield balance_entity

        async for txn_entity in self._generate_balance_transaction_entities():
            yield txn_entity

        async for charge_entity in self._generate_charge_entities():
            yield charge_entity

        async for customer_entity in self._generate_customer_entities():
            yield customer_entity

        async for event_entity in self._generate_event_entities():
            yield event_entity

        async for invoice_entity in self._generate_invoice_entities():
            yield invoice_entity

        async for pi_entity in self._generate_payment_intent_entities():
            yield pi_entity

        async for pm_entity in self._generate_payment_method_entities():
            yield pm_entity

        async for payout_entity in self._generate_payout_entities():
            yield payout_entity

        async for refund_entity in self._generate_refund_entities():
            yield refund_entity

        async for sub_entity in self._generate_subscription_entities():
            yield sub_entity

    async def validate(self) -> None:
        """Verify Stripe API key by pinging a lightweight endpoint (/v1/balance)."""
        await self._get("https://api.stripe.com/v1/balance")
