"""Zoho CRM source implementation.

We retrieve data from the Zoho CRM REST API v8 for the full sales suite:
- Accounts, Contacts, Deals (core CRM)
- Leads (pre-qualified prospects)
- Products (product catalog)
- Quotes, Sales Orders, Invoices (sales documents)

Then, we yield them as entities using the respective entity schemas defined
in entities/zoho_crm.py.
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import ZohoCRMAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
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
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


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

    # Zoho CRM API limits
    ZOHO_API_LIMIT = 200  # Maximum results per page

    def __init__(self):
        """Initialize the Zoho CRM source."""
        super().__init__()
        self._org_id: Optional[str] = None
        # Default to US data center, can be configured
        self.api_domain: str = "https://www.zohoapis.com"

    @classmethod
    async def create(
        cls, credentials: Any, config: Optional[Dict[str, Any]] = None
    ) -> "ZohoCRMSource":
        """Create a new Zoho CRM source instance.

        Args:
            credentials: OAuth credentials - either a string (access_token) or
                        an auth config object with access_token attribute
            config: Optional configuration containing api_domain for different regions

        Returns:
            Configured ZohoCRMSource instance
        """
        instance = cls()

        # DEBUG: Log what we're receiving
        print(f"🔍 ZohoCRM.create called with credentials type: {type(credentials).__name__}")
        print(f"🔍 credentials repr: {repr(credentials)[:200]}")

        # Handle both string token and auth config object
        if isinstance(credentials, str):
            instance.access_token = credentials
            print(f"🔍 Using string token: {credentials[:20]}...")
        elif hasattr(credentials, "access_token"):
            instance.access_token = credentials.access_token
            token_preview = credentials.access_token[:20] if credentials.access_token else "None"
            print(f"🔍 Extracted token from object: {token_preview}...")
        else:
            raise ValueError("credentials must be a string or have an access_token attribute")

        # Allow configuring region-specific API domain
        if config and config.get("api_domain"):
            instance.api_domain = config["api_domain"]

        return instance

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse Zoho CRM ISO datetimes."""
        if not value:
            return None
        try:
            # Zoho uses ISO 8601 format: 2023-01-15T10:30:00+05:30
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _get_base_url(self) -> str:
        """Get the base URL for Zoho CRM API calls."""
        return f"{self.api_domain}/crm/v8"

    def _build_record_url(self, module: str, record_id: str) -> Optional[str]:
        """Construct a Zoho CRM record URL."""
        if not record_id:
            return None
        # Zoho CRM URLs follow this pattern
        return f"https://crm.zoho.com/crm/org{self._org_id or ''}/tab/{module}/{record_id}"

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an authenticated GET request to the Zoho CRM API.

        Args:
            client: HTTP client
            url: Full URL to the Zoho CRM API endpoint
            params: Optional query parameters

        Returns:
            JSON response data

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

        response = await client.get(url, headers=headers, params=params)

        # Handle 401 errors by refreshing token and retrying
        if response.status_code == 401:
            self.logger.warning(
                f"Got 401 Unauthorized from Zoho CRM API at {url}, refreshing token..."
            )
            await self.refresh_on_unauthorized()

            # Get new token and retry
            access_token = await self.get_access_token()
            headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
            response = await client.get(url, headers=headers, params=params)

        # Log detailed error information for 4xx/5xx responses before raising
        if not response.is_success:
            try:
                error_body = response.json()
                error_code = error_body.get("code", "N/A")
                error_message = error_body.get("message", "No message provided")
                self.logger.error(
                    f"❌ Zoho CRM API error at {url} - "
                    f"Status: {response.status_code}, "
                    f"Code: {error_code}, "
                    f"Message: {error_message}, "
                    f"Full response: {error_body}"
                )
            except Exception:
                self.logger.error(
                    f"❌ Zoho CRM API error at {url} - "
                    f"Status: {response.status_code}, "
                    f"Response: {response.text}"
                )

        response.raise_for_status()

        # Handle 204 No Content (no records found)
        if response.status_code == 204 or not response.content:
            return {"data": []}

        return response.json()

    async def _ensure_org_id(self, client: httpx.AsyncClient) -> Optional[str]:
        """Fetch and cache the Zoho CRM org ID for building record URLs."""
        if self._org_id:
            return self._org_id
        try:
            # Get org info from users endpoint
            data = await self._get_with_auth(
                client, f"{self._get_base_url()}/users?type=CurrentUser"
            )
            users = data.get("users", [])
            if users:
                self._org_id = users[0].get("org_id")
            else:
                self.logger.warning("Zoho CRM response missing org_id; web URLs may be incomplete.")
        except Exception as exc:
            self.logger.warning("Failed to fetch Zoho CRM org ID: %s", exc)
        return self._org_id

    async def _generate_account_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve accounts from Zoho CRM.

        Uses Zoho CRM REST API to fetch Account records.
        Paginated, yields ZohoCRMAccountEntity objects.
        """
        self.logger.info("🔍 [ZOHO CRM] Fetching accounts...")

        page_token = None
        # Zoho CRM v8 requires explicit field names
        account_fields = (
            "id,Account_Name,Phone,Website,Industry,Billing_Street,Billing_City,"
            "Billing_State,Billing_Code,Billing_Country,Description,Annual_Revenue,"
            "Employees,Parent_Account,Created_Time,Modified_Time"
        )
        while True:
            url = f"{self._get_base_url()}/Accounts"
            params = {"fields": account_fields}
            if page_token:
                params["page_token"] = page_token

            try:
                data = await self._get_with_auth(client, url, params)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 204:
                    # No more data
                    break
                raise

            accounts = data.get("data", [])
            if not accounts:
                break

            for account in accounts:
                account_id = str(account.get("id", ""))
                account_name = account.get("Account_Name") or f"Account {account_id}"
                created_time = (
                    self._parse_datetime(account.get("Created_Time")) or datetime.utcnow()
                )
                updated_time = self._parse_datetime(account.get("Modified_Time")) or created_time
                web_url = self._build_record_url("Accounts", account_id)

                # Get owner info
                owner = account.get("Owner", {})
                owner_id = owner.get("id") if isinstance(owner, dict) else None
                owner_name = owner.get("name") if isinstance(owner, dict) else None

                # Get parent account info
                parent_account = account.get("Parent_Account", {})
                parent_account_id = (
                    parent_account.get("id") if isinstance(parent_account, dict) else None
                )

                # Debug: Log account name for verification
                self.logger.info(f"🏢 [ZOHO CRM] Account {account_id}: name={account_name}")

                yield ZohoCRMAccountEntity(
                    # Base fields
                    entity_id=account_id,
                    breadcrumbs=[],
                    name=account_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    # API fields
                    account_id=account_id,
                    account_name=account_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=web_url,
                    website=account.get("Website"),
                    phone=account.get("Phone"),
                    fax=account.get("Fax"),
                    industry=account.get("Industry"),
                    annual_revenue=account.get("Annual_Revenue"),
                    employees=account.get("Employees"),
                    ownership=account.get("Ownership"),
                    ticker_symbol=account.get("Ticker_Symbol"),
                    description=account.get("Description"),
                    rating=account.get("Rating"),
                    parent_account_id=parent_account_id,
                    account_type=account.get("Account_Type"),
                    billing_street=account.get("Billing_Street"),
                    billing_city=account.get("Billing_City"),
                    billing_state=account.get("Billing_State"),
                    billing_code=account.get("Billing_Code"),
                    billing_country=account.get("Billing_Country"),
                    shipping_street=account.get("Shipping_Street"),
                    shipping_city=account.get("Shipping_City"),
                    shipping_state=account.get("Shipping_State"),
                    shipping_code=account.get("Shipping_Code"),
                    shipping_country=account.get("Shipping_Country"),
                    account_number=account.get("Account_Number"),
                    sic_code=account.get("SIC_Code"),
                    owner_id=owner_id,
                    owner_name=owner_name,
                    metadata=account,
                )

            # Check for more pages (cursor-based pagination)
            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("✅ [ZOHO CRM] Finished fetching accounts")

    async def _generate_contact_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve contacts from Zoho CRM.

        Uses Zoho CRM REST API to fetch Contact records.
        Paginated, yields ZohoCRMContactEntity objects.
        """
        self.logger.info("🔍 [ZOHO CRM] Fetching contacts...")

        page_token = None
        # Zoho CRM v8 requires explicit field names
        contact_fields = (
            "id,First_Name,Last_Name,Email,Phone,Mobile,Account_Name,Title,Department,"
            "Mailing_Street,Mailing_City,Mailing_State,Mailing_Zip,Mailing_Country,"
            "Description,Lead_Source,Created_Time,Modified_Time"
        )
        while True:
            url = f"{self._get_base_url()}/Contacts"
            params = {"fields": contact_fields}
            if page_token:
                params["page_token"] = page_token

            try:
                data = await self._get_with_auth(client, url, params)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 204:
                    # No more data
                    break
                raise

            contacts = data.get("data", [])
            if not contacts:
                break

            for contact in contacts:
                contact_id = str(contact.get("id", ""))
                first_name = contact.get("First_Name") or ""
                last_name = contact.get("Last_Name") or ""
                contact_name = f"{first_name} {last_name}".strip() or f"Contact {contact_id}"
                created_time = (
                    self._parse_datetime(contact.get("Created_Time")) or datetime.utcnow()
                )
                updated_time = self._parse_datetime(contact.get("Modified_Time")) or created_time
                web_url = self._build_record_url("Contacts", contact_id)

                # Get owner info
                owner = contact.get("Owner", {})
                owner_id = owner.get("id") if isinstance(owner, dict) else None
                owner_name = owner.get("name") if isinstance(owner, dict) else None

                # Get account info
                account = contact.get("Account_Name", {})
                account_id = account.get("id") if isinstance(account, dict) else None
                account_name_val = account.get("name") if isinstance(account, dict) else None

                # Get reports to info
                reports_to = contact.get("Reporting_To", {})
                reports_to_id = reports_to.get("id") if isinstance(reports_to, dict) else None

                # Build breadcrumbs if contact belongs to an account
                breadcrumbs = []
                if account_id:
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=account_id,
                            name=account_name_val or f"Account {account_id}",
                            entity_type=ZohoCRMAccountEntity.__name__,
                        )
                    )

                # Debug: Log email for verification
                email_value = contact.get("Email")
                self.logger.info(f"📧 [ZOHO CRM] Contact {contact_id}: email={email_value}")

                yield ZohoCRMContactEntity(
                    # Base fields
                    entity_id=contact_id,
                    breadcrumbs=breadcrumbs,
                    name=contact_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    # API fields
                    contact_id=contact_id,
                    contact_name=contact_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=web_url,
                    first_name=first_name if first_name else None,
                    last_name=last_name if last_name else None,
                    email=email_value,
                    secondary_email=contact.get("Secondary_Email"),
                    phone=contact.get("Phone"),
                    mobile=contact.get("Mobile"),
                    fax=contact.get("Fax"),
                    title=contact.get("Title"),
                    department=contact.get("Department"),
                    account_id=account_id,
                    account_name=account_name_val,
                    lead_source=contact.get("Lead_Source"),
                    date_of_birth=contact.get("Date_of_Birth"),
                    description=contact.get("Description"),
                    owner_id=owner_id,
                    owner_name=owner_name,
                    mailing_street=contact.get("Mailing_Street"),
                    mailing_city=contact.get("Mailing_City"),
                    mailing_state=contact.get("Mailing_State"),
                    mailing_zip=contact.get("Mailing_Zip"),
                    mailing_country=contact.get("Mailing_Country"),
                    other_street=contact.get("Other_Street"),
                    other_city=contact.get("Other_City"),
                    other_state=contact.get("Other_State"),
                    other_zip=contact.get("Other_Zip"),
                    other_country=contact.get("Other_Country"),
                    assistant=contact.get("Assistant"),
                    asst_phone=contact.get("Asst_Phone"),
                    reports_to_id=reports_to_id,
                    email_opt_out=contact.get("Email_Opt_Out", False),
                    metadata=contact,
                )

            # Check for more pages (cursor-based pagination)
            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("✅ [ZOHO CRM] Finished fetching contacts")

    async def _generate_deal_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve deals from Zoho CRM.

        Uses Zoho CRM REST API to fetch Deal records.
        Paginated, yields ZohoCRMDealEntity objects.
        """
        self.logger.info("🔍 [ZOHO CRM] Fetching deals...")

        page_token = None
        # Zoho CRM v8 requires explicit field names
        deal_fields = (
            "id,Deal_Name,Stage,Amount,Closing_Date,Account_Name,Contact_Name,Description,"
            "Probability,Type,Lead_Source,Next_Step,Expected_Revenue,Created_Time,Modified_Time"
        )
        while True:
            url = f"{self._get_base_url()}/Deals"
            params = {"fields": deal_fields}
            if page_token:
                params["page_token"] = page_token

            try:
                data = await self._get_with_auth(client, url, params)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 204:
                    # No more data
                    break
                raise

            deals = data.get("data", [])
            if not deals:
                break

            for deal in deals:
                deal_id = str(deal.get("id", ""))
                deal_name = deal.get("Deal_Name") or f"Deal {deal_id}"
                created_time = self._parse_datetime(deal.get("Created_Time")) or datetime.utcnow()
                updated_time = self._parse_datetime(deal.get("Modified_Time")) or created_time
                web_url = self._build_record_url("Deals", deal_id)

                # Get owner info
                owner = deal.get("Owner", {})
                owner_id = owner.get("id") if isinstance(owner, dict) else None
                owner_name = owner.get("name") if isinstance(owner, dict) else None

                # Get account info
                account = deal.get("Account_Name", {})
                account_id = account.get("id") if isinstance(account, dict) else None
                account_name_val = account.get("name") if isinstance(account, dict) else None

                # Get contact info
                contact = deal.get("Contact_Name", {})
                contact_id = contact.get("id") if isinstance(contact, dict) else None
                contact_name_val = contact.get("name") if isinstance(contact, dict) else None

                # Get campaign info
                campaign = deal.get("Campaign_Source", {})
                campaign_source = campaign.get("name") if isinstance(campaign, dict) else None

                # Build breadcrumbs
                breadcrumbs = []
                if account_id:
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=account_id,
                            name=account_name_val or f"Account {account_id}",
                            entity_type=ZohoCRMAccountEntity.__name__,
                        )
                    )

                yield ZohoCRMDealEntity(
                    # Base fields
                    entity_id=deal_id,
                    breadcrumbs=breadcrumbs,
                    name=deal_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    # API fields
                    deal_id=deal_id,
                    deal_name=deal_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=web_url,
                    account_id=account_id,
                    account_name=account_name_val,
                    contact_id=contact_id,
                    contact_name=contact_name_val,
                    amount=deal.get("Amount"),
                    closing_date=deal.get("Closing_Date"),
                    stage=deal.get("Stage"),
                    probability=deal.get("Probability"),
                    expected_revenue=deal.get("Expected_Revenue"),
                    pipeline=deal.get("Pipeline"),
                    campaign_source=campaign_source,
                    owner_id=owner_id,
                    owner_name=owner_name,
                    lead_source=deal.get("Lead_Source"),
                    deal_type=deal.get("Type"),
                    next_step=deal.get("Next_Step"),
                    description=deal.get("Description"),
                    reason_for_loss=deal.get("Reason_For_Loss__s"),
                    metadata=deal,
                )

            # Check for more pages (cursor-based pagination)
            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("✅ [ZOHO CRM] Finished fetching deals")

    async def _generate_lead_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve leads from Zoho CRM.

        Uses Zoho CRM REST API to fetch Lead records.
        Paginated, yields ZohoCRMLeadEntity objects.
        """
        self.logger.info("🔍 [ZOHO CRM] Fetching leads...")

        page_token = None
        # Zoho CRM v8 requires explicit field names
        lead_fields = (
            "id,First_Name,Last_Name,Email,Phone,Mobile,Company,Title,Industry,Lead_Source,"
            "Lead_Status,Annual_Revenue,No_of_Employees,Street,City,State,Zip_Code,Country,"
            "Description,Rating,Website,Created_Time,Modified_Time"
        )
        while True:
            url = f"{self._get_base_url()}/Leads"
            params = {"fields": lead_fields}
            if page_token:
                params["page_token"] = page_token

            try:
                data = await self._get_with_auth(client, url, params)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 204:
                    break
                raise

            leads = data.get("data", [])
            if not leads:
                break

            for lead in leads:
                lead_id = str(lead.get("id", ""))
                first_name = lead.get("First_Name") or ""
                last_name = lead.get("Last_Name") or ""
                lead_name = f"{first_name} {last_name}".strip() or f"Lead {lead_id}"
                created_time = self._parse_datetime(lead.get("Created_Time")) or datetime.utcnow()
                updated_time = self._parse_datetime(lead.get("Modified_Time")) or created_time
                web_url = self._build_record_url("Leads", lead_id)

                owner = lead.get("Owner", {})
                owner_id = owner.get("id") if isinstance(owner, dict) else None
                owner_name = owner.get("name") if isinstance(owner, dict) else None

                # Debug: Log lead email for verification
                lead_email = lead.get("Email")
                self.logger.info(f"📧 [ZOHO CRM] Lead {lead_id}: email={lead_email}")

                yield ZohoCRMLeadEntity(
                    entity_id=lead_id,
                    breadcrumbs=[],
                    name=lead_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    lead_id=lead_id,
                    lead_name=lead_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=web_url,
                    first_name=first_name if first_name else None,
                    last_name=last_name if last_name else None,
                    company=lead.get("Company"),
                    email=lead.get("Email"),
                    phone=lead.get("Phone"),
                    mobile=lead.get("Mobile"),
                    fax=lead.get("Fax"),
                    title=lead.get("Title"),
                    website=lead.get("Website"),
                    lead_source=lead.get("Lead_Source"),
                    lead_status=lead.get("Lead_Status"),
                    industry=lead.get("Industry"),
                    annual_revenue=lead.get("Annual_Revenue"),
                    no_of_employees=lead.get("No_of_Employees"),
                    rating=lead.get("Rating"),
                    description=lead.get("Description"),
                    street=lead.get("Street"),
                    city=lead.get("City"),
                    state=lead.get("State"),
                    zip_code=lead.get("Zip_Code"),
                    country=lead.get("Country"),
                    owner_id=owner_id,
                    owner_name=owner_name,
                    converted=lead.get("$converted", False),
                    email_opt_out=lead.get("Email_Opt_Out", False),
                    metadata=lead,
                )

            # Check for more pages (cursor-based pagination)
            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("✅ [ZOHO CRM] Finished fetching leads")

    async def _generate_product_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve products from Zoho CRM.

        Uses Zoho CRM REST API to fetch Product records.
        Paginated, yields ZohoCRMProductEntity objects.
        """
        self.logger.info("🔍 [ZOHO CRM] Fetching products...")

        page_token = None
        # Zoho CRM v8 requires explicit field names
        product_fields = (
            "id,Product_Name,Product_Code,Vendor_Name,Product_Active,Product_Category,"
            "Unit_Price,Commission_Rate,Qty_in_Stock,Description,Tax,Created_Time,Modified_Time"
        )
        while True:
            url = f"{self._get_base_url()}/Products"
            params = {"fields": product_fields}
            if page_token:
                params["page_token"] = page_token

            try:
                data = await self._get_with_auth(client, url, params)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 204:
                    break
                raise

            products = data.get("data", [])
            if not products:
                break

            for product in products:
                product_id = str(product.get("id", ""))
                product_name = product.get("Product_Name") or f"Product {product_id}"
                created_time = (
                    self._parse_datetime(product.get("Created_Time")) or datetime.utcnow()
                )
                updated_time = self._parse_datetime(product.get("Modified_Time")) or created_time
                web_url = self._build_record_url("Products", product_id)

                owner = product.get("Owner", {})
                owner_id = owner.get("id") if isinstance(owner, dict) else None
                owner_name = owner.get("name") if isinstance(owner, dict) else None

                vendor = product.get("Vendor_Name", {})
                vendor_name = vendor.get("name") if isinstance(vendor, dict) else None

                yield ZohoCRMProductEntity(
                    entity_id=product_id,
                    breadcrumbs=[],
                    name=product_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    product_id=product_id,
                    product_name=product_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=web_url,
                    product_code=product.get("Product_Code"),
                    product_category=product.get("Product_Category"),
                    manufacturer=product.get("Manufacturer"),
                    vendor_name=vendor_name,
                    unit_price=product.get("Unit_Price"),
                    sales_start_date=product.get("Sales_Start_Date"),
                    sales_end_date=product.get("Sales_End_Date"),
                    support_start_date=product.get("Support_Start_Date"),
                    support_expiry_date=product.get("Support_Expiry_Date"),
                    qty_in_stock=product.get("Qty_in_Stock"),
                    qty_in_demand=product.get("Qty_in_Demand"),
                    qty_ordered=product.get("Qty_Ordered"),
                    reorder_level=product.get("Reorder_Level"),
                    commission_rate=product.get("Commission_Rate"),
                    tax=product.get("Tax"),
                    taxable=product.get("Taxable", False),
                    product_active=product.get("Product_Active", True),
                    description=product.get("Description"),
                    owner_id=owner_id,
                    owner_name=owner_name,
                    metadata=product,
                )

            # Check for more pages (cursor-based pagination)
            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("✅ [ZOHO CRM] Finished fetching products")

    async def _generate_quote_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve quotes from Zoho CRM.

        Uses Zoho CRM REST API to fetch Quote records.
        Paginated, yields ZohoCRMQuoteEntity objects.
        """
        self.logger.info("🔍 [ZOHO CRM] Fetching quotes...")

        page_token = None
        # Zoho CRM v8 requires explicit field names
        quote_fields = (
            "id,Subject,Quote_Stage,Valid_Till,Account_Name,Contact_Name,Deal_Name,"
            "Grand_Total,Sub_Total,Discount,Tax,Terms_and_Conditions,Description,"
            "Billing_Street,Billing_City,Billing_State,Billing_Code,Billing_Country,"
            "Shipping_Street,Shipping_City,Shipping_State,Shipping_Code,Shipping_Country,"
            "Created_Time,Modified_Time"
        )
        while True:
            url = f"{self._get_base_url()}/Quotes"
            params = {"fields": quote_fields}
            if page_token:
                params["page_token"] = page_token

            try:
                data = await self._get_with_auth(client, url, params)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 204:
                    break
                raise

            quotes = data.get("data", [])
            if not quotes:
                break

            for quote in quotes:
                quote_id = str(quote.get("id", ""))
                quote_name = quote.get("Subject") or f"Quote {quote_id}"
                created_time = self._parse_datetime(quote.get("Created_Time")) or datetime.utcnow()
                updated_time = self._parse_datetime(quote.get("Modified_Time")) or created_time
                web_url = self._build_record_url("Quotes", quote_id)

                owner = quote.get("Owner", {})
                owner_id = owner.get("id") if isinstance(owner, dict) else None
                owner_name = owner.get("name") if isinstance(owner, dict) else None

                account = quote.get("Account_Name", {})
                account_id = account.get("id") if isinstance(account, dict) else None
                account_name_val = account.get("name") if isinstance(account, dict) else None

                contact = quote.get("Contact_Name", {})
                contact_id = contact.get("id") if isinstance(contact, dict) else None
                contact_name_val = contact.get("name") if isinstance(contact, dict) else None

                deal = quote.get("Deal_Name", {})
                deal_id = deal.get("id") if isinstance(deal, dict) else None
                deal_name_val = deal.get("name") if isinstance(deal, dict) else None

                breadcrumbs = []
                if account_id:
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=account_id,
                            name=account_name_val or f"Account {account_id}",
                            entity_type=ZohoCRMAccountEntity.__name__,
                        )
                    )

                yield ZohoCRMQuoteEntity(
                    entity_id=quote_id,
                    breadcrumbs=breadcrumbs,
                    name=quote_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    quote_id=quote_id,
                    quote_name=quote_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=web_url,
                    quote_number=quote.get("Quote_Number"),
                    quote_stage=quote.get("Quote_Stage"),
                    account_id=account_id,
                    account_name=account_name_val,
                    contact_id=contact_id,
                    contact_name=contact_name_val,
                    deal_id=deal_id,
                    deal_name=deal_name_val,
                    valid_till=quote.get("Valid_Till"),
                    sub_total=quote.get("Sub_Total"),
                    discount=quote.get("Discount"),
                    tax=quote.get("Tax"),
                    adjustment=quote.get("Adjustment"),
                    grand_total=quote.get("Grand_Total"),
                    carrier=quote.get("Carrier"),
                    shipping_charge=quote.get("Shipping_Charge"),
                    terms_and_conditions=quote.get("Terms_and_Conditions"),
                    description=quote.get("Description"),
                    billing_street=quote.get("Billing_Street"),
                    billing_city=quote.get("Billing_City"),
                    billing_state=quote.get("Billing_State"),
                    billing_code=quote.get("Billing_Code"),
                    billing_country=quote.get("Billing_Country"),
                    shipping_street=quote.get("Shipping_Street"),
                    shipping_city=quote.get("Shipping_City"),
                    shipping_state=quote.get("Shipping_State"),
                    shipping_code=quote.get("Shipping_Code"),
                    shipping_country=quote.get("Shipping_Country"),
                    owner_id=owner_id,
                    owner_name=owner_name,
                    metadata=quote,
                )

            # Check for more pages (cursor-based pagination)
            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("✅ [ZOHO CRM] Finished fetching quotes")

    async def _generate_sales_order_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve sales orders from Zoho CRM.

        Uses Zoho CRM REST API to fetch Sales_Orders records.
        Paginated, yields ZohoCRMSalesOrderEntity objects.
        """
        self.logger.info("🔍 [ZOHO CRM] Fetching sales orders...")

        page_token = None
        # Zoho CRM v8 requires explicit field names
        sales_order_fields = (
            "id,Subject,SO_Number,Account_Name,Contact_Name,Deal_Name,Quote_Name,"
            "Grand_Total,Sub_Total,Discount,Tax,Status,Due_Date,Terms_and_Conditions,"
            "Description,Billing_Street,Billing_City,Billing_State,Billing_Code,"
            "Billing_Country,Shipping_Street,Shipping_City,Shipping_State,Shipping_Code,"
            "Shipping_Country,Created_Time,Modified_Time"
        )
        while True:
            url = f"{self._get_base_url()}/Sales_Orders"
            params = {"fields": sales_order_fields}
            if page_token:
                params["page_token"] = page_token

            try:
                data = await self._get_with_auth(client, url, params)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 204:
                    break
                raise

            sales_orders = data.get("data", [])
            if not sales_orders:
                break

            for so in sales_orders:
                so_id = str(so.get("id", ""))
                so_name = so.get("Subject") or f"Sales Order {so_id}"
                created_time = self._parse_datetime(so.get("Created_Time")) or datetime.utcnow()
                updated_time = self._parse_datetime(so.get("Modified_Time")) or created_time
                web_url = self._build_record_url("Sales_Orders", so_id)

                owner = so.get("Owner", {})
                owner_id = owner.get("id") if isinstance(owner, dict) else None
                owner_name = owner.get("name") if isinstance(owner, dict) else None

                account = so.get("Account_Name", {})
                account_id = account.get("id") if isinstance(account, dict) else None
                account_name_val = account.get("name") if isinstance(account, dict) else None

                contact = so.get("Contact_Name", {})
                contact_id = contact.get("id") if isinstance(contact, dict) else None
                contact_name_val = contact.get("name") if isinstance(contact, dict) else None

                deal = so.get("Deal_Name", {})
                deal_id = deal.get("id") if isinstance(deal, dict) else None
                deal_name_val = deal.get("name") if isinstance(deal, dict) else None

                quote = so.get("Quote_Name", {})
                quote_id = quote.get("id") if isinstance(quote, dict) else None
                quote_name_val = quote.get("name") if isinstance(quote, dict) else None

                breadcrumbs = []
                if account_id:
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=account_id,
                            name=account_name_val or f"Account {account_id}",
                            entity_type=ZohoCRMAccountEntity.__name__,
                        )
                    )

                yield ZohoCRMSalesOrderEntity(
                    entity_id=so_id,
                    breadcrumbs=breadcrumbs,
                    name=so_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    sales_order_id=so_id,
                    sales_order_name=so_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=web_url,
                    so_number=so.get("SO_Number"),
                    status=so.get("Status"),
                    account_id=account_id,
                    account_name=account_name_val,
                    contact_id=contact_id,
                    contact_name=contact_name_val,
                    deal_id=deal_id,
                    deal_name=deal_name_val,
                    quote_id=quote_id,
                    quote_name=quote_name_val,
                    due_date=so.get("Due_Date"),
                    sub_total=so.get("Sub_Total"),
                    discount=so.get("Discount"),
                    tax=so.get("Tax"),
                    adjustment=so.get("Adjustment"),
                    grand_total=so.get("Grand_Total"),
                    carrier=so.get("Carrier"),
                    shipping_charge=so.get("Shipping_Charge"),
                    excise_duty=so.get("Excise_Duty"),
                    terms_and_conditions=so.get("Terms_and_Conditions"),
                    description=so.get("Description"),
                    billing_street=so.get("Billing_Street"),
                    billing_city=so.get("Billing_City"),
                    billing_state=so.get("Billing_State"),
                    billing_code=so.get("Billing_Code"),
                    billing_country=so.get("Billing_Country"),
                    shipping_street=so.get("Shipping_Street"),
                    shipping_city=so.get("Shipping_City"),
                    shipping_state=so.get("Shipping_State"),
                    shipping_code=so.get("Shipping_Code"),
                    shipping_country=so.get("Shipping_Country"),
                    owner_id=owner_id,
                    owner_name=owner_name,
                    metadata=so,
                )

            # Check for more pages (cursor-based pagination)
            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("✅ [ZOHO CRM] Finished fetching sales orders")

    async def _generate_invoice_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve invoices from Zoho CRM.

        Uses Zoho CRM REST API to fetch Invoices records.
        Paginated, yields ZohoCRMInvoiceEntity objects.
        """
        self.logger.info("🔍 [ZOHO CRM] Fetching invoices...")

        page_token = None
        # Zoho CRM v8 requires explicit field names
        invoice_fields = (
            "id,Subject,Invoice_Number,Account_Name,Contact_Name,Deal_Name,Sales_Order,"
            "Grand_Total,Sub_Total,Discount,Tax,Status,Invoice_Date,Due_Date,"
            "Terms_and_Conditions,Description,Billing_Street,Billing_City,Billing_State,"
            "Billing_Code,Billing_Country,Shipping_Street,Shipping_City,Shipping_State,"
            "Shipping_Code,Shipping_Country,Created_Time,Modified_Time"
        )
        while True:
            url = f"{self._get_base_url()}/Invoices"
            params = {"fields": invoice_fields}
            if page_token:
                params["page_token"] = page_token

            try:
                data = await self._get_with_auth(client, url, params)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 204:
                    break
                raise

            invoices = data.get("data", [])
            if not invoices:
                break

            for invoice in invoices:
                invoice_id = str(invoice.get("id", ""))
                invoice_name = invoice.get("Subject") or f"Invoice {invoice_id}"
                created_time = (
                    self._parse_datetime(invoice.get("Created_Time")) or datetime.utcnow()
                )
                updated_time = self._parse_datetime(invoice.get("Modified_Time")) or created_time
                web_url = self._build_record_url("Invoices", invoice_id)

                owner = invoice.get("Owner", {})
                owner_id = owner.get("id") if isinstance(owner, dict) else None
                owner_name = owner.get("name") if isinstance(owner, dict) else None

                account = invoice.get("Account_Name", {})
                account_id = account.get("id") if isinstance(account, dict) else None
                account_name_val = account.get("name") if isinstance(account, dict) else None

                contact = invoice.get("Contact_Name", {})
                contact_id = contact.get("id") if isinstance(contact, dict) else None
                contact_name_val = contact.get("name") if isinstance(contact, dict) else None

                deal = invoice.get("Deal_Name", {})
                deal_id = deal.get("id") if isinstance(deal, dict) else None
                deal_name_val = deal.get("name") if isinstance(deal, dict) else None

                sales_order = invoice.get("Sales_Order", {})
                sales_order_id = sales_order.get("id") if isinstance(sales_order, dict) else None
                sales_order_name_val = (
                    sales_order.get("name") if isinstance(sales_order, dict) else None
                )

                breadcrumbs = []
                if account_id:
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=account_id,
                            name=account_name_val or f"Account {account_id}",
                            entity_type=ZohoCRMAccountEntity.__name__,
                        )
                    )

                yield ZohoCRMInvoiceEntity(
                    entity_id=invoice_id,
                    breadcrumbs=breadcrumbs,
                    name=invoice_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    invoice_id=invoice_id,
                    invoice_name=invoice_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=web_url,
                    invoice_number=invoice.get("Invoice_Number"),
                    invoice_date=invoice.get("Invoice_Date"),
                    status=invoice.get("Status"),
                    account_id=account_id,
                    account_name=account_name_val,
                    contact_id=contact_id,
                    contact_name=contact_name_val,
                    deal_id=deal_id,
                    deal_name=deal_name_val,
                    sales_order_id=sales_order_id,
                    sales_order_name=sales_order_name_val,
                    due_date=invoice.get("Due_Date"),
                    purchase_order=invoice.get("Purchase_Order"),
                    sub_total=invoice.get("Sub_Total"),
                    discount=invoice.get("Discount"),
                    tax=invoice.get("Tax"),
                    adjustment=invoice.get("Adjustment"),
                    grand_total=invoice.get("Grand_Total"),
                    shipping_charge=invoice.get("Shipping_Charge"),
                    excise_duty=invoice.get("Excise_Duty"),
                    terms_and_conditions=invoice.get("Terms_and_Conditions"),
                    description=invoice.get("Description"),
                    billing_street=invoice.get("Billing_Street"),
                    billing_city=invoice.get("Billing_City"),
                    billing_state=invoice.get("Billing_State"),
                    billing_code=invoice.get("Billing_Code"),
                    billing_country=invoice.get("Billing_Country"),
                    shipping_street=invoice.get("Shipping_Street"),
                    shipping_city=invoice.get("Shipping_City"),
                    shipping_state=invoice.get("Shipping_State"),
                    shipping_code=invoice.get("Shipping_Code"),
                    shipping_country=invoice.get("Shipping_Country"),
                    owner_id=owner_id,
                    owner_name=owner_name,
                    metadata=invoice,
                )

            # Check for more pages (cursor-based pagination)
            info = data.get("info", {})
            if not info.get("more_records", False):
                break
            page_token = info.get("next_page_token")
            if not page_token:
                break

        self.logger.info("✅ [ZOHO CRM] Finished fetching invoices")

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Zoho CRM entities.

        Yields:
            Zoho CRM entities: Accounts, Contacts, Deals, Leads, Products,
            Quotes, Sales Orders, and Invoices.
        """
        async with self.http_client(timeout=30.0) as client:
            await self._ensure_org_id(client)

            # Generate accounts
            async for account_entity in self._generate_account_entities(client):
                yield account_entity

            # Generate contacts
            async for contact_entity in self._generate_contact_entities(client):
                yield contact_entity

            # Generate deals
            async for deal_entity in self._generate_deal_entities(client):
                yield deal_entity

            # Generate leads
            async for lead_entity in self._generate_lead_entities(client):
                yield lead_entity

            # Generate products
            async for product_entity in self._generate_product_entities(client):
                yield product_entity

            # Generate quotes
            async for quote_entity in self._generate_quote_entities(client):
                yield quote_entity

            # Generate sales orders
            async for sales_order_entity in self._generate_sales_order_entities(client):
                yield sales_order_entity

            # Generate invoices
            async for invoice_entity in self._generate_invoice_entities(client):
                yield invoice_entity

    async def validate(self) -> bool:
        """Verify Zoho CRM OAuth2 token by pinging a lightweight endpoint.

        Note: Zoho uses 'Zoho-oauthtoken' header format, not standard 'Bearer'.
        """
        # DEBUG: Log token state
        self.logger.info(
            f"🔍 validate() - self.access_token exists: {bool(getattr(self, 'access_token', None))}"
        )
        if getattr(self, "access_token", None):
            self.logger.info(
                f"🔍 validate() - self.access_token preview: {self.access_token[:20]}..."
            )

        token = await self.get_access_token()
        self.logger.info(
            (f"🔍 validate() - get_access_token() returned: {token[:20] if token else 'None'}...")
        )

        if not token:
            self.logger.error("OAuth2 validation failed: no access token available.")
            return False

        ping_url = f"{self._get_base_url()}/users?type=CurrentUser"
        self.logger.info(f"🔍 validate() - ping_url: {ping_url}")
        headers = {
            "Authorization": f"Zoho-oauthtoken {token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(ping_url, headers=headers)
                if 200 <= resp.status_code < 300:
                    return True
                self.logger.warning(
                    f"Zoho validation failed: HTTP {resp.status_code} - {resp.text[:200]}"
                )
                return False
        except httpx.RequestError as e:
            self.logger.error(f"Zoho validation request error: {e}")
            return False
