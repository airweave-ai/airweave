"""SharePoint 2019 On-Premise V2 Entities.

Entity hierarchy:
- SharePoint2019V2SiteEntity (BaseEntity) - Sites/Webs
- SharePoint2019V2ListEntity (BaseEntity) - Lists and Document Libraries
- SharePoint2019V2ItemEntity (BaseEntity) - Regular list items (contacts, tasks, etc.)
- SharePoint2019V2FileEntity (FileEntity) - Files in Document Libraries
"""

from datetime import datetime
from typing import Any, Dict, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, DeletionEntity, FileEntity


class SharePoint2019V2SiteEntity(BaseEntity):
    """Entity representing a SharePoint Site (Web)."""

    site_id: str = AirweaveField(..., description="Site GUID", is_entity_id=True)
    title: str = AirweaveField(..., description="Site Title", is_name=True, embeddable=True)
    url: str = AirweaveField(..., description="Full Site URL")
    server_relative_url: str = AirweaveField(..., description="Server Relative URL")
    web_template: Optional[str] = AirweaveField(None, description="Web Template (e.g. PROJECTSITE)")
    description: Optional[str] = AirweaveField(
        None, description="Site Description", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Creation time", is_created_at=True
    )
    last_modified_date: Optional[datetime] = AirweaveField(
        None, description="Last modified time", is_updated_at=True
    )


class SharePoint2019V2ListEntity(BaseEntity):
    """Entity representing a SharePoint List or Document Library."""

    list_id: str = AirweaveField(..., description="List GUID", is_entity_id=True)
    title: str = AirweaveField(..., description="List Title", is_name=True, embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="List Description", embeddable=True
    )
    parent_web_url: str = AirweaveField(..., description="URL of the parent site")
    item_count: int = AirweaveField(0, description="Number of items in the list")
    base_template: int = AirweaveField(..., description="Base Template ID (e.g. 101)")
    hidden: bool = AirweaveField(False, description="Is the list hidden?")
    created_at: Optional[datetime] = AirweaveField(
        None, description="Creation time", is_created_at=True
    )
    last_modified_date: Optional[datetime] = AirweaveField(
        None, description="Last modified time", is_updated_at=True
    )


class SharePoint2019V2ItemEntity(BaseEntity):
    """Entity representing a SharePoint List Item (non-file).

    For regular list items like contacts, calendar events, tasks, etc.
    Files in Document Libraries use SharePoint2019V2FileEntity instead.
    """

    list_id: str = AirweaveField(..., description="List GUID containing this item")
    item_id: int = AirweaveField(..., description="Integer ID unique within the list")
    sp_entity_id: str = AirweaveField(
        ...,
        description="Composite entity ID: sp2019v2:item:{list_id}:{item_id}",
        is_entity_id=True,
    )
    guid: str = AirweaveField(..., description="SharePoint Globally Unique ID (GUID)")
    title: str = AirweaveField(..., description="Item Title", is_name=True, embeddable=True)
    web_url: str = AirweaveField(..., description="Full URL to view the item")

    created_at: Optional[datetime] = AirweaveField(
        None, description="Creation time", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Last modification time", is_updated_at=True
    )
    file_system_object_type: int = AirweaveField(0, description="0=Item, 1=Folder")

    fields: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Cleaned FieldValuesAsText containing searchable content",
        embeddable=True,
    )


class SharePoint2019V2FileEntity(FileEntity):
    """Entity representing a file in a SharePoint Document Library.

    Inherits from FileEntity which provides:
    - url: Download URL (required)
    - size: File size in bytes (required)
    - file_type: File extension (required)
    - mime_type: MIME type (optional)
    - local_path: Local path after download (set by downloader)
    """

    list_id: str = AirweaveField(..., description="Document library GUID containing this file")
    item_id: int = AirweaveField(..., description="Integer ID unique within the list")
    sp_entity_id: str = AirweaveField(
        ...,
        description="Composite entity ID: sp2019v2:file:{list_id}:{item_id}",
        is_entity_id=True,
    )
    guid: str = AirweaveField(..., description="SharePoint Globally Unique ID (GUID)")
    title: str = AirweaveField(..., description="File Title", is_name=True, embeddable=True)

    web_url: str = AirweaveField(..., description="Full URL to view the file in browser")

    created_at: Optional[datetime] = AirweaveField(
        None, description="Creation time", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Last modification time", is_updated_at=True
    )
    file_system_object_type: int = AirweaveField(0, description="0=File, 1=Folder")

    file_name: str = AirweaveField(..., description="File name with extension", embeddable=True)
    server_relative_url: str = AirweaveField(..., description="Server relative URL for API calls")

    fields: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Cleaned FieldValuesAsText containing searchable content",
        embeddable=True,
    )


class SharePoint2019V2ItemDeletionEntity(DeletionEntity):
    """Deletion marker for a SharePoint list item.

    Yielded during incremental sync when the GetChanges API reports
    a ChangeType.Delete for an item. Entity ID format: sp2019v2:item:{list_id}:{item_id}
    """

    deletes_entity_class = SharePoint2019V2ItemEntity

    list_id: str = AirweaveField(..., description="List GUID containing the deleted item")
    item_id: int = AirweaveField(..., description="Integer ID of the deleted item")
    sp_entity_id: str = AirweaveField(
        ...,
        description="Composite entity ID matching the original item",
        is_entity_id=True,
    )
    label: str = AirweaveField(
        ...,
        description="Human-readable label for the deleted item",
        is_name=True,
        embeddable=True,
    )


class SharePoint2019V2FileDeletionEntity(DeletionEntity):
    """Deletion marker for a SharePoint file.

    Yielded during incremental sync when the GetChanges API reports
    a ChangeType.Delete for a file. Entity ID format: sp2019v2:file:{list_id}:{item_id}
    """

    deletes_entity_class = SharePoint2019V2FileEntity

    list_id: str = AirweaveField(..., description="List GUID containing the deleted file")
    item_id: int = AirweaveField(..., description="Integer ID of the deleted file")
    sp_entity_id: str = AirweaveField(
        ...,
        description="Composite entity ID matching the original file",
        is_entity_id=True,
    )
    label: str = AirweaveField(
        ...,
        description="Human-readable label for the deleted file",
        is_name=True,
        embeddable=True,
    )
