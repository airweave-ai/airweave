"""Intercom source implementation.

Ingests customer conversations, conversation messages (parts), and tickets from Intercom.
API reference: https://developers.intercom.com/docs/build-an-integration/learn-more/authentication
"""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, cast

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import IntercomConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.intercom import (
    IntercomConversationEntity,
    IntercomConversationMessageEntity,
    IntercomTicketEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

API_BASE = "https://api.intercom.io"
# Tickets search requires 2.11+; conversations supported in 2.6+
INTERCOM_VERSION = "2.11"


def _parse_timestamp(value: Optional[Any]) -> Optional[datetime]:
    """Parse Intercom Unix timestamp (seconds) to timezone-aware datetime."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        if isinstance(value, str):
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        # If the timestamp value is malformed or out of range, treat it as missing.
        pass
    return None


def _now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


def _strip_html(html: Optional[str]) -> str:
    """Strip HTML tags for plain-text subject/body; return empty string if None."""
    if not html:
        return ""
    import re

    text = re.sub(r"<[^>]+>", " ", html)
    return " ".join(text.split()).strip() or ""


def _unwrap_list(value: Any, inner_key: str) -> List[Dict[str, Any]]:
    """Extract list from Intercom API list objects per reference.

    Conversations return teammates as { "type": "admin.list", "teammates": [...] }
    and contacts as an object containing the list. If value is already a list of
    dicts, return it; if it's a dict, return the inner list; otherwise [].
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        inner = value.get(inner_key) or value.get("data")
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
    return []


@source(
    name="Intercom",
    short_name="intercom",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=None,
    config_class=IntercomConfig,
    labels=["Customer Support", "CRM"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class IntercomSource(BaseSource):
    """Intercom source connector.

    Syncs conversations, conversation messages (parts), and tickets from Intercom
    to enhance support and CX queries.
    """

    access_token: str = ""
    exclude_closed_conversations: bool = False

    @classmethod
    async def create(
        cls,
        credentials: Any = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> "IntercomSource":
        """Create a new Intercom source.

        Args:
            credentials: OAuth access token (str) or dict with access_token
            config: Optional configuration (e.g., exclude_closed_conversations)

        Returns:
            Configured IntercomSource instance
        """
        instance = cls()
        token = (
            credentials
            if isinstance(credentials, str)
            else (credentials or {}).get("access_token", "")
        )
        if not token:
            raise ValueError("Access token is required")
        instance.access_token = token
        instance.exclude_closed_conversations = bool(
            (config or {}).get("exclude_closed_conversations", False)
        )
        return instance

    def _headers(self) -> Dict[str, str]:
        """Return auth and version headers for Intercom API."""
        return {
            "Authorization": f"Bearer {getattr(self, 'access_token', '')}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Intercom-Version": INTERCOM_VERSION,
        }

    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get OAuth headers (with token from token_manager if set)."""
        token = await self.get_access_token()
        if not token:
            raise ValueError("No access token available for authentication")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Intercom-Version": INTERCOM_VERSION,
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated GET request with optional token refresh on 401."""
        headers = await self._get_auth_headers()
        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            if response.status_code == 401 and self.token_manager:
                self.logger.warning(f"Received 401 for {url}, refreshing token...")
                try:
                    new_token = await self.token_manager.refresh_on_unauthorized()
                    headers["Authorization"] = f"Bearer {new_token}"
                    response = await client.get(url, headers=headers, params=params, timeout=30.0)
                except TokenRefreshError as e:
                    self.logger.error(f"Failed to refresh token: {str(e)}")
                    response.raise_for_status()
            response.raise_for_status()
            return cast(Dict[str, Any], response.json())
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Intercom API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Intercom API: {url}, {e}")
            raise

    async def _post_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        json_body: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Make authenticated POST request (e.g. for tickets search)."""
        headers = await self._get_auth_headers()
        try:
            response = await client.post(url, headers=headers, json=json_body, timeout=30.0)
            if response.status_code == 401 and self.token_manager:
                self.logger.warning(f"Received 401 for {url}, refreshing token...")
                try:
                    new_token = await self.token_manager.refresh_on_unauthorized()
                    headers["Authorization"] = f"Bearer {new_token}"
                    response = await client.post(url, headers=headers, json=json_body, timeout=30.0)
                except TokenRefreshError as e:
                    self.logger.error(f"Failed to refresh token: {str(e)}")
                    response.raise_for_status()
            response.raise_for_status()
            return cast(Dict[str, Any], response.json())
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Intercom API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Intercom API: {url}, {e}")
            raise

    def _build_conversation_url(self, conversation_id: str) -> str:
        """Build user-facing URL for a conversation."""
        return f"https://app.intercom.com/a/apps/_/inbox/inbox/conversation/{conversation_id}"

    def _build_ticket_url(self, ticket_id: str) -> str:
        """Build user-facing URL for a ticket (Inbox > Tickets)."""
        return f"https://app.intercom.com/a/apps/_/tickets/{ticket_id}"

    def _conv_to_entity(
        self, conv: Dict[str, Any]
    ) -> Optional[Tuple[IntercomConversationEntity, str, str, str, Breadcrumb]]:
        """Map one conversation API dict to entity and metadata for parts. Returns None if skip."""
        if self.exclude_closed_conversations and conv.get("state") == "closed":
            return None
        conv_id = str(conv.get("id", ""))
        if not conv_id:
            return None
        created_ts = conv.get("created_at")
        updated_ts = conv.get("updated_at")
        created_at = _parse_timestamp(created_ts) or _now()
        updated_at = _parse_timestamp(updated_ts) or created_at
        source_obj = conv.get("source") or {}
        subject = _strip_html(source_obj.get("subject") or source_obj.get("body"))
        if not subject:
            subject = f"Conversation {conv_id}"
        teammates = _unwrap_list(conv.get("teammates"), "teammates")
        assignee_name = None
        assignee_email = None
        admin_assignee_id = conv.get("admin_assignee_id")
        if admin_assignee_id is not None:
            for t in teammates:
                if str(t.get("id")) == str(admin_assignee_id):
                    assignee_name = t.get("name")
                    assignee_email = t.get("email")
                    break
        custom_attrs = conv.get("custom_attributes") or {}
        tags_list = _unwrap_list(conv.get("tags"), "tags")
        tag_names = [str(t.get("name", "")) for t in tags_list if t.get("name")]
        contacts_list = _unwrap_list(conv.get("contacts"), "contacts")
        contact_ids = [str(c.get("id", "")) for c in contacts_list if c.get("id")]
        entity = IntercomConversationEntity(
            entity_id=conv_id,
            breadcrumbs=[],
            name=subject[:500],
            created_at=created_at,
            updated_at=updated_at,
            conversation_id=conv_id,
            subject=subject[:500],
            created_at_value=created_at,
            updated_at_value=updated_at,
            web_url_value=self._build_conversation_url(conv_id),
            state=conv.get("state"),
            priority=conv.get("priority"),
            assignee_name=assignee_name,
            assignee_email=assignee_email,
            contact_ids=contact_ids,
            custom_attributes=custom_attrs,
            tags=tag_names,
            source_body=_strip_html(source_obj.get("body")),
        )
        web_url = self._build_conversation_url(conv_id)
        breadcrumb = Breadcrumb(
            entity_id=conv_id,
            name=subject[:200],
            entity_type=IntercomConversationEntity.__name__,
        )
        return (entity, conv_id, subject, web_url, breadcrumb)

    async def validate(self) -> bool:
        """Verify credentials by calling Intercom /me."""
        return await self._validate_oauth2(
            ping_url=f"{API_BASE}/me",
            headers={"Intercom-Version": INTERCOM_VERSION},
            timeout=10.0,
        )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate conversations, messages, and tickets from Intercom."""
        self.logger.info("Starting Intercom sync")
        async with self.http_client() as client:
            async for conv in self._generate_conversations(client):
                yield conv
            async for ticket in self._generate_tickets(client):
                yield ticket

    async def _generate_conversations(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """List conversations (paginated), fetch each for parts, yield conversation + messages."""
        url = f"{API_BASE}/conversations"
        params: Dict[str, Any] = {"per_page": 50}
        starting_after: Optional[str] = None

        while True:
            if starting_after:
                params["starting_after"] = starting_after
            data = await self._get_with_auth(client, url, params=params)
            conversations = data.get("conversations") or []
            pages = data.get("pages") or {}

            for conv in conversations:
                packed = self._conv_to_entity(conv)
                if not packed:
                    continue
                conv_entity, conv_id, subject, conversation_web_url, conv_breadcrumb = packed
                yield conv_entity
                async for msg_entity in self._generate_conversation_parts(
                    client, conv_id, subject, conversation_web_url, [conv_breadcrumb]
                ):
                    yield msg_entity

            next_info = pages.get("next")
            if not next_info or not isinstance(next_info, dict):
                break
            starting_after = next_info.get("starting_after")
            if not starting_after:
                break
            params = {"per_page": 50, "starting_after": starting_after}

    async def _generate_conversation_parts(
        self,
        client: httpx.AsyncClient,
        conversation_id: str,
        conversation_subject: str,
        conversation_web_url: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Fetch one conversation by ID for conversation_parts; yield message entities."""
        url = f"{API_BASE}/conversations/{conversation_id}"
        try:
            data = await self._get_with_auth(client, url, params={"display_as": "plaintext"})
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 403):
                self.logger.warning(
                    f"Could not load conversation {conversation_id}: {e.response.status_code}"
                )
                return
            raise
        # API: conversation_parts is object { "conversation_parts": [...], "total_count": n }
        parts_list = _unwrap_list(data.get("conversation_parts"), "conversation_parts")
        for part in parts_list:
            part_id = str(part.get("id", ""))
            if not part_id:
                continue
            body = part.get("body") or ""
            created_ts = part.get("created_at")
            created_at = _parse_timestamp(created_ts)
            author_raw = part.get("author")
            author = author_raw if isinstance(author_raw, dict) else {}
            author_id = str(author.get("id", "")) if author.get("id") else None
            author_type = author.get("type")
            author_name = author.get("name")
            author_email = author.get("email")
            yield IntercomConversationMessageEntity(
                entity_id=part_id,
                breadcrumbs=breadcrumbs,
                name=body[:200] if body else f"Message {part_id}",
                created_at=created_at,
                updated_at=created_at,
                message_id=part_id,
                conversation_id=conversation_id,
                conversation_subject=conversation_subject[:500],
                body=body,
                created_at_value=created_at,
                web_url_value=conversation_web_url,
                part_type=part.get("part_type"),
                author_id=author_id,
                author_type=author_type,
                author_name=author_name,
                author_email=author_email,
            )

    async def _get_ticket_parts(
        self, client: httpx.AsyncClient, ticket_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch one ticket by ID for ticket_parts (replies/comments) when search omits them."""
        try:
            data = await self._get_with_auth(client, f"{API_BASE}/tickets/{ticket_id}", params=None)
            if not isinstance(data, dict):
                return []
            ticket = data.get("ticket") or data.get("data") or data
            if not isinstance(ticket, dict):
                return []
            return _unwrap_list(ticket.get("ticket_parts"), "ticket_parts")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 403):
                return []
            raise

    async def _ticket_record_to_entity(
        self, client: httpx.AsyncClient, t: Dict[str, Any]
    ) -> Optional[IntercomTicketEntity]:
        """Map one ticket API record to IntercomTicketEntity. Returns None if id missing."""
        ticket_id = str(t.get("id", ""))
        if not ticket_id:
            return None
        attrs = t.get("ticket_attributes") or {}
        name = (
            t.get("name")
            or t.get("default_title")
            or attrs.get("default_title")
            or f"Ticket {ticket_id}"
        )
        desc = (
            t.get("description") or t.get("default_description") or attrs.get("default_description")
        )
        created_ts = t.get("created_at")
        updated_ts = t.get("updated_at")
        created_at = _parse_timestamp(created_ts) or _now()
        updated_at = _parse_timestamp(updated_ts) or created_at
        assignee_raw = t.get("assignee")
        assignee = assignee_raw if isinstance(assignee_raw, dict) else {}
        assignee_id = str(assignee.get("id", "")) if assignee.get("id") else None
        assignee_name = assignee.get("name")
        ticket_type_raw = t.get("ticket_type")
        ticket_type = ticket_type_raw if isinstance(ticket_type_raw, dict) else {}
        type_name = ticket_type.get("name")
        type_id = str(ticket_type.get("id", "")) if ticket_type.get("id") else None
        contacts_list = _unwrap_list(t.get("contacts"), "contacts")
        if not contacts_list and t.get("contact_ids"):
            contact_ids_raw = t.get("contact_ids")
            if isinstance(contact_ids_raw, list):
                contact_id = str(contact_ids_raw[0]) if contact_ids_raw else None
            else:
                contact_id = str(contact_ids_raw) if contact_ids_raw else None
        else:
            contact_id = str(contacts_list[0].get("id", "")) if contacts_list else None
        parts_list = _unwrap_list(t.get("ticket_parts"), "ticket_parts")
        if not parts_list:
            parts_list = await self._get_ticket_parts(client, ticket_id)
        parts_bodies = [
            _strip_html(p.get("body")) for p in parts_list if _strip_html(p.get("body"))
        ]
        ticket_parts_text = "\n\n".join(parts_bodies) if parts_bodies else None
        return IntercomTicketEntity(
            entity_id=ticket_id,
            breadcrumbs=[],
            name=name,
            created_at=created_at,
            updated_at=updated_at,
            ticket_id=ticket_id,
            description=desc,
            created_at_value=created_at,
            updated_at_value=updated_at,
            web_url_value=self._build_ticket_url(ticket_id),
            state=t.get("state") or t.get("ticket_state"),
            priority=t.get("priority"),
            assignee_id=assignee_id,
            assignee_name=assignee_name,
            contact_id=contact_id,
            ticket_type_id=type_id,
            ticket_type_name=type_name,
            ticket_parts_text=ticket_parts_text,
        )

    async def _generate_tickets(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Search tickets (POST /tickets/search) with cursor pagination; yield ticket entities."""
        url = f"{API_BASE}/tickets/search"
        body: Dict[str, Any] = {
            "query": {
                "operator": "AND",
                "value": [{"field": "created_at", "operator": ">", "value": 0}],
            },
            "pagination": {"per_page": 50},
        }
        starting_after: Optional[str] = None

        while True:
            if starting_after:
                body["pagination"]["starting_after"] = starting_after
            try:
                data = await self._post_with_auth(client, url, body)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    self.logger.debug("Tickets API not available (e.g. plan)")
                    return
                raise
            # API: search returns { "tickets": [...], "pages": {...} }
            tickets_raw = data.get("tickets")
            tickets = (
                _unwrap_list(tickets_raw, "tickets")
                if isinstance(tickets_raw, dict)
                else ([t for t in (tickets_raw or []) if isinstance(t, dict)])
            )
            pages = data.get("pages") or {}
            for t in tickets:
                entity = await self._ticket_record_to_entity(client, t)
                if entity:
                    yield entity
            next_info = pages.get("next")
            if not next_info or not isinstance(next_info, dict):
                break
            starting_after = next_info.get("starting_after")
            if not starting_after:
                break
            body["pagination"]["starting_after"] = starting_after
