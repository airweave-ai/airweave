"""Slite-specific bongo implementation.

Creates, updates, and deletes test notes via the Slite API.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class SliteBongo(BaseBongo):
    """Bongo for Slite that creates notes (docs) for end-to-end testing.

    Uses API key (x-slite-api-key). Creates notes with embedded token for verification.
    """

    connector_type = "slite"

    API_BASE = "https://api.slite.com/v1"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Slite bongo.

        Args:
            credentials: Dict with "api_key" (direct auth) or "access_token" (auth provider)
            **kwargs: Configuration from config file
        """
        super().__init__(credentials)

        self.api_key: str = (
            credentials.get("api_key")
            or credentials.get("access_token")
            or credentials.get("generic_api_key")
        )

        if not self.api_key:
            available_fields = list(credentials.keys())
            raise ValueError(
                f"Missing Slite credentials. Expected 'api_key' or 'access_token'. "
                f"Available: {available_fields}"
            )

        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.max_concurrency: int = int(kwargs.get("max_concurrency", 2))
        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 500))
        self.rate_limit_delay: float = rate_limit_ms / 1000.0

        self._notes: List[Dict[str, Any]] = []
        self.last_request_time = 0.0
        self.logger = get_logger("slite_bongo")

    def _headers(self) -> Dict[str, str]:
        """Return headers for Slite API (x-slite-api-key)."""
        return {
            "x-slite-api-key": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _rate_limit(self):
        """Simple rate limiting."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    async def _ensure_workspace(self):
        """No-op: Slite API does not require workspace ID for note creation."""
        pass

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create notes in Slite with embedded tokens."""
        self.logger.info(f"🥁 Creating {self.entity_count} Slite notes")
        await self._ensure_workspace()

        from monke.generation.slite import generate_slite_note

        entities: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async with httpx.AsyncClient() as client:
            for i in range(self.entity_count):
                async with semaphore:
                    try:
                        await self._rate_limit()
                        token = str(uuid.uuid4())[:8]
                        self.logger.info(f"📝 Generating note with token: {token}")

                        note_data = await generate_slite_note(self.openai_model, token)
                        title = note_data["title"]
                        markdown = note_data["markdown"]

                        resp = await client.post(
                            f"{self.API_BASE}/notes",
                            headers=self._headers(),
                            json={"title": title, "markdown": markdown},
                            timeout=20.0,
                        )

                        if resp.status_code not in (200, 201):
                            self.logger.error(
                                f"Failed to create note: {resp.status_code} - {resp.text}"
                            )
                        resp.raise_for_status()

                        created = resp.json()
                        note_id = created.get("id")
                        if not note_id:
                            self.logger.error(f"No id in create response: {created}")
                            continue

                        self.logger.info(f"✅ Created note: {note_id}")

                        entity = {
                            "type": "note",
                            "id": note_id,
                            "name": title,
                            "token": token,
                            "expected_content": token,
                        }
                        entities.append(entity)
                        self._notes.append(entity)

                    except Exception as e:
                        self.logger.error(f"❌ Error creating note: {type(e).__name__}: {e}")
                        raise

        self.created_entities = entities
        self.logger.info(f"✅ Created {len(entities)} Slite notes")
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a subset of notes via PUT /v1/notes/{noteId} (title and markdown)."""
        self.logger.info("🥁 Updating some Slite notes")
        if not self.created_entities:
            return []

        from monke.generation.slite import generate_slite_note

        updated: List[Dict[str, Any]] = []
        count = min(2, len(self.created_entities))

        async with httpx.AsyncClient() as client:
            for i in range(count):
                entity = self.created_entities[i]
                await self._rate_limit()
                try:
                    note_data = await generate_slite_note(
                        self.openai_model, entity["token"]
                    )
                    resp = await client.put(
                        f"{self.API_BASE}/notes/{entity['id']}",
                        headers=self._headers(),
                        json={
                            "title": note_data["title"],
                            "markdown": note_data["markdown"],
                        },
                        timeout=20.0,
                    )
                    if resp.status_code not in (200, 201):
                        self.logger.error(
                            f"Failed to update note {entity['id']}: {resp.status_code} - {resp.text}"
                        )
                        continue
                    updated.append(entity)
                    self.logger.info(f"✅ Updated note: {entity['id']}")
                except Exception as e:
                    self.logger.error(f"Failed to update note {entity['id']}: {e}")

        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all created notes."""
        self.logger.info("🥁 Deleting all Slite test notes")
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete provided notes by id via DELETE /v1/notes/{noteId}."""
        self.logger.info(f"🥁 Deleting {len(entities)} Slite notes")
        deleted: List[str] = []

        async with httpx.AsyncClient() as client:
            for entity in entities:
                try:
                    await self._rate_limit()
                    resp = await client.request(
                        "DELETE",
                        f"{self.API_BASE}/notes/{entity['id']}",
                        headers=self._headers(),
                        timeout=20.0,
                    )
                    if resp.status_code in (200, 204, 404):
                        deleted.append(entity["id"])
                        self.logger.info(f"✅ Deleted note: {entity['id']}")
                    else:
                        self.logger.warning(
                            f"Delete note {entity['id']} returned {resp.status_code}"
                        )
                except Exception as e:
                    self.logger.error(f"Failed to delete {entity['id']}: {e}")

        return deleted

    async def cleanup(self) -> None:
        """Clean up test data."""
        if self.created_entities:
            await self.delete_entities()
