"""Monday entity schemas.

Based on the Monday.com API (GraphQL-based), we define entity schemas for
commonly used Monday resources: Boards, Groups, Columns, Items, Subitems, and Updates.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb


def _parse_monday_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse Monday.com ISO 8601 datetime string to datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class MondayBoardEntity(BaseEntity):
    """Schema for Monday Board objects."""

    board_id: str = AirweaveField(
        ..., description="Unique identifier for the board.", is_entity_id=True
    )
    board_name: str = AirweaveField(
        ..., description="Display name of the board.", embeddable=True, is_name=True
    )
    created_time: Optional[datetime] = AirweaveField(
        None, description="Board creation timestamp (if available).", is_created_at=True
    )
    updated_time: Optional[datetime] = AirweaveField(
        None, description="Board update timestamp.", is_updated_at=True
    )
    board_kind: Optional[str] = AirweaveField(
        None,
        description="The board's kind/type: 'public', 'private', or 'share'.",
        embeddable=False,
    )
    columns: List[Dict] = AirweaveField(
        default_factory=list,
        description="A list of columns on the board (each column is typically a dict of fields).",
        embeddable=False,
    )
    description: Optional[str] = AirweaveField(
        None, description="The description of the board.", embeddable=True
    )
    groups: List[Dict] = AirweaveField(
        default_factory=list,
        description="A list of groups on the board (each group is typically a dict of fields).",
        embeddable=False,
    )
    owners: List[Dict] = AirweaveField(
        default_factory=list,
        description="A list of users or teams who own the board.",
        embeddable=True,
    )
    state: Optional[str] = AirweaveField(
        None,
        description="The board's current state: 'active', 'archived', or 'deleted'.",
        embeddable=False,
    )
    workspace_id: Optional[str] = AirweaveField(
        None,
        description="The unique identifier of the workspace containing this board (if any).",
        embeddable=False,
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the board in Monday.", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        breadcrumbs: List[Breadcrumb],
        web_url: Optional[str] = None,
    ) -> MondayBoardEntity:
        """Build from a Monday.com GraphQL board object."""
        board_id = str(data["id"])
        board_name = data.get("name") or f"Board {board_id}"
        updated_time = _parse_monday_datetime(data.get("updated_at"))
        return cls(
            entity_id=board_id,
            breadcrumbs=breadcrumbs,
            name=board_name,
            created_at=None,
            updated_at=updated_time,
            board_id=board_id,
            board_name=board_name,
            created_time=None,
            updated_time=updated_time,
            board_kind=data.get("type"),
            columns=data.get("columns", []),
            description=None,
            groups=data.get("groups", []),
            owners=data.get("owners", []),
            state=data.get("state"),
            workspace_id=str(data.get("workspace_id")) if data.get("workspace_id") else None,
            web_url_value=web_url,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the board."""
        return self.web_url_value or ""


class MondayGroupEntity(BaseEntity):
    """Schema for Monday Group objects."""

    group_id: str = AirweaveField(
        ...,
        description="The unique identifier (ID) of the group.",
        embeddable=False,
        is_entity_id=True,
    )
    board_id: str = AirweaveField(
        ..., description="ID of the board this group belongs to.", embeddable=False
    )
    title: str = AirweaveField(
        ..., description="Title or display name of the group.", embeddable=True, is_name=True
    )
    color: Optional[str] = AirweaveField(
        None, description="Group color code (e.g., 'red', 'green', 'blue', etc.).", embeddable=False
    )
    archived: bool = AirweaveField(
        False, description="Whether this group is archived.", embeddable=False
    )
    items: List[Dict] = AirweaveField(
        default_factory=list,
        description="List of items (rows) contained within this group.",
        embeddable=False,
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the group in Monday.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the group."""
        return self.web_url_value or ""


class MondayColumnEntity(BaseEntity):
    """Schema for Monday Column objects."""

    column_id: str = AirweaveField(
        ...,
        description="The unique identifier (ID) of the column.",
        embeddable=False,
        is_entity_id=True,
    )
    board_id: str = AirweaveField(
        ..., description="ID of the board this column belongs to.", embeddable=False
    )
    title: str = AirweaveField(
        ..., description="The display title of the column.", embeddable=True, is_name=True
    )
    column_type: Optional[str] = AirweaveField(
        None,
        description="The type of the column (e.g., 'text', 'number', 'date', 'link').",
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="The description of the column.", embeddable=True
    )
    settings_str: Optional[str] = AirweaveField(
        None,
        description="Raw settings/configuration details for the column.",
        embeddable=False,
    )
    archived: bool = AirweaveField(
        False, description="Whether this column is archived or hidden.", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the column in Monday.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the column."""
        return self.web_url_value or ""


class MondayItemEntity(BaseEntity):
    """Schema for Monday Item objects (rows on a board)."""

    item_id: str = AirweaveField(
        ...,
        description="The unique identifier (ID) of the item.",
        embeddable=False,
        is_entity_id=True,
    )
    item_name: str = AirweaveField(
        ..., description="Display name of the item.", embeddable=True, is_name=True
    )
    created_time: Optional[datetime] = AirweaveField(
        None, description="When the item was created.", is_created_at=True
    )
    updated_time: Optional[datetime] = AirweaveField(
        None, description="When the item was updated.", is_updated_at=True
    )
    board_id: str = AirweaveField(
        ..., description="ID of the board this item belongs to.", embeddable=False
    )
    group_id: Optional[str] = AirweaveField(
        None, description="ID of the group this item is placed in.", embeddable=False
    )
    state: Optional[str] = AirweaveField(
        None,
        description="The current state of the item: active, archived, or deleted.",
        embeddable=False,
    )
    column_values: List[Dict] = AirweaveField(
        default_factory=list,
        description="A list of column-value dicts that contain the data for each column.",
        embeddable=True,
    )
    creator: Optional[Dict] = AirweaveField(
        None, description="Information about the user/team who created this item.", embeddable=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the item in Monday.", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        breadcrumbs: List[Breadcrumb],
        board_id: str,
        web_url: Optional[str] = None,
    ) -> MondayItemEntity:
        """Build from a Monday.com GraphQL item object."""
        item_id = str(data["id"])
        item_name = data.get("name") or f"Item {item_id}"
        created_time = _parse_monday_datetime(data.get("created_at")) or datetime.utcnow()
        updated_time = _parse_monday_datetime(data.get("updated_at")) or created_time
        group = data.get("group")
        return cls(
            entity_id=item_id,
            breadcrumbs=breadcrumbs,
            name=item_name,
            created_at=created_time,
            updated_at=updated_time,
            item_id=item_id,
            item_name=item_name,
            created_time=created_time,
            updated_time=updated_time,
            board_id=board_id,
            group_id=group["id"] if group else None,
            state=data.get("state"),
            column_values=data.get("column_values", []),
            creator=data.get("creator"),
            web_url_value=web_url,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the item."""
        return self.web_url_value or ""


class MondaySubitemEntity(BaseEntity):
    """Schema for Monday Subitem objects."""

    subitem_id: str = AirweaveField(
        ...,
        description="The unique identifier (ID) of the subitem.",
        embeddable=False,
        is_entity_id=True,
    )
    subitem_name: str = AirweaveField(
        ..., description="Display name of the subitem.", embeddable=True, is_name=True
    )
    created_time: Optional[datetime] = AirweaveField(
        None, description="When the subitem was created.", is_created_at=True
    )
    updated_time: Optional[datetime] = AirweaveField(
        None, description="When the subitem was updated.", is_updated_at=True
    )
    parent_item_id: str = AirweaveField(
        ..., description="ID of the parent item this subitem belongs to.", embeddable=False
    )
    board_id: str = AirweaveField(
        ..., description="ID of the board that this subitem resides in.", embeddable=False
    )
    group_id: Optional[str] = AirweaveField(
        None, description="ID of the group this subitem is placed in.", embeddable=False
    )
    state: Optional[str] = AirweaveField(
        None,
        description="The current state of the subitem: active, archived, or deleted.",
        embeddable=False,
    )
    column_values: List[Dict] = AirweaveField(
        default_factory=list,
        description="A list of column-value dicts for each column on the subitem.",
        embeddable=True,
    )
    creator: Optional[Dict] = AirweaveField(
        None,
        description="Information about the user/team who created this subitem.",
        embeddable=True,
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the subitem in Monday.", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        breadcrumbs: List[Breadcrumb],
        parent_item_id: str,
        web_url: Optional[str] = None,
    ) -> MondaySubitemEntity:
        """Build from a Monday.com GraphQL subitem object."""
        subitem_id = str(data["id"])
        subitem_name = data.get("name") or f"Subitem {subitem_id}"
        created_time = _parse_monday_datetime(data.get("created_at")) or datetime.utcnow()
        updated_time = _parse_monday_datetime(data.get("updated_at")) or created_time
        board_id = str(data["board"]["id"]) if data.get("board") else ""
        group = data.get("group")
        return cls(
            entity_id=subitem_id,
            breadcrumbs=breadcrumbs,
            name=subitem_name,
            created_at=created_time,
            updated_at=updated_time,
            subitem_id=subitem_id,
            subitem_name=subitem_name,
            created_time=created_time,
            updated_time=updated_time,
            parent_item_id=parent_item_id,
            board_id=board_id,
            group_id=group["id"] if group else None,
            state=data.get("state"),
            column_values=data.get("column_values", []),
            creator=data.get("creator"),
            web_url_value=web_url,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the subitem."""
        return self.web_url_value or ""


class MondayUpdateEntity(BaseEntity):
    """Schema for Monday Update objects."""

    update_id: str = AirweaveField(
        ...,
        description="The unique identifier (ID) of the update.",
        embeddable=False,
        is_entity_id=True,
    )
    update_preview: str = AirweaveField(
        ..., description="Preview text for the update body.", embeddable=True, is_name=True
    )
    created_time: Optional[datetime] = AirweaveField(
        None, description="When the update was created.", is_created_at=True
    )
    item_id: Optional[str] = AirweaveField(
        None,
        description=(
            "ID of the item this update is referencing (could also be a board-level update)."
        ),
        embeddable=False,
    )
    board_id: Optional[str] = AirweaveField(
        None, description="ID of the board, if applicable.", embeddable=False
    )
    creator_id: Optional[str] = AirweaveField(
        None,
        description="ID of the user who created this update.",
        embeddable=False,
    )
    body: Optional[str] = AirweaveField(
        None,
        description="The text (body) of the update, which may include markdown or HTML formatting.",
        embeddable=True,
    )
    assets: List[Dict] = AirweaveField(
        default_factory=list,
        description="Assets (e.g. images, attachments) associated with this update.",
        embeddable=False,
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the update in Monday.", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        breadcrumbs: List[Breadcrumb],
        board_id: str,
        item_id: Optional[str] = None,
        web_url: Optional[str] = None,
    ) -> MondayUpdateEntity:
        """Build from a Monday.com GraphQL update object."""
        body = data.get("body", "")
        update_name = body[:50] + "..." if len(body) > 50 else body
        if not update_name:
            update_name = f"Update {data['id']}"
        created_time = _parse_monday_datetime(data.get("created_at")) or datetime.utcnow()
        creator = data.get("creator")
        return cls(
            entity_id=str(data["id"]),
            breadcrumbs=breadcrumbs,
            name=update_name,
            created_at=created_time,
            updated_at=None,
            update_id=str(data["id"]),
            update_preview=update_name,
            created_time=created_time,
            item_id=item_id,
            board_id=board_id if item_id is None else None,
            creator_id=str(creator["id"]) if creator else None,
            body=body,
            assets=data.get("assets", []),
            web_url_value=web_url,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the update."""
        return self.web_url_value or ""
