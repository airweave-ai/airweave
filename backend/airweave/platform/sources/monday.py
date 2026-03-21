"""Monday source implementation.

Retrieves data from Monday.com's GraphQL API and yields entity objects for Boards,
Groups, Columns, Items, Subitems, and Updates. Uses a stepwise pattern to issue
GraphQL queries for retrieving these objects.
"""

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
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
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

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: MondayConfig,
    ) -> MondaySource:
        """Create a new Monday source."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance._account_slug: Optional[str] = None
        return instance

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _graphql_query(
        self, query: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a single GraphQL query against the Monday.com API.

        Monday.com expects the raw token (no 'Bearer' prefix) in the
        Authorization header.
        """
        token = await self.auth.get_token()
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        response = await self.http_client.post(self.GRAPHQL_ENDPOINT, json=payload, headers=headers)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning("Received 401 from Monday — attempting token refresh")
            new_token = await self.auth.force_refresh()
            headers["Authorization"] = new_token
            response = await self.http_client.post(
                self.GRAPHQL_ENDPOINT, json=payload, headers=headers
            )

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )

        data = response.json()

        if "errors" in data:
            error_messages = []
            for error in data.get("errors", []):
                message = error.get("message", "Unknown error")
                locations = error.get("locations", [])
                if locations:
                    location_info = ", ".join(
                        [f"line {loc.get('line')}, column {loc.get('column')}" for loc in locations]
                    )
                    message = f"{message} at {location_info}"
                extensions = error.get("extensions", {})
                if extensions:
                    code = extensions.get("code", "")
                    if code:
                        message = f"{message} (code: {code})"
                error_messages.append(message)

            error_string = "; ".join(error_messages)
            self.logger.warning(f"GraphQL error in Monday.com API: {error_string}")

        return data.get("data", {})

    # ------------------------------------------------------------------
    # URL builders
    # ------------------------------------------------------------------

    async def _ensure_account_slug(self) -> Optional[str]:
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
            data = await self._graphql_query(slug_query)
            account = ((data.get("me") or {}).get("account")) or {}
            slug = account.get("slug")
            if slug:
                self._account_slug = slug
            else:
                self.logger.warning("Monday account slug not available; web URLs will be disabled.")
        except SourceAuthError:
            raise
        except Exception as exc:
            self.logger.warning(f"Failed to fetch Monday account slug: {exc}")
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

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _generate_board_entities(self) -> AsyncGenerator[MondayBoardEntity, None]:
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
        result = await self._graphql_query(query)
        boards = result.get("boards", [])

        for board in boards:
            board_id = str(board["id"])
            board_url = self._build_board_url(board_id)
            yield MondayBoardEntity.from_api(board, breadcrumbs=[], web_url=board_url)

    async def _generate_group_entities(
        self,
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
        result = await self._graphql_query(query, variables)
        boards_data = result.get("boards", [])
        if not boards_data:
            return

        groups = boards_data[0].get("groups", [])
        for group in groups:
            native_group_id = str(group["id"])
            group_title = group.get("title") or f"Group {native_group_id}"
            group_entity_id = f"{board_id}-{native_group_id}"
            group_url = self._build_group_url(board_id, native_group_id)
            yield MondayGroupEntity(
                entity_id=group_entity_id,
                breadcrumbs=[board_breadcrumb],
                name=group_title,
                created_at=None,
                updated_at=None,
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
        board_id: str,
        board_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[MondayColumnEntity, None]:
        """Generate MondayColumnEntity objects by querying columns for a specific board."""
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
        result = await self._graphql_query(query, variables)
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
                entity_id=column_entity_id,
                breadcrumbs=[board_breadcrumb],
                name=column_title,
                created_at=None,
                updated_at=None,
                column_id=native_column_id,
                board_id=board_id,
                title=column_title,
                column_type=col.get("type"),
                description=None,
                settings_str=None,
                archived=False,
                web_url_value=column_url,
            )

    async def _generate_item_entities(
        self,
        board_id: str,
        board_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[MondayItemEntity, None]:
        """Generate MondayItemEntity objects for items on a given board."""
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
        result = await self._graphql_query(query, variables)
        boards_data = result.get("boards", [])
        if not boards_data:
            return

        items_page = boards_data[0].get("items_page", {})
        items = items_page.get("items", [])

        for item in items:
            item_id = str(item["id"])
            item_url = self._build_item_url(board_id, item_id)
            yield MondayItemEntity.from_api(
                item,
                breadcrumbs=[board_breadcrumb],
                board_id=board_id,
                web_url=item_url,
            )

    async def _generate_subitem_entities(
        self,
        parent_item_id: str,
        item_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[MondaySubitemEntity, None]:
        """Generate MondaySubitemEntity objects for subitems nested under a given item."""
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
        result = await self._graphql_query(query, variables)
        items_data = result.get("items", [])
        if not items_data or "subitems" not in items_data[0]:
            return

        subitems = items_data[0].get("subitems", [])
        for subitem in subitems:
            board_id = str(subitem["board"]["id"]) if subitem.get("board") else ""
            subitem_url = self._build_item_url(board_id, str(subitem["id"])) if board_id else None
            yield MondaySubitemEntity.from_api(
                subitem,
                breadcrumbs=item_breadcrumbs,
                parent_item_id=parent_item_id,
                web_url=subitem_url,
            )

    async def _generate_update_entities(
        self,
        board_id: str,
        item_id: Optional[str] = None,
        item_breadcrumbs: Optional[List[Breadcrumb]] = None,
    ) -> AsyncGenerator[MondayUpdateEntity, None]:
        """Generate MondayUpdateEntity objects for a given board or item."""
        if item_id is not None:
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
            result = await self._graphql_query(query, variables)
            items_data = result.get("items", [])
            if not items_data:
                return
            updates = items_data[0].get("updates", [])
        else:
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
            result = await self._graphql_query(query, variables)
            boards_data = result.get("boards", [])
            if not boards_data:
                return
            updates = boards_data[0].get("updates", [])

        for upd in updates:
            update_url = self._build_update_url(board_id, item_id, str(upd["id"]))
            yield MondayUpdateEntity.from_api(
                upd,
                breadcrumbs=item_breadcrumbs or [],
                board_id=board_id,
                item_id=item_id,
                web_url=update_url,
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Monday.com entities.

        Yields Monday.com entities in the following order:
            - Boards
            - Groups per board
            - Columns per board
            - Items per board
            - Subitems per item
            - Updates per item or board
        """
        await self._ensure_account_slug()

        async for board_entity in self._generate_board_entities():
            yield board_entity

            board_breadcrumb = Breadcrumb(
                entity_id=board_entity.board_id,
                name=board_entity.board_name,
                entity_type=MondayBoardEntity.__name__,
            )

            async for group_entity in self._generate_group_entities(
                board_entity.entity_id, board_breadcrumb
            ):
                yield group_entity

            async for column_entity in self._generate_column_entities(
                board_entity.entity_id, board_breadcrumb
            ):
                yield column_entity

            async for item_entity in self._generate_item_entities(
                board_entity.entity_id, board_breadcrumb
            ):
                yield item_entity

                item_breadcrumb = Breadcrumb(
                    entity_id=item_entity.item_id,
                    name=item_entity.item_name,
                    entity_type=MondayItemEntity.__name__,
                )
                item_breadcrumbs = [board_breadcrumb, item_breadcrumb]

                async for subitem_entity in self._generate_subitem_entities(
                    item_entity.item_id, item_breadcrumbs
                ):
                    yield subitem_entity

                async for update_entity in self._generate_update_entities(
                    board_entity.entity_id,
                    item_id=item_entity.item_id,
                    item_breadcrumbs=item_breadcrumbs,
                ):
                    yield update_entity

            async for update_entity in self._generate_update_entities(
                board_entity.entity_id,
                item_id=None,
                item_breadcrumbs=[board_breadcrumb],
            ):
                yield update_entity

    async def validate(self) -> None:
        """Verify Monday OAuth2 token by POSTing a minimal GraphQL query to /v2."""
        await self._graphql_query("query { me { id } }")
