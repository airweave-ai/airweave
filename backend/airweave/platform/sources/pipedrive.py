"""
Pipedrive source implementation.

Retrieves data (read-only) from a user's Pipedrive account via Pipedrive API:
 - Organizations
 - Deals (associated with organizations or persons)

References:
    https://developers.pipedrive.com/docs/api/v1/Organizations
    https://developers.pipedrive.com/docs/api/v1/Deals

This connector follows the general style of other source connectors (e.g., Outlook Mail, Asana, HubSpot).
"""

from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.pipedrive import PipedriveDealEntity, PipedriveOrganizationEntity
from airweave.platform.sources._base import BaseSource


@source(
    "Pipedrive", "pipedrive", AuthType.oauth2_with_refresh, labels=["CRM", "Sales"]
)
class PipedriveSource(BaseSource):
    """Pipedrive source implementation (read-only).

    This connector retrieves Pipedrive organizations and yields PipedriveOrganizationEntity
    for each organization. For each organization, it also retrieves associated deals
    and yields PipedriveDealEntity items.
    """

    API_BASE_URL = "https://api.pipedrive.com/v1"

    @classmethod
    async def create(cls, access_token: str) -> "PipedriveSource":
        """Create a PipedriveSource instance with the given access token."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
        """Utility to make an authenticated GET request to Pipedrive API.

        Raises for non-2xx responses and returns parsed JSON.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def _generate_organization_entities(
        self,
        client: httpx.AsyncClient,
        parent_breadcrumbs: Optional[list[Breadcrumb]] = None,
    ) -> AsyncGenerator[PipedriveOrganizationEntity, None]:
        """Generate PipedriveOrganizationEntity objects.

        Fetches organizations with GET /organizations.
        """
        if parent_breadcrumbs is None:
            parent_breadcrumbs = []

        url = f"{self.API_BASE_URL}/organizations"
        while url:
            data = await self._get_with_auth(client, url)
            for org in data.get("data", []):
                # Yield organization entity
                org_entity = PipedriveOrganizationEntity(
                    entity_id=str(org["id"]),
                    breadcrumbs=parent_breadcrumbs,
                    name=org.get("name"),
                    address=org.get("address"),
                    address_country=org.get("address_country"),
                    people_count=org.get("people_count"),
                    open_deals_count=org.get("open_deals_count"),
                    closed_deals_count=org.get("closed_deals_count"),
                    owner_id=org.get("owner_id"),
                    created_at=org.get("add_time"),
                    updated_at=org.get("update_time"),
                )
                yield org_entity

                # Build breadcrumb for this organization
                org_breadcrumb = Breadcrumb(
                    entity_id=org_entity.entity_id,
                    name=org_entity.name,
                    type="organization",
                )

                # Generate deals associated with this organization
                async for deal_entity in self._generate_deal_entities(
                    client, org_entity, parent_breadcrumbs + [org_breadcrumb]
                ):
                    yield deal_entity

            # Handle pagination
            next_page = data.get("additional_data", {}).get("pagination", {}).get("next_start")
            url = f"{self.API_BASE_URL}/organizations?start={next_page}" if next_page else None

    async def _generate_deal_entities(
        self,
        client: httpx.AsyncClient,
        org_entity: Optional[PipedriveOrganizationEntity] = None,
        parent_breadcrumbs: Optional[list[Breadcrumb]] = None,
    ) -> AsyncGenerator[PipedriveDealEntity, None]:
        """Generate PipedriveDealEntity objects for a given organization.

        Fetches deals with GET /deals, optionally filtered by organization.
        """
        if parent_breadcrumbs is None:
            parent_breadcrumbs = []

        url = f"{self.API_BASE_URL}/deals"
        if org_entity:
            url += f"?org_id={org_entity.entity_id}"

        while url:
            data = await self._get_with_auth(client, url)
            for deal in data.get("data", []):
                yield PipedriveDealEntity(
                    entity_id=str(deal["id"]),
                    breadcrumbs=parent_breadcrumbs,
                    title=deal.get("title"),
                    value=deal.get("value"),
                    currency=deal.get("currency"),
                    status=deal.get("status"),
                    stage_id=deal.get("stage_id"),
                    pipeline_id=deal.get("pipeline_id"),
                    probability=deal.get("probability"),
                    expected_close_date=deal.get("expected_close_date"),
                    org_id=deal.get("org_id"),
                    person_id=deal.get("person_id"),
                    owner_id=deal.get("owner_id"),
                    creator_user_id=deal.get("creator_user_id"),
                    has_activities=bool(deal.get("activities_count", 0)),
                    activities_count=deal.get("activities_count"),
                    notes_count=deal.get("notes_count"),
                    created_at=deal.get("add_time"),
                    updated_at=deal.get("update_time"),
                    add_time=deal.get("add_time"),
                    won_time=deal.get("won_time"),
                    lost_time=deal.get("lost_time"),
                )

            # Handle pagination
            next_page = data.get("additional_data", {}).get("pagination", {}).get("next_start")
            url = f"{self.API_BASE_URL}/deals?start={next_page}" if next_page else None

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Pipedrive entities.

        Yields entities in the following order:
          - Organizations
          - Deals associated with each organization
        """
        async with httpx.AsyncClient() as client:
            # Generate all organizations and their associated deals
            async for entity in self._generate_organization_entities(client):
                yield entity