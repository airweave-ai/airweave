"""Intercom source implementation.

Ingests customer conversations, conversation messages (parts), and tickets from Intercom.
API reference: https://developers.intercom.com/docs/build-an-integration/learn-more/authentication
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional, Tuple

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import (
    SourceEntityForbiddenError,
    SourceEntityNotFoundError,
)
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import IntercomConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.intercom import (
    IntercomConversationEntity,
    IntercomConversationMessageEntity,
    IntercomTicketEntity,
    _strip_html,
    _unwrap_list,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup

API_BASE = "https://api.intercom.io"
INTERCOM_VERSION = "2.11"


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

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: IntercomConfig,
    ) -> IntercomSource:
        """Create a new Intercom source."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance._exclude_closed = bool(config.exclude_closed_conversations)
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated GET request with token refresh on 401."""
        token = await self.auth.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Intercom-Version": INTERCOM_VERSION,
        }
        response = await self.http_client.get(url, headers=headers, params=params, timeout=30.0)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers["Authorization"] = f"Bearer {new_token}"
            response = await self.http_client.get(url, headers=headers, params=params, timeout=30.0)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post(
        self,
        url: str,
        json_body: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Make authenticated POST request with token refresh on 401."""
        token = await self.auth.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Intercom-Version": INTERCOM_VERSION,
        }
        response = await self.http_client.post(url, headers=headers, json=json_body, timeout=30.0)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers["Authorization"] = f"Bearer {new_token}"
            response = await self.http_client.post(
                url, headers=headers, json=json_body, timeout=30.0
            )

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

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
        if self._exclude_closed and conv.get("state") == "closed":
            return None
        conv_id = str(conv.get("id", ""))
        if not conv_id:
            return None

        web_url = self._build_conversation_url(conv_id)
        entity = IntercomConversationEntity.from_api(conv, breadcrumbs=[], web_url=web_url)

        breadcrumb = Breadcrumb(
            entity_id=conv_id,
            name=entity.subject[:200],
            entity_type=IntercomConversationEntity.__name__,
        )
        return (entity, conv_id, entity.subject, web_url, breadcrumb)

    async def validate(self) -> None:
        """Validate credentials by pinging Intercom's /me endpoint."""
        await self._get(f"{API_BASE}/me")

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate conversations, messages, and tickets from Intercom."""
        self.logger.info("Starting Intercom sync")
        async for conv in self._generate_conversations():
            yield conv
        async for ticket in self._generate_tickets():
            yield ticket

    async def _generate_conversations(self) -> AsyncGenerator[BaseEntity, None]:
        """List conversations (paginated), fetch each for parts, yield conversation + messages."""
        url = f"{API_BASE}/conversations"
        params: Dict[str, Any] = {"per_page": 50}
        starting_after: Optional[str] = None

        while True:
            if starting_after:
                params["starting_after"] = starting_after
            data = await self._get(url, params=params)
            conversations = data.get("conversations") or []
            pages = data.get("pages") or {}

            for conv in conversations:
                packed = self._conv_to_entity(conv)
                if not packed:
                    continue
                conv_entity, conv_id, subject, conversation_web_url, conv_breadcrumb = packed
                yield conv_entity
                async for msg_entity in self._generate_conversation_parts(
                    conv_id, subject, conversation_web_url, [conv_breadcrumb]
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
        conversation_id: str,
        conversation_subject: str,
        conversation_web_url: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Fetch one conversation by ID for conversation_parts; yield message entities."""
        url = f"{API_BASE}/conversations/{conversation_id}"
        try:
            data = await self._get(url, params={"display_as": "plaintext"})
        except (SourceEntityNotFoundError, SourceEntityForbiddenError):
            self.logger.warning(f"Could not load conversation {conversation_id}")
            return

        parts_list = _unwrap_list(data.get("conversation_parts"), "conversation_parts")
        for part in parts_list:
            if not str(part.get("id", "")):
                continue
            yield IntercomConversationMessageEntity.from_api(
                part,
                breadcrumbs=breadcrumbs,
                conversation_id=conversation_id,
                conversation_subject=conversation_subject,
                web_url=conversation_web_url,
            )

    async def _get_ticket_parts(self, ticket_id: str) -> List[Dict[str, Any]]:
        """Fetch one ticket by ID for ticket_parts (replies/comments) when search omits them."""
        try:
            data = await self._get(f"{API_BASE}/tickets/{ticket_id}", params=None)
            if not isinstance(data, dict):
                return []
            ticket = data.get("ticket") or data.get("data") or data
            if not isinstance(ticket, dict):
                return []
            return _unwrap_list(ticket.get("ticket_parts"), "ticket_parts")
        except (SourceEntityNotFoundError, SourceEntityForbiddenError):
            return []

    async def _ticket_record_to_entity(self, t: Dict[str, Any]) -> Optional[IntercomTicketEntity]:
        """Map one ticket API record to IntercomTicketEntity. Returns None if id missing."""
        ticket_id = str(t.get("id", ""))
        if not ticket_id:
            return None

        parts_list = _unwrap_list(t.get("ticket_parts"), "ticket_parts")
        if not parts_list:
            parts_list = await self._get_ticket_parts(ticket_id)
        parts_bodies = [
            _strip_html(p.get("body")) for p in parts_list if _strip_html(p.get("body"))
        ]
        ticket_parts_text = "\n\n".join(parts_bodies) if parts_bodies else None

        return IntercomTicketEntity.from_api(
            t,
            breadcrumbs=[],
            web_url=self._build_ticket_url(ticket_id),
            ticket_parts_text=ticket_parts_text,
        )

    async def _generate_tickets(self) -> AsyncGenerator[BaseEntity, None]:
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
                data = await self._post(url, body)
            except SourceEntityNotFoundError:
                self.logger.debug("Tickets API not available (e.g. plan)")
                return

            tickets_raw = data.get("tickets")
            tickets = (
                _unwrap_list(tickets_raw, "tickets")
                if isinstance(tickets_raw, dict)
                else ([t for t in (tickets_raw or []) if isinstance(t, dict)])
            )
            pages = data.get("pages") or {}
            for t in tickets:
                entity = await self._ticket_record_to_entity(t)
                if entity:
                    yield entity
            next_info = pages.get("next")
            if not next_info or not isinstance(next_info, dict):
                break
            starting_after = next_info.get("starting_after")
            if not starting_after:
                break
            body["pagination"]["starting_after"] = starting_after
