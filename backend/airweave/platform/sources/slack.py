"""Slack source implementation for federated search."""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import SlackAuthConfig
from airweave.platform.configs.config import SlackConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import AirweaveSystemMetadata, BaseEntity, Breadcrumb
from airweave.platform.entities.slack import SlackMessageEntity
from airweave.platform.sources._base import BaseSource
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
    federated_search=True,  # This source uses federated search instead of syncing
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
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "SlackSource":
        """Create a new Slack source.

        Args:
            access_token: OAuth access token for Slack API
            config: Optional configuration parameters

        Returns:
            Configured SlackSource instance
        """
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Make authenticated GET request to Slack API with token manager support.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters
        """
        # Get a valid token (will refresh if needed)
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError("No access token available")

        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 Unauthorized - token might have expired
            if response.status_code == 401:
                self.logger.warning(f"Received 401 Unauthorized for {url}, refreshing token...")

                # If we have a token manager, try to refresh
                if self.token_manager:
                    try:
                        # Force refresh the token
                        new_token = await self.token_manager.refresh_on_unauthorized()
                        headers = {"Authorization": f"Bearer {new_token}"}

                        # Retry the request with the new token
                        self.logger.info(f"Retrying request with refreshed token: {url}")
                        response = await client.get(url, headers=headers, params=params)

                    except TokenRefreshError as e:
                        self.logger.error(f"Failed to refresh token: {str(e)}")
                        response.raise_for_status()
                else:
                    # No token manager, can't refresh
                    self.logger.error("No token manager available to refresh expired token")
                    response.raise_for_status()

            # Raise for other HTTP errors
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Slack API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Slack API: {url}, {str(e)}")
            raise

    async def search(self, query: str, limit: int) -> List[BaseEntity]:
        """Search Slack for messages matching the query with pagination support.

        Uses Slack's search.messages API endpoint with pagination to retrieve
        up to the requested limit. Files are not included since processing file
        content requires the full sync pipeline (download, chunking, vectorization)
        which federated search sources skip.

        Args:
            query: Search query string
            limit: Maximum number of message results to return

        Returns:
            List of SlackMessageEntity objects
        """
        self.logger.info(f"Searching Slack messages for query: '{query}' (limit: {limit})")

        async with self.http_client() as client:
            try:
                results = await self._paginate_search_results(client, query, limit)
                self.logger.info(f"Slack search complete: returned {len(results)} results")
                return results

            except httpx.HTTPStatusError as e:
                self.logger.error(f"HTTP error during Slack search: {e}")
                raise
            except Exception as e:
                self.logger.error(f"Unexpected error during Slack search: {e}")
                raise

    async def _paginate_search_results(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> List[BaseEntity]:
        """Paginate through Slack search results."""
        page = 1
        results_fetched = 0
        max_results_per_page = 100  # Slack's hard limit per page
        all_entities = []

        while results_fetched < limit:
            count = min(max_results_per_page, limit - results_fetched)
            response_data = await self._fetch_search_page(client, query, count, page)

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

            entities = await self._process_message_matches(message_matches, limit, results_fetched)
            all_entities.extend(entities)
            results_fetched += len(entities)

            # Check if there are more pages
            if page >= paging_info.get("pages", 1):
                break

            page += 1

        return all_entities

    async def _fetch_search_page(
        self, client: httpx.AsyncClient, query: str, count: int, page: int
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single page of search results from Slack API."""
        params = {
            "query": query,
            "count": count,
            "page": page,
            "highlight": True,
            "sort": "score",
        }

        response_data = await self._get_with_auth(
            client, "https://slack.com/api/search.messages", params=params
        )

        if not response_data.get("ok"):
            error = response_data.get("error", "unknown_error")
            self.logger.error(f"Slack search API error: {error}")

            # Provide helpful error messages for common issues
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

    async def _process_message_matches(
        self, message_matches: List[Dict], limit: int, results_fetched: int
    ) -> List[BaseEntity]:
        """Process message matches and return entities."""
        entities = []
        for message in message_matches:
            # Stop once we've reached the total limit
            if results_fetched + len(entities) >= limit:
                break

            try:
                entity = await self._create_message_entity(message)
                if entity:
                    entities.append(entity)
            except Exception as e:
                self.logger.error(f"Error creating message entity: {e}")
                continue

        return entities

    async def _create_message_entity(self, message: Dict[str, Any]) -> Optional[SlackMessageEntity]:
        """Create a SlackMessageEntity from search result.

        Args:
            message: Message data from Slack search API

        Returns:
            SlackMessageEntity or None if creation fails
        """
        try:
            channel_info = message.get("channel", {})
            channel_id = channel_info.get("id", "unknown")
            channel_name = channel_info.get("name")

            # Parse timestamp to datetime
            ts = message.get("ts", "0")
            try:
                created_at = datetime.fromtimestamp(float(ts))
            except (ValueError, TypeError):
                created_at = None

            # Create message name from text preview
            text = message.get("text", "")
            message_name = text[:50] + "..." if len(text) > 50 else text
            if not message_name:
                message_name = f"Slack message {ts}"

            # Build breadcrumbs
            breadcrumbs = [
                Breadcrumb(
                    entity_id=channel_id,
                    name=f"#{channel_name}" if channel_name else channel_id,
                    entity_type="SlackChannel",
                )
            ]

            message_text = text or message_name
            username = message.get("username")

            # Build system metadata for federated search
            # (normally built by EntityPipeline._enrich_early_metadata in sync pipeline)
            system_metadata = AirweaveSystemMetadata(
                source_name="slack",  # short_name from @source decorator
                entity_type="SlackMessageEntity",
                sync_id=None,  # No sync for federated search
                sync_job_id=None,  # No sync job for federated search
            )

            # Create entity first (text_builder needs entity to extract embeddable fields)
            entity = SlackMessageEntity(
                # Base fields
                entity_id=message.get("iid", message.get("ts", "")),
                breadcrumbs=breadcrumbs,
                name=message_name,
                created_at=created_at,
                updated_at=None,  # Messages don't have update timestamp
                airweave_system_metadata=system_metadata,
                # API fields
                text=message_text,
                user=message.get("user"),
                username=username,
                ts=message.get("ts", ""),
                channel_id=channel_id,
                channel_name=channel_name,
                channel_is_private=channel_info.get("is_private", False),
                type=message.get("type", "message"),
                permalink=message.get("permalink"),
                team=message.get("team"),
                previous_message=message.get("previous"),
                next_message=message.get("next"),
                score=float(message.get("score", 0)),
                iid=message.get("iid"),
                url=message.get("permalink"),
                message_time=created_at or datetime.utcnow(),
                web_url_value=message.get("permalink"),
            )

            # Build textual representation using shared utility
            # (normally built by TextualRepresentationBuilder in sync pipeline)
            entity.textual_representation = text_builder.build_metadata_section(
                entity=entity,
                source_name="slack",
            )

            return entity
        except Exception as e:
            self.logger.error(f"Error creating message entity: {e}")
            return None

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities for the source.

        This method should not be called for federated search sources.
        Federated search sources use the search() method instead.
        """
        self.logger.error("generate_entities() called on federated search source")
        raise NotImplementedError(
            "Slack uses federated search. Use the search() method instead of generate_entities()."
        )

    async def validate(self) -> bool:
        """Verify OAuth2 token by testing Slack API access."""
        return await self._validate_oauth2(
            ping_url="https://slack.com/api/auth.test",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10.0,
        )
