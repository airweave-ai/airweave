"""Freshdesk-specific bongo implementation.

Creates, updates, and deletes test tickets via the real Freshdesk API.
Uses API key auth (Basic: api_key as username, 'X' as password).
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class FreshdeskBongo(BaseBongo):
    """Bongo for Freshdesk that creates tickets for end-to-end testing.

    - Uses API key (Basic auth: username=api_key, password='X')
    - Requires config: domain (e.g. mycompany for mycompany.freshdesk.com)
    - Embeds a short token in ticket subject/description for verification
    """

    connector_type = "freshdesk"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.api_key: str = credentials["api_key"]
        self.domain: str = kwargs.get("domain", "")
        self.entity_count: int = int(kwargs.get("entity_count", 5))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4o-mini")
        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 1000))
        self.rate_limit_delay: float = rate_limit_ms / 1000.0
        self._tickets: List[Dict[str, Any]] = []
        self.last_request_time = 0.0
        self.logger = get_logger("freshdesk_bongo")

    def _base_url(self) -> str:
        return f"https://{self.domain}.freshdesk.com/api/v2"

    def _auth(self) -> httpx.BasicAuth:
        return httpx.BasicAuth(username=self.api_key, password="X")

    async def _rate_limit(self):
        now = time.time()
        delta = now - self.last_request_time
        if delta < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self.last_request_time = time.time()

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create tickets in Freshdesk via POST /api/v2/tickets."""
        self.logger.info(f"🥁 Creating {self.entity_count} Freshdesk tickets")
        from monke.generation.freshdesk import generate_freshdesk_ticket

        entities: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(self.entity_count):
                await self._rate_limit()
                token = str(uuid.uuid4())[:8]
                self.logger.info(f"🔨 Generating content for ticket with token: {token}")
                subject, description = await generate_freshdesk_ticket(
                    self.openai_model, token
                )
                self.logger.info(f"📝 Generated ticket: '{subject[:50]}...'")

                resp = await client.post(
                    f"{self._base_url()}/tickets",
                    auth=self._auth(),
                    headers={"Content-Type": "application/json"},
                    json={
                        "subject": subject,
                        "description": description,
                        "email": "monke-test@example.com",
                        "priority": 2,
                        "status": 2,
                    },
                )
                if resp.status_code not in (200, 201):
                    self.logger.error(
                        f"Failed to create ticket: {resp.status_code} - {resp.text}"
                    )
                    resp.raise_for_status()
                data = resp.json()
                ticket_id = data.get("id")
                if not ticket_id:
                    raise RuntimeError(f"Freshdesk create ticket response missing id: {data}")

                ent = {
                    "type": "ticket",
                    "id": str(ticket_id),
                    "name": subject,
                    "token": token,
                    "expected_content": token,
                    "path": f"freshdesk/ticket/{ticket_id}",
                }
                entities.append(ent)
                self._tickets.append(ent)
                self.logger.info(f"✅ Created ticket {i+1}/{self.entity_count}: {ticket_id}")

        self.created_entities = entities
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a subset of tickets (subject/description) with same token."""
        self.logger.info("🥁 Updating some Freshdesk tickets")
        if not self._tickets:
            return []

        from monke.generation.freshdesk import generate_freshdesk_ticket

        updated: List[Dict[str, Any]] = []
        count = min(3, len(self._tickets))
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(count):
                await self._rate_limit()
                t = self._tickets[i]
                subject, description = await generate_freshdesk_ticket(
                    self.openai_model, t["token"]
                )
                resp = await client.put(
                    f"{self._base_url()}/tickets/{t['id']}",
                    auth=self._auth(),
                    headers={"Content-Type": "application/json"},
                    json={"subject": subject, "description": description},
                )
                resp.raise_for_status()
                updated.append({**t, "name": subject, "expected_content": t["token"]})
                self.logger.info(f"📝 Updated ticket: {t['id']}")
        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all created tickets."""
        self.logger.info("🥁 Deleting all Freshdesk test tickets")
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete tickets by id (Freshdesk: DELETE /api/v2/tickets/:id)."""
        self.logger.info(f"🥁 Deleting {len(entities)} Freshdesk tickets")
        deleted: List[str] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for e in entities:
                try:
                    await self._rate_limit()
                    r = await client.delete(
                        f"{self._base_url()}/tickets/{e['id']}",
                        auth=self._auth(),
                    )
                    if r.status_code in (200, 204):
                        deleted.append(e["id"])
                    else:
                        self.logger.warning(
                            f"Delete failed for {e.get('id')}: {r.status_code} - {r.text}"
                        )
                except Exception as ex:
                    self.logger.warning(f"Delete error for {e.get('id')}: {ex}")
        return deleted

    async def cleanup(self):
        """Clean up current session tickets and optionally orphaned monke tickets."""
        self.logger.info("🧹 Freshdesk cleanup")
        if self._tickets:
            await self.delete_specific_entities(self._tickets)
            self.logger.info(f"🗑️ Cleaned {len(self._tickets)} session tickets")
