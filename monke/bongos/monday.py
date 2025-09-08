import asyncio, time, uuid, json
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.generation.monday import generate_monday_item
from monke.utils.logging import get_logger

MNDY = "https://api.monday.com/v2"


class MondayBongo(BaseBongo):
    connector_type = "monday"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 500)) / 1000.0
        self.logger = get_logger("monday_bongo")
        self._items: List[Dict[str, Any]] = []
        self._board_id: Optional[str] = None
        self._text_column_id: Optional[str] = None
        self._last_req = 0.0

    async def create_entities(self) -> List[Dict[str, Any]]:
        self.logger.info(f"🥁 Creating monday.com board + {self.entity_count} items")
        async with httpx.AsyncClient(timeout=30) as client:
            # 1) Create a temporary board
            self._board_id = await self._create_board(
                client, name=f"monke-monday-test-{uuid.uuid4().hex[:6]}"
            )

            # 2) Create a text column to stash token/note
            self._text_column_id = await self._create_text_column(
                client, self._board_id, title="Note"
            )

            # 3) Create items
            out: List[Dict[str, Any]] = []
            for _ in range(self.entity_count):
                await self._pace()
                token = uuid.uuid4().hex[:8]
                item = await generate_monday_item(self.openai_model, token)
                created = await self._gql(
                    client,
                    """
                    mutation($board: ID!, $name: String!, $col: String!, $val: JSON!) {
                      create_item(board_id: $board, item_name: $name, column_values: $val) { id name }
                    }""",
                    {
                        "board": int(self._board_id),
                        "name": item.name,
                        "col": self._text_column_id,
                        "val": json.dumps({self._text_column_id: item.note or token}),
                    },
                )
                iid = ((created.get("data") or {}).get("create_item") or {}).get("id")
                ent = {
                    "type": "item",
                    "id": iid,
                    "name": item.name,
                    "token": token,
                    "expected_content": token,
                    "path": f"monday/board/{self._board_id}/item/{iid}",
                }
                out.append(ent)
                self._items.append(ent)
                self.created_entities.append({"id": iid, "name": item.name})
            return out

    async def update_entities(self) -> List[Dict[str, Any]]:
        if not self._items or not self._board_id or not self._text_column_id:
            return []
        self.logger.info("🥁 Updating monday.com items (append '[updated]')")
        async with httpx.AsyncClient(timeout=30) as client:
            updated = []
            for ent in self._items[: min(3, len(self._items))]:
                await self._pace()
                _ = await self._gql(
                    client,
                    """
                    mutation($board: ID!, $item: ID!, $col: String!, $value: String!) {
                      change_simple_column_value(board_id: $board, item_id: $item, column_id: $col, value: $value) { id }
                    }""",
                    {
                        "board": int(self._board_id),
                        "item": int(ent["id"]),
                        "col": self._text_column_id,
                        "value": f"{ent['token']} updated",
                    },
                )
                updated.append({**ent, "updated": True})
            return updated

    async def delete_entities(self) -> List[str]:
        return await self.delete_specific_entities(self._items)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        if not entities:
            return []
        self.logger.info(f"🥁 Deleting {len(entities)} monday items")
        deleted: List[str] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for ent in entities:
                try:
                    await self._pace()
                    r = await self._gql(
                        client,
                        "mutation($id: ID!){ delete_item(item_id:$id){ id }}",
                        {"id": int(ent["id"])},
                    )
                    deleted.append(ent["id"])
                except Exception as e:
                    self.logger.warning(f"Delete failed for {ent['id']}: {e}")

        # delete board last
        await self._delete_board()
        return deleted

    async def cleanup(self):
        try:
            await self._delete_board()
        except Exception:
            pass

    async def _create_board(self, client, name: str) -> str:
        await self._pace()
        r = await self._gql(
            client,
            "mutation($name: String!){ create_board(board_name:$name, board_kind: private){ id }}",
            {"name": name},
        )
        return ((r.get("data") or {}).get("create_board") or {}).get("id")

    async def _create_text_column(self, client, board_id: str, title: str) -> str:
        await self._pace()
        r = await self._gql(
            client,
            "mutation($board:ID!,$title:String!){ create_column(board_id:$board, title:$title, column_type:text){ id title }}",
            {"board": int(board_id), "title": title},
        )
        return ((r.get("data") or {}).get("create_column") or {}).get("id")

    async def _delete_board(self):
        if not self._board_id:
            return
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                await self._pace()
                _ = await self._gql(
                    client,
                    "mutation($id:ID!){ delete_board(board_id:$id){ id }}",
                    {"id": int(self._board_id)},
                )
                self._board_id = None
            except Exception as e:
                self.logger.warning(f"Board delete failed: {e}")

    async def _gql(
        self, client: httpx.AsyncClient, query: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        r = await client.post(
            MNDY,
            headers={"Authorization": self.access_token, "Content-Type": "application/json"},
            json={"query": query, "variables": variables},
        )
        if r.status_code != 200:
            raise RuntimeError(f"monday GraphQL error {r.status_code}: {r.text}")
        return r.json()

    async def _pace(self):
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()
