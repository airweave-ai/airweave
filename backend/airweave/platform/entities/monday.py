"""Monday entity schemas.

Based on the Monday.com API (GraphQL-based), we define entity schemas for
commonly used Monday resources: Boards, Groups, Columns, Items, Subitems, and Updates.
"""

from datetime import datetime
from typing import Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import 


class MondayBoardEntity(BaseEntity):
    """Schema for Monday Board objects.

    https://developer.monday.com/api-reference/reference/boards
    """

    board_id: str = AirweaveField(..., description="The unique identifier (ID) of the board.")
    board_kind: Optional[str] = AirweaveField(
        None, description="The board's kind/type: 'public', 'private', or 'share'."
    )
    columns: List[Dict] = AirweaveField(
        default_factory=list,
        description="A list of columns on the board (each column is typically a dict of fields).",
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the board was first created.", is_created_at=True
    )
    description: Optional[str] = AirweaveField(
        None, description="The description of the board.", embeddable=True
    )
    groups: List[Dict] = AirweaveField(
        default_factory=list,
        description="A list of groups on the board (each group is typically a dict of fields).",
    )
    name: Optional[str] = AirweaveField(
        None, description="The display name/title of the board.", embeddable=True
    )
    owners: List[Dict] = AirweaveField(
        default_factory=list,
        description="A list of users or teams who own the board.",
    )
    state: Optional[str] = AirweaveField(
        None, description="The board's current state: 'active', 'archived', or 'deleted'."
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the board was last updated.", is_updated_at=True
    )
    workspace_id: Optional[str] = AirweaveField(
        None,
        description="The unique identifier of the workspace containing this board (if any).",
    )


class MondayGroupEntity(BaseEntity):
    """Schema for Monday Group objects.

    Groups are collections of items (rows) within a board.

    https://developer.monday.com/api-reference/reference/boards
    """

    group_id: str = AirweaveField(..., description="The unique identifier (ID) of the group.")
    board_id: str = AirweaveField(..., description="ID of the board this group belongs to.")
    title: Optional[str] = AirweaveField(
        None, description="Title or display name of the group.", embeddable=True
    )
    color: Optional[str] = AirweaveField(
        None, description="Group color code (e.g., 'red', 'green', 'blue', etc.)."
    )
    archived: bool = AirweaveField(False, description="Whether this group is archived.")
    items: List[Dict] = AirweaveField(
        default_factory=list,
        description="List of items (rows) contained within this group.",
    )


class MondayColumnEntity(BaseEntity):
    """Schema for Monday Column objects.

    Columns define the structure of data on a Monday board.

    https://developer.monday.com/api-reference/reference/column-types-reference
    """

    column_id: str = AirweaveField(..., description="The unique identifier (ID) of the column.")
    board_id: str = AirweaveField(..., description="ID of the board this column belongs to.")
    title: Optional[str] = AirweaveField(
        None, description="The display title of the column.", embeddable=True
    )
    column_type: Optional[str] = AirweaveField(
        None,
        description="The type of the column (e.g., 'text', 'number', 'date', 'link').",
    )
    description: Optional[str] = AirweaveField(
        None, description="The description of the column.", embeddable=True
    )
    settings_str: Optional[str] = AirweaveField(
        None,
        description="Raw settings/configuration details for the column.",
    )
    archived: bool = AirweaveField(False, description="Whether this column is archived or hidden.")


class MondayItemEntity(BaseEntity):
    """Schema for Monday Item objects (rows on a board).

    https://developer.monday.com/api-reference/reference/boards
    """

    item_id: str = AirweaveField(..., description="The unique identifier (ID) of the item.")
    board_id: str = AirweaveField(..., description="ID of the board this item belongs to.")
    group_id: Optional[str] = AirweaveField(
        None, description="ID of the group this item is placed in."
    )
    name: Optional[str] = AirweaveField(
        None, description="The display name/title of the item.", embeddable=True
    )
    state: Optional[str] = AirweaveField(
        None, description="The current state of the item: active, archived, or deleted."
    )
    column_values: List[Dict] = AirweaveField(
        default_factory=list,
        description="A list of column-value dicts that contain the data for each column.",
    )
    creator: Optional[Dict] = AirweaveField(
        None, description="Information about the user/team who created this item."
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the item was first created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the item was last updated.", is_updated_at=True
    )


class MondaySubitemEntity(BaseEntity):
    """Schema for Monday Subitem objects.

    Subitems are items nested under a parent item, often in a dedicated 'Subitems' column.

    https://developer.monday.com/api-reference/reference/boards
    """

    subitem_id: str = AirweaveField(..., description="The unique identifier (ID) of the subitem.")
    parent_item_id: str = AirweaveField(
        ..., description="ID of the parent item this subitem belongs to."
    )
    board_id: str = AirweaveField(..., description="ID of the board that this subitem resides in.")
    group_id: Optional[str] = AirweaveField(
        None, description="ID of the group this subitem is placed in."
    )
    name: Optional[str] = AirweaveField(
        None, description="The display name/title of the subitem.", embeddable=True
    )
    state: Optional[str] = AirweaveField(
        None, description="The current state of the subitem: active, archived, or deleted."
    )
    column_values: List[Dict] = AirweaveField(
        default_factory=list,
        description="A list of column-value dicts for each column on the subitem.",
    )
    creator: Optional[Dict] = AirweaveField(
        None, description="Information about the user/team who created this subitem."
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the subitem was first created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the subitem was last updated.", is_updated_at=True
    )


class MondayUpdateEntity(BaseEntity):
    """Schema for Monday Update objects.

    monday.com updates add notes and discussions to items outside of their column data.

    https://developer.monday.com/api-reference/reference/updates
    """

    update_id: str = AirweaveField(..., description="The unique identifier (ID) of the update.")
    item_id: Optional[str] = AirweaveField(
        None,
        description=(
            "ID of the item this update is referencing (could also be a board-level update)."
        ),
    )
    board_id: Optional[str] = AirweaveField(None, description="ID of the board, if applicable.")
    creator_id: Optional[str] = AirweaveField(
        None,
        description="ID of the user who created this update.",
    )
    body: Optional[str] = AirweaveField(
        None,
        description="The text (body) of the update, which may include markdown or HTML formatting.",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the update was first created.", is_created_at=True
    )
    assets: List[Dict] = AirweaveField(
        default_factory=list,
        description="Assets (e.g. images, attachments) associated with this update.",
    )
