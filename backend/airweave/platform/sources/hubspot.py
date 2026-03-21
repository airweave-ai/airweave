"""HubSpot source implementation."""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import HubspotConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.hubspot import (
    HubspotCompanyEntity,
    HubspotContactEntity,
    HubspotDealEntity,
    HubspotTicketEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="HubSpot",
    short_name="hubspot",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    config_class=HubspotConfig,
    labels=["CRM", "Marketing"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class HubspotSource(BaseSource):
    """HubSpot source connector integrates with the HubSpot CRM API to extract CRM data.

    Synchronizes customer relationship management data.

    It provides comprehensive access to contacts, companies, deals, and support tickets.
    """

    HUBSPOT_API_LIMIT = 100
    HUBSPOT_BATCH_SIZE = 100

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: HubspotConfig,
    ) -> HubspotSource:
        """Create a new HubSpot source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance._property_cache: Dict[str, List[str]] = {}
        instance._portal_id: Optional[str] = None
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str) -> Dict:
        """Make authenticated GET request to HubSpot API."""
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.http_client.get(url, headers=headers)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers = {"Authorization": f"Bearer {new_token}"}
            response = await self.http_client.get(url, headers=headers)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post(self, url: str, json_data: Dict[str, Any]) -> Dict:
        """Make authenticated POST request to HubSpot API."""
        token = await self.auth.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = await self.http_client.post(url, headers=headers, json=json_data)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers = {
                "Authorization": f"Bearer {new_token}",
                "Content-Type": "application/json",
            }
            response = await self.http_client.post(url, headers=headers, json=json_data)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    def _safe_float_conversion(self, value: Any) -> Optional[float]:
        """Safely convert a value to float, handling empty strings and None."""
        if not value or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    async def _get_all_properties(self, object_type: str) -> List[str]:
        """Get all available properties for a specific HubSpot object type.

        Args:
            object_type: HubSpot object type (contacts, companies, deals, tickets)

        Returns:
            List of property names available for the object type
        """
        if object_type in self._property_cache:
            return self._property_cache[object_type]

        url = f"https://api.hubapi.com/crm/v3/properties/{object_type}"
        try:
            data = await self._get(url)
            properties = [prop.get("name") for prop in data.get("results", []) if prop.get("name")]
            self._property_cache[object_type] = properties
            return properties
        except SourceAuthError:
            raise
        except Exception:
            fallback_properties = {
                "contacts": [
                    "firstname",
                    "lastname",
                    "email",
                    "phone",
                    "company",
                    "website",
                    "lifecyclestage",
                    "createdate",
                    "lastmodifieddate",
                ],
                "companies": [
                    "name",
                    "domain",
                    "industry",
                    "city",
                    "state",
                    "country",
                    "createdate",
                    "lastmodifieddate",
                    "numberofemployees",
                ],
                "deals": [
                    "dealname",
                    "amount",
                    "dealstage",
                    "pipeline",
                    "closedate",
                    "createdate",
                    "lastmodifieddate",
                    "dealtype",
                ],
                "tickets": [
                    "subject",
                    "content",
                    "hs_ticket_priority",
                    "hs_ticket_category",
                    "createdate",
                    "lastmodifieddate",
                    "hs_ticket_id",
                ],
            }
            properties = fallback_properties.get(object_type, [])
            self._property_cache[object_type] = properties
            return properties

    def _clean_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Remove null, empty string, and meaningless values from properties.

        Args:
            properties: Raw properties dictionary from HubSpot

        Returns:
            Cleaned properties dictionary with only meaningful values
        """
        cleaned = {}
        for key, value in properties.items():
            if value is not None and value != "" and value != "0" and value != "false":
                if isinstance(value, str):
                    if value == "0" and any(
                        keyword in key.lower()
                        for keyword in ["count", "number", "num_", "score", "revenue", "amount"]
                    ):
                        cleaned[key] = value
                    elif value == "false" and any(
                        keyword in key.lower()
                        for keyword in ["is_", "has_", "opt", "enable", "active"]
                    ):
                        cleaned[key] = value
                    elif value not in ["0", "false"]:
                        cleaned[key] = value
                else:
                    cleaned[key] = value
        return cleaned

    async def _ensure_portal_id(self) -> Optional[str]:
        """Fetch and cache the HubSpot portal ID for building record URLs."""
        if self._portal_id:
            return self._portal_id
        info_url = "https://api.hubapi.com/integrations/v1/me"
        try:
            data = await self._get(info_url)
            portal_id = data.get("portalId")
            if portal_id:
                self._portal_id = str(portal_id)
            else:
                self.logger.warning("HubSpot response missing portalId; web URLs will be disabled.")
        except SourceAuthError:
            raise
        except Exception as exc:
            self.logger.warning("Failed to fetch HubSpot portal ID: %s", exc)
        return self._portal_id

    def _build_record_url(self, object_type: str, object_id: str) -> Optional[str]:
        """Build a HubSpot UI URL for the given object."""
        if not self._portal_id:
            return None
        return (
            f"https://app.hubspot.com/contacts/{self._portal_id}/record/{object_type}/{object_id}"
        )

    async def _generate_contact_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Contact entities from HubSpot.

        This uses the REST CRM API endpoint for contacts:
          GET /crm/v3/objects/contacts
        """
        all_properties = await self._get_all_properties("contacts")

        fetch_start = time.time()
        self.logger.info("Fetching all contact IDs (paginated)...")

        url = f"https://api.hubapi.com/crm/v3/objects/contacts?limit={self.HUBSPOT_API_LIMIT}"
        contact_ids = []
        while url:
            data = await self._get(url)
            for contact in data.get("results", []):
                contact_ids.append(contact["id"])

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

        fetch_duration = time.time() - fetch_start
        self.logger.info(f"Fetched {len(contact_ids)} contact IDs in {fetch_duration:.2f}s")

        self.logger.info(f"Batch reading {len(contact_ids)} contacts with properties...")
        batch_url = "https://api.hubapi.com/crm/v3/objects/contacts/batch/read"
        for i in range(0, len(contact_ids), self.HUBSPOT_BATCH_SIZE):
            chunk = contact_ids[i : i + self.HUBSPOT_BATCH_SIZE]
            data = await self._post(
                batch_url,
                {
                    "inputs": [{"id": contact_id} for contact_id in chunk],
                    "properties": all_properties,
                },
            )

            for contact in data.get("results", []):
                raw_properties = contact.get("properties", {})
                cleaned_properties = self._clean_properties(raw_properties)
                yield HubspotContactEntity.from_api(
                    contact,
                    cleaned_properties=cleaned_properties,
                    web_url_value=self._build_record_url("0-1", contact["id"]),
                )

    async def _generate_company_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Company entities from HubSpot.

        This uses the REST CRM API endpoint for companies:
          GET /crm/v3/objects/companies
        """
        all_properties = await self._get_all_properties("companies")

        fetch_start = time.time()
        self.logger.info("Fetching all company IDs (paginated)...")

        url = f"https://api.hubapi.com/crm/v3/objects/companies?limit={self.HUBSPOT_API_LIMIT}"
        company_ids = []
        while url:
            data = await self._get(url)
            for company in data.get("results", []):
                company_ids.append(company["id"])

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

        fetch_duration = time.time() - fetch_start
        self.logger.info(f"Fetched {len(company_ids)} company IDs in {fetch_duration:.2f}s")

        self.logger.info(f"Batch reading {len(company_ids)} companies with properties...")
        batch_url = "https://api.hubapi.com/crm/v3/objects/companies/batch/read"
        for i in range(0, len(company_ids), self.HUBSPOT_BATCH_SIZE):
            chunk = company_ids[i : i + self.HUBSPOT_BATCH_SIZE]
            data = await self._post(
                batch_url,
                {
                    "inputs": [{"id": company_id} for company_id in chunk],
                    "properties": all_properties,
                },
            )

            for company in data.get("results", []):
                raw_properties = company.get("properties", {})
                cleaned_properties = self._clean_properties(raw_properties)
                yield HubspotCompanyEntity.from_api(
                    company,
                    cleaned_properties=cleaned_properties,
                    web_url_value=self._build_record_url("0-2", company["id"]),
                )

    async def _generate_deal_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Deal entities from HubSpot.

        This uses the REST CRM API endpoint for deals:
          GET /crm/v3/objects/deals
        """
        all_properties = await self._get_all_properties("deals")

        url = f"https://api.hubapi.com/crm/v3/objects/deals?limit={self.HUBSPOT_API_LIMIT}"
        deal_ids = []
        while url:
            data = await self._get(url)
            for deal in data.get("results", []):
                deal_ids.append(deal["id"])

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

        batch_url = "https://api.hubapi.com/crm/v3/objects/deals/batch/read"
        for i in range(0, len(deal_ids), self.HUBSPOT_BATCH_SIZE):
            chunk = deal_ids[i : i + self.HUBSPOT_BATCH_SIZE]
            data = await self._post(
                batch_url,
                {
                    "inputs": [{"id": deal_id} for deal_id in chunk],
                    "properties": all_properties,
                },
            )

            for deal in data.get("results", []):
                raw_properties = deal.get("properties", {})
                cleaned_properties = self._clean_properties(raw_properties)
                yield HubspotDealEntity.from_api(
                    deal,
                    cleaned_properties=cleaned_properties,
                    web_url_value=self._build_record_url("0-3", deal["id"]),
                )

    async def _generate_ticket_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Ticket entities from HubSpot.

        This uses the REST CRM API endpoint for tickets:
          GET /crm/v3/objects/tickets
        """
        all_properties = await self._get_all_properties("tickets")

        fetch_start = time.time()
        self.logger.info("Fetching all ticket IDs (paginated)...")

        url = f"https://api.hubapi.com/crm/v3/objects/tickets?limit={self.HUBSPOT_API_LIMIT}"
        ticket_ids = []
        while url:
            data = await self._get(url)
            for ticket in data.get("results", []):
                ticket_ids.append(ticket["id"])

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

        fetch_duration = time.time() - fetch_start
        self.logger.info(f"Fetched {len(ticket_ids)} ticket IDs in {fetch_duration:.2f}s")

        self.logger.info(f"Batch reading {len(ticket_ids)} tickets with properties...")
        batch_url = "https://api.hubapi.com/crm/v3/objects/tickets/batch/read"
        for i in range(0, len(ticket_ids), self.HUBSPOT_BATCH_SIZE):
            chunk = ticket_ids[i : i + self.HUBSPOT_BATCH_SIZE]
            data = await self._post(
                batch_url,
                {
                    "inputs": [{"id": ticket_id} for ticket_id in chunk],
                    "properties": all_properties,
                },
            )

            for ticket in data.get("results", []):
                raw_properties = ticket.get("properties", {})
                cleaned_properties = self._clean_properties(raw_properties)
                yield HubspotTicketEntity.from_api(
                    ticket,
                    cleaned_properties=cleaned_properties,
                    web_url_value=self._build_record_url("0-5", ticket["id"]),
                )

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from HubSpot.

        Yields:
            HubSpot entities: Contacts, Companies, Deals, and Tickets.
        """
        await self._ensure_portal_id()

        async for contact_entity in self._generate_contact_entities():
            yield contact_entity

        async for company_entity in self._generate_company_entities():
            yield company_entity

        async for deal_entity in self._generate_deal_entities():
            yield deal_entity

        async for ticket_entity in self._generate_ticket_entities():
            yield ticket_entity

    async def validate(self) -> None:
        """Validate credentials by pinging a lightweight CRM endpoint."""
        await self._get("https://api.hubapi.com/crm/v3/objects/contacts?limit=1")
