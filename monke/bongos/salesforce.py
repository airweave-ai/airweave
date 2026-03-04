import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx

from monke.bongos.base_bongo import BaseBongo
from monke.generation.salesforce import generate_salesforce_contact
from monke.utils.logging import get_logger


class SalesforceBongo(BaseBongo):
    """Creates/updates/deletes Salesforce Contacts using OAuth token."""

    connector_type = "salesforce"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        # instance_url can come from config_fields (kwargs) or from the credentials blob (Composio)
        raw_instance_url = kwargs.get("instance_url") or credentials.get(
            "instance_url", ""
        )
        self.instance_url: str = raw_instance_url.replace("https://", "").replace(
            "http://", ""
        )
        self.api_version: str = kwargs.get("api_version", "58.0")
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 200)) / 1000.0
        self.logger = get_logger("salesforce_bongo")
        self._contacts: List[Dict[str, Any]] = []
        self._last_req = 0.0

    def _get_base_url(self) -> str:
        """Get the base URL for Salesforce API calls."""
        if not self.instance_url:
            raise ValueError("Salesforce instance_url is not set")
        return f"https://{self.instance_url}/services/data/v{self.api_version}"

    async def create_entities(self) -> List[Dict[str, Any]]:
        self.logger.info(f"🥁 Creating {self.entity_count} Salesforce contacts")
        out: List[Dict[str, Any]] = []

        # Generate all contacts in parallel
        tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]

        async def generate_contact_data(token: str):
            c = await generate_salesforce_contact(self.openai_model, token)
            return token, c

        # Generate all content in parallel
        gen_results = await asyncio.gather(
            *[generate_contact_data(token) for token in tokens]
        )

        # Create contacts sequentially to respect API rate limits
        async with httpx.AsyncClient(timeout=30) as client:
            for token, c in gen_results:
                await self._pace()
                payload = {
                    "FirstName": c.first_name,
                    "LastName": c.last_name,
                    "Email": c.email,
                    **({"Phone": c.phone} if c.phone else {}),
                    **({"MobilePhone": c.mobile_phone} if c.mobile_phone else {}),
                    **({"Title": c.title} if c.title else {}),
                    **({"Department": c.department} if c.department else {}),
                    **({"Description": c.description} if c.description else {}),
                    # Mailing address fields omitted -- Salesforce has strict
                    # picklist/dependency validation that LLM-generated values fail
                }
                r = await client.post(
                    f"{self._get_base_url()}/sobjects/Contact",
                    headers=self._hdrs(),
                    json=payload,
                )
                if r.status_code not in (200, 201):
                    self.logger.error(
                        f"Salesforce create failed {r.status_code}: {r.text}"
                    )
                r.raise_for_status()
                data = r.json()
                contact_id = data.get("id")
                ent = {
                    "type": "contact",
                    "id": contact_id,
                    "name": f"{c.first_name} {c.last_name}",
                    "token": token,
                    "expected_content": token,
                    "path": f"salesforce/contact/{contact_id}",
                }
                out.append(ent)
                self._contacts.append(ent)
                self.created_entities.append({"id": contact_id, "name": ent["name"]})
        return out

    async def update_entities(self) -> List[Dict[str, Any]]:
        if not self._contacts:
            return []
        self.logger.info("🥁 Updating some Salesforce contacts")
        updated: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for ent in self._contacts[: min(3, len(self._contacts))]:
                await self._pace()
                # Update contact with test data
                r = await client.patch(
                    f"{self._get_base_url()}/sobjects/Contact/{ent['id']}",
                    headers=self._hdrs(),
                    json={
                        "Title": "Senior Test Engineer",
                        "Department": "Monke QA",
                        "Phone": "+1-555-0100",
                    },
                )
                r.raise_for_status()
                updated.append({**ent, "updated": True})
        return updated

    async def delete_entities(self) -> List[str]:
        return await self.delete_specific_entities(self._contacts)

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        self.logger.info(f"🥁 Deleting {len(entities)} Salesforce contacts")
        deleted: List[str] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for ent in entities:
                try:
                    await self._pace()
                    r = await client.delete(
                        f"{self._get_base_url()}/sobjects/Contact/{ent['id']}",
                        headers=self._hdrs(),
                    )
                    if r.status_code in (200, 204):
                        deleted.append(ent["id"])
                    else:
                        self.logger.warning(f"Delete failed {r.status_code}: {r.text}")
                except Exception as e:
                    self.logger.warning(f"Delete error {ent['id']}: {e}")
        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all test Salesforce contacts."""
        self.logger.info("🧹 Starting comprehensive Salesforce cleanup")

        cleanup_stats = {"contacts_deleted": 0, "errors": 0}

        try:
            # First, delete current session contacts
            if self._contacts:
                self.logger.info(
                    f"🗑️ Cleaning up {len(self._contacts)} current session contacts"
                )
                deleted = await self.delete_specific_entities(self._contacts)
                cleanup_stats["contacts_deleted"] += len(deleted)
                self._contacts.clear()

            # Search for any remaining monke test contacts
            await self._cleanup_orphaned_test_contacts(cleanup_stats)

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['contacts_deleted']} contacts deleted, "
                f"{cleanup_stats['errors']} errors"
            )
        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")

    async def _cleanup_orphaned_test_contacts(self, stats: Dict[str, Any]):
        """Find and delete orphaned test contacts from previous runs."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # SOQL query to find test contacts
                soql_query = """
                    SELECT Id, FirstName, LastName, Email
                    FROM Contact
                    WHERE Email LIKE '%example.test%'
                    OR Email LIKE '%monke.test%'
                    OR FirstName LIKE '%test%'
                    OR LastName LIKE '%test%'
                    LIMIT 100
                """
                r = await client.get(
                    f"{self._get_base_url()}/query",
                    headers=self._hdrs(),
                    params={"q": soql_query.strip()},
                )

                if r.status_code == 200:
                    contacts = r.json().get("records", [])

                    if contacts:
                        self.logger.info(
                            f"🔍 Found {len(contacts)} potential test contacts to clean"
                        )
                        for contact in contacts:
                            try:
                                await self._pace()
                                del_r = await client.delete(
                                    f"{self._get_base_url()}/sobjects/Contact/{contact['Id']}",
                                    headers=self._hdrs(),
                                )
                                if del_r.status_code in (204, 200):
                                    stats["contacts_deleted"] += 1
                                    self.logger.info(
                                        f"✅ Deleted orphaned contact: "
                                        f"{contact.get('Email', 'unknown')}"
                                    )
                                else:
                                    stats["errors"] += 1
                            except Exception as e:
                                stats["errors"] += 1
                                self.logger.warning(
                                    f"⚠️ Failed to delete contact {contact['Id']}: {e}"
                                )
        except Exception as e:
            self.logger.warning(f"⚠️ Could not search for orphaned contacts: {e}")

    def _hdrs(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Sforce-Duplicate-Rule-Header": "allowSave=true",
        }

    async def _pace(self):
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()
