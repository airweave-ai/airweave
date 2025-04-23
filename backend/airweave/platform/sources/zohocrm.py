"""
Zoho CRM source implementation.

Retrieves data (read-only) from a user's Zoho CRM account via Zoho CRM API v2:
    - Modules (e.g., Leads, Accounts, Contacts, Deals)
    - Records (within each module)
    - Notes (attached to each record)

References:
    https://www.zoho.com/crm/developer/docs/api/v2/modules-api.html
    https://www.zoho.com/crm/developer/docs/api/v2/records-api.html
    https://www.zoho.com/crm/developer/docs/api/v2/notes-api.html
"""

import logging
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.zohocrm import (
    ZohoCRMModuleEntity,
    ZohoCRMNoteEntity,
    ZohoCRMRecordEntity,
)
from airweave.platform.sources._base import BaseSource

logger = logging.getLogger(__name__)


@source(
    "Zoho CRM", "zohocrm", AuthType.oauth2_with_refresh, labels=["CRM", "Customer Service" , "Marketing"]
)
class ZohoCRMSource(BaseSource):
    """Zoho CRM source implementation (read-only).

    This connector retrieves hierarchical data from Zoho CRM's REST API:
        - Modules (e.g., Leads, Accounts, Contacts, Deals)
        - Records (within each module)
        - Notes (attached to each record)
    """

    BASE_URL = "https://www.zohoapis.com/crm/v2/"

    @classmethod
    async def create(cls, access_token: str) -> "ZohoCRMSource":
        """Create a new Zoho CRM source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _make_request(
        self, client: httpx.AsyncClient, method: str, endpoint: str, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an authenticated HTTP request to the Zoho CRM API."""
        url = f"{self.BASE_URL}{endpoint}"
        logger.debug(f"Making request to: {url}")
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json",
        }
        response = await client.request(method, url, headers=headers, params=params)
        logger.debug(f"Response status: {response.status_code}")
        response.raise_for_status()
        return response.json()

    async def _fetch_modules(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch all Zoho CRM modules."""
        logger.debug("Generating Module entities")
        params = {"type": "all"}
        data = await self._make_request(client, "GET", "settings/modules", params=params)
        for module in data.get("modules", []):
            yield module

    async def _generate_record_entities(
        self, client: httpx.AsyncClient, module: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate records for a given module."""
        logger.debug(f"Generating Record entities for module: {module['api_name']}")
        page = 1
        per_page = 200  # Zoho CRM max per_page is 200
        while True:
            params = {"page": page, "per_page": per_page}
            data = await self._make_request(client, "GET", module["api_name"], params=params)
            records = data.get("data", [])
            if not records:
                break
            for record in records:
                yield record
            page += 1

    async def _generate_note_entities(
        self, client: httpx.AsyncClient, module: Dict[str, Any], record: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate notes for a given record in a module."""
        logger.debug(f"Generating Note entities for record: {record['id']} in module: {module['api_name']}")
        data = await self._make_request(client, "GET", f"{module['api_name']}/{record['id']}/Notes")
        for note in data.get("data", []):
            yield note

    async def generate_entities(self) -> AsyncGenerator[Any, None]:
        """Generate all Zoho CRM entities (Modules, Records, Notes)."""
        logger.debug("Generating Zoho CRM entities")
        async with httpx.AsyncClient() as client:
            # Generate Module entities
            async for module in self._fetch_modules(client):
                module_entity = ZohoCRMModuleEntity(
                    entity_id=module.get("api_name"),
                    module_id=module.get("api_name"),
                    module_name=module.get("singular_label"),
                    plural_label=module.get("plural_label"),
                    is_custom=module.get("is_custom", False),
                    is_global_search_supported=module.get("global_search_supported", False),
                    record_count=module.get("record_count"),
                    created_at=module.get("created_time"),
                    modified_at=module.get("modified_time"),
                )
                yield module_entity

                # Build breadcrumb for this module
                module_breadcrumb = Breadcrumb(
                    entity_id=module_entity.entity_id,
                    name=module_entity.plural_label,
                    type="module",
                )

                # Generate Record entities for this module
                async for record in self._generate_record_entities(client, module):
                    record_entity = ZohoCRMRecordEntity(
                        entity_id=record.get("id"),
                        breadcrumbs=[module_breadcrumb],
                        module_id=module.get("api_name"),
                        record_id=record.get("id"),
                        data=record,
                        owner=record.get("Owner"),
                        created_by=record.get("Created_By"),
                        modified_by=record.get("Modified_By"),
                        created_at=record.get("Created_Time"),
                        modified_at=record.get("Modified_Time"),
                        has_notes=bool(record.get("Notes", [])),
                        notes_count=len(record.get("Notes", [])) if record.get("Notes") else 0,
                    )
                    yield record_entity

                    # Build breadcrumb for this record
                    record_name = record.get("Name") or record.get("id")
                    record_breadcrumb = Breadcrumb(
                        entity_id=record_entity.entity_id,
                        name=record_name,
                        type="record",
                    )

                    # Generate Note entities for this record
                    async for note in self._generate_note_entities(client, module, record):
                        note_entity = ZohoCRMNoteEntity(
                            entity_id=note.get("id"),
                            breadcrumbs=[module_breadcrumb, record_breadcrumb],
                            note_id=note.get("id"),
                            module_id=module.get("api_name"),
                            record_id=record.get("id"),
                            note_content=note.get("Note_Content", ""),
                            created_by=note.get("Created_By"),
                            modified_by=note.get("Modified_By"),
                            created_at=note.get("Created_Time"),
                            modified_at=note.get("Modified_Time"),
                        )
                        yield note_entity