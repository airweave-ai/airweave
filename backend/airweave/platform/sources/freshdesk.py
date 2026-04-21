"""Freshdesk source implementation.

Syncs Tickets, Conversations, Contacts, Companies, and Solution Articles from Freshdesk.
API reference: https://developers.freshdesk.com/api/
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError, SourceError
from airweave.domains.sources.token_providers.protocol import (
    AuthProviderKind,
    TokenProviderProtocol,
)
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
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
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup


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
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: FreshdeskConfig,
    ) -> FreshdeskSource:
        """Create a new Freshdesk source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if auth.provider_kind == AuthProviderKind.CREDENTIAL:
            instance._api_key = auth.credentials.api_key
        else:
            instance._api_key = await auth.get_token()
        instance._domain = config.domain
        return instance

    def _base_url(self) -> str:
        """Return the Freshdesk API base URL."""
        return f"https://{self._domain}.freshdesk.com/api/v2"

    def _build_ticket_url(self, ticket_id: int) -> str:
        """Build user-facing URL for a ticket."""
        return f"https://{self._domain}.freshdesk.com/a/tickets/{ticket_id}"

    def _build_contact_url(self, contact_id: int) -> str:
        """Build user-facing URL for a contact."""
        return f"https://{self._domain}.freshdesk.com/a/contacts/{contact_id}"

    def _build_company_url(self, company_id: int) -> str:
        """Build user-facing URL for a company."""
        return f"https://{self._domain}.freshdesk.com/a/companies/{company_id}"

    def _build_article_url(self, article_id: int) -> str:
        """Build user-facing URL for a solution article."""
        return f"https://{self._domain}.freshdesk.com/support/solutions/articles/{article_id}"

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
    ) -> httpx.Response:
        """Make an authenticated GET request to the Freshdesk API.

        Uses Basic auth: API key as username, "X" as password.
        See: https://developers.freshdesk.com/api/#authentication
        """
        auth = httpx.BasicAuth(username=self._api_key, password="X")
        response = await self.http_client.get(url, auth=auth, params=params, timeout=30.0)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            auth = httpx.BasicAuth(username=new_token, password="X")
            response = await self.http_client.get(url, auth=auth, params=params, timeout=30.0)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
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
                response = await self._get(url)
            else:
                response = await self._get(url, params=page_params)

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

    async def _generate_company_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate company entities from GET /api/v2/companies."""
        async for company in self._paginate_list("/companies"):
            yield FreshdeskCompanyEntity.from_api(
                company, web_url=self._build_company_url(company["id"])
            )

    async def _generate_contact_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate contact entities from GET /api/v2/contacts."""
        async for contact in self._paginate_list("/contacts"):
            yield FreshdeskContactEntity.from_api(
                contact, web_url=self._build_contact_url(contact["id"])
            )

    async def _generate_ticket_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate ticket entities from GET /api/v2/tickets."""
        async for ticket in self._paginate_list("/tickets"):
            yield FreshdeskTicketEntity.from_api(
                ticket, web_url=self._build_ticket_url(ticket["id"])
            )

    async def _generate_conversation_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate conversation entities by fetching conversations for each ticket."""
        base = self._base_url()
        async for ticket in self._paginate_list("/tickets"):
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
                try:
                    response = await self._get(
                        f"{base}/tickets/{ticket_id}/conversations",
                        params={"page": page, "per_page": 100},
                    )
                except SourceAuthError:
                    raise
                except SourceError:
                    break
                conversations = response.json()
                if not conversations:
                    break
                for conv in conversations:
                    yield FreshdeskConversationEntity.from_api(
                        conv,
                        ticket_id=ticket_id,
                        ticket_subject=ticket_subject,
                        ticket_url=ticket_url,
                        breadcrumbs=[ticket_breadcrumb],
                    )
                link_header = response.headers.get("link") or response.headers.get("Link")
                if self._parse_link_header(link_header) and len(conversations) == 100:
                    page += 1
                else:
                    break

    async def _generate_articles_from_folder(
        self,
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
            art_response = await self._get(
                f"{base}/solutions/folders/{folder_id}/articles",
                params={"page": page, "per_page": 100},
            )
            articles = art_response.json() or []
            if not articles:
                break
            for article in articles:
                yield FreshdeskSolutionArticleEntity.from_api(
                    article,
                    web_url=self._build_article_url(article["id"]),
                    folder_id=folder_id,
                    folder_name=folder_name,
                    category_id=category_id,
                    category_name=category_name,
                    breadcrumbs=breadcrumbs,
                )
            link_header = art_response.headers.get("link") or art_response.headers.get("Link")
            if self._parse_link_header(link_header) and len(articles) == 100:
                page += 1
            else:
                break

        subfolders_response = await self._get(
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
                base,
                subfolder_id,
                subfolder_name,
                category_id,
                category_name,
                sub_breadcrumbs,
            ):
                yield entity

    async def _generate_solution_article_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate solution article entities by walking categories, folders, and articles."""
        base = self._base_url()
        response = await self._get(f"{base}/solutions/categories")
        categories = response.json() or []
        for category in categories:
            category_id = category.get("id")
            category_name = category.get("name") or f"Category {category_id}"
            category_breadcrumb = Breadcrumb(
                entity_id=str(category_id),
                name=category_name,
                entity_type="Category",
            )
            folder_response = await self._get(
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
                    base,
                    folder_id,
                    folder_name,
                    category_id,
                    category_name,
                    breadcrumbs,
                ):
                    yield entity

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities: companies, contacts, tickets, conversations, articles."""
        async for entity in self._generate_company_entities():
            yield entity
        async for entity in self._generate_contact_entities():
            yield entity
        async for entity in self._generate_ticket_entities():
            yield entity
        async for entity in self._generate_conversation_entities():
            yield entity
        async for entity in self._generate_solution_article_entities():
            yield entity

    async def validate(self) -> None:
        """Validate Freshdesk credentials by calling GET /api/v2/agents/me."""
        await self._get(f"{self._base_url()}/agents/me")
