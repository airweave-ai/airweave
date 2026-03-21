"""Slack source implementation for federated search."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import SlackAuthConfig
from airweave.platform.configs.config import SlackConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import AirweaveSystemMetadata, BaseEntity, Breadcrumb
from airweave.platform.entities.slack import SlackMessageEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.sync.pipeline.text_builder import text_builder
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Slack",
    short_name="slack",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=SlackAuthConfig,
    config_class=SlackConfig,
    labels=["Communication", "Messaging"],
    supports_continuous=False,
    federated_search=True,
    rate_limit_level=RateLimitLevel.ORG,
)
class SlackSource(BaseSource):
    """Slack source connector using federated search.

    Instead of syncing all messages and files, this source searches Slack at query time
    using the search.all API endpoint. This is necessary because Slack's rate limits
    are too restrictive for full synchronization.
    """

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: SlackConfig,
    ) -> SlackSource:
        """Create a new Slack source."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """Make authenticated GET request to Slack API with token refresh support."""
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers = {"Authorization": f"Bearer {new_token}"}
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # ------------------------------------------------------------------
    # Federated search
    # ------------------------------------------------------------------

    async def search(self, query: str, limit: int) -> List[BaseEntity]:
        """Search Slack for messages matching the query with pagination support.

        Uses Slack's search.messages API endpoint with pagination to retrieve
        up to the requested limit. Files are not included since processing file
        content requires the full sync pipeline (download, chunking, vectorization)
        which federated search sources skip.
        """
        self.logger.info(f"Searching Slack messages for query: '{query}' (limit: {limit})")
        results = await self._paginate_search_results(query, limit)
        self.logger.info(f"Slack search complete: returned {len(results)} results")
        return results

    async def _paginate_search_results(self, query: str, limit: int) -> List[BaseEntity]:
        """Paginate through Slack search results."""
        page = 1
        results_fetched = 0
        max_results_per_page = 100
        all_entities: List[BaseEntity] = []

        while results_fetched < limit:
            count = min(max_results_per_page, limit - results_fetched)
            response_data = await self._fetch_search_page(query, count, page)

            if not response_data:
                break

            messages = response_data.get("messages", {})
            message_matches = messages.get("matches", [])
            paging_info = messages.get("paging", {})

            self.logger.debug(
                f"Page {page}: found {len(message_matches)} results "
                f"(total available: {paging_info.get('total', 'unknown')})"
            )

            if not message_matches:
                break

            entities = self._process_message_matches(message_matches, limit, results_fetched)
            all_entities.extend(entities)
            results_fetched += len(entities)

            if page >= paging_info.get("pages", 1):
                break

            page += 1

        return all_entities

    async def _fetch_search_page(
        self, query: str, count: int, page: int
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single page of search results from Slack API."""
        params = {
            "query": query,
            "count": count,
            "page": page,
            "highlight": True,
            "sort": "score",
        }

        response_data = await self._get("https://slack.com/api/search.messages", params=params)

        if not response_data.get("ok"):
            error = response_data.get("error", "unknown_error")
            self.logger.warning(f"Slack search API error: {error}")

            if error == "missing_scope":
                raise ValueError(
                    "Slack search failed: missing 'search:read' scope. "
                    "Please ensure your Slack OAuth connection includes the 'search:read' scope "
                    "to enable message search."
                )
            elif error == "not_authed":
                raise ValueError("Slack search failed: authentication token is invalid or expired")
            elif error == "account_inactive":
                raise ValueError("Slack search failed: account is inactive")
            else:
                raise ValueError(f"Slack search failed: {error}")

        return response_data

    def _process_message_matches(
        self, message_matches: List[Dict], limit: int, results_fetched: int
    ) -> List[BaseEntity]:
        """Process message matches and return entities."""
        entities: List[BaseEntity] = []
        for message in message_matches:
            if results_fetched + len(entities) >= limit:
                break

            try:
                entity = self._create_message_entity(message)
                if entity:
                    entities.append(entity)
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Error creating message entity: {e}")
                continue

        return entities

    def _create_message_entity(self, message: Dict[str, Any]) -> Optional[SlackMessageEntity]:
        """Create a SlackMessageEntity from a search result."""
        channel_info = message.get("channel", {})
        channel_id = channel_info.get("id", "unknown")
        channel_name = channel_info.get("name")

        breadcrumbs = [
            Breadcrumb(
                entity_id=channel_id,
                name=f"#{channel_name}" if channel_name else channel_id,
                entity_type="SlackChannel",
            )
        ]

        entity = SlackMessageEntity.from_api(message, breadcrumbs=breadcrumbs)

        entity.airweave_system_metadata = AirweaveSystemMetadata(
            source_name="slack",
            entity_type="SlackMessageEntity",
            sync_id=None,
            sync_job_id=None,
        )

        entity.textual_representation = text_builder.build_metadata_section(
            entity=entity,
            source_name="slack",
        )

        return entity

    # ------------------------------------------------------------------
    # Sync entry point (not used for federated search)
    # ------------------------------------------------------------------

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Not used — Slack is a federated search source.

        Raises NotImplementedError; use search() instead.
        """
        self.logger.warning("generate_entities() called on federated search source")
        raise NotImplementedError(
            "Slack uses federated search. Use the search() method instead of generate_entities()."
        )

    async def validate(self) -> None:
        """Validate credentials by calling Slack auth.test."""
        await self._get("https://slack.com/api/auth.test")
