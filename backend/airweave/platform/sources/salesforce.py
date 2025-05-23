"""
Salesforce source implementation.

Retrieves data (read-only) from a user's Salesforce org via Salesforce REST API:
    - Objects (e.g., Accounts, Contacts, Opportunities)
    - Records (within each object)
    - Notes (attached to each record)

References:
    https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_sobjects.htm
    https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_sobject_basic_info.htm
    https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_sobject_note.htm
"""

import logging
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.salesforce import (
    SalesforceObjectEntity,
    SalesforceRecordEntity,
    SalesforceNoteEntity,
)
from airweave.platform.sources._base import BaseSource

logger = logging.getLogger(__name__)


@source(
    "Salesforce", "salesforce", AuthType.oauth2_with_refresh, labels=["CRM", "Marketing"]
)
class SalesforceSource(BaseSource):
    """Salesforce source implementation (read-only).

    This connector retrieves hierarchical data from Salesforce's REST API:
        - Objects (e.g., Accounts, Contacts, Opportunities)
        - Records (within each object)
        - Notes (attached to each record)
    """

    BASE_URL = "https://<instance>.salesforce.com/services/data/v59.0/"

    @classmethod
    async def create(cls, access_token: str, instance_url: str) -> "SalesforceSource":
        """Create a new Salesforce source instance."""
        instance = cls()
        instance.access_token = access_token
        instance.instance_url = instance_url
        instance.BASE_URL = instance.BASE_URL.replace("<instance>", instance_url.split("://")[1].split(".")[0])
        return instance

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _make_request(
        self, client: httpx.AsyncClient, method: str, endpoint: str, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an authenticated HTTP request to the Salesforce API."""
        url = f"{self.BASE_URL}{endpoint}"
        logger.debug(f"Making request to: {url}")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        response = await client.request(method, url, headers=headers, params=params)
        logger.debug(f"Response status: {response.status_code}")
        response.raise_for_status()
        return response.json()

    async def _fetch_objects(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch all Salesforce objects."""
        logger.debug("Generating Object entities")
        data = await self._make_request(client, "GET", "sobjects")
        for sobject in data.get("sobjects", []):
            if sobject.get("queryable", False):  # Only include queryable objects
                yield sobject

    async def _generate_record_entities(
        self, client: httpx.AsyncClient, sobject: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate records for a given Salesforce object using SOQL."""
        logger.debug(f"Generating Record entities for object: {sobject['name']}")
        query = f"SELECT Id, Name, OwnerId, CreatedById, CreatedDate, LastModifiedById, LastModifiedDate FROM {sobject['name']}"
        url = f"query?q={query}"
        while url:
            data = await self._make_request(client, "GET", url)
            records = data.get("records", [])
            for record in records:
                yield record
            url = data.get("nextRecordsUrl")

    async def _generate_note_entities(
        self, client: httpx.AsyncClient, sobject: Dict[str, Any], record: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate notes for a given record in a Salesforce object."""
        logger.debug(f"Generating Note entities for record: {record['Id']} in object: {sobject['name']}")
        data = await self._make_request(client, "GET", f"sobjects/{sobject['name']}/{record['Id']}/Notes")
        for note in data.get("records", []):
            yield note

    async def generate_entities(self) -> AsyncGenerator[Any, None]:
        """Generate all Salesforce entities (Objects, Records, Notes)."""
        logger.debug("Generating Salesforce entities")
        async with httpx.AsyncClient() as client:
            # Generate Object entities
            async for sobject in self._fetch_objects(client):
                object_entity = SalesforceObjectEntity(
                    entity_id=sobject.get("name"),
                    object_name=sobject.get("name"),
                    label=sobject.get("label"),
                    label_plural=sobject.get("labelPlural"),
                    is_custom=sobject.get("custom", False),
                    is_searchable=sobject.get("searchable", False),
                    created_date=sobject.get("createdDate"),
                    last_modified_date=sobject.get("lastModifiedDate"),
                )
                yield object_entity

                # Build breadcrumb for this object
                object_breadcrumb = Breadcrumb(
                    entity_id=object_entity.entity_id,
                    name=object_entity.label_plural,
                    type="object",
                )

                # Generate Record entities for this object
                async for record in self._generate_record_entities(client, sobject):
                    record_entity = SalesforceRecordEntity(
                        entity_id=record.get("Id"),
                        breadcrumbs=[object_breadcrumb],
                        object_name=sobject.get("name"),
                        record_id=record.get("Id"),
                        data=record,
                        owner_id=record.get("OwnerId"),
                        created_by_id=record.get("CreatedById"),
                        last_modified_by_id=record.get("LastModifiedById"),
                        created_date=record.get("CreatedDate"),
                        last_modified_date=record.get("LastModifiedDate"),
                        has_notes=False,  # Will be updated if notes are found
                    )
                    yield record_entity

                    # Build breadcrumb for this record
                    record_name = record.get("Name") or record.get("Id")
                    record_breadcrumb = Breadcrumb(
                        entity_id=record_entity.entity_id,
                        name=record_name,
                        type="record",
                    )

                    # Generate Note entities for this record
                    async for note in self._generate_note_entities(client, sobject, record):
                        record_entity.has_notes = True
                        note_entity = SalesforceNoteEntity(
                            entity_id=note.get("Id"),
                            breadcrumbs=[object_breadcrumb, record_breadcrumb],
                            note_id=note.get("Id"),
                            object_name=sobject.get("name"),
                            record_id=record.get("Id"),
                            title=note.get("Title"),
                            body=note.get("Body", ""),
                            owner_id=note.get("OwnerId"),
                            created_by_id=note.get("CreatedById"),
                            last_modified_by_id=note.get("LastModifiedById"),
                            created_date=note.get("CreatedDate"),
                            last_modified_date=note.get("LastModifiedDate"),
                            is_private=note.get("IsPrivate", False),
                        )
                        yield note_entity