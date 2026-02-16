"""Monday source implementation.

Retrieves data from Monday.com's GraphQL API and yields entity objects for Boards,
Groups, Columns, Items, Subitems, and Updates. Uses a stepwise pattern to issue
GraphQL queries for retrieving these objects.
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import MondayAuthConfig
from airweave.platform.configs.config import MondayConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.monday import (
    MondayBoardEntity,
    MondayColumnEntity,
    MondayGroupEntity,
    MondayItemEntity,
    MondaySubitemEntity,
    MondayUpdateEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Monday",
    short_name="monday",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=None,
    config_class=MondayConfig,
    labels=["Project Management"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class MondaySource(BaseSource):
    """Monday source connector integrates with the Monday.com GraphQL API to extract work data.

    Connects to your Monday.com workspace.

    It provides comprehensive access to boards, items, and team
    collaboration features with full relationship mapping and custom field support.
    """

    GRAPHQL_ENDPOINT = "https://api.monday.com/v2"

    def __init__(self) -> None:
        """Initialize Monday source with account metadata cache."""
        super().__init__()
        self._account_slug: Optional[str] = None

    @classmethod
    async def create(
        cls, auth_config: MondayAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "MondaySource":
        """Create a new Monday source.

        Args:
            auth_config: Authentication configuration containing the access token.
            config: Optional configuration parameters for the Monday source.

        Returns:
            A configured MondaySource instance.
        """
        instance = cls()
        instance.access_token = auth_config.access_token
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _graphql_query(
        self, client: httpx.AsyncClient, query: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a single GraphQL query against the Monday.com API."""
        headers = {
            "Authorization": self.access_token,
            "Content-Type": "application/json",
        }
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = await client.post(self.GRAPHQL_ENDPOINT, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Handle GraphQL-level errors which come with 200 status
            if "errors" in data:
                error_messages = []
                for error in data.get("errors", []):
                    message = error.get("message", "Unknown error")
                    locations = error.get("locations", [])
                    if locations:
                        location_info = ", ".join(
                            [
                                f"line {loc.get('line')}, column {loc.get('column')}"
                                for loc in locations
                            ]
                        )
                        message = f"{message} at {location_info}"

                    extensions = error.get("extensions", {})
                    if extensions:
                        code = extensions.get("code", "")
                        if code:
                            message = f"{message} (code: {code})"

                    error_messages.append(message)

                error_string = "; ".join(error_messages)
                self.logger.error(f"GraphQL error in Monday.com API: {error_string}")
                self.logger.error(f"Query that caused the error: {query}")
                if variables:
                    self.logger.error(f"Variables: {variables}")

            return data.get("data", {})

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error in Monday.com API: {e.response.status_code}")
            self.logger.error(f"Response text: {e.response.text}")
            self.logger.error(
                f"Request details: URL={self.GRAPHQL_ENDPOINT}, "
                f"Headers={headers} (sensitive info redacted)"
            )
            self.logger.error(f"Query that caused the error: {query}")
            if variables:
                self.logger.error(f"Variables: {variables}")
            raise

    async def _ensure_account_slug(self, client: httpx.AsyncClient) -> Optional[str]:
        """Fetch and cache the Monday account slug for building UI URLs."""
        if self._account_slug:
            return self._account_slug

        slug_query = """
        query {
          me {
            account {
              slug
            }
          }
        }
        """
        try:
            data = await self._graphql_query(client, slug_query)
            account = ((data.get("me") or {}).get("account")) or {}
            slug = account.get("slug")
            if slug:
                self._account_slug = slug
            else:
                self.logger.warning("Monday account slug not available; web URLs will be disabled.")
        except Exception as exc:  # pragma: no cover - network call
            self.logger.warning("Failed to fetch Monday account slug: %s", exc)
        return self._account_slug

    def _build_board_url(self, board_id: str) -> Optional[str]:
        if not self._account_slug:
            return None
        return f"https://{self._account_slug}.monday.com/boards/{board_id}"

    def _build_group_url(self, board_id: str, group_id: str) -> Optional[str]:
        board_url = self._build_board_url(board_id)
        if not board_url:
            return None
        return f"{board_url}?groupIds={group_id}"

    def _build_item_url(self, board_id: str, item_id: str) -> Optional[str]:
        board_url = self._build_board_url(board_id)
        if not board_url:
            return None
        return f"{board_url}/pulses/{item_id}"

    def _build_update_url(
        self, board_id: str, item_id: Optional[str], update_id: str
    ) -> Optional[str]:
        if item_id:
            item_url = self._build_item_url(board_id, item_id)
            if not item_url:
                return None
            return f"{item_url}?postId={update_id}"
        return self._build_board_url(board_id)

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    async def _generate_board_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[MondayBoardEntity, None]:
        """Generate MondayBoardEntity objects by querying boards."""
        query = """
        query {
          boards (limit: 100) {
            id
            name
            type
            state
            workspace_id
            updated_at
            owners {
              id
              name
            }
            groups {
              id
              title
            }
            columns {
              id
              title
              type
            }
          }
        }
        """
        result = await self._graphql_query(client, query)
        boards = result.get("boards", [])

        for board in boards:
            board_id = str(board["id"])
            board_name = board.get("name") or f"Board {board_id}"
            updated_time = self._parse_datetime(board.get("updated_at"))
            board_url = self._build_board_url(board_id)
            yield MondayBoardEntity(
                # Base fields
                entity_id=board_id,
                breadcrumbs=[],
                name=board_name,
                created_at=None,
                updated_at=updated_time,
                # API fields
                board_id=board_id,
                board_name=board_name,
                created_time=None,
                updated_time=updated_time,
                board_kind=board.get("type"),
                columns=board.get("columns", []),
                description=None,  # Not provided in this query
                groups=board.get("groups", []),
                owners=board.get("owners", []),
                state=board.get("state"),
                workspace_id=str(board.get("workspace_id")) if board.get("workspace_id") else None,
                web_url_value=board_url,
            )

    async def _generate_group_entities(
        self,
        client: httpx.AsyncClient,
        board_id: str,
        board_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[MondayGroupEntity, None]:
        """Generate MondayGroupEntity objects by querying groups for a specific board."""
        query = """
        query ($boardIds: [ID!]) {
          boards (ids: $boardIds) {
            groups {
              id
              title
              color
              archived
            }
          }
        }
        """
        variables = {"boardIds": [board_id]}
        result = await self._graphql_query(client, query, variables)
        boards_data = result.get("boards", [])
        if not boards_data:
            return

        groups = boards_data[0].get("groups", [])
        for group in groups:
            native_group_id = str(group["id"])
            group_title = group.get("title") or f"Group {native_group_id}"
            # Use a composite entity_id for uniqueness but keep the native Monday
            # group ID in the API-facing group_id field for downstream consumers.
            group_entity_id = f"{board_id}-{native_group_id}"
            group_url = self._build_group_url(board_id, native_group_id)
            yield MondayGroupEntity(
                # Base fields
                entity_id=group_entity_id,
                breadcrumbs=[board_breadcrumb],
                name=group_title,
                created_at=None,  # Groups don't have creation timestamp
                updated_at=None,  # Groups don't have update timestamp
                # API fields
                group_id=native_group_id,
                board_id=board_id,
                title=group_title,
                color=group.get("color"),
                archived=group.get("archived", False),
                items=[],
                web_url_value=group_url,
            )

    async def _generate_column_entities(
        self,
        client: httpx.AsyncClient,
        board_id: str,
        board_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[MondayColumnEntity, None]:
        """Generate MondayColumnEntity objects by querying columns for a specific board.

        (You could also retrieve columns from the board query, but here's a separate example.)
        """
        query = """
        query ($boardIds: [ID!]) {
          boards (ids: $boardIds) {
            columns {
              id
              title
              type
            }
          }
        }
        """
        variables = {"boardIds": [board_id]}
        result = await self._graphql_query(client, query, variables)
        boards_data = result.get("boards", [])
        if not boards_data:
            return

        columns = boards_data[0].get("columns", [])
        for col in columns:
            native_column_id = str(col["id"])
            column_entity_id = f"{board_id}-{native_column_id}"
            column_title = col.get("title") or f"Column {native_column_id}"
            column_url = self._build_board_url(board_id)
            yield MondayColumnEntity(
                # Base fields
                entity_id=column_entity_id,
                breadcrumbs=[board_breadcrumb],
                name=column_title,
                created_at=None,  # Columns don't have creation timestamp
                updated_at=None,  # Columns don't have update timestamp
                # API fields
                column_id=native_column_id,
                board_id=board_id,
                title=column_title,
                column_type=col.get("type"),
                description=None,  # Not provided in this query
                settings_str=None,  # Not provided in this query
                archived=False,  # Not provided in this query
                web_url_value=column_url,
            )

    async def _generate_item_entities(
        self,
        client: httpx.AsyncClient,
        board_id: str,
        board_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[MondayItemEntity, None]:
        """Generate MondayItemEntity objects for items on a given board.

        We'll retrieve items via a GraphQL query that includes item fields.
        """
        query = """
        query ($boardIds: [ID!]) {
          boards (ids: $boardIds) {
            items_page(limit: 500) {
              items {
                id
                name
                group {
                  id
                }
                state
                creator {
                  id
                  name
                }
                created_at
                updated_at
                column_values {
                  id
                  text
                  value
                }
              }
            }
          }
        }
        """
        variables = {"boardIds": [board_id]}
        result = await self._graphql_query(client, query, variables)
        boards_data = result.get("boards", [])
        if not boards_data:
            return

        # The structure is now different, we need to extract items from items_page
        items_page = boards_data[0].get("items_page", {})
        items = items_page.get("items", [])

        for item in items:
            item_id = str(item["id"])
            item_name = item.get("name") or f"Item {item_id}"
            created_time = self._parse_datetime(item.get("created_at")) or datetime.utcnow()
            updated_time = self._parse_datetime(item.get("updated_at")) or created_time
            item_url = self._build_item_url(board_id, item_id)
            yield MondayItemEntity(
                # Base fields
                entity_id=item_id,
                breadcrumbs=[board_breadcrumb],
                name=item_name,
                created_at=created_time,
                updated_at=updated_time,
                # API fields
                item_id=item_id,
                item_name=item_name,
                created_time=created_time,
                updated_time=updated_time,
                board_id=board_id,
                group_id=item["group"]["id"] if item["group"] else None,
                state=item.get("state"),
                column_values=item.get("column_values", []),
                creator=item.get("creator"),
                web_url_value=item_url,
            )

    async def _generate_subitem_entities(
        self,
        client: httpx.AsyncClient,
        parent_item_id: str,
        item_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[MondaySubitemEntity, None]:
        """Generate MondaySubitemEntity objects for subitems nested under a given item.

        Typically, subitems are retrieved separately since they're on a dedicated 'subitems' board.
        """
        query = """
        query ($itemIds: [ID!]) {
          items (ids: $itemIds) {
            subitems {
              id
              name
              board {
                id
              }
              group {
                id
              }
              state
              creator {
                id
                name
              }
              created_at
              updated_at
              column_values {
                id
                text
                value
              }
            }
          }
        }
        """
        variables = {"itemIds": [parent_item_id]}
        result = await self._graphql_query(client, query, variables)
        items_data = result.get("items", [])
        if not items_data or "subitems" not in items_data[0]:
            return

        subitems = items_data[0].get("subitems", [])
        for subitem in subitems:
            subitem_id = str(subitem["id"])
            subitem_name = subitem.get("name") or f"Subitem {subitem_id}"
            created_time = self._parse_datetime(subitem.get("created_at")) or datetime.utcnow()
            updated_time = self._parse_datetime(subitem.get("updated_at")) or created_time
            board_id = str(subitem["board"]["id"]) if subitem.get("board") else ""
            subitem_url = self._build_item_url(board_id, subitem_id) if board_id else None
            yield MondaySubitemEntity(
                # Base fields
                entity_id=subitem_id,
                breadcrumbs=item_breadcrumbs,
                name=subitem_name,
                created_at=created_time,
                updated_at=updated_time,
                # API fields
                subitem_id=subitem_id,
                subitem_name=subitem_name,
                created_time=created_time,
                updated_time=updated_time,
                parent_item_id=parent_item_id,
                board_id=board_id,
                group_id=subitem["group"]["id"] if subitem.get("group") else None,
                state=subitem.get("state"),
                column_values=subitem.get("column_values", []),
                creator=subitem.get("creator"),
                web_url_value=subitem_url,
            )

    async def _generate_update_entities(
        self,
        client: httpx.AsyncClient,
        board_id: str,
        item_id: Optional[str] = None,
        item_breadcrumbs: Optional[List[Breadcrumb]] = None,
    ) -> AsyncGenerator[MondayUpdateEntity, None]:
        """Generate MondayUpdateEntity objects for a given board or item.

        If item_id is provided, we fetch updates for a specific item; otherwise,
        board-level updates.
        """
        if item_id is not None:
            # Query updates nested under a single item
            query = """
            query ($itemIds: [ID!]) {
              items (ids: $itemIds) {
                updates {
                  id
                  body
                  created_at
                  creator {
                    id
                  }
                  assets {
                    id
                    public_url
                  }
                }
              }
            }
            """
            variables = {"itemIds": [item_id]}
            result = await self._graphql_query(client, query, variables)
            items_data = result.get("items", [])
            if not items_data:
                return
            updates = items_data[0].get("updates", [])
        else:
            # Query all updates in a board
            query = """
            query ($boardIds: [ID!]) {
              boards (ids: $boardIds) {
                updates {
                  id
                  body
                  created_at
                  creator {
                    id
                  }
                  assets {
                    id
                    public_url
                  }
                }
              }
            }
            """
            variables = {"boardIds": [board_id]}
            result = await self._graphql_query(client, query, variables)
            boards_data = result.get("boards", [])
            if not boards_data:
                return
            updates = boards_data[0].get("updates", [])

        for upd in updates:
            # Create update name from body preview
            body = upd.get("body", "")
            update_name = body[:50] + "..." if len(body) > 50 else body
            if not update_name:
                update_name = f"Update {upd['id']}"
            created_time = self._parse_datetime(upd.get("created_at")) or datetime.utcnow()
            update_url = self._build_update_url(board_id, item_id, str(upd["id"]))

            yield MondayUpdateEntity(
                # Base fields
                entity_id=str(upd["id"]),
                breadcrumbs=item_breadcrumbs or [],
                name=update_name,
                created_at=created_time,
                updated_at=None,  # Updates don't have update timestamp
                # API fields
                update_id=str(upd["id"]),
                update_preview=update_name,
                created_time=created_time,
                item_id=item_id,
                board_id=board_id if item_id is None else None,
                creator_id=str(upd["creator"]["id"]) if upd.get("creator") else None,
                body=body,
                assets=upd.get("assets", []),
                web_url_value=update_url,
            )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Monday.com entities in a style similar to other connectors.

        Yields Monday.com entities in the following order:
            - Boards
            - Groups per board
            - Columns per board
            - Items per board
            - Subitems per item
            - Updates per item or board
        """
        async with self.http_client() as client:
            # 1) Boards
            await self._ensure_account_slug(client)

            async for board_entity in self._generate_board_entities(client):
                yield board_entity

                board_breadcrumb = Breadcrumb(
                    entity_id=board_entity.board_id,
                    name=board_entity.board_name,
                    entity_type=MondayBoardEntity.__name__,
                )

                # 2) Groups
                async for group_entity in self._generate_group_entities(
                    client, board_entity.entity_id, board_breadcrumb
                ):
                    yield group_entity

                # 3) Columns
                async for column_entity in self._generate_column_entities(
                    client, board_entity.entity_id, board_breadcrumb
                ):
                    yield column_entity

                # 4) Items
                async for item_entity in self._generate_item_entities(
                    client, board_entity.entity_id, board_breadcrumb
                ):
                    yield item_entity

                    item_breadcrumb = Breadcrumb(
                        entity_id=item_entity.item_id,
                        name=item_entity.item_name,
                        entity_type=MondayItemEntity.__name__,
                    )
                    item_breadcrumbs = [board_breadcrumb, item_breadcrumb]

                    # 4a) Subitems for each item
                    async for subitem_entity in self._generate_subitem_entities(
                        client, item_entity.item_id, item_breadcrumbs
                    ):
                        yield subitem_entity

                    # 4b) Updates for each item
                    async for update_entity in self._generate_update_entities(
                        client,
                        board_entity.entity_id,
                        item_id=item_entity.item_id,
                        item_breadcrumbs=item_breadcrumbs,
                    ):
                        yield update_entity

                # 5) Board-level updates (if desired)
                # (Some users only store item-level updates; you can include or exclude this.)
                async for update_entity in self._generate_update_entities(
                    client,
                    board_entity.entity_id,
                    item_id=None,
                    item_breadcrumbs=[board_breadcrumb],
                ):
                    yield update_entity

    async def validate(self) -> bool:
        """Verify Monday OAuth2 token by POSTing a minimal GraphQL query to /v2."""
        try:
            token = await self.get_access_token()
            if not token:
                self.logger.error("Monday validation failed: no access token available.")
                return False

            query = {"query": "query { me { id } }"}

            async with self.http_client(timeout=10.0) as client:
                headers = {
                    "Authorization": token,  # Monday expects the raw token here (no added 'Bearer')
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
                resp = await client.post(self.GRAPHQL_ENDPOINT, json=query, headers=headers)

                # One-time retry on 401 using BaseSource refresh helper
                if resp.status_code == 401:
                    self.logger.info("Monday validate: 401 Unauthorized; attempting token refresh.")
                    new_token = await self.refresh_on_unauthorized()
                    if new_token:
                        headers["Authorization"] = new_token
                        resp = await client.post(self.GRAPHQL_ENDPOINT, json=query, headers=headers)

                if not (200 <= resp.status_code < 300):
                    self.logger.warning(
                        f"Monday validate failed: HTTP {resp.status_code} - {resp.text[:200]}"
                    )
                    return False

                body = resp.json()
                if body.get("errors"):
                    self.logger.warning(f"Monday validate GraphQL errors: {body['errors']}")
                    return False

                me = (body.get("data") or {}).get("me") or {}
                return bool(me.get("id"))

        except httpx.RequestError as e:
            self.logger.error(f"Monday validation request error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during Monday validation: {e}")
            return False
