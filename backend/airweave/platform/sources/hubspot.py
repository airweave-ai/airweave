"""HubSpot source implementation."""

from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity
from airweave.platform.entities.hubspot import (
    HubspotCompanyEntity,
    HubspotContactEntity,
    HubspotDealEntity,
    HubspotTicketEntity,
    parse_hubspot_datetime,
)
from airweave.platform.sources._base import BaseSource


@source(
    name="HubSpot",
    short_name="hubspot",
    auth_type=AuthType.oauth2_with_refresh,
    auth_config_class="HubspotAuthConfig",
    config_class="HubspotConfig",
    labels=["CRM", "Marketing"],
)
class HubspotSource(BaseSource):
    """HubSpot source implementation.

    This connector retrieves data from HubSpot CRM objects such as Contacts,
    Companies, Deals, and Tickets, then yields them as entities using
    their respective entity schemas.
    """

    def __init__(self):
        """Initialize the HubSpot source."""
        super().__init__()
        # Cache for property names to avoid repeated API calls
        self._property_cache: Dict[str, List[str]] = {}

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "HubspotSource":
        """Create a new HubSpot source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Dict:
        """Make authenticated GET request to HubSpot API."""
        return await self._make_authenticated_request(
            lambda token: client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
        )

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

    async def _generate_contact_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Contact entities from HubSpot.

        This uses the REST CRM API endpoint for contacts:
          GET /crm/v3/objects/contacts
        """
        # Get all available properties for contacts
        all_properties = await self._get_all_properties(client, "contacts")
        properties_param = ",".join(all_properties)

        url = f"https://api.hubapi.com/crm/v3/objects/contacts?properties={properties_param}"
        while url:
            data = await self._get_with_auth(client, url)
            for contact in data.get("results", []):
                raw_properties = contact.get("properties", {})
                # Clean properties to remove null/empty values
                cleaned_properties = self._clean_properties(raw_properties)

                yield HubspotContactEntity(
                    entity_id=contact["id"],
                    # Core fields for easy access
                    first_name=cleaned_properties.get("firstname"),
                    last_name=cleaned_properties.get("lastname"),
                    email=cleaned_properties.get("email"),
                    # Cleaned properties from HubSpot
                    properties=cleaned_properties,
                    created_at=parse_hubspot_datetime(contact.get("createdAt")),
                    updated_at=parse_hubspot_datetime(contact.get("updatedAt")),
                    archived=contact.get("archived", False),
                )

            # Handle pagination
            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

    async def _generate_company_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Company entities from HubSpot.

        This uses the REST CRM API endpoint for companies:
          GET /crm/v3/objects/companies
        """
        # Get all available properties for companies
        all_properties = await self._get_all_properties(client, "companies")
        properties_param = ",".join(all_properties)

        url = f"https://api.hubapi.com/crm/v3/objects/companies?properties={properties_param}"
        while url:
            data = await self._get_with_auth(client, url)
            for company in data.get("results", []):
                raw_properties = company.get("properties", {})
                # Clean properties to remove null/empty values
                cleaned_properties = self._clean_properties(raw_properties)

                yield HubspotCompanyEntity(
                    entity_id=company["id"],
                    # Core fields for easy access
                    name=cleaned_properties.get("name"),
                    domain=cleaned_properties.get("domain"),
                    # Cleaned properties from HubSpot
                    properties=cleaned_properties,
                    created_at=parse_hubspot_datetime(company.get("createdAt")),
                    updated_at=parse_hubspot_datetime(company.get("updatedAt")),
                    archived=company.get("archived", False),
                )

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

    async def _generate_deal_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Deal entities from HubSpot.

        This uses the REST CRM API endpoint for deals:
          GET /crm/v3/objects/deals
        """
        # Get all available properties for deals
        all_properties = await self._get_all_properties(client, "deals")
        properties_param = ",".join(all_properties)

        url = f"https://api.hubapi.com/crm/v3/objects/deals?properties={properties_param}"
        while url:
            data = await self._get_with_auth(client, url)
            for deal in data.get("results", []):
                raw_properties = deal.get("properties", {})
                # Clean properties to remove null/empty values
                cleaned_properties = self._clean_properties(raw_properties)

                yield HubspotDealEntity(
                    entity_id=deal["id"],
                    # Core fields for easy access
                    deal_name=cleaned_properties.get("dealname"),
                    amount=self._safe_float_conversion(cleaned_properties.get("amount")),
                    # Cleaned properties from HubSpot
                    properties=cleaned_properties,
                    created_at=parse_hubspot_datetime(deal.get("createdAt")),
                    updated_at=parse_hubspot_datetime(deal.get("updatedAt")),
                    archived=deal.get("archived", False),
                )

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

    async def _generate_ticket_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Ticket entities from HubSpot.

        This uses the REST CRM API endpoint for tickets:
          GET /crm/v3/objects/tickets
        """
        # Get all available properties for tickets
        all_properties = await self._get_all_properties(client, "tickets")
        properties_param = ",".join(all_properties)

        url = f"https://api.hubapi.com/crm/v3/objects/tickets?properties={properties_param}"
        while url:
            data = await self._get_with_auth(client, url)
            for ticket in data.get("results", []):
                raw_properties = ticket.get("properties", {})
                # Clean properties to remove null/empty values
                cleaned_properties = self._clean_properties(raw_properties)

                yield HubspotTicketEntity(
                    entity_id=ticket["id"],
                    # Core fields for easy access
                    subject=cleaned_properties.get("subject"),
                    content=cleaned_properties.get("content"),
                    # Cleaned properties from HubSpot
                    properties=cleaned_properties,
                    created_at=parse_hubspot_datetime(ticket.get("createdAt")),
                    updated_at=parse_hubspot_datetime(ticket.get("updatedAt")),
                    archived=ticket.get("archived", False),
                )

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all entities from HubSpot.

        Yields:
            HubSpot entities: Contacts, Companies, Deals, and Tickets.
        """
        async with httpx.AsyncClient() as client:
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
