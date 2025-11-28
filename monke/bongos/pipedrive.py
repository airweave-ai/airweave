"""Pipedrive bongo - creates, updates, and deletes test data in Pipedrive."""

import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx

from monke.bongos.base_bongo import BaseBongo
from monke.generation.pipedrive import generate_pipedrive_person
from monke.utils.logging import get_logger

PIPEDRIVE_API = "https://api.pipedrive.com/v1"


class PipedriveBongo(BaseBongo):
    """Creates/updates/deletes Pipedrive Persons using API token."""

    connector_type = "pipedrive"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.api_token: str = credentials["api_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 500)) / 1000.0
        self.logger = get_logger("pipedrive_bongo")
        self._persons: List[Dict[str, Any]] = []
        self._last_req = 0.0

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test persons in Pipedrive."""
        self.logger.info(f"🥁 Creating {self.entity_count} Pipedrive persons")
        out: List[Dict[str, Any]] = []

        # Generate unique tokens for each entity
        tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]

        async def generate_person_data(token: str):
            p = await generate_pipedrive_person(self.openai_model, token)
            return token, p

        # Generate all content in parallel
        gen_results = await asyncio.gather(*[generate_person_data(token) for token in tokens])

        # Create persons sequentially to respect API rate limits
        async with httpx.AsyncClient(timeout=30) as client:
            for token, p in gen_results:
                await self._pace()

                # Build payload - embed token in name for vector search
                # Note: org_name is not a valid create field in Pipedrive API
                name_with_token = f"{p.name} [{token}]"
                payload = {
                    "name": name_with_token,
                    "email": [{"value": p.email, "primary": True, "label": "work"}],
                }
                if p.phone:
                    payload["phone"] = [{"value": p.phone, "primary": True, "label": "work"}]

                url = f"{PIPEDRIVE_API}/persons?api_token={self.api_token}"
                r = await client.post(url, json=payload)

                if r.status_code not in (200, 201):
                    self.logger.error(f"Pipedrive create failed {r.status_code}: {r.text}")
                r.raise_for_status()

                data = r.json()
                if not data.get("success"):
                    self.logger.error(f"Pipedrive API error: {data}")
                    continue

                person_data = data.get("data", {})
                person_id = person_data.get("id")

                ent = {
                    "type": "person",
                    "id": person_id,
                    "name": p.name,
                    "token": token,
                    "expected_content": token,
                    "path": f"pipedrive/person/{person_id}",
                }
                out.append(ent)
                self._persons.append(ent)
                self.created_entities.append({"id": person_id, "name": p.name})

        self.logger.info(f"✅ Created {len(out)} Pipedrive persons")
        return out

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update some test persons in Pipedrive."""
        if not self._persons:
            return []

        self.logger.info("🥁 Updating some Pipedrive persons")
        updated: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for ent in self._persons[: min(3, len(self._persons))]:
                await self._pace()

                token = ent.get("token", "")
                url = f"{PIPEDRIVE_API}/persons/{ent['id']}?api_token={self.api_token}"

                # Update with preserved token in name
                r = await client.put(
                    url,
                    json={
                        "name": f"Updated Person [{token}]",  # Preserve token in name
                        "phone": [{"value": "+1-555-0100", "primary": True, "label": "work"}],
                    },
                )
                r.raise_for_status()
                updated.append({**ent, "updated": True})

        self.logger.info(f"✅ Updated {len(updated)} Pipedrive persons")
        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all tracked test persons."""
        return await self.delete_specific_entities(self._persons)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete specific persons from Pipedrive."""
        self.logger.info(f"🥁 Deleting {len(entities)} Pipedrive persons")
        deleted: List[str] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for ent in entities:
                try:
                    await self._pace()
                    url = f"{PIPEDRIVE_API}/persons/{ent['id']}?api_token={self.api_token}"
                    r = await client.delete(url)

                    if r.status_code in (200, 204):
                        deleted.append(str(ent["id"]))
                    else:
                        self.logger.warning(f"Delete failed {r.status_code}: {r.text}")
                except Exception as e:
                    self.logger.warning(f"Delete error {ent['id']}: {e}")

        self.logger.info(f"✅ Deleted {len(deleted)} Pipedrive persons")
        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all test Pipedrive persons."""
        self.logger.info("🧹 Starting comprehensive Pipedrive cleanup")

        cleanup_stats = {"persons_deleted": 0, "errors": 0}

        try:
            # First, delete current session persons
            if self._persons:
                self.logger.info(f"🗑️ Cleaning up {len(self._persons)} current session persons")
                deleted = await self.delete_specific_entities(self._persons)
                cleanup_stats["persons_deleted"] += len(deleted)
                self._persons.clear()

            # Search for any remaining monke test persons
            await self._cleanup_orphaned_test_persons(cleanup_stats)

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['persons_deleted']} persons deleted, "
                f"{cleanup_stats['errors']} errors"
            )
        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")

    async def _cleanup_orphaned_test_persons(self, stats: Dict[str, Any]):
        """Find and delete orphaned test persons from previous runs."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Search for persons - Pipedrive doesn't have great search, so list and filter
                url = f"{PIPEDRIVE_API}/persons?api_token={self.api_token}&limit=100"
                r = await client.get(url)

                if r.status_code == 200:
                    data = r.json()
                    if not data.get("success"):
                        return

                    persons = data.get("data") or []
                    test_persons = []

                    for person in persons:
                        name = (person.get("name") or "").lower()
                        email = ""
                        if person.get("email"):
                            emails = person["email"]
                            if isinstance(emails, list) and emails:
                                email = (emails[0].get("value") or "").lower()

                        # Check if this looks like a test person (token in name or monke email)
                        if (
                            "monke" in name
                            or "monke-test.com" in email
                            or "[" in name  # Token pattern in name
                        ):
                            test_persons.append(person)

                    if test_persons:
                        self.logger.info(
                            f"🔍 Found {len(test_persons)} potential test persons to clean"
                        )
                        for person in test_persons:
                            try:
                                await self._pace()
                                del_url = (
                                    f"{PIPEDRIVE_API}/persons/{person['id']}"
                                    f"?api_token={self.api_token}"
                                )
                                del_r = await client.delete(del_url)

                                if del_r.status_code in (200, 204):
                                    stats["persons_deleted"] += 1
                                    self.logger.info(
                                        f"✅ Deleted orphaned person: {person.get('name', 'unknown')}"
                                    )
                                else:
                                    stats["errors"] += 1
                            except Exception as e:
                                stats["errors"] += 1
                                self.logger.warning(
                                    f"⚠️ Failed to delete person {person['id']}: {e}"
                                )
        except Exception as e:
            self.logger.warning(f"⚠️ Could not search for orphaned persons: {e}")

    async def _pace(self):
        """Rate limiting helper."""
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()

