"""Salesforce source implementation.

We retrieve data from the Salesforce REST API for the following core
resources:
- Accounts
- Contacts
- Opportunities

Then, we yield them as entities using the respective entity schemas defined
in entities/salesforce.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import SalesforceConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.salesforce import (
    SalesforceAccountEntity,
    SalesforceContactEntity,
    SalesforceOpportunityEntity,
    _parse_dt,
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


@source(
    name="Salesforce",
    short_name="salesforce",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_BYOC,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    requires_byoc=True,
    auth_config_class=None,
    config_class=SalesforceConfig,
    labels=["CRM", "Sales"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
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
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: SalesforceConfig,
    ) -> SalesforceSource:
        """Create a new Salesforce source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)

        if config.instance_url:
            instance.instance_url = cls._normalize_instance_url(config.instance_url)
        else:
            instance.instance_url = None
            instance._is_validation_mode = True

        instance.api_version = config.api_version
        return instance

    @staticmethod
    def _normalize_instance_url(url: Optional[str]) -> Optional[str]:
        """Normalize Salesforce instance URL to remove protocol.

        Salesforce returns instance_url like 'https://mycompany.my.salesforce.com',
        but we need just 'mycompany.my.salesforce.com' for our URL construction.
        """
        if not url:
            return url
        return url.replace("https://", "").replace("http://", "")

    def _get_base_url(self) -> str:
        """Get the base URL for Salesforce API calls."""
        if not self.instance_url:
            raise ValueError(
                f"Salesforce instance_url is not set. instance_url={self.instance_url}"
            )
        return f"https://{self.instance_url}/services/data/v{self.api_version}"

    def _build_record_url(self, object_api_name: str, record_id: Optional[str]) -> Optional[str]:
        """Construct a Lightning record URL for the given object."""
        if not record_id or not getattr(self, "instance_url", None):
            return None
        if getattr(self, "_is_validation_mode", False):
            return None
        return f"https://{self.instance_url}/lightning/r/{object_api_name}/{record_id}/view"

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an authenticated GET request to the Salesforce API."""
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers = {"Authorization": f"Bearer {new_token}"}
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _get_object_fields(self, sobject_name: str) -> List[str]:
        """Get all queryable fields for a Salesforce object.

        Uses the Salesforce Describe API to discover all fields available in the org.
        Returns ALL fields - we store everything in metadata anyway.

        Args:
            sobject_name: Salesforce object API name (e.g., "Contact", "Account")

        Returns:
            List of all queryable field names
        """
        url = f"{self._get_base_url()}/sobjects/{sobject_name}/describe"
        try:
            data = await self._get(url)
            all_fields = [
                field["name"] for field in data.get("fields", []) if field.get("queryable", True)
            ]
            self.logger.info(
                f"📋 [SALESFORCE] Discovered {len(all_fields)} queryable fields for {sobject_name}"
            )
            return all_fields
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(
                f"⚠️ [SALESFORCE] Failed to describe {sobject_name}, using fallback fields: {e}"
            )
            fallback = {
                "Contact": [
                    "Id",
                    "FirstName",
                    "LastName",
                    "Name",
                    "Email",
                    "CreatedDate",
                    "LastModifiedDate",
                ],
                "Account": ["Id", "Name", "CreatedDate", "LastModifiedDate"],
                "Opportunity": [
                    "Id",
                    "Name",
                    "Amount",
                    "CloseDate",
                    "StageName",
                    "CreatedDate",
                    "LastModifiedDate",
                ],
            }
            return fallback.get(sobject_name, ["Id", "Name", "CreatedDate", "LastModifiedDate"])

    async def _generate_account_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve accounts from Salesforce using SOQL query.

        Uses Salesforce Object Query Language (SOQL) to fetch Account records.
        Paginated, yields SalesforceAccountEntity objects.
        """
        all_fields = await self._get_object_fields("Account")

        fields_str = ", ".join(all_fields)
        soql_query = f"SELECT {fields_str} FROM Account"

        url = f"{self._get_base_url()}/query"
        params: Optional[Dict[str, Any]] = {"q": soql_query.strip()}

        while url:
            data = await self._get(url, params)

            for account in data.get("records", []):
                account_id = account["Id"]
                account_name = account.get("Name") or f"Account {account_id}"
                created_time = _parse_dt(account.get("CreatedDate")) or datetime.utcnow()
                updated_time = _parse_dt(account.get("LastModifiedDate")) or created_time
                web_url = self._build_record_url("Account", account_id)

                yield SalesforceAccountEntity(
                    entity_id=account_id,
                    breadcrumbs=[],
                    name=account_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    account_id=account_id,
                    account_name=account_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=web_url,
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
                    metadata=account,
                )

            next_records_url = data.get("nextRecordsUrl")
            if next_records_url:
                url = f"https://{self.instance_url}{next_records_url}"
                params = None
            else:
                url = None

    async def _generate_contact_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve contacts from Salesforce using SOQL query.

        Uses Salesforce Object Query Language (SOQL) to fetch Contact records.
        Paginated, yields SalesforceContactEntity objects.
        """
        all_fields = await self._get_object_fields("Contact")

        fields_str = ", ".join(all_fields)
        soql_query = f"SELECT {fields_str} FROM Contact"

        url = f"{self._get_base_url()}/query"
        params: Optional[Dict[str, Any]] = {"q": soql_query.strip()}

        while url:
            data = await self._get(url, params)

            for contact in data.get("records", []):
                yield SalesforceContactEntity.from_api(
                    contact, build_record_url_fn=self._build_record_url
                )

            next_records_url = data.get("nextRecordsUrl")
            if next_records_url:
                url = f"https://{self.instance_url}{next_records_url}"
                params = None
            else:
                url = None

    async def _generate_opportunity_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Retrieve opportunities from Salesforce using SOQL query.

        Uses Salesforce Object Query Language (SOQL) to fetch Opportunity records.
        Paginated, yields SalesforceOpportunityEntity objects.
        """
        all_fields = await self._get_object_fields("Opportunity")

        fields_str = ", ".join(all_fields)
        soql_query = f"SELECT {fields_str} FROM Opportunity"

        url = f"{self._get_base_url()}/query"
        params: Optional[Dict[str, Any]] = {"q": soql_query.strip()}

        while url:
            data = await self._get(url, params)

            for opportunity in data.get("records", []):
                yield SalesforceOpportunityEntity.from_api(
                    opportunity, build_record_url_fn=self._build_record_url
                )

            next_records_url = data.get("nextRecordsUrl")
            if next_records_url:
                url = f"https://{self.instance_url}{next_records_url}"
                params = None
            else:
                url = None

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Salesforce entities.

        - Accounts
        - Contacts
        - Opportunities
        """
        async for account_entity in self._generate_account_entities():
            yield account_entity

        async for contact_entity in self._generate_contact_entities():
            yield contact_entity

        async for opportunity_entity in self._generate_opportunity_entities():
            yield opportunity_entity

    async def validate(self) -> None:
        """Validate credentials by pinging the Salesforce OAuth2 userinfo endpoint."""
        await self._get(f"https://{self.instance_url}/services/oauth2/userinfo")
