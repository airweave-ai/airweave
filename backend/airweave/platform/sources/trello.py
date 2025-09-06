"""Trello source implementation for Airweave platform."""

from __future__ import annotations

import asyncio
import io
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs.auth import TrelloAuthConfig
from airweave.platform.configs.config import TrelloConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.trello import (
    TrelloAttachmentEntity,
    TrelloBoardEntity,
    TrelloCardEntity,
    TrelloCommentEntity,
    TrelloListEntity,
)
from airweave.platform.sources._base import BaseSource

API = "https://api.trello.com/1"


@source(
    name="Trello",
    short_name="trello",
    auth_type=AuthType.api_key,  # key+token
    auth_config_class="TrelloAuthConfig",
    config_class="TrelloConfig",
    labels=["Project Management", "Tasks"],
)
class TrelloSource(BaseSource):
    """Trello connector (full sync; supports comments & attachments; no incremental)."""

    @classmethod
    async def create(
        cls,
        credentials: TrelloAuthConfig,
        config: Optional[Dict[str, Any]] = None,
    ) -> "TrelloSource":
        """Create a TrelloSource instance with the given credentials and config.

        Args:
            credentials: Trello API credentials containing key and token
            config: Optional configuration dictionary for behavior settings

        Returns:
            Configured TrelloSource instance
        """
        inst = cls()
        inst.api_key = credentials.api_key
        inst.api_token = credentials.api_token

        cfg = TrelloConfig(**(config or {}))
        inst.cfg: TrelloConfig = cfg
        return inst

    # ----------------------------- HTTP helpers -----------------------------

    def _auth_params(self) -> Dict[str, str]:
        return {"key": self.api_key, "token": self.api_token}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.ReadTimeout, httpx.HTTPError)),
        reraise=True,
    )
    async def _get(
        self, client: httpx.AsyncClient, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        """GET with key/token and gentle handling for 429s."""
        qp = {}
        qp.update(self._auth_params())
        if params:
            qp.update(params)

        for _attempt in range(4):
            resp = await client.get(f"{API}{path}", params=qp, timeout=30.0)
            if resp.status_code == 429:
                # Respect Retry-After where available (rate limits documented by Trello)
                ra = resp.headers.get("Retry-After")
                delay = float(ra) if ra else 1.0
                self.logger.warning(f"Trello 429 on {path}. Sleeping {delay}s then retrying...")
                await asyncio.sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json()
        # One last raise if somehow we exhausted the loop without return
        resp.raise_for_status()  # type: ignore[misc]
        return {}

    # ----------------------------- Listing primitives -----------------------------

    async def _get_member_boards(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """Boards for the current token-holder."""
        fields = "name,desc,closed,url,dateLastActivity"
        filter_val = "all" if self.cfg.include_archived else "open"
        data = await self._get(
            client, "/members/me/boards", params={"fields": fields, "filter": filter_val}
        )
        return [board for board in data if isinstance(board, dict)]

    async def _get_board_lists(
        self, client: httpx.AsyncClient, board_id: str
    ) -> List[Dict[str, Any]]:
        fields = "name,closed,pos"
        filter_val = "all" if self.cfg.include_archived else "open"
        lists = await self._get(
            client, f"/boards/{board_id}/lists", params={"fields": fields, "filter": filter_val}
        )
        return [list_item for list_item in lists if isinstance(list_item, dict)]

    async def _get_board_cards(
        self, client: httpx.AsyncClient, board_id: str
    ) -> List[Dict[str, Any]]:
        # requested fields: keep light but useful for search
        fields = ",".join(
            [
                "id",
                "name",
                "desc",
                "idList",
                "idBoard",
                "labels",
                "idMembers",
                "url",
                "shortUrl",
                "due",
                "start",
                "dueComplete",
                "closed",
                "dateLastActivity",
            ]
        )
        filter_val = "all" if self.cfg.include_archived else "visible"
        cards = await self._get(
            client, f"/boards/{board_id}/cards", params={"fields": fields, "filter": filter_val}
        )
        return [card for card in cards if isinstance(card, dict)]

    async def _get_card_attachments(
        self, client: httpx.AsyncClient, card_id: str
    ) -> List[Dict[str, Any]]:
        # requesting key attachment fields, including fileName
        fields = "id,bytes,date,idMember,isUpload,mimeType,name,url,fileName"
        atts = await self._get(client, f"/cards/{card_id}/attachments", params={"fields": fields})
        return [attachment for attachment in atts if isinstance(attachment, dict)]

    async def _get_card_checklists(
        self, client: httpx.AsyncClient, card_id: str
    ) -> List[Dict[str, Any]]:
        # include checkItems (text + state)
        checklists = await self._get(
            client, f"/cards/{card_id}/checklists", params={"checkItems": "all"}
        )
        return [checklist for checklist in checklists if isinstance(checklist, dict)]

    async def _get_card_comments(
        self, client: httpx.AsyncClient, card_id: str
    ) -> List[Dict[str, Any]]:
        # commentCard actions (text in data.text)
        acts = await self._get(
            client, f"/cards/{card_id}/actions", params={"filter": "commentCard"}
        )
        return [action for action in acts if isinstance(action, dict)]

    # ----------------------------- Building entities -----------------------------

    def _board_entity(self, board_data: Dict[str, Any]) -> TrelloBoardEntity:
        content = f"{board_data.get('name', '')}\n\n{board_data.get('desc', '') or ''}".strip()
        return TrelloBoardEntity(
            entity_id=board_data["id"],
            board_id=board_data["id"],
            name=board_data.get("name", ""),
            desc=board_data.get("desc"),
            url=board_data.get("url"),
            closed=bool(board_data.get("closed", False)),
            date_last_activity=board_data.get("dateLastActivity"),
            content=content or None,
            breadcrumbs=[],
        )

    def _list_entity(self, list_data: Dict[str, Any], board_id: str) -> TrelloListEntity:
        return TrelloListEntity(
            entity_id=list_data["id"],
            list_id=list_data["id"],
            board_id=board_id,
            name=list_data.get("name", ""),
            closed=bool(list_data.get("closed", False)),
            pos=list_data.get("pos"),
            content=list_data.get("name", ""),
            breadcrumbs=[Breadcrumb(entity_id=board_id, name="", type="board")],
        )

    def _card_breadcrumbs(self, board_name: str, list_name: str) -> List[Breadcrumb]:
        breadcrumbs: List[Breadcrumb] = []
        if board_name:
            breadcrumbs.append(Breadcrumb(entity_id="", name=board_name, type="board"))
        if list_name:
            breadcrumbs.append(Breadcrumb(entity_id="", name=list_name, type="list"))
        return breadcrumbs

    def _card_entity(
        self, card_data: Dict[str, Any], board_name: str, list_name: str
    ) -> TrelloCardEntity:
        desc = card_data.get("desc") or ""
        labels = card_data.get("labels") or []
        label_names = ", ".join(
            [lb.get("name") or lb.get("color", "") for lb in labels if isinstance(lb, dict)]
        )
        content = f"{card_data.get('name', '')}\n\n{desc}\n\nlabels: {label_names}".strip()
        return TrelloCardEntity(
            entity_id=card_data["id"],
            card_id=card_data["id"],
            board_id=card_data.get("idBoard", ""),
            list_id=card_data.get("idList", ""),
            name=card_data.get("name", ""),
            desc=desc or None,
            url=card_data.get("url"),
            labels=labels,
            id_members=card_data.get("idMembers", []) or [],
            closed=bool(card_data.get("closed", False)),
            due=card_data.get("due"),
            start=card_data.get("start"),
            due_complete=bool(card_data.get("dueComplete", False)),
            date_last_activity=card_data.get("dateLastActivity"),
            content=content or None,
            breadcrumbs=self._card_breadcrumbs(board_name, list_name),
        )

    def _comment_entity(
        self,
        action_data: Dict[str, Any],
        card_id: str,
        board_id: str,
        list_id: Optional[str],
        board_name: str,
        list_name: str,
    ) -> Optional[TrelloCommentEntity]:
        data = action_data.get("data") or {}
        text = data.get("text")
        if not text:
            return None
        return TrelloCommentEntity(
            entity_id=action_data["id"],
            action_id=action_data["id"],
            card_id=card_id,
            board_id=board_id,
            list_id=list_id,
            member_creator_id=(action_data.get("idMemberCreator")),
            text=text,
            date=action_data.get("date"),
            content=text,
            breadcrumbs=self._card_breadcrumbs(board_name, list_name),
        )

    def _attachment_entity(
        self, att: Dict[str, Any], card: Dict[str, Any], list_name: str, board_name: str
    ) -> Optional[TrelloAttachmentEntity]:
        # Skip non-upload links if you only want real files; keep both by default.
        file_name = att.get("fileName") or att.get("name") or "attachment"
        download_url = f"{API}/cards/{card['id']}/attachments/{att['id']}/download/{file_name}"
        size = att.get("bytes")
        if (
            self.cfg.attachment_max_bytes
            and isinstance(size, int)
            and size > self.cfg.attachment_max_bytes
        ):
            self.logger.info(f"Skipping large attachment {file_name} ({size} bytes)")
            return None

        return TrelloAttachmentEntity(
            entity_id=att["id"],
            file_id=att["id"],
            name=file_name,
            mime_type=att.get("mimeType"),
            size=size if isinstance(size, int) else None,
            download_url=download_url,  # requires Authorization header, see downloader
            card_id=card["id"],
            board_id=card.get("idBoard", ""),
            list_id=card.get("idList"),
            url=att.get("url"),  # UI/attachment URL (not necessarily the binary)
            breadcrumbs=self._card_breadcrumbs(board_name, list_name),
        )

    # ----------------------------- Attachment download -----------------------------

    async def _download_attachment_bytes(
        self, client: httpx.AsyncClient, card_id: str, att_id: str, file_name: str
    ) -> bytes:
        """Download attachment bytes with OAuth authorization header.

        Trello requires Authorization header (OAuth 1.0 style) when hitting the /download route.
        Format documented by Atlassian:
        Authorization: OAuth oauth_consumer_key="<key>", oauth_token="<token>"
        See: https://api.trello.com/…/attachments/{id}/download/{name} + header.
        """
        url = f"{API}/cards/{card_id}/attachments/{att_id}/download/{file_name}"
        headers = {
            "Authorization": (
                f'OAuth oauth_consumer_key="{self.api_key}", oauth_token="{self.api_token}"'
            )
        }
        response = await client.get(url, headers=headers, timeout=60.0)
        response.raise_for_status()
        return response.content

    # ----------------------------- Main sync helpers -----------------------------

    async def _fetch_boards(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """Fetch boards based on configuration."""
        board_objs: List[Dict[str, Any]] = []
        try:
            if self.cfg.board_ids:
                # fetch specific boards
                for bid in self.cfg.board_ids:
                    board_data = await self._get(
                        client,
                        f"/boards/{bid}",
                        params={"fields": "name,desc,closed,url,dateLastActivity"},
                    )
                    if isinstance(board_data, dict):
                        board_objs.append(board_data)
            else:
                board_objs = await self._get_member_boards(client)
        except Exception as e:
            self.logger.error(f"Trello: failed to list boards: {e}")
        return board_objs

    async def _process_board_entities(
        self, board_objs: List[Dict[str, Any]]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Yield board entities."""
        for board_data in board_objs:
            try:
                yield self._board_entity(board_data)
            except Exception as e:
                self.logger.error(f"Trello: board entity error: {e}")

    async def _process_card_comments(
        self,
        client: httpx.AsyncClient,
        card_data: Dict[str, Any],
        board_id: str,
        board_name: str,
        list_name: str,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process and yield card comments."""
        if not self.cfg.include_comments:
            return

        try:
            actions = await self._get_card_comments(client, card_data["id"])
            for action_data in actions:
                comment_entity = self._comment_entity(
                    action_data,
                    card_data["id"],
                    board_id,
                    card_data.get("idList"),
                    board_name,
                    list_name,
                )
                if comment_entity:
                    yield comment_entity
        except Exception as e:
            self.logger.error(f"Trello: comments failed for card {card_data['id']}: {e}")

    async def _process_card_checklists(
        self,
        client: httpx.AsyncClient,
        card_data: Dict[str, Any],
        board_id: str,
        board_name: str,
        list_name: str,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process and yield card checklists as comment entities."""
        if not self.cfg.include_checklists:
            return

        try:
            checklists = await self._get_card_checklists(client, card_data["id"])
            for checklist in checklists:
                items = checklist.get("checkItems") or []
                lines = [
                    f"- [{'x' if it.get('state') == 'complete' else ' '}] {it.get('name', '')}"
                    for it in items
                ]
                text = f"Checklist: {checklist.get('name', '')}\n" + "\n".join(lines)
                yield TrelloCommentEntity(
                    entity_id=f"{card_data['id']}:checklist:{checklist['id']}",
                    action_id=f"{card_data['id']}:checklist:{checklist['id']}",
                    card_id=card_data["id"],
                    board_id=board_id,
                    list_id=card_data.get("idList"),
                    member_creator_id=None,
                    text=text,
                    date=checklist.get("dateLastActivity") or card_data.get("dateLastActivity"),
                    content=text,
                    breadcrumbs=self._card_breadcrumbs(board_name, list_name),
                )
        except Exception as e:
            self.logger.error(f"Trello: checklists failed for card {card_data['id']}: {e}")

    async def _process_card_attachments(
        self,
        client: httpx.AsyncClient,
        card_data: Dict[str, Any],
        board_name: str,
        list_name: str,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process and yield card attachments."""
        if not self.cfg.include_attachments:
            return

        try:
            attachments = await self._get_card_attachments(client, card_data["id"])
            for attachment in attachments:
                attachment_entity = self._attachment_entity(
                    attachment, card_data, list_name=list_name, board_name=board_name
                )
                if not attachment_entity:
                    continue
                try:
                    data = await self._download_attachment_bytes(
                        client,
                        card_data["id"],
                        attachment["id"],
                        attachment_entity.name or "attachment",
                    )
                    # Use the direct-content pipeline (no OAuth bearer needed)
                    stream = io.BytesIO(data)
                    processed = await self.process_file_entity_with_content(
                        file_entity=attachment_entity, content_stream=stream
                    )
                    if processed:
                        yield processed
                except httpx.HTTPStatusError as e:
                    self.logger.error(
                        f"Trello: download failed for attachment {attachment.get('id')}: {e}"
                    )
                except Exception as e:
                    self.logger.error(f"Trello: attachment processing error: {e}")
        except Exception as e:
            self.logger.error(f"Trello: list attachments failed for card {card_data['id']}: {e}")

    async def _process_board_lists_and_cards(
        self, client: httpx.AsyncClient, board_data: Dict[str, Any]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process lists and cards for a single board."""
        board_id = board_data["id"]
        board_name = board_data.get("name", "")

        try:
            lists = await self._get_board_lists(client, board_id)
        except Exception as e:
            self.logger.error(f"Trello: failed to list lists for board {board_id}: {e}")
            lists = []

        list_index = {
            list_item["id"]: list_item for list_item in lists if isinstance(list_item, dict)
        }

        # yield list entities
        for list_item in lists:
            try:
                yield self._list_entity(list_item, board_id=board_id)
            except Exception as e:
                self.logger.error(f"Trello: list entity error: {e}")

        # Process cards
        try:
            cards = await self._get_board_cards(client, board_id)
        except Exception as e:
            self.logger.error(f"Trello: failed to list cards for board {board_id}: {e}")
            cards = []

        for card_data in cards:
            list_name = (list_index.get(card_data.get("idList") or "", {}) or {}).get("name", "")
            async for entity in self._process_single_card(
                client, card_data, board_id, board_name, list_name
            ):
                yield entity

    async def _process_single_card(
        self,
        client: httpx.AsyncClient,
        card_data: Dict[str, Any],
        board_id: str,
        board_name: str,
        list_name: str,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a single card and all its related entities."""
        try:
            # Card chunk
            yield self._card_entity(card_data, board_name=board_name, list_name=list_name)

            # Process comments
            async for comment_entity in self._process_card_comments(
                client, card_data, board_id, board_name, list_name
            ):
                yield comment_entity

            # Process checklists
            async for checklist_entity in self._process_card_checklists(
                client, card_data, board_id, board_name, list_name
            ):
                yield checklist_entity

            # Process attachments
            async for attachment_entity in self._process_card_attachments(
                client, card_data, board_name, list_name
            ):
                yield attachment_entity

        except Exception as e:
            self.logger.error(f"Trello: card entity error: {e}")

    # ----------------------------- Main sync -----------------------------

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Full sync.

        Processes:
        - Boards (visible or selected)
        - Lists per board
        - Cards per board
        - Optional: comments (as chunks)
        - Optional: attachments (download into FileEntity and process with file_manager)
        """
        async with httpx.AsyncClient() as client:
            # Fetch and yield boards
            board_objs = await self._fetch_boards(client)
            async for board_entity in self._process_board_entities(board_objs):
                yield board_entity

            # Process lists and cards for each board
            for board_data in board_objs:
                async for entity in self._process_board_lists_and_cards(client, board_data):
                    yield entity
