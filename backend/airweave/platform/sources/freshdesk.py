"""Freshdesk source implementation.

Syncs Tickets, Conversations, Contacts, Companies, and Solution Articles from Freshdesk.
API reference: https://developers.freshdesk.com/api/
"""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import FreshdeskAuthConfig
from airweave.platform.configs.config import FreshdeskConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.freshdesk import (
    FreshdeskCompanyEntity,
    FreshdeskContactEntity,
    FreshdeskConversationEntity,
    FreshdeskSolutionArticleEntity,
    FreshdeskTicketEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse Freshdesk ISO8601 timestamps to timezone-aware datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


@source(
    name="Freshdesk",
    short_name="freshdesk",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class=FreshdeskAuthConfig,
    config_class=FreshdeskConfig,
    labels=["Customer Support", "CRM"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class FreshdeskSource(BaseSource):
    """Freshdesk source connector.

    Syncs tickets, conversations, contacts, companies, and solution articles from Freshdesk.
    """

    @classmethod
    async def create(
        cls,
        auth_config: FreshdeskAuthConfig,
        config: Optional[Dict[str, Any]] = None,
    ) -> "FreshdeskSource":
        """Create a new Freshdesk source instance."""
        instance = cls()
        instance.api_key = auth_config.api_key
        instance.domain = (config or {}).get("domain") or ""
        return instance

    def _base_url(self) -> str:
        """Return the Freshdesk API base URL."""
        return f"https://{self.domain}.freshdesk.com/api/v2"

    def _build_ticket_url(self, ticket_id: int) -> str:
        """Build user-facing URL for a ticket."""
        return f"https://{self.domain}.freshdesk.com/a/tickets/{ticket_id}"

    def _build_contact_url(self, contact_id: int) -> str:
        """Build user-facing URL for a contact."""
        return f"https://{self.domain}.freshdesk.com/a/contacts/{contact_id}"

    def _build_company_url(self, company_id: int) -> str:
        """Build user-facing URL for a company."""
        return f"https://{self.domain}.freshdesk.com/a/companies/{company_id}"

    def _build_article_url(self, article_id: int) -> str:
        """Build user-facing URL for a solution article."""
        return f"https://{self.domain}.freshdesk.com/support/solutions/articles/{article_id}"

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make an authenticated GET request to the Freshdesk API.

        Uses Basic auth: API key as username, "X" as password.
        See: https://developers.freshdesk.com/api/#authentication
        """
        auth = httpx.BasicAuth(username=self.api_key, password="X")
        response = await client.get(url, auth=auth, params=params, timeout=30.0)
        response.raise_for_status()
        return response

    def _parse_link_header(self, link_header: Optional[str]) -> Optional[str]:
        """Parse Link header and return next page URL if present."""
        if not link_header:
            return None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
                return url
        return None

    async def _paginate_list(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Paginate through a Freshdesk list endpoint (page=1, per_page=100; follow Link header)."""
        base = self._base_url()
        url = f"{base}{path}"
        page_params = {"page": 1, "per_page": 100}
        if params:
            page_params.update(params)

        while url:
            if "?" in url:
                # url is full URL from Link header
                response = await self._get_with_auth(client, url)
            else:
                response = await self._get_with_auth(client, url, params=page_params)

            data = response.json()
            if not isinstance(data, list):
                data = data.get("results", data.get("records", []))

            for item in data:
                yield item

            link_header = response.headers.get("link") or response.headers.get("Link")
            next_url = self._parse_link_header(link_header)
            if next_url:
                url = next_url
                page_params = {}
            elif len(data) < page_params.get("per_page", 100):
                url = None
            else:
                page_params["page"] = page_params.get("page", 1) + 1
                url = f"{base}{path}"

    async def _generate_company_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate company entities from GET /api/v2/companies."""
        async for company in self._paginate_list(client, "/companies"):
            company_id = company["id"]
            name = company.get("name") or f"Company {company_id}"
            created_at = _parse_datetime(company.get("created_at")) or _now()
            updated_at = _parse_datetime(company.get("updated_at")) or created_at
            yield FreshdeskCompanyEntity(
                entity_id=str(company_id),
                breadcrumbs=[],
                name=name,
                created_at=created_at,
                updated_at=updated_at,
                company_id=company_id,
                created_at_value=created_at,
                updated_at_value=updated_at,
                web_url_value=self._build_company_url(company_id),
                description=company.get("description"),
                note=company.get("note"),
                domains=company.get("domains") or [],
                custom_fields=company.get("custom_fields") or {},
                industry=company.get("industry"),
            )

    async def _generate_contact_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate contact entities from GET /api/v2/contacts."""
        async for contact in self._paginate_list(client, "/contacts"):
            contact_id = contact["id"]
            name = contact.get("name") or contact.get("email") or f"Contact {contact_id}"
            created_at = _parse_datetime(contact.get("created_at")) or _now()
            updated_at = _parse_datetime(contact.get("updated_at")) or created_at
            yield FreshdeskContactEntity(
                entity_id=str(contact_id),
                breadcrumbs=[],
                name=name,
                created_at=created_at,
                updated_at=updated_at,
                contact_id=contact_id,
                email=contact.get("email"),
                created_at_value=created_at,
                updated_at_value=updated_at,
                web_url_value=self._build_contact_url(contact_id),
                company_id=contact.get("company_id"),
                job_title=contact.get("job_title"),
                phone=contact.get("phone"),
                mobile=contact.get("mobile"),
                description=contact.get("description"),
                tags=contact.get("tags") or [],
                custom_fields=contact.get("custom_fields") or {},
            )

    async def _generate_ticket_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ticket entities from GET /api/v2/tickets."""
        async for ticket in self._paginate_list(client, "/tickets"):
            ticket_id = ticket["id"]
            subject = ticket.get("subject") or f"Ticket #{ticket_id}"
            created_at = _parse_datetime(ticket.get("created_at")) or _now()
            updated_at = _parse_datetime(ticket.get("updated_at")) or created_at
            yield FreshdeskTicketEntity(
                entity_id=str(ticket_id),
                breadcrumbs=[],
                name=subject,
                created_at=created_at,
                updated_at=updated_at,
                ticket_id=ticket_id,
                subject=subject,
                created_at_value=created_at,
                updated_at_value=updated_at,
                web_url_value=self._build_ticket_url(ticket_id),
                description=ticket.get("description"),
                description_text=ticket.get("description_text"),
                status=ticket.get("status"),
                priority=ticket.get("priority"),
                requester_id=ticket.get("requester_id"),
                responder_id=ticket.get("responder_id"),
                company_id=ticket.get("company_id"),
                group_id=ticket.get("group_id"),
                type=ticket.get("type"),
                source=ticket.get("source"),
                tags=ticket.get("tags") or [],
                custom_fields=ticket.get("custom_fields") or {},
            )

    async def _generate_conversation_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate conversation entities by fetching conversations for each ticket."""
        base = self._base_url()
        async for ticket in self._paginate_list(client, "/tickets"):
            ticket_id = ticket["id"]
            ticket_subject = ticket.get("subject") or f"Ticket #{ticket_id}"
            ticket_breadcrumb = Breadcrumb(
                entity_id=str(ticket_id),
                name=ticket_subject,
                entity_type=FreshdeskTicketEntity.__name__,
            )
            ticket_url = self._build_ticket_url(ticket_id)

            page = 1
            while True:
                response = await self._get_with_auth(
                    client,
                    f"{base}/tickets/{ticket_id}/conversations",
                    params={"page": page, "per_page": 100},
                )
                conversations = response.json()
                if not conversations:
                    break
                for conv in conversations:
                    conv_id = conv["id"]
                    body_text = (
                        conv.get("body_text")
                        or (conv.get("body") or "").strip()
                        or f"Conversation {conv_id}"
                    )
                    created_at = _parse_datetime(conv.get("created_at")) or _now()
                    updated_at = _parse_datetime(conv.get("updated_at")) or created_at
                    yield FreshdeskConversationEntity(
                        entity_id=f"{ticket_id}_{conv_id}",
                        breadcrumbs=[ticket_breadcrumb],
                        name=body_text[:200] if body_text else f"Conversation {conv_id}",
                        created_at=created_at,
                        updated_at=updated_at,
                        conversation_id=conv_id,
                        ticket_id=ticket_id,
                        ticket_subject=ticket_subject,
                        body=conv.get("body"),
                        body_text=body_text,
                        created_at_value=created_at,
                        updated_at_value=updated_at,
                        user_id=conv.get("user_id"),
                        incoming=conv.get("incoming", False),
                        private=conv.get("private", False),
                        web_url_value=ticket_url,
                    )
                link_header = response.headers.get("link") or response.headers.get("Link")
                if self._parse_link_header(link_header) and len(conversations) == 100:
                    page += 1
                else:
                    break

    async def _generate_articles_from_folder(
        self,
        client: httpx.AsyncClient,
        base: str,
        folder_id: int,
        folder_name: str,
        category_id: int,
        category_name: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield solution articles in a folder, then recursively process subfolders."""
        page = 1
        while True:
            art_response = await self._get_with_auth(
                client,
                f"{base}/solutions/folders/{folder_id}/articles",
                params={"page": page, "per_page": 100},
            )
            articles = art_response.json() or []
            if not articles:
                break
            for article in articles:
                article_id = article["id"]
                title = article.get("title") or f"Article {article_id}"
                created_at = _parse_datetime(article.get("created_at")) or _now()
                updated_at = _parse_datetime(article.get("updated_at")) or created_at
                yield FreshdeskSolutionArticleEntity(
                    entity_id=str(article_id),
                    breadcrumbs=breadcrumbs,
                    name=title,
                    created_at=created_at,
                    updated_at=updated_at,
                    article_id=article_id,
                    title=title,
                    created_at_value=created_at,
                    updated_at_value=updated_at,
                    web_url_value=self._build_article_url(article_id),
                    description=article.get("description"),
                    description_text=article.get("description_text"),
                    status=article.get("status"),
                    folder_id=folder_id,
                    category_id=category_id,
                    folder_name=folder_name,
                    category_name=category_name,
                    tags=article.get("tags") or [],
                )
            link_header = art_response.headers.get("link") or art_response.headers.get("Link")
            if self._parse_link_header(link_header) and len(articles) == 100:
                page += 1
            else:
                break

        subfolders_response = await self._get_with_auth(
            client,
            f"{base}/solutions/folders/{folder_id}/subfolders",
        )
        subfolders = subfolders_response.json() or []
        for subfolder in subfolders:
            subfolder_id = subfolder.get("id")
            subfolder_name = subfolder.get("name") or f"Folder {subfolder_id}"
            subfolder_breadcrumb = Breadcrumb(
                entity_id=str(subfolder_id),
                name=subfolder_name,
                entity_type="Folder",
            )
            sub_breadcrumbs = [*breadcrumbs, subfolder_breadcrumb]
            async for entity in self._generate_articles_from_folder(
                client,
                base,
                subfolder_id,
                subfolder_name,
                category_id,
                category_name,
                sub_breadcrumbs,
            ):
                yield entity

    async def _generate_solution_article_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate solution article entities by walking categories→folders→subfolders→articles."""
        base = self._base_url()
        response = await self._get_with_auth(client, f"{base}/solutions/categories")
        categories = response.json() or []
        for category in categories:
            category_id = category.get("id")
            category_name = category.get("name") or f"Category {category_id}"
            category_breadcrumb = Breadcrumb(
                entity_id=str(category_id),
                name=category_name,
                entity_type="Category",
            )
            folder_response = await self._get_with_auth(
                client,
                f"{base}/solutions/categories/{category_id}/folders",
            )
            folders = folder_response.json() or []
            for folder in folders:
                folder_id = folder.get("id")
                folder_name = folder.get("name") or f"Folder {folder_id}"
                folder_breadcrumb = Breadcrumb(
                    entity_id=str(folder_id),
                    name=folder_name,
                    entity_type="Folder",
                )
                breadcrumbs = [category_breadcrumb, folder_breadcrumb]
                async for entity in self._generate_articles_from_folder(
                    client,
                    base,
                    folder_id,
                    folder_name,
                    category_id,
                    category_name,
                    breadcrumbs,
                ):
                    yield entity

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities: companies, contacts, tickets, conversations, articles."""
        async with self.http_client(timeout=30.0) as client:
            async for entity in self._generate_company_entities(client):
                yield entity
            async for entity in self._generate_contact_entities(client):
                yield entity
            async for entity in self._generate_ticket_entities(client):
                yield entity
            async for entity in self._generate_conversation_entities(client):
                yield entity
            async for entity in self._generate_solution_article_entities(client):
                yield entity

    async def validate(self) -> bool:
        """Validate Freshdesk credentials by calling GET /api/v2/agents/me."""
        if not getattr(self, "api_key", None):
            self.logger.error("Freshdesk validation failed: missing API key.")
            return False
        if not getattr(self, "domain", None):
            self.logger.error("Freshdesk validation failed: missing domain.")
            return False
        try:
            async with self.http_client(timeout=10.0) as client:
                await self._get_with_auth(client, f"{self._base_url()}/agents/me")
                return True
        except httpx.HTTPStatusError as e:
            text_preview = (e.response.text or "")[:200]
            self.logger.error(
                f"Freshdesk validation failed: HTTP {e.response.status_code} - {text_preview}"
            )
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during Freshdesk validation: {e}")
            return False
