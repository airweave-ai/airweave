"""
Freshdesk source implementation.

Retrieves data (read-only) from a user's Freshdesk account via Freshdesk API v2:
    - Groups (agent groups)
    - Tickets (within each group)
    - Conversations (within each ticket)

References:
    https://developers.freshdesk.com/api/#groups
    https://developers.freshdesk.com/api/#tickets
    https://developers.freshdesk.com/api/#conversations
"""

import logging
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.freshdesk import (
    FreshdeskGroupEntity,
    FreshdeskTicketEntity,
    FreshdeskConversationEntity,
)
from airweave.platform.sources._base import BaseSource

logger = logging.getLogger(__name__)


@source(
    "Freshdesk", "freshdesk", AuthType.oauth2_with_refresh, labels=["Support", "Ticketing"]
)
class FreshdeskSource(BaseSource):
    """Freshdesk source implementation (read-only).

    This connector retrieves hierarchical data from Freshdesk's REST API:
        - Groups (agent groups)
        - Tickets (within each group)
        - Conversations (within each ticket)
    """

    def __init__(self):
        super().__init__()
        self.subdomain = None

    @classmethod
    async def create(cls, access_token: str, subdomain: str) -> "FreshdeskSource":
        """Create a new Freshdesk source instance."""
        instance = cls()
        instance.access_token = access_token
        instance.subdomain = subdomain
        return instance

    @property
    def BASE_URL(self):
        return f"https://{self.subdomain}.freshdesk.com/api/v2/"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _make_request(
        self, client: httpx.AsyncClient, method: str, endpoint: str, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an authenticated HTTP request to the Freshdesk API."""
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

    async def _fetch_groups(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetch all Freshdesk groups."""
        logger.debug("Generating Group entities")
        page = 1
        while True:
            params = {"page": page, "per_page": 100}
            data = await self._make_request(client, "GET", "groups", params=params)
            if not data:
                break
            for group in data:
                yield group
            page += 1

    async def _generate_ticket_entities(
        self, client: httpx.AsyncClient, group: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate tickets for a given group."""
        logger.debug(f"Generating Ticket entities for group: {group['id']}")
        page = 1
        while True:
            params = {"group_id": group["id"], "page": page, "per_page": 100}
            data = await self._make_request(client, "GET", "tickets", params=params)
            if not data:
                break
            for ticket in data:
                yield ticket
            page += 1

    async def _generate_conversation_entities(
        self, client: httpx.AsyncClient, ticket: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate conversations for a given ticket."""
        logger.debug(f"Generating Conversation entities for ticket: {ticket['id']}")
        data = await self._make_request(client, "GET", f"tickets/{ticket['id']}/conversations")
        for conversation in data:
            yield conversation

    async def generate_entities(self) -> AsyncGenerator[Any, None]:
        """Generate all Freshdesk entities (Groups, Tickets, Conversations)."""
        logger.debug("Generating Freshdesk entities")
        async with httpx.AsyncClient() as client:
            # Generate Group entities
            async for group in self._fetch_groups(client):
                group_entity = FreshdeskGroupEntity(
                    entity_id=str(group.get("id")),
                    group_id=str(group.get("id")),
                    name=group.get("name"),
                    description=group.get("description"),
                    escalate_to=group.get("escalate_to"),
                    unassigned_for=group.get("unassigned_for"),
                    business_hours_id=group.get("business_hours_id"),
                    agent_ids=group.get("agent_ids", []),
                    created_at=group.get("created_at"),
                    updated_at=group.get("updated_at"),
                )
                yield group_entity

                # Build breadcrumb for this group
                group_breadcrumb = Breadcrumb(
                    entity_id=group_entity.entity_id,
                    name=group_entity.name,
                    type="group",
                )

                # Generate Ticket entities for this group
                async for ticket in self._generate_ticket_entities(client, group):
                    ticket_entity = FreshdeskTicketEntity(
                        entity_id=str(ticket.get("id")),
                        breadcrumbs=[group_breadcrumb],
                        ticket_id=str(ticket.get("id")),
                        subject=ticket.get("subject"),
                        description=ticket.get("description"),
                        description_text=ticket.get("description_text"),
                        status=ticket.get("status"),
                        priority=ticket.get("priority"),
                        source=ticket.get("source"),
                        requester_id=ticket.get("requester_id"),
                        responder_id=ticket.get("responder_id"),
                        group_id=str(ticket.get("group_id")),
                        tags=ticket.get("tags", []),
                        custom_fields=ticket.get("custom_fields", {}),
                        created_at=ticket.get("created_at"),
                        updated_at=ticket.get("updated_at"),
                        due_by=ticket.get("due_by"),
                        fr_due_by=ticket.get("fr_due_by"),
                    )
                    yield ticket_entity

                    # Build breadcrumb for this ticket
                    ticket_breadcrumb = Breadcrumb(
                        entity_id=ticket_entity.entity_id,
                        name=ticket_entity.subject,
                        type="ticket",
                    )

                    # Generate Conversation entities for this ticket
                    async for conversation in self._generate_conversation_entities(client, ticket):
                        conversation_entity = FreshdeskConversationEntity(
                            entity_id=str(conversation.get("id")),
                            breadcrumbs=[group_breadcrumb, ticket_breadcrumb],
                            conversation_id=str(conversation.get("id")),
                            ticket_id=str(ticket.get("id")),
                            body=conversation.get("body"),
                            body_text=conversation.get("body_text"),
                            user_id=conversation.get("user_id"),
                            to_emails=conversation.get("to_emails", []),
                            cc_emails=conversation.get("cc_emails", []),
                            bcc_emails=conversation.get("bcc_emails", []),
                            incoming=conversation.get("incoming", False),
                            private=conversation.get("private", False),
                            created_at=conversation.get("created_at"),
                            updated_at=conversation.get("updated_at"),
                        )
                        yield conversation_entity