"""HubSpot source implementation."""

import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import HubspotConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.hubspot import (
    HubspotCompanyEntity,
    HubspotContactEntity,
    HubspotDealEntity,
    HubspotTicketEntity,
    parse_hubspot_datetime,
)
from airweave.platform.sources._base import BaseSource
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

    # HubSpot API limits
    HUBSPOT_API_LIMIT = 100  # Maximum results per page for list endpoints
    HUBSPOT_BATCH_SIZE = 100  # Maximum items per batch read request

    def __init__(self):
        """Initialize the HubSpot source."""
        super().__init__()
        # Cache for property names to avoid repeated API calls
        self._property_cache: Dict[str, List[str]] = {}
        self._portal_id: Optional[str] = None

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "HubspotSource":
        """Create a new HubSpot source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Dict:
        """Make authenticated GET request to HubSpot API.

        For example, to retrieve contacts:
          GET https://api.hubapi.com/crm/v3/objects/contacts
        """
        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await client.get(url, headers=headers)

        # Handle 401 errors by refreshing token and retrying
        if response.status_code == 401:
            self.logger.warning(
                f"Got 401 Unauthorized from HubSpot API at {url}, refreshing token..."
            )
            await self.refresh_on_unauthorized()

            # Get new token and retry
            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.get(url, headers=headers)

        # Log detailed error information for 4xx/5xx responses before raising
        if not response.is_success:
            try:
                error_body = response.json()
                correlation_id = error_body.get("correlationId", "N/A")
                error_message = error_body.get("message", "No message provided")
                error_category = error_body.get("category", "Unknown")
                self.logger.error(
                    f"❌ HubSpot API error at {url} - "
                    f"Status: {response.status_code}, "
                    f"Message: {error_message}, "
                    f"Category: {error_category}, "
                    f"CorrelationId: {correlation_id}, "
                    f"Full response: {error_body}"
                )
            except Exception:
                # If we can't parse JSON, log the raw response
                self.logger.error(
                    f"❌ HubSpot API error at {url} - "
                    f"Status: {response.status_code}, "
                    f"Response: {response.text}"
                )

        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post_with_auth(
        self, client: httpx.AsyncClient, url: str, json_data: Dict[str, Any]
    ) -> Dict:
        """Make authenticated POST request to HubSpot API.

        Args:
            client: HTTP client
            url: API endpoint URL
            json_data: JSON payload for POST body

        Returns:
            JSON response from API
        """
        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = await client.post(url, headers=headers, json=json_data)

        # Handle 401 errors by refreshing token and retrying
        if response.status_code == 401:
            self.logger.warning(
                f"Got 401 Unauthorized from HubSpot API at {url}, refreshing token..."
            )
            await self.refresh_on_unauthorized()

            # Get new token and retry
            access_token = await self.get_access_token()
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            response = await client.post(url, headers=headers, json=json_data)

        # Log detailed error information for 4xx/5xx responses before raising
        if not response.is_success:
            try:
                error_body = response.json()
                correlation_id = error_body.get("correlationId", "N/A")
                error_message = error_body.get("message", "No message provided")
                error_category = error_body.get("category", "Unknown")
                self.logger.error(
                    f"❌ HubSpot API error at {url} - "
                    f"Status: {response.status_code}, "
                    f"Message: {error_message}, "
                    f"Category: {error_category}, "
                    f"CorrelationId: {correlation_id}, "
                    f"Request body: {json_data}, "
                    f"Full response: {error_body}"
                )
            except Exception:
                # If we can't parse JSON, log the raw response
                self.logger.error(
                    f"❌ HubSpot API error at {url} - "
                    f"Status: {response.status_code}, "
                    f"Request body: {json_data}, "
                    f"Response: {response.text}"
                )

        response.raise_for_status()
        return response.json()

    def _safe_float_conversion(self, value: Any) -> Optional[float]:
        """Safely convert a value to float, handling empty strings and None."""
        if not value or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    async def _get_all_properties(self, client: httpx.AsyncClient, object_type: str) -> List[str]:
        """Get all available properties for a specific HubSpot object type.

        Args:
            client: HTTP client for making requests
            object_type: HubSpot object type (contacts, companies, deals, tickets)

        Returns:
            List of property names available for the object type
        """
        # Check cache first
        if object_type in self._property_cache:
            return self._property_cache[object_type]

        url = f"https://api.hubapi.com/crm/v3/properties/{object_type}"
        try:
            data = await self._get_with_auth(client, url)
            # Extract property names from the response
            properties = [prop.get("name") for prop in data.get("results", []) if prop.get("name")]
            # Cache the results
            self._property_cache[object_type] = properties
            return properties
        except Exception:
            # If properties API fails, return a minimal set of common properties
            # This ensures the sync can still work even if properties endpoint has issues
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
            # Skip null, empty string, and meaningless values
            if value is not None and value != "" and value != "0" and value != "false":
                # Special handling for string "0" and "false" that might be meaningful
                if isinstance(value, str):
                    # Keep "0" if it's a meaningful number-like field
                    if value == "0" and any(
                        keyword in key.lower()
                        for keyword in ["count", "number", "num_", "score", "revenue", "amount"]
                    ):
                        cleaned[key] = value
                    # Keep "false" if it's a meaningful boolean field
                    elif value == "false" and any(
                        keyword in key.lower()
                        for keyword in ["is_", "has_", "opt", "enable", "active"]
                    ):
                        cleaned[key] = value
                    # Otherwise, skip empty-ish string values
                    elif value not in ["0", "false"]:
                        cleaned[key] = value
                else:
                    cleaned[key] = value
        return cleaned

    async def _ensure_portal_id(self, client: httpx.AsyncClient) -> Optional[str]:
        """Fetch and cache the HubSpot portal ID for building record URLs."""
        if self._portal_id:
            return self._portal_id
        info_url = "https://api.hubapi.com/integrations/v1/me"
        try:
            data = await self._get_with_auth(client, info_url)
            portal_id = data.get("portalId")
            if portal_id:
                self._portal_id = str(portal_id)
            else:
                self.logger.warning("HubSpot response missing portalId; web URLs will be disabled.")
        except Exception as exc:  # pragma: no cover - network failure
            self.logger.warning("Failed to fetch HubSpot portal ID: %s", exc)
        return self._portal_id

    def _build_record_url(self, object_type: str, object_id: str) -> Optional[str]:
        """Build a HubSpot UI URL for the given object."""
        if not self._portal_id:
            return None
        return (
            f"https://app.hubspot.com/contacts/{self._portal_id}/record/{object_type}/{object_id}"
        )

    async def _generate_contact_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Contact entities from HubSpot.

        This uses the REST CRM API endpoint for contacts:
          GET /crm/v3/objects/contacts
        """
        # Get all available properties for contacts
        all_properties = await self._get_all_properties(client, "contacts")

        # Fetch all contact IDs first (without properties to avoid URI length issues)
        fetch_start = time.time()
        self.logger.info("🔍 [HUBSPOT] Fetching all contact IDs (paginated)...")

        url = f"https://api.hubapi.com/crm/v3/objects/contacts?limit={self.HUBSPOT_API_LIMIT}"
        contact_ids = []
        while url:
            data = await self._get_with_auth(client, url)
            for contact in data.get("results", []):
                contact_ids.append(contact["id"])

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

        fetch_duration = time.time() - fetch_start
        self.logger.info(
            f"✅ [HUBSPOT] Fetched {len(contact_ids)} contact IDs in {fetch_duration:.2f}s"
        )

        # Batch read contacts with all properties
        self.logger.info(
            f"🔍 [HUBSPOT] Batch reading {len(contact_ids)} contacts with properties..."
        )
        batch_url = "https://api.hubapi.com/crm/v3/objects/contacts/batch/read"
        for i in range(0, len(contact_ids), self.HUBSPOT_BATCH_SIZE):
            chunk = contact_ids[i : i + self.HUBSPOT_BATCH_SIZE]
            data = await self._post_with_auth(
                client,
                batch_url,
                {
                    "inputs": [{"id": contact_id} for contact_id in chunk],
                    "properties": all_properties,
                },
            )

            # Process results
            for contact in data.get("results", []):
                raw_properties = contact.get("properties", {})
                # Clean properties to remove null/empty values
                cleaned_properties = self._clean_properties(raw_properties)

                # Construct contact name
                first_name = cleaned_properties.get("firstname")
                last_name = cleaned_properties.get("lastname")
                email = cleaned_properties.get("email")

                if first_name and last_name:
                    contact_name = f"{first_name} {last_name}"
                elif first_name:
                    contact_name = first_name
                elif last_name:
                    contact_name = last_name
                elif email:
                    contact_name = email
                else:
                    contact_name = f"Contact {contact['id']}"

                created_time = parse_hubspot_datetime(contact.get("createdAt")) or datetime.utcnow()
                updated_time = parse_hubspot_datetime(contact.get("updatedAt")) or created_time
                yield HubspotContactEntity(
                    entity_id=contact["id"],
                    breadcrumbs=[],
                    name=contact_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    contact_id=contact["id"],
                    display_name=contact_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    properties=cleaned_properties,
                    archived=contact.get("archived", False),
                    web_url_value=self._build_record_url("0-1", contact["id"]),
                )

    async def _generate_company_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Company entities from HubSpot.

        This uses the REST CRM API endpoint for companies:
          GET /crm/v3/objects/companies
        """
        # Get all available properties for companies
        all_properties = await self._get_all_properties(client, "companies")

        # Fetch all company IDs first (without properties to avoid URI length issues)
        fetch_start = time.time()
        self.logger.info("🔍 [HUBSPOT] Fetching all company IDs (paginated)...")

        url = f"https://api.hubapi.com/crm/v3/objects/companies?limit={self.HUBSPOT_API_LIMIT}"
        company_ids = []
        while url:
            data = await self._get_with_auth(client, url)
            for company in data.get("results", []):
                company_ids.append(company["id"])

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

        fetch_duration = time.time() - fetch_start
        self.logger.info(
            f"✅ [HUBSPOT] Fetched {len(company_ids)} company IDs in {fetch_duration:.2f}s"
        )

        # Batch read companies with all properties
        self.logger.info(
            f"🔍 [HUBSPOT] Batch reading {len(company_ids)} companies with properties..."
        )
        batch_url = "https://api.hubapi.com/crm/v3/objects/companies/batch/read"
        for i in range(0, len(company_ids), self.HUBSPOT_BATCH_SIZE):
            chunk = company_ids[i : i + self.HUBSPOT_BATCH_SIZE]
            data = await self._post_with_auth(
                client,
                batch_url,
                {
                    "inputs": [{"id": company_id} for company_id in chunk],
                    "properties": all_properties,
                },
            )

            # Process results
            for company in data.get("results", []):
                raw_properties = company.get("properties", {})
                # Clean properties to remove null/empty values
                cleaned_properties = self._clean_properties(raw_properties)

                # Get company name
                company_name = cleaned_properties.get("name") or f"Company {company['id']}"

                created_time = parse_hubspot_datetime(company.get("createdAt")) or datetime.utcnow()
                updated_time = parse_hubspot_datetime(company.get("updatedAt")) or created_time
                yield HubspotCompanyEntity(
                    entity_id=company["id"],
                    breadcrumbs=[],
                    name=company_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    company_id=company["id"],
                    company_name=company_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    domain=cleaned_properties.get("domain"),
                    properties=cleaned_properties,
                    archived=company.get("archived", False),
                    web_url_value=self._build_record_url("0-2", company["id"]),
                )

    async def _generate_deal_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Deal entities from HubSpot.

        This uses the REST CRM API endpoint for deals:
          GET /crm/v3/objects/deals
        """
        # Get all available properties for deals
        all_properties = await self._get_all_properties(client, "deals")

        # Fetch all deal IDs first (without properties to avoid URI length issues)
        fetch_start = time.time()
        self.logger.info("🔍 [HUBSPOT] Fetching all deal IDs (paginated)...")

        url = f"https://api.hubapi.com/crm/v3/objects/deals?limit={self.HUBSPOT_API_LIMIT}"
        deal_ids = []
        while url:
            data = await self._get_with_auth(client, url)
            for deal in data.get("results", []):
                deal_ids.append(deal["id"])

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

        fetch_duration = time.time() - fetch_start
        self.logger.info(f"✅ [HUBSPOT] Fetched {len(deal_ids)} deal IDs in {fetch_duration:.2f}s")

        # Batch read deals with all properties
        self.logger.info(f"🔍 [HUBSPOT] Batch reading {len(deal_ids)} deals with properties...")
        batch_url = "https://api.hubapi.com/crm/v3/objects/deals/batch/read"
        for i in range(0, len(deal_ids), self.HUBSPOT_BATCH_SIZE):
            chunk = deal_ids[i : i + self.HUBSPOT_BATCH_SIZE]
            data = await self._post_with_auth(
                client,
                batch_url,
                {
                    "inputs": [{"id": deal_id} for deal_id in chunk],
                    "properties": all_properties,
                },
            )

            # Process results
            for deal in data.get("results", []):
                raw_properties = deal.get("properties", {})
                # Clean properties to remove null/empty values
                cleaned_properties = self._clean_properties(raw_properties)

                # Get deal name
                deal_name = cleaned_properties.get("dealname") or f"Deal {deal['id']}"

                created_time = parse_hubspot_datetime(deal.get("createdAt")) or datetime.utcnow()
                updated_time = parse_hubspot_datetime(deal.get("updatedAt")) or created_time
                yield HubspotDealEntity(
                    entity_id=deal["id"],
                    breadcrumbs=[],
                    name=deal_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    deal_id=deal["id"],
                    deal_name=deal_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    amount=self._safe_float_conversion(cleaned_properties.get("amount")),
                    properties=cleaned_properties,
                    archived=deal.get("archived", False),
                    web_url_value=self._build_record_url("0-3", deal["id"]),
                )

    async def _generate_ticket_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Ticket entities from HubSpot.

        This uses the REST CRM API endpoint for tickets:
          GET /crm/v3/objects/tickets
        """
        # Get all available properties for tickets
        all_properties = await self._get_all_properties(client, "tickets")

        # Fetch all ticket IDs first (without properties to avoid URI length issues)
        fetch_start = time.time()
        self.logger.info("🔍 [HUBSPOT] Fetching all ticket IDs (paginated)...")

        url = f"https://api.hubapi.com/crm/v3/objects/tickets?limit={self.HUBSPOT_API_LIMIT}"
        ticket_ids = []
        while url:
            data = await self._get_with_auth(client, url)
            for ticket in data.get("results", []):
                ticket_ids.append(ticket["id"])

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

        fetch_duration = time.time() - fetch_start
        self.logger.info(
            f"✅ [HUBSPOT] Fetched {len(ticket_ids)} ticket IDs in {fetch_duration:.2f}s"
        )

        # Batch read tickets with all properties
        self.logger.info(f"🔍 [HUBSPOT] Batch reading {len(ticket_ids)} tickets with properties...")
        batch_url = "https://api.hubapi.com/crm/v3/objects/tickets/batch/read"
        for i in range(0, len(ticket_ids), self.HUBSPOT_BATCH_SIZE):
            chunk = ticket_ids[i : i + self.HUBSPOT_BATCH_SIZE]
            data = await self._post_with_auth(
                client,
                batch_url,
                {
                    "inputs": [{"id": ticket_id} for ticket_id in chunk],
                    "properties": all_properties,
                },
            )

            # Process results
            for ticket in data.get("results", []):
                raw_properties = ticket.get("properties", {})
                # Clean properties to remove null/empty values
                cleaned_properties = self._clean_properties(raw_properties)

                # Get ticket name (from subject)
                ticket_name = cleaned_properties.get("subject") or f"Ticket {ticket['id']}"

                created_time = parse_hubspot_datetime(ticket.get("createdAt")) or datetime.utcnow()
                updated_time = parse_hubspot_datetime(ticket.get("updatedAt")) or created_time
                yield HubspotTicketEntity(
                    entity_id=ticket["id"],
                    breadcrumbs=[],
                    name=ticket_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    ticket_id=ticket["id"],
                    ticket_name=ticket_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    subject=cleaned_properties.get("subject"),
                    content=cleaned_properties.get("content"),
                    properties=cleaned_properties,
                    archived=ticket.get("archived", False),
                    web_url_value=self._build_record_url("0-5", ticket["id"]),
                )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from HubSpot.

        Yields:
            HubSpot entities: Contacts, Companies, Deals, and Tickets.
        """
        async with self.http_client() as client:
            await self._ensure_portal_id(client)
            # Yield contact entities
            async for contact_entity in self._generate_contact_entities(client):
                yield contact_entity

            # Yield company entities
            async for company_entity in self._generate_company_entities(client):
                yield company_entity

            # Yield deal entities
            async for deal_entity in self._generate_deal_entities(client):
                yield deal_entity

            # Yield ticket entities
            async for ticket_entity in self._generate_ticket_entities(client):
                yield ticket_entity

    async def validate(self) -> bool:
        """Verify HubSpot OAuth2 token by pinging a lightweight CRM endpoint."""
        return await self._validate_oauth2(
            ping_url="https://api.hubapi.com/crm/v3/objects/contacts?limit=1",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
