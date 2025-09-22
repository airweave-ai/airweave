"""Zendesk-specific bongo implementation.

Creates, updates, and deletes test tickets via the real Zendesk API.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class ZendeskBongo(BaseBongo):
    """Bongo for Zendesk that creates tickets for end-to-end testing.

    - Uses OAuth2 access token for authentication
    - Embeds a short token in ticket description for verification
    - Creates tickets with realistic content for testing
    """

    connector_type = "zendesk"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Zendesk bongo.

        Args:
            credentials: Dict with at least "access_token" (Zendesk OAuth token)
            **kwargs: Optional configuration such as entity_count, openai_model,
                max_concurrency, rate_limit_delay, subdomain
        """
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        self.subdomain: str = credentials.get("subdomain", "your-subdomain")
        self.entity_count: int = int(kwargs.get("entity_count", 5))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4o-mini")
        self.max_concurrency: int = int(kwargs.get("max_concurrency", 1))
        # Use rate_limit_delay_ms from config if provided, otherwise default to 1000ms
        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 1000))
        self.rate_limit_delay: float = rate_limit_ms / 1000.0

        # Runtime state
        self._tickets: List[Dict[str, Any]] = []

        # Pacing
        self.last_request_time = 0.0

        self.logger = get_logger("zendesk_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create tickets in Zendesk.

        Returns a list of created entity descriptors used by the test flow.
        """
        self.logger.info(f"🥁 Creating {self.entity_count} Zendesk tickets")

        from monke.generation.zendesk import generate_zendesk_ticket

        entities: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async with httpx.AsyncClient() as client:

            async def create_one() -> Optional[Dict[str, Any]]:
                async with semaphore:
                    try:
                        await self._rate_limit()
                        token = str(uuid.uuid4())[:8]
                        self.logger.info(f"🔨 Generating content for ticket with token: {token}")
                        subject, description = await generate_zendesk_ticket(self.openai_model, token)
                        self.logger.info(f"📝 Generated ticket: '{subject[:50]}...'")

                        # Create ticket
                        resp = await client.post(
                            f"https://{self.subdomain}.zendesk.com/api/v2/tickets.json",
                            headers=self._headers(),
                            json={
                                "ticket": {
                                    "subject": subject,
                                    "description": description,
                                    "priority": "normal",
                                    "status": "open",
                                    "type": "question"
                                }
                            },
                        )

                        if resp.status_code not in (200, 201):
                            error_data = resp.text
                            try:
                                error_json = resp.json()
                                error_data = error_json
                            except Exception:
                                pass
                            self.logger.error(
                                f"Failed to create ticket: {resp.status_code} - {error_data}"
                            )
                            self.logger.error(
                                f"Request data: subject='{subject[:50]}...', description='{description[:50]}...'"
                            )

                        resp.raise_for_status()
                        ticket = resp.json()["ticket"]
                        ticket_id = ticket["id"]

                        # Entity descriptor used by generic verification
                        return {
                            "type": "ticket",
                            "id": str(ticket_id),
                            "name": subject,
                            "token": token,
                            "expected_content": token,
                            # Synthetic path for logging/verification helpers
                            "path": f"zendesk/ticket/{ticket_id}",
                        }
                    except Exception as e:
                        self.logger.error(f"❌ Error in create_one: {type(e).__name__}: {str(e)}")
                        # Re-raise to be caught by gather
                        raise

            # Create tickets with better error handling
            tasks = [create_one() for _ in range(self.entity_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to create ticket {i+1}: {result}")
                    # Re-raise the first exception we encounter
                    raise result
                elif result:
                    entities.append(result)
                    self._tickets.append(result)
                    self.logger.info(
                        f"✅ Created ticket {i+1}/{self.entity_count}: {result['name'][:50]}..."
                    )

        self.created_entities = entities
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a small subset of tickets by regenerating subject/description with same token."""
        self.logger.info("🥁 Updating some Zendesk tickets")
        if not self._tickets:
            return []

        from monke.generation.zendesk import generate_zendesk_ticket

        updated_entities: List[Dict[str, Any]] = []
        count = min(3, len(self._tickets))

        async with httpx.AsyncClient() as client:
            for i in range(count):
                await self._rate_limit()
                t = self._tickets[i]
                subject, description = await generate_zendesk_ticket(self.openai_model, t["token"])
                resp = await client.put(
                    f"https://{self.subdomain}.zendesk.com/api/v2/tickets/{t['id']}.json",
                    headers=self._headers(),
                    json={
                        "ticket": {
                            "subject": subject,
                            "description": description
                        }
                    },
                )
                resp.raise_for_status()
                updated_entities.append({**t, "name": subject, "expected_content": t["token"]})

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all created tickets."""
        self.logger.info("🥁 Deleting all Zendesk test tickets")
        deleted_ids = await self.delete_specific_entities(self.created_entities)
        return deleted_ids

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete provided list of tickets by id."""
        self.logger.info(f"🥁 Deleting {len(entities)} Zendesk tickets")
        deleted: List[str] = []
        async with httpx.AsyncClient() as client:
            for e in entities:
                try:
                    await self._rate_limit()
                    r = await client.delete(
                        f"https://{self.subdomain}.zendesk.com/api/v2/tickets/{e['id']}.json",
                        headers=self._headers()
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
        """Comprehensive cleanup of all monke test data from Zendesk."""
        self.logger.info("🧹 Starting comprehensive Zendesk cleanup")

        cleanup_stats = {"tickets_deleted": 0, "errors": 0}

        try:
            # Clean up current session data first
            if self._tickets:
                self.logger.info(f"🗑️ Cleaning up {len(self._tickets)} current session tickets")
                await self.delete_specific_entities(self._tickets)
                cleanup_stats["tickets_deleted"] += len(self._tickets)

            # Find and clean up orphaned monke test tickets
            orphaned_tickets = await self._find_orphaned_monke_tickets()
            if orphaned_tickets:
                self.logger.info(
                    f"🔍 Found {len(orphaned_tickets)} orphaned monke test tickets to clean up"
                )
                for ticket in orphaned_tickets:
                    try:
                        await self._delete_ticket_by_id(ticket["id"])
                        cleanup_stats["tickets_deleted"] += 1
                        self.logger.info(
                            f"✅ Deleted orphaned ticket: {ticket['subject']} ({ticket['id']})"
                        )
                    except Exception as e:
                        cleanup_stats["errors"] += 1
                        self.logger.warning(f"⚠️ Failed to delete ticket {ticket['id']}: {e}")

            # Log cleanup summary
            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['tickets_deleted']} tickets deleted, "
                f"{cleanup_stats['errors']} errors"
            )

        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")
            # Don't re-raise - cleanup should be best-effort

    async def _delete_ticket_by_id(self, ticket_id: str):
        """Delete a ticket by its ID."""
        async with httpx.AsyncClient() as client:
            await self._rate_limit()
            r = await client.delete(
                f"https://{self.subdomain}.zendesk.com/api/v2/tickets/{ticket_id}.json",
                headers=self._headers()
            )
            if r.status_code in (200, 204):
                self.logger.debug(f"Deleted ticket {ticket_id}")
            else:
                self.logger.warning(f"Failed to delete ticket {ticket_id}: {r.status_code} - {r.text}")
                r.raise_for_status()

    async def _find_orphaned_monke_tickets(self) -> List[Dict[str, Any]]:
        """Find orphaned monke test tickets."""
        orphaned_tickets = []

        async with httpx.AsyncClient() as client:
            # Search for tickets that might be monke tests
            await self._rate_limit()
            r = await client.get(
                f"https://{self.subdomain}.zendesk.com/api/v2/tickets.json",
                headers=self._headers(),
                params={
                    "status": "open",  # Only get open tickets
                },
            )

            if r.status_code == 200:
                tickets = r.json().get("tickets", [])
                for ticket in tickets:
                    subject = ticket.get("subject", "")
                    description = ticket.get("description", "")

                    # Check if this looks like a monke test ticket
                    is_monke_ticket = (
                        "monke" in subject.lower()
                        or "monke test" in description.lower()
                        or any(uuid_pattern in description for uuid_pattern in ["-", "test-token"])
                        or "test" in subject.lower()
                    )

                    if is_monke_ticket:
                        orphaned_tickets.append(ticket)
            else:
                self.logger.warning(
                    f"Failed to search for orphaned tickets: {r.status_code} - {r.text}"
                )

        return orphaned_tickets

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _rate_limit(self):
        now = time.time()
        delta = now - self.last_request_time
        if delta < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self.last_request_time = time.time()
