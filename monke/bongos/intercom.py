"""Intercom-specific bongo implementation.

Creates, updates, and deletes test tickets (and optionally conversations) via the Intercom API.
Intercom supports: POST /tickets (create ticket), POST /conversations (create conversation).
We focus on tickets for E2E as they are fully creatable; conversations require an existing contact.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger

API_BASE = "https://api.intercom.io"
# Tickets API requires 2.11+; use 2.15 for reply/close/delete
INTERCOM_VERSION = "2.15"


class IntercomBongo(BaseBongo):
    """Bongo for Intercom that creates tickets for end-to-end testing.

    - Uses OAuth2 access token
    - Embeds a short token in ticket title/description for verification
    - Creates tickets via POST /tickets (requires ticket_type_id and contact)
    """

    connector_type = "intercom"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Intercom bongo.

        Args:
            credentials: Dict with at least "access_token"
            **kwargs: entity_count, openai_model, max_concurrency, rate_limit_delay_ms
        """
        super().__init__(credentials)
        self.access_token: str = credentials.get("access_token", "")
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4o-mini")
        self.max_concurrency: int = int(kwargs.get("max_concurrency", 1))
        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 500))
        self.rate_limit_delay: float = rate_limit_ms / 1000.0
        self._tickets: List[Dict[str, Any]] = []
        self.last_request_time = 0.0
        self.logger = get_logger("intercom_bongo")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Intercom-Version": INTERCOM_VERSION,
        }

    async def _rate_limit(self):
        now = time.time()
        delta = now - self.last_request_time
        if delta < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self.last_request_time = time.time()

    async def _get_ticket_type_id(self, client: httpx.AsyncClient) -> Optional[str]:
        """Get first available ticket type ID (required to create tickets)."""
        await self._rate_limit()
        try:
            r = await client.get(
                f"{API_BASE}/ticket_types",
                headers=self._headers(),
                timeout=15.0,
            )
            if r.status_code != 200:
                return None
            data = r.json()
            types_list = data.get("ticket_types") or data.get("data") or []
            if isinstance(types_list, list) and types_list:
                first = types_list[0]
                return str(first.get("id", first) if isinstance(first, dict) else first)
        except Exception as e:
            self.logger.warning(f"Could not list ticket types: {e}")
        return None

    async def _get_first_contact_id(self, client: httpx.AsyncClient) -> Optional[str]:
        """Get first contact ID (required to create tickets)."""
        await self._rate_limit()
        try:
            r = await client.get(
                f"{API_BASE}/contacts",
                headers=self._headers(),
                params={"per_page": 1},
                timeout=15.0,
            )
            if r.status_code != 200:
                return None
            data = r.json()
            contacts = data.get("data") or data.get("contacts") or []
            if isinstance(contacts, list) and contacts:
                c = contacts[0]
                return str(c.get("id", c) if isinstance(c, dict) else c)
        except Exception as e:
            self.logger.warning(f"Could not list contacts: {e}")
        return None

    def _ticket_type_attribute_names(
        self, ticket_type: Dict[str, Any]
    ) -> List[str]:
        """Return list of attribute names defined on this ticket type.

        The create-ticket API expects ticket_attributes keys to match the exact
        attribute names (or ids) from the type, not reserved names like default_title.
        """
        names: List[str] = []
        attrs_obj = ticket_type.get("ticket_type_attributes") or {}
        attrs_list = attrs_obj.get("ticket_type_attributes") or attrs_obj.get("data")
        if not isinstance(attrs_list, list):
            return names
        for attr in attrs_list:
            if not isinstance(attr, dict):
                continue
            name = attr.get("name")
            if name:
                names.append(name)
        return names

    def _build_ticket_attributes(
        self,
        attr_names: List[str],
        title: str,
        description: str,
    ) -> Dict[str, Any]:
        """Build ticket_attributes using only exact attribute names from the ticket type.

        Maps our title/description to attributes whose name looks like Title/Description.
        Does not use reserved keys default_title/default_description unless that exact
        name exists on the type (API rejects keys not found on the type).
        """
        out: Dict[str, Any] = {}
        for name in attr_names:
            n = (name or "").strip().lower()
            if n and n in ("default_title", "title", "subject", "name"):
                out[name] = title  # use exact name as key
                break
        for name in attr_names:
            n = (name or "").strip().lower()
            if n and n in ("default_description", "description", "body", "details"):
                out[name] = description
                break
        return out

    async def _get_ticket_type_with_attributes(
        self, client: httpx.AsyncClient, ticket_type_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch ticket type details including attributes (for allowed ticket_attributes keys)."""
        await self._rate_limit()
        try:
            r = await client.get(
                f"{API_BASE}/ticket_types/{ticket_type_id}",
                headers=self._headers(),
                timeout=15.0,
            )
            if r.status_code != 200:
                return None
            return r.json()
        except Exception as e:
            self.logger.warning(f"Could not get ticket type {ticket_type_id}: {e}")
        return None

    async def _get_current_admin_id(self, client: httpx.AsyncClient) -> Optional[str]:
        """Get the current admin id via GET /me (required for ticket reply)."""
        await self._rate_limit()
        try:
            r = await client.get(
                f"{API_BASE}/me",
                headers=self._headers(),
                timeout=15.0,
            )
            if r.status_code != 200:
                return None
            data = r.json()
            admin_id = data.get("id")
            if admin_id is not None:
                return str(admin_id)
            return None
        except Exception as e:
            self.logger.warning(f"Could not get current admin from /me: {e}")
        return None

    async def _add_ticket_reply_with_token(
        self,
        client: httpx.AsyncClient,
        ticket_id: str,
        token: str,
        fallback_text: str,
        admin_id: str,
    ) -> None:
        """Add a comment reply to the ticket so the verification token appears in ticket parts.

        Used when the ticket type has no default_title/default_description; reply body is
        synced so the token can be found.
        admin_id is required by the API for the reply author."""
        await self._rate_limit()
        body_text = f"{fallback_text}\n\nVerification token: {token}"
        headers = {**self._headers(), "Intercom-Version": INTERCOM_VERSION}
        r = await client.post(
            f"{API_BASE}/tickets/{ticket_id}/reply",
            headers=headers,
            json={
                "body": body_text,
                "part_type": "comment",
                "admin_id": admin_id,
            },
            timeout=15.0,
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(
                f"Ticket reply (verification token) failed: {r.status_code} - {r.text}"
            )
        self.logger.info(
            f"Added reply with verification token to ticket {ticket_id}"
        )

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create tickets in Intercom. Requires ticket types and at least one contact."""
        self.logger.info(f"Creating {self.entity_count} Intercom tickets")

        from monke.generation.intercom import generate_intercom_ticket

        entities: List[Dict[str, Any]] = []
        async with httpx.AsyncClient() as client:
            ticket_type_id = await self._get_ticket_type_id(client)
            contact_id = await self._get_first_contact_id(client)
            if not ticket_type_id or not contact_id:
                self.logger.warning(
                    "Intercom tickets require ticket_type_id and contact. "
                    "Skipping create_entities (no ticket types or contacts?)."
                )
                self.created_entities = []
                return []

            admin_id: Optional[str] = await self._get_current_admin_id(client)

            ticket_type = await self._get_ticket_type_with_attributes(
                client, ticket_type_id
            )
            attr_names = (
                self._ticket_type_attribute_names(ticket_type)
                if ticket_type
                else []
            )
            semaphore = asyncio.Semaphore(self.max_concurrency)

            async def create_one() -> Optional[Dict[str, Any]]:
                async with semaphore:
                    try:
                        await self._rate_limit()
                        token = str(uuid.uuid4())[:8]
                        title, description = await generate_intercom_ticket(
                            self.openai_model, token
                        )
                        ticket_attributes = self._build_ticket_attributes(
                            attr_names, title, description
                        )
                        payload: Dict[str, Any] = {
                            "ticket_type_id": ticket_type_id,
                            "contacts": [{"id": contact_id, "type": "contact"}],
                        }
                        if ticket_attributes:
                            payload["ticket_attributes"] = ticket_attributes
                        r = await client.post(
                            f"{API_BASE}/tickets",
                            headers=self._headers(),
                            json=payload,
                            timeout=30.0,
                        )
                        if r.status_code not in (200, 201):
                            self.logger.error(
                                f"Failed to create ticket: {r.status_code} - {r.text}"
                            )
                            r.raise_for_status()
                        data = r.json()
                        ticket_id = str(
                            data.get("id")
                            or data.get("ticket", {}).get("id")
                            or data.get("data", {}).get("id", "")
                        )
                        if not ticket_id:
                            self.logger.error(f"No ticket id in response: {data}")
                            return None
                        if not ticket_attributes and (title or description):
                            if not admin_id:
                                raise RuntimeError(
                                    "Intercom ticket reply requires admin_id (for verification token); "
                                    "GET /me did not return an admin. Ensure the token has Read admins."
                                )
                            await self._add_ticket_reply_with_token(
                                client,
                                ticket_id,
                                token,
                                title or description,
                                admin_id,
                            )
                        display_name = title if ticket_attributes else f"Ticket {ticket_id}"
                        desc = {
                            "type": "ticket",
                            "id": ticket_id,
                            "name": display_name,
                            "token": token,
                            "expected_content": token,
                            "path": f"intercom/ticket/{ticket_id}",
                            "ticket_type_id": ticket_type_id,
                        }
                        return desc
                    except Exception as e:
                        self.logger.error(f"Error creating ticket: {type(e).__name__}: {e}")
                        raise

            tasks = [create_one() for _ in range(self.entity_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            first_exception: Optional[BaseException] = None
            for result in results:
                if isinstance(result, Exception):
                    if first_exception is None:
                        first_exception = result
                    continue
                if result:
                    entities.append(result)
                    self._tickets.append(result)
            self.created_entities = entities
            if first_exception is not None:
                raise first_exception
            return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a subset of tickets. Only sends ticket_attributes that exist on the ticket type."""
        self.logger.info("Updating some Intercom tickets")
        if not self._tickets:
            return []
        from monke.generation.intercom import generate_intercom_ticket

        updated: List[Dict[str, Any]] = []
        count = min(2, len(self._tickets))
        async with httpx.AsyncClient() as client:
            for i in range(count):
                await self._rate_limit()
                t = self._tickets[i]
                title, description = await generate_intercom_ticket(
                    self.openai_model, t["token"]
                )
                ticket_type_id = t.get("ticket_type_id")
                ticket_attributes: Dict[str, Any] = {}
                if ticket_type_id:
                    ticket_type = await self._get_ticket_type_with_attributes(
                        client, ticket_type_id
                    )
                    attr_names = (
                        self._ticket_type_attribute_names(ticket_type)
                        if ticket_type
                        else []
                    )
                    ticket_attributes = self._build_ticket_attributes(
                        attr_names, title, description
                    )
                try:
                    payload: Dict[str, Any] = {}
                    if ticket_attributes:
                        payload["ticket_attributes"] = ticket_attributes
                    if not payload:
                        updated.append({**t, "name": t.get("name"), "expected_content": t["token"]})
                        continue
                    r = await client.patch(
                        f"{API_BASE}/tickets/{t['id']}",
                        headers=self._headers(),
                        json=payload,
                        timeout=15.0,
                    )
                    if r.status_code == 200:
                        updated.append({**t, "name": title, "expected_content": t["token"]})
                    else:
                        self.logger.warning(
                            f"Update ticket {t['id']}: {r.status_code} - {r.text}"
                        )
                except Exception as e:
                    self.logger.warning(f"Update ticket {t['id']}: {e}")
        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all created tickets."""
        self.logger.info("Deleting all Intercom test tickets")
        return await self.delete_specific_entities(self.created_entities or [])

    async def _close_ticket(
        self, client: httpx.AsyncClient, ticket_id: str
    ) -> bool:
        """Close ticket (open=false) so it can be deleted."""
        await self._rate_limit()
        headers = {**self._headers(), "Intercom-Version": INTERCOM_VERSION}
        r = await client.put(
            f"{API_BASE}/tickets/{ticket_id}",
            headers=headers,
            json={"open": False},
            timeout=15.0,
        )
        return r.status_code == 200

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete tickets by ID. Closes each ticket first (Intercom requires closed before delete)."""
        deleted: List[str] = []
        async with httpx.AsyncClient() as client:
            for e in entities:
                ticket_id = str(e.get("id", ""))
                if not ticket_id:
                    continue
                try:
                    await self._rate_limit()
                    if not await self._close_ticket(client, ticket_id):
                        self.logger.debug(
                            f"Close ticket {ticket_id} returned non-200 (may already be closed)"
                        )
                    await self._rate_limit()
                    headers = {**self._headers(), "Intercom-Version": INTERCOM_VERSION}
                    r = await client.delete(
                        f"{API_BASE}/tickets/{ticket_id}",
                        headers=headers,
                        timeout=15.0,
                    )
                    if r.status_code in (200, 204):
                        deleted.append(ticket_id)
                        self.logger.info(f"Deleted ticket {ticket_id}")
                    else:
                        self.logger.warning(
                            f"Delete failed for {ticket_id}: {r.status_code} - {r.text}"
                        )
                except Exception as ex:
                    self.logger.warning(f"Delete error for {ticket_id}: {ex}")
        return deleted

    async def cleanup(self):
        """Clean up current session tickets."""
        self.logger.info("Intercom cleanup")
        if self._tickets:
            await self.delete_specific_entities(self._tickets)
            self._tickets = []
        self.created_entities = []
