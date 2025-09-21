"""Trello entity definitions for boards, lists, cards, comments, and attachments."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity

# -------- Boards / Lists / Cards as searchable chunks --------


class TrelloBoardEntity(ChunkEntity):
    """Trello Board (metadata + brief content)."""

    board_id: str = Field(..., description="Board ID")
    name: str = Field(..., description="Board name")
    desc: Optional[str] = Field(None, description="Board description")
    url: Optional[str] = Field(None, description="Board URL")
    closed: bool = Field(False, description="Whether the board is archived/closed")
    date_last_activity: Optional[datetime] = Field(None, description="Last activity (board)")

    # Use for embedding/search text
    content: Optional[str] = Field(None, description="Canonical text (name + desc)")


class TrelloListEntity(ChunkEntity):
    """Trello List (metadata)."""

    list_id: str = Field(..., description="List ID")
    board_id: str = Field(..., description="Parent board ID")
    name: str = Field(..., description="List name")
    closed: bool = Field(False, description="Archived list?")
    pos: Optional[float] = Field(None, description="Position")

    content: Optional[str] = Field(None, description="Canonical text (name)")


class TrelloCardEntity(ChunkEntity):
    """Trello Card (the main searchable text)."""

    card_id: str = Field(..., description="Card ID")
    board_id: str = Field(..., description="Parent board ID")
    list_id: str = Field(..., description="Parent list ID")

    name: str = Field(..., description="Card title")
    desc: Optional[str] = Field(None, description="Card description")
    url: Optional[str] = Field(None, description="Card URL")

    labels: List[Dict[str, Any]] = Field(default_factory=list, description="Labels on card")
    id_members: List[str] = Field(default_factory=list, description="Member IDs")

    closed: bool = Field(False, description="Archived card?")
    due: Optional[datetime] = Field(None, description="Due date")
    start: Optional[datetime] = Field(None, description="Start date")
    due_complete: bool = Field(False, description="Due completed?")
    date_last_activity: Optional[datetime] = Field(None, description="Last card activity")

    # canonical text for search
    content: Optional[str] = Field(None, description="Use desc + labels + metadata for embedding")


class TrelloCommentEntity(ChunkEntity):
    """Card comment (commentCard action)."""

    action_id: str = Field(..., description="Action ID")
    card_id: str = Field(..., description="Card ID")
    board_id: str = Field(..., description="Board ID")
    list_id: Optional[str] = Field(None, description="List ID at comment time, if known")
    member_creator_id: Optional[str] = Field(None, description="Comment author")

    text: str = Field(..., description="Comment text")
    date: datetime = Field(..., description="Comment date")

    content: Optional[str] = Field(None, description="Canonical text for search")


# -------- Attachments as FileEntity (downloaded & chunked by file_manager) --------


class TrelloAttachmentEntity(FileEntity):
    """Attachment on a card (downloaded via Trello /download route)."""

    file_id: str = Field(..., description="Attachment ID (also entity_id)")
    name: str = Field(..., description="Attachment filename")
    mime_type: Optional[str] = Field(None, description="MIME type if known")
    size: Optional[int] = Field(None, description="Size in bytes")
    download_url: str = Field(
        ..., description="Direct download route (api.trello.com ... /download/...)"
    )

    card_id: str = Field(..., description="Parent card")
    board_id: str = Field(..., description="Parent board")
    list_id: Optional[str] = Field(None, description="Parent list (if known)")
    url: Optional[str] = Field(None, description="Trello UI URL for the attachment")
