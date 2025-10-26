"""Salesforce source implementation.

We retrieve data from the Salesforce REST API for the following core
resources:
- Accounts
- Contacts
- Opportunities

Then, we yield them as entities using the respective entity schemas defined
in entities/salesforce.py.
"""

from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.salesforce import (
    SalesforceAccountEntity,
    SalesforceContactEntity,
    SalesforceOpportunityEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Salesforce",
    short_name="salesforce",
    auth_methods=[AuthenticationMethod.OAUTH_BROWSER, AuthenticationMethod.OAUTH_BYOC],
    oauth_type=OAuthType.WITH_REFRESH,
    requires_byoc=True,  # Users must bring their own Salesforce OAuth credentials
    auth_config_class="SalesforceAuthConfig",  # This tells factory to pass full dict
    config_class="SalesforceConfig",
    labels=["CRM", "Sales"],
    supports_continuous=False,
)
class SalesforceSource(BaseSource):
    """Salesforce source connector integrates with the Salesforce REST API to extract CRM data.

    Synchronizes comprehensive data from your Salesforce org including:
    - Accounts (companies, organizations)
    - Contacts (people, leads)
    - Opportunities (deals, sales prospects)

    It provides access to all major Salesforce objects with proper OAuth2 authentication.
    """

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "SalesforceSource":
        """Create a new Salesforce source instance.

        Args:
            access_token: OAuth access token for Salesforce API
            config: Required configuration containing instance_url

        Returns:
            Configured SalesforceSource instance
        """
        instance = cls()

        if not access_token:
            raise ValueError("Access token is required")

        instance.access_token = access_token
        instance.auth_type = "oauth"

        # Get instance_url from config (template field)
        if config and config.get("instance_url"):
            instance.instance_url = cls._normalize_instance_url(config["instance_url"])
            instance.api_version = config.get("api_version", "58.0")
        else:
            # For token validation, we can use a placeholder instance_url
            # The actual instance_url will be provided during connection creation
            instance.instance_url = "validation-placeholder.salesforce.com"
            instance.api_version = "58.0"
            instance._is_validation_mode = True  # Flag to indicate this is for validation only

        return instance

    @staticmethod
    def _normalize_instance_url(url: Optional[str]) -> Optional[str]:
        """Normalize Salesforce instance URL to remove protocol.

        Salesforce returns instance_url like 'https://mycompany.my.salesforce.com',
        but we need just 'mycompany.my.salesforce.com' for our URL construction.
        """
        if not url:
            return url
        # Remove https:// or http:// prefix
        return url.replace("https://", "").replace("http://", "")

    def _get_base_url(self) -> str:
        """Get the base URL for Salesforce API calls."""
        if not self.instance_url:
            token_status = "<set>" if self.access_token else "<not set>"
            raise ValueError(
                f"Salesforce instance_url is not set. "
                f"instance_url={self.instance_url}, access_token={token_status}"
            )
        return f"https://{self.instance_url}/services/data/v{self.api_version}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an authenticated GET request to the Salesforce API.

        Args:
            client: HTTP client
            url: Full URL to the Salesforce API endpoint
            params: Optional query parameters

        Returns:
            JSON response data

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def _generate_account_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve accounts from Salesforce using SOQL query.

        Uses Salesforce Object Query Language (SOQL) to fetch Account records.
        Paginated, yields SalesforceAccountEntity objects.
        """
        # Build SOQL query with only core standard fields that exist in all Salesforce editions
        # Removed fields that may not exist in Developer/Trial orgs to ensure compatibility
        soql_query = """
            SELECT Id, Name, AccountNumber, Website, Phone, Fax, Industry,
                   AnnualRevenue, NumberOfEmployees, Description, Type,
                   BillingStreet, BillingCity, BillingState, BillingPostalCode, BillingCountry,
                   ShippingStreet, ShippingCity, ShippingState, ShippingPostalCode, ShippingCountry,
                   CreatedDate, LastModifiedDate, IsDeleted
            FROM Account
        """

        url = f"{self._get_base_url()}/query"
        params = {"q": soql_query.strip()}

        while url:
            data = await self._get_with_auth(client, url, params)

            for account in data.get("records", []):
                yield SalesforceAccountEntity(
                    entity_id=account["Id"],
                    name=account.get("Name"),
                    account_number=account.get("AccountNumber"),
                    website=account.get("Website"),
                    phone=account.get("Phone"),
                    fax=account.get("Fax"),
                    industry=account.get("Industry"),
                    annual_revenue=account.get("AnnualRevenue"),
                    number_of_employees=account.get("NumberOfEmployees"),
                    ownership=account.get("Ownership"),
                    ticker_symbol=account.get("TickerSymbol"),
                    description=account.get("Description"),
                    rating=account.get("Rating"),
                    parent_id=account.get("ParentId"),
                    type=account.get("Type"),
                    billing_street=account.get("BillingStreet"),
                    billing_city=account.get("BillingCity"),
                    billing_state=account.get("BillingState"),
                    billing_postal_code=account.get("BillingPostalCode"),
                    billing_country=account.get("BillingCountry"),
                    shipping_street=account.get("ShippingStreet"),
                    shipping_city=account.get("ShippingCity"),
                    shipping_state=account.get("ShippingState"),
                    shipping_postal_code=account.get("ShippingPostalCode"),
                    shipping_country=account.get("ShippingCountry"),
                    created_date=account.get("CreatedDate"),
                    last_modified_date=account.get("LastModifiedDate"),
                    last_activity_date=account.get("LastActivityDate"),
                    last_viewed_date=account.get("LastViewedDate"),
                    last_referenced_date=account.get("LastReferencedDate"),
                    is_deleted=account.get("IsDeleted", False),
                    is_customer_portal=account.get("IsCustomerPortal", False),
                    is_person_account=account.get("IsPersonAccount", False),
                    jigsaw=account.get("Jigsaw"),
                    clean_status=account.get("CleanStatus"),
                    account_source=account.get("AccountSource"),
                    sic_desc=account.get("SicDesc"),
                    duns_number=account.get("DunsNumber"),
                    tradestyle=account.get("Tradestyle"),
                    naics_code=account.get("NaicsCode"),
                    naics_desc=account.get("NaicsDesc"),
                    year_started=account.get("YearStarted"),
                    metadata=account,  # Store the full record for additional/custom fields
                )

            # Check for next page
            next_records_url = data.get("nextRecordsUrl")
            if next_records_url:
                url = f"https://{self.instance_url}{next_records_url}"
                params = None  # nextRecordsUrl already includes all parameters
            else:
                url = None

    async def _generate_contact_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve contacts from Salesforce using SOQL query.

        Uses Salesforce Object Query Language (SOQL) to fetch Contact records.
        Paginated, yields SalesforceContactEntity objects.
        """
        # Build SOQL query with core standard fields
        soql_query = """
            SELECT Id, FirstName, LastName, Name, Email, Phone, MobilePhone, Fax,
                   Title, Department, AccountId, Birthdate, Description, OwnerId,
                   CreatedDate, LastModifiedDate, IsDeleted,
                   MailingStreet, MailingCity, MailingState, MailingPostalCode, MailingCountry,
                   OtherStreet, OtherCity, OtherState, OtherPostalCode, OtherCountry
            FROM Contact
        """

        url = f"{self._get_base_url()}/query"
        params = {"q": soql_query.strip()}

        while url:
            data = await self._get_with_auth(client, url, params)

            for contact in data.get("records", []):
                yield SalesforceContactEntity(
                    entity_id=contact["Id"],
                    first_name=contact.get("FirstName"),
                    last_name=contact.get("LastName"),
                    name=contact.get("Name"),
                    email=contact.get("Email"),
                    phone=contact.get("Phone"),
                    mobile_phone=contact.get("MobilePhone"),
                    fax=contact.get("Fax"),
                    title=contact.get("Title"),
                    department=contact.get("Department"),
                    account_id=contact.get("AccountId"),
                    lead_source=contact.get("LeadSource"),
                    birthdate=contact.get("Birthdate"),
                    description=contact.get("Description"),
                    owner_id=contact.get("OwnerId"),
                    created_date=contact.get("CreatedDate"),
                    last_modified_date=contact.get("LastModifiedDate"),
                    last_activity_date=contact.get("LastActivityDate"),
                    last_viewed_date=contact.get("LastViewedDate"),
                    last_referenced_date=contact.get("LastReferencedDate"),
                    is_deleted=contact.get("IsDeleted", False),
                    is_email_bounced=contact.get("IsEmailBounced", False),
                    is_unread_by_owner=contact.get("IsUnreadByOwner", False),
                    jigsaw=contact.get("Jigsaw"),
                    jigsaw_contact_id=contact.get("JigsawContactId"),
                    clean_status=contact.get("CleanStatus"),
                    level=contact.get("Level__c"),
                    languages=contact.get("Languages__c"),
                    has_opted_out_of_email=contact.get("HasOptedOutOfEmail", False),
                    has_opted_out_of_fax=contact.get("HasOptedOutOfFax", False),
                    do_not_call=contact.get("DoNotCall", False),
                    mailing_street=contact.get("MailingStreet"),
                    mailing_city=contact.get("MailingCity"),
                    mailing_state=contact.get("MailingState"),
                    mailing_postal_code=contact.get("MailingPostalCode"),
                    mailing_country=contact.get("MailingCountry"),
                    other_street=contact.get("OtherStreet"),
                    other_city=contact.get("OtherCity"),
                    other_state=contact.get("OtherState"),
                    other_postal_code=contact.get("OtherPostalCode"),
                    other_country=contact.get("OtherCountry"),
                    assistant_name=contact.get("AssistantName"),
                    assistant_phone=contact.get("AssistantPhone"),
                    reports_to_id=contact.get("ReportsToId"),
                    email_bounced_date=contact.get("EmailBouncedDate"),
                    email_bounced_reason=contact.get("EmailBouncedReason"),
                    individual_id=contact.get("IndividualId"),
                    metadata=contact,  # Store the full record for additional fields
                )

            # Check for next page
            next_records_url = data.get("nextRecordsUrl")
            if next_records_url:
                url = f"{self.instance_url}{next_records_url}"
                params = None
            else:
                url = None

    async def _generate_opportunity_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve opportunities from Salesforce using SOQL query.

        Uses Salesforce Object Query Language (SOQL) to fetch Opportunity records.
        Paginated, yields SalesforceOpportunityEntity objects.
        """
        # Build SOQL query with core standard fields
        soql_query = """
            SELECT Id, Name, AccountId, Amount, CloseDate, StageName, Probability,
                   OwnerId, CreatedDate, LastModifiedDate,
                   IsDeleted, IsWon, IsClosed,
                   Description, Type, NextStep
            FROM Opportunity
        """

        url = f"{self._get_base_url()}/query"
        params = {"q": soql_query.strip()}

        while url:
            data = await self._get_with_auth(client, url, params)

            for opportunity in data.get("records", []):
                yield SalesforceOpportunityEntity(
                    entity_id=opportunity["Id"],
                    name=opportunity.get("Name"),
                    account_id=opportunity.get("AccountId"),
                    amount=opportunity.get("Amount"),
                    close_date=opportunity.get("CloseDate"),
                    stage_name=opportunity.get("StageName"),
                    probability=opportunity.get("Probability"),
                    forecast_category=opportunity.get("ForecastCategory"),
                    forecast_category_name=opportunity.get("ForecastCategoryName"),
                    campaign_id=opportunity.get("CampaignId"),
                    has_opportunity_line_item=opportunity.get("HasOpportunityLineItem", False),
                    pricebook2_id=opportunity.get("Pricebook2Id"),
                    owner_id=opportunity.get("OwnerId"),
                    created_date=opportunity.get("CreatedDate"),
                    last_modified_date=opportunity.get("LastModifiedDate"),
                    last_activity_date=opportunity.get("LastActivityDate"),
                    last_viewed_date=opportunity.get("LastViewedDate"),
                    last_referenced_date=opportunity.get("LastReferencedDate"),
                    is_deleted=opportunity.get("IsDeleted", False),
                    is_won=opportunity.get("IsWon", False),
                    is_closed=opportunity.get("IsClosed", False),
                    has_open_activity=opportunity.get("HasOpenActivity", False),
                    has_overdue_task=opportunity.get("HasOverdueTask", False),
                    description=opportunity.get("Description"),
                    type=opportunity.get("Type"),
                    lead_source=opportunity.get("LeadSource"),
                    next_step=opportunity.get("NextStep"),
                    metadata=opportunity,  # Store the full record for additional/custom fields
                )

            # Check for next page
            next_records_url = data.get("nextRecordsUrl")
            if next_records_url:
                url = f"{self.instance_url}{next_records_url}"
                params = None
            else:
                url = None

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Salesforce entities.

        - Accounts
        - Contacts
        - Opportunities
        """
        async with self.http_client(timeout=30.0) as client:
            # Generate accounts
            async for account_entity in self._generate_account_entities(client):
                yield account_entity

            # Generate contacts
            async for contact_entity in self._generate_contact_entities(client):
                yield contact_entity

            # Generate opportunities
            async for opportunity_entity in self._generate_opportunity_entities(client):
                yield opportunity_entity

    async def validate(self) -> bool:
        """Verify Salesforce access token by pinging the identity endpoint."""
        # If we're in validation mode without a real instance_url, skip the actual API call
        if getattr(self, "_is_validation_mode", False):
            # For validation mode, we can't make a real API call without the instance_url
            # Just validate that we have an access token
            return bool(getattr(self, "access_token", None))

        if not getattr(self, "access_token", None):
            self.logger.error("Salesforce validation failed: missing access token.")
            return False

        if not getattr(self, "instance_url", None):
            self.logger.error("Salesforce validation failed: missing instance URL.")
            return False

        try:
            # Use the OAuth2 validation helper with Salesforce's identity endpoint
            # instance_url is normalized (no protocol), so we need to add https://
            return await self._validate_oauth2(
                ping_url=f"https://{self.instance_url}/services/oauth2/userinfo",
                access_token=self.access_token,
                timeout=10.0,
            )
        except Exception as e:
            self.logger.error(f"Unexpected error during Salesforce validation: {e}")
            return False
