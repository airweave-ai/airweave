"""Miro entity schemas.

Reference:
    https://developers.miro.com/reference/api-reference
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


class MiroBoardEntity(BaseEntity):
    """Schema for Miro board entities.

    Reference:
        https://developers.miro.com/reference/get-boards
    """

    board_id: str = AirweaveField(..., description="Miro board ID", is_entity_id=True)
    board_name: str = AirweaveField(
        ..., description="Board name", is_name=True, embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created at", is_created_at=True
    )
    modified_at: Optional[datetime] = AirweaveField(
        None, description="Last modified at", is_updated_at=True
    )

    description: Optional[str] = AirweaveField(
        None, description="Board description", embeddable=True
    )
    team_id: Optional[str] = AirweaveField(
        None, description="Team ID this board belongs to", embeddable=False
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="Owner user ID", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Owner display name", embeddable=True
    )
    view_link: Optional[str] = AirweaveField(
        None, description="URL to view the board", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this board."""
        return self.view_link or f"https://miro.com/app/board/{self.board_id}/"


class MiroStickyNoteEntity(BaseEntity):
    """Schema for Miro sticky note items.

    Reference:
        https://developers.miro.com/reference/get-sticky-notes
    """

    item_id: str = AirweaveField(
        ..., description="Sticky note item ID", is_entity_id=True
    )
    content: str = AirweaveField(
        ..., description="Sticky note text content", is_name=True, embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created at", is_created_at=True
    )
    modified_at: Optional[datetime] = AirweaveField(
        None, description="Last modified at", is_updated_at=True
    )

    board_id: str = AirweaveField(
        ..., description="Board ID this item belongs to", embeddable=False
    )
    board_name: str = AirweaveField(
        ..., description="Board name this item belongs to", embeddable=True
    )
    frame_id: Optional[str] = AirweaveField(
        None, description="ID of containing frame, if any", embeddable=False
    )
    frame_title: Optional[str] = AirweaveField(
        None, description="Title of containing frame, if any", embeddable=True
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created the item", embeddable=True
    )
    modified_by: Optional[Dict] = AirweaveField(
        None, description="User who last modified the item", embeddable=True
    )
    tags: List[Dict] = AirweaveField(
        default_factory=list, description="Tags attached to this item", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this sticky note."""
        return f"https://miro.com/app/board/{self.board_id}/?moveToWidget={self.item_id}"


class MiroCardEntity(BaseEntity):
    """Schema for Miro card items (Kanban-style cards).

    Reference:
        https://developers.miro.com/reference/get-cards
    """

    item_id: str = AirweaveField(..., description="Card item ID", is_entity_id=True)
    title: str = AirweaveField(
        ..., description="Card title", is_name=True, embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created at", is_created_at=True
    )
    modified_at: Optional[datetime] = AirweaveField(
        None, description="Last modified at", is_updated_at=True
    )

    board_id: str = AirweaveField(
        ..., description="Board ID this card belongs to", embeddable=False
    )
    board_name: str = AirweaveField(
        ..., description="Board name this card belongs to", embeddable=True
    )
    frame_id: Optional[str] = AirweaveField(
        None, description="ID of containing frame, if any", embeddable=False
    )
    frame_title: Optional[str] = AirweaveField(
        None, description="Title of containing frame, if any", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Card description", embeddable=True
    )
    due_date: Optional[str] = AirweaveField(
        None, description="Due date for the card", embeddable=True
    )
    assignee_id: Optional[str] = AirweaveField(
        None, description="Unique user identifier of the card assignee", embeddable=True
    )
    fields: List[Dict] = AirweaveField(
        default_factory=list, description="Custom fields on the card", embeddable=True
    )
    tags: List[Dict] = AirweaveField(
        default_factory=list, description="Tags attached to this card", embeddable=True
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created the card", embeddable=True
    )
    modified_by: Optional[Dict] = AirweaveField(
        None, description="User who last modified the card", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this card."""
        return f"https://miro.com/app/board/{self.board_id}/?moveToWidget={self.item_id}"


class MiroTextEntity(BaseEntity):
    """Schema for Miro text items.

    Reference:
        https://developers.miro.com/reference/get-texts
    """

    item_id: str = AirweaveField(..., description="Unique identifier of the text item", is_entity_id=True)
    content: str = AirweaveField(
        ..., description="Text content", is_name=True, embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created at", is_created_at=True
    )
    modified_at: Optional[datetime] = AirweaveField(
        None, description="Last modified at", is_updated_at=True
    )

    board_id: str = AirweaveField(
        ..., description="Board ID this text belongs to", embeddable=False
    )
    board_name: str = AirweaveField(
        ..., description="Board name this text belongs to", embeddable=True
    )
    frame_id: Optional[str] = AirweaveField(
        None, description="ID of containing frame, if any", embeddable=False
    )
    frame_title: Optional[str] = AirweaveField(
        None, description="Title of containing frame, if any", embeddable=True
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created the text", embeddable=True
    )
    modified_by: Optional[Dict] = AirweaveField(
        None, description="User who last modified the text", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this text item."""
        return f"https://miro.com/app/board/{self.board_id}/?moveToWidget={self.item_id}"


class MiroFrameEntity(BaseEntity):
    """Schema for Miro frame items (visual groupings/containers).

    Reference:
        https://developers.miro.com/reference/get-frames
    """

    item_id: str = AirweaveField(..., description="Frame item ID", is_entity_id=True)
    title: str = AirweaveField(
        ..., description="Frame title", is_name=True, embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created at", is_created_at=True
    )
    modified_at: Optional[datetime] = AirweaveField(
        None, description="Last modified at", is_updated_at=True
    )

    board_id: str = AirweaveField(
        ..., description="Board ID this frame belongs to", embeddable=False
    )
    board_name: str = AirweaveField(
        ..., description="Board name this frame belongs to", embeddable=True
    )
    frame_id: Optional[str] = AirweaveField(
        None, description="ID of containing frame, if any (for nested frames)", embeddable=False
    )
    frame_title: Optional[str] = AirweaveField(
        None, description="Title of containing frame, if any (for nested frames)", embeddable=True
    )
    format: Optional[str] = AirweaveField(
        None, description="Frame format (e.g. custom, a4, letter)", embeddable=True
    )
    frame_type: Optional[str] = AirweaveField(
        None, description="Frame layout type (e.g. freeform, grid)", embeddable=True
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created the frame", embeddable=True
    )
    modified_by: Optional[Dict] = AirweaveField(
        None, description="User who last modified the frame", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this frame."""
        return f"https://miro.com/app/board/{self.board_id}/?moveToWidget={self.item_id}"


class MiroTagEntity(BaseEntity):
    """Schema for Miro tag entities.

    Reference:
        https://developers.miro.com/reference/get-tags-from-board
    """

    tag_id: str = AirweaveField(..., description="Unique identifier of the tag", is_entity_id=True)
    title: str = AirweaveField(
        ..., description="Tag title", is_name=True, embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created at (snapshot time)", is_created_at=True
    )
    modified_at: Optional[datetime] = AirweaveField(
        None, description="Last modified at (snapshot time)", is_updated_at=True
    )

    board_id: str = AirweaveField(
        ..., description="Board ID this tag belongs to", embeddable=False
    )
    board_name: str = AirweaveField(
        ..., description="Board name this tag belongs to", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for the board containing this tag."""
        return f"https://miro.com/app/board/{self.board_id}/"


class MiroAppCardEntity(BaseEntity):
    """Schema for Miro app card items (integration cards from Jira, GitHub, etc.).

    Reference:
        https://developers.miro.com/reference/get-app-card-item
    """

    item_id: str = AirweaveField(..., description="App card item ID", is_entity_id=True)
    title: str = AirweaveField(
        ..., description="App card title", is_name=True, embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created at", is_created_at=True
    )
    modified_at: Optional[datetime] = AirweaveField(
        None, description="Last modified at", is_updated_at=True
    )

    board_id: str = AirweaveField(
        ..., description="Board ID this app card belongs to", embeddable=False
    )
    board_name: str = AirweaveField(
        ..., description="Board name this app card belongs to", embeddable=True
    )
    frame_id: Optional[str] = AirweaveField(
        None, description="ID of containing frame, if any", embeddable=False
    )
    frame_title: Optional[str] = AirweaveField(
        None, description="Title of containing frame, if any", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="App card description", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="App card sync status", embeddable=False
    )
    fields: List[Dict] = AirweaveField(
        default_factory=list, description="Custom preview fields on the app card", embeddable=True
    )
    owned: Optional[bool] = AirweaveField(
        None, description="Whether the app owns this card", embeddable=False
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created the app card", embeddable=True
    )
    modified_by: Optional[Dict] = AirweaveField(
        None, description="User who last modified the app card", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this app card."""
        return f"https://miro.com/app/board/{self.board_id}/?moveToWidget={self.item_id}"


class MiroDocumentEntity(FileEntity):
    """Schema for Miro document items (uploaded PDFs, DOCXs, etc.).

    Reference:
        https://developers.miro.com/reference/get-document-item
    """

    item_id: str = AirweaveField(..., description="Unique identifier of the document item", is_entity_id=True)
    title: str = AirweaveField(
        ..., description="Document title", is_name=True, embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created at", is_created_at=True
    )
    modified_at: Optional[datetime] = AirweaveField(
        None, description="Last modified at", is_updated_at=True
    )

    board_id: str = AirweaveField(
        ..., description="Board ID this document belongs to", embeddable=False
    )
    board_name: str = AirweaveField(
        ..., description="Board name this document belongs to", embeddable=True
    )
    frame_id: Optional[str] = AirweaveField(
        None, description="ID of containing frame, if any", embeddable=False
    )
    frame_title: Optional[str] = AirweaveField(
        None, description="Title of containing frame, if any", embeddable=True
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created the document", embeddable=True
    )
    modified_by: Optional[Dict] = AirweaveField(
        None, description="User who last modified the document", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this document."""
        return f"https://miro.com/app/board/{self.board_id}/?moveToWidget={self.item_id}"


class MiroImageEntity(FileEntity):
    """Schema for Miro image items.

    Reference:
        https://developers.miro.com/reference/get-image-item
    """

    item_id: str = AirweaveField(..., description="Unique identifier of the image item", is_entity_id=True)
    title: str = AirweaveField(
        ..., description="Image title", is_name=True, embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created at", is_created_at=True
    )
    modified_at: Optional[datetime] = AirweaveField(
        None, description="Last modified at", is_updated_at=True
    )

    board_id: str = AirweaveField(
        ..., description="Board ID this image belongs to", embeddable=False
    )
    board_name: str = AirweaveField(
        ..., description="Board name this image belongs to", embeddable=True
    )
    frame_id: Optional[str] = AirweaveField(
        None, description="ID of containing frame, if any", embeddable=False
    )
    frame_title: Optional[str] = AirweaveField(
        None, description="Title of containing frame, if any", embeddable=True
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created the image", embeddable=True
    )
    modified_by: Optional[Dict] = AirweaveField(
        None, description="User who last modified the image", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this image."""
        return f"https://miro.com/app/board/{self.board_id}/?moveToWidget={self.item_id}"
