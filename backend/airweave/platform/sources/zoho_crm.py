"""Zoho CRM source implementation.

Retrieves data from the Zoho CRM REST API v8 for the full sales suite:
- Accounts, Contacts, Deals (core CRM)
- Leads (pre-qualified prospects)
- Products (product catalog)
- Quotes, Sales Orders, Invoices (sales documents)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Optional

from pydantic import BaseModel
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import (
    AuthProviderKind,
    TokenProviderProtocol,
)
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import ZohoCRMAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.zoho_crm import (
    ZohoCRMAccountEntity,
    ZohoCRMContactEntity,
    ZohoCRMDealEntity,
    ZohoCRMInvoiceEntity,
    ZohoCRMLeadEntity,
    ZohoCRMProductEntity,
    ZohoCRMQuoteEntity,
    ZohoCRMSalesOrderEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup

ZOHO_API_LIMIT = 200


@source(
    name="Zoho CRM",
    short_name="zoho_crm",
    auth_methods=[
        AuthenticationMethod.DIRECT,
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=ZohoCRMAuthConfig,
    labels=["CRM", "Sales"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class ZohoCRMSource(BaseSource):
    """Zoho CRM source connector integrates with the Zoho CRM REST API to extract CRM data.

    Synchronizes comprehensive data from your Zoho CRM org including:
    - Accounts (companies, organizations)
    - Contacts (people)
    - Deals (sales opportunities, pipelines)
    - Leads (pre-qualified prospects)
    - Products (product catalog)
    - Quotes (sales proposals)
    - Sales Orders (confirmed orders)
    - Invoices (billing documents)

    It provides access to all major Zoho CRM modules with proper OAuth2 authentication.
    """

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: BaseModel,
    ) -> ZohoCRMSource:
        """Create a new Zoho CRM source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance._org_id: Optional[str] = None
        instance.api_domain: str = "https://www.zohoapis.com"
        return instance

    def _get_base_url(self) -> str:
        """Get the base URL for Zoho CRM API calls."""
        return f"{self.api_domain}/crm/v8"

    async def _authed_headers(self) -> Dict[str, str]:
        """Build Zoho-oauthtoken Authorization header with a fresh token."""
        if self.auth.provider_kind == AuthProviderKind.CREDENTIAL:
            token = self.auth.credentials.access_token
        else:
            token = await self.auth.get_token()
        return {"Authorization": f"Zoho-oauthtoken {token}"}

    async def _refresh_and_get_headers(self) -> Dict[str, str]:
        """Force-refresh the token and return updated headers."""
        if self.auth.provider_kind == AuthProviderKind.CREDENTIAL:
            return await self._authed_headers()
        new_token = await self.auth.force_refresh()
        return {"Authorization": f"Zoho-oauthtoken {new_token}"}

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Make an authenticated GET request to the Zoho CRM API.

        Handles 401 with a single token refresh, delegates error translation
        to ``raise_for_status``, and returns ``{"data": []}`` for 204 (no records).
        """
        headers = await self._authed_headers()
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning("Received 401 from Zoho CRM — attempting token refresh")
            headers = await self._refresh_and_get_headers()
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )

        if response.status_code == 204 or not response.content:
            return {"data": []}

        return response.json()

    async def _ensure_org_id(self) -> Optional[str]:
        """Fetch and cache the Zoho CRM org ID for building record URLs."""
        if self._org_id:
            return self._org_id
        try:
            data = await self._get(f"{self._get_base_url()}/users?type=CurrentUser")
            users = data.get("users", [])
            if users:
                self._org_id = users[0].get("org_id")
            else:
                self.logger.warning("Zoho CRM response missing org_id; web URLs may be incomplete.")
        except Exception as exc:
            self.logger.warning("Failed to fetch Zoho CRM org ID: %s", exc)
        return self._org_id

    async def _generate_account_entities(self) -> AsyncGenerator[ZohoCRMAccountEntity, None]:
        """Retrieve accounts from Zoho CRM."""
        self.logger.info("Fetching accounts")
        page_token = None
        account_fields = (
            "id,Account_Name,Phone,Website,Industry,Billing_Street,Billing_City,"
            "Billing_State,Billing_Code,Billing_Country,Description,Annual_Revenue,"
            "Employees,Parent_Account,Created_Time,Modified_Time"
        )
        while True:
            params: Dict[str, Any] = {"fields": account_fields}
            if page_token:
                params["page_token"] = page_token

            data = await self._get(f"{self._get_base_url()}/Accounts", params)
            accounts = data.get("data", [])
            if not accounts:
                break

            for account in accounts:
                yield ZohoCRMAccountEntity.from_api(account, org_id=self._org_id)

            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("Finished fetching accounts")

    async def _generate_contact_entities(self) -> AsyncGenerator[ZohoCRMContactEntity, None]:
        """Retrieve contacts from Zoho CRM."""
        self.logger.info("Fetching contacts")
        page_token = None
        contact_fields = (
            "id,First_Name,Last_Name,Email,Phone,Mobile,Account_Name,Title,Department,"
            "Mailing_Street,Mailing_City,Mailing_State,Mailing_Zip,Mailing_Country,"
            "Description,Lead_Source,Created_Time,Modified_Time"
        )
        while True:
            params: Dict[str, Any] = {"fields": contact_fields}
            if page_token:
                params["page_token"] = page_token

            data = await self._get(f"{self._get_base_url()}/Contacts", params)
            contacts = data.get("data", [])
            if not contacts:
                break

            for contact in contacts:
                yield ZohoCRMContactEntity.from_api(contact, org_id=self._org_id)

            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("Finished fetching contacts")

    async def _generate_deal_entities(self) -> AsyncGenerator[ZohoCRMDealEntity, None]:
        """Retrieve deals from Zoho CRM."""
        self.logger.info("Fetching deals")
        page_token = None
        deal_fields = (
            "id,Deal_Name,Stage,Amount,Closing_Date,Account_Name,Contact_Name,Description,"
            "Probability,Type,Lead_Source,Next_Step,Expected_Revenue,Created_Time,Modified_Time"
        )
        while True:
            params: Dict[str, Any] = {"fields": deal_fields}
            if page_token:
                params["page_token"] = page_token

            data = await self._get(f"{self._get_base_url()}/Deals", params)
            deals = data.get("data", [])
            if not deals:
                break

            for deal in deals:
                yield ZohoCRMDealEntity.from_api(deal, org_id=self._org_id)

            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("Finished fetching deals")

    async def _generate_lead_entities(self) -> AsyncGenerator[ZohoCRMLeadEntity, None]:
        """Retrieve leads from Zoho CRM."""
        self.logger.info("Fetching leads")
        page_token = None
        lead_fields = (
            "id,First_Name,Last_Name,Email,Phone,Mobile,Company,Title,Industry,Lead_Source,"
            "Lead_Status,Annual_Revenue,No_of_Employees,Street,City,State,Zip_Code,Country,"
            "Description,Rating,Website,Created_Time,Modified_Time"
        )
        while True:
            params: Dict[str, Any] = {"fields": lead_fields}
            if page_token:
                params["page_token"] = page_token

            data = await self._get(f"{self._get_base_url()}/Leads", params)
            leads = data.get("data", [])
            if not leads:
                break

            for lead in leads:
                yield ZohoCRMLeadEntity.from_api(lead, org_id=self._org_id)

            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("Finished fetching leads")

    async def _generate_product_entities(self) -> AsyncGenerator[ZohoCRMProductEntity, None]:
        """Retrieve products from Zoho CRM."""
        self.logger.info("Fetching products")
        page_token = None
        product_fields = (
            "id,Product_Name,Product_Code,Vendor_Name,Product_Active,Product_Category,"
            "Unit_Price,Commission_Rate,Qty_in_Stock,Description,Tax,Created_Time,Modified_Time"
        )
        while True:
            params: Dict[str, Any] = {"fields": product_fields}
            if page_token:
                params["page_token"] = page_token

            data = await self._get(f"{self._get_base_url()}/Products", params)
            products = data.get("data", [])
            if not products:
                break

            for product in products:
                yield ZohoCRMProductEntity.from_api(product, org_id=self._org_id)

            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("Finished fetching products")

    async def _generate_quote_entities(self) -> AsyncGenerator[ZohoCRMQuoteEntity, None]:
        """Retrieve quotes from Zoho CRM."""
        self.logger.info("Fetching quotes")
        page_token = None
        quote_fields = (
            "id,Subject,Quote_Stage,Valid_Till,Account_Name,Contact_Name,Deal_Name,"
            "Grand_Total,Sub_Total,Discount,Tax,Terms_and_Conditions,Description,"
            "Billing_Street,Billing_City,Billing_State,Billing_Code,Billing_Country,"
            "Shipping_Street,Shipping_City,Shipping_State,Shipping_Code,Shipping_Country,"
            "Created_Time,Modified_Time"
        )
        while True:
            params: Dict[str, Any] = {"fields": quote_fields}
            if page_token:
                params["page_token"] = page_token

            data = await self._get(f"{self._get_base_url()}/Quotes", params)
            quotes = data.get("data", [])
            if not quotes:
                break

            for quote in quotes:
                yield ZohoCRMQuoteEntity.from_api(quote, org_id=self._org_id)

            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("Finished fetching quotes")

    async def _generate_sales_order_entities(
        self,
    ) -> AsyncGenerator[ZohoCRMSalesOrderEntity, None]:
        """Retrieve sales orders from Zoho CRM."""
        self.logger.info("Fetching sales orders")
        page_token = None
        sales_order_fields = (
            "id,Subject,SO_Number,Account_Name,Contact_Name,Deal_Name,Quote_Name,"
            "Grand_Total,Sub_Total,Discount,Tax,Status,Due_Date,Terms_and_Conditions,"
            "Description,Billing_Street,Billing_City,Billing_State,Billing_Code,"
            "Billing_Country,Shipping_Street,Shipping_City,Shipping_State,Shipping_Code,"
            "Shipping_Country,Created_Time,Modified_Time"
        )
        while True:
            params: Dict[str, Any] = {"fields": sales_order_fields}
            if page_token:
                params["page_token"] = page_token

            data = await self._get(f"{self._get_base_url()}/Sales_Orders", params)
            sales_orders = data.get("data", [])
            if not sales_orders:
                break

            for so in sales_orders:
                yield ZohoCRMSalesOrderEntity.from_api(so, org_id=self._org_id)

            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("Finished fetching sales orders")

    async def _generate_invoice_entities(self) -> AsyncGenerator[ZohoCRMInvoiceEntity, None]:
        """Retrieve invoices from Zoho CRM."""
        self.logger.info("Fetching invoices")
        page_token = None
        invoice_fields = (
            "id,Subject,Invoice_Number,Account_Name,Contact_Name,Deal_Name,Sales_Order,"
            "Grand_Total,Sub_Total,Discount,Tax,Status,Invoice_Date,Due_Date,"
            "Terms_and_Conditions,Description,Billing_Street,Billing_City,Billing_State,"
            "Billing_Code,Billing_Country,Shipping_Street,Shipping_City,Shipping_State,"
            "Shipping_Code,Shipping_Country,Created_Time,Modified_Time"
        )
        while True:
            params: Dict[str, Any] = {"fields": invoice_fields}
            if page_token:
                params["page_token"] = page_token

            data = await self._get(f"{self._get_base_url()}/Invoices", params)
            invoices = data.get("data", [])
            if not invoices:
                break

            for invoice in invoices:
                yield ZohoCRMInvoiceEntity.from_api(invoice, org_id=self._org_id)

            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("Finished fetching invoices")

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Zoho CRM entities."""
        await self._ensure_org_id()

        async for entity in self._generate_account_entities():
            yield entity

        async for entity in self._generate_contact_entities():
            yield entity

        async for entity in self._generate_deal_entities():
            yield entity

        async for entity in self._generate_lead_entities():
            yield entity

        async for entity in self._generate_product_entities():
            yield entity

        async for entity in self._generate_quote_entities():
            yield entity

        async for entity in self._generate_sales_order_entities():
            yield entity

        async for entity in self._generate_invoice_entities():
            yield entity

    async def validate(self) -> None:
        """Verify Zoho CRM OAuth2 token by pinging a lightweight endpoint.

        Note: Zoho uses 'Zoho-oauthtoken' header format, not standard 'Bearer'.
        """
        await self._get(f"{self._get_base_url()}/users?type=CurrentUser")
