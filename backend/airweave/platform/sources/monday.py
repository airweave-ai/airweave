"""Monday source implementation.

Retrieves data from Monday.com's GraphQL API and yields entity objects for Boards,
Groups, Columns, Items, Subitems, and Updates. Uses a stepwise pattern to issue
GraphQL queries for retrieving these objects.
"""

from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from airweave.platform.configs.auth import MondayAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, BaseEntity
from airweave.platform.entities.monday import (
    MondayBoardEntity,
    MondayColumnEntity,
    MondayGroupEntity,
    MondayItemEntity,
    MondaySubitemEntity,
    MondayUpdateEntity,
)
from airweave.platform.sources._base import BaseSource
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
    config_class="MondayConfig",
    labels=["Project Management"],
    supports_continuous=False,
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
            yield MondayBoardEntity(
                entity_id=str(board["id"]),
                board_id=str(board["id"]),
                name=board.get("name"),
                board_kind=board.get("type"),
                state=board.get("state"),
                workspace_id=str(board.get("workspace_id")) if board.get("workspace_id") else None,
                owners=board.get("owners", []),
                created_at=None,  # Board API doesn't provide created_at field
                updated_at=board.get("updated_at"),
                groups=board.get("groups", []),
                columns=board.get("columns", []),
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
            yield MondayGroupEntity(
                entity_id=f"{board_id}-{group['id']}",  # or just group["id"]
                breadcrumbs=[board_breadcrumb],
                group_id=group["id"],
                board_id=board_id,
                title=group.get("title"),
                color=group.get("color"),
                archived=group.get("archived", False),
                items=[],  # You could populate items in a separate step if desired
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
            yield MondayColumnEntity(
                entity_id=f"{board_id}-{col['id']}",
                breadcrumbs=[board_breadcrumb],
                column_id=col["id"],
                board_id=board_id,
                title=col.get("title"),
                column_type=col.get("type"),
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
            yield MondayItemEntity(
                entity_id=str(item["id"]),
                breadcrumbs=[board_breadcrumb],
                item_id=str(item["id"]),
                board_id=board_id,
                group_id=item["group"]["id"] if item["group"] else None,
                name=item.get("name"),
                state=item.get("state"),
                creator=item.get("creator"),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                column_values=item.get("column_values", []),
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
            yield MondaySubitemEntity(
                entity_id=str(subitem["id"]),
                breadcrumbs=item_breadcrumbs,
                subitem_id=str(subitem["id"]),
                parent_item_id=parent_item_id,
                board_id=str(subitem["board"]["id"]) if subitem.get("board") else "",
                group_id=subitem["group"]["id"] if subitem.get("group") else None,
                name=subitem.get("name"),
                state=subitem.get("state"),
                creator=subitem.get("creator"),
                created_at=subitem.get("created_at"),
                updated_at=subitem.get("updated_at"),
                column_values=subitem.get("column_values", []),
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
            yield MondayUpdateEntity(
                entity_id=str(upd["id"]),
                breadcrumbs=item_breadcrumbs or [],
                update_id=str(upd["id"]),
                item_id=item_id,
                board_id=board_id if item_id is None else None,
                creator_id=str(upd["creator"]["id"]) if upd.get("creator") else None,
                body=upd.get("body"),
                created_at=upd.get("created_at"),
                assets=upd.get("assets", []),
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
            async for board_entity in self._generate_board_entities(client):
                yield board_entity

                board_breadcrumb = Breadcrumb(
                    entity_id=board_entity.board_id,
                    name=board_entity.name or "",
                    type="board",
                )

                # 2) Groups
                async for group_entity in self._generate_group_entities(
                    client, board_entity.board_id, board_breadcrumb
                ):
                    yield group_entity

                # 3) Columns
                async for column_entity in self._generate_column_entities(
                    client, board_entity.board_id, board_breadcrumb
                ):
                    yield column_entity

                # 4) Items
                async for item_entity in self._generate_item_entities(
                    client, board_entity.board_id, board_breadcrumb
                ):
                    yield item_entity

                    item_breadcrumbs = [
                        board_breadcrumb,
                        Breadcrumb(
                            entity_id=item_entity.item_id,
                            name=item_entity.name or "",
                            type="item",
                        ),
                    ]

                    # 4a) Subitems for each item
                    async for subitem_entity in self._generate_subitem_entities(
                        client, item_entity.item_id, item_breadcrumbs
                    ):
                        yield subitem_entity

                    # 4b) Updates for each item
                    async for update_entity in self._generate_update_entities(
                        client,
                        board_entity.board_id,
                        item_id=item_entity.item_id,
                        item_breadcrumbs=item_breadcrumbs,
                    ):
                        yield update_entity

                # 5) Board-level updates (if desired)
                # (Some users only store item-level updates; you can include or exclude this.)
                async for update_entity in self._generate_update_entities(
                    client, board_entity.board_id, item_id=None, item_breadcrumbs=[board_breadcrumb]
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
