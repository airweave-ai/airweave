"""OneDrive entity schemas.

Based on the Microsoft Graph API reference for OneDrive,
we define entity schemas for the following core objects:
  • Drive
  • DriveItem

Each schema inherits from which provides an entity_id field to
store the OneDrive object's unique ID (e.g., drive.id or driveItem.id).

References:
  https://learn.microsoft.com/en-us/graph/api/resources/drive?view=graph-rest-1.0
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem?view=graph-rest-1.0
"""

from datetime import datetime
from typing import Any, Dict, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import FileEntity


class OneDriveDriveEntity(BaseEntity):
    """Schema for a OneDrive Drive object.

    The inherited entity_id stores the drive's unique ID. Additional key fields come
    from the Microsoft Graph drive resource.
    """

    drive_type: Optional[str] = AirweaveField(
        None,
        description=(
            "Describes the type of drive represented by this resource "
            "(e.g., personal, business, documentLibrary)."
        ),
        embeddable=True,
    )
    owner: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Information about the user or application that owns this drive.",
        embeddable=True,
    )
    quota: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Information about the drive's storage quota (total, used, remaining, etc.).",
    )

    created_at: Optional[datetime] = AirweaveField(
        None,
        description="Datetime when the drive was created (from createdDateTime).",
        is_created_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="Datetime when the drive was last modified (from lastModifiedDateTime).",
        is_updated_at=True,
    )


class OneDriveDriveItemEntity(FileEntity):
    """Schema for a OneDrive DriveItem object (file or folder).

    Inherits from FileEntity to support file processing capabilities.
    The inherited entity_id stores the DriveItem's unique ID.
    """

    name: Optional[str] = AirweaveField(None, description="The name of the item (folder or file).")
    description: Optional[str] = AirweaveField(
        None, description="Description of the item (if available)."
    )
    etag: Optional[str] = AirweaveField(
        None, description="An eTag for the content of the item. Used for change tracking."
    )
    ctag: Optional[str] = AirweaveField(
        None, description="A cTag for the content of the item. Used for internal sync."
    )

    created_at: Optional[datetime] = AirweaveField(
        None,
        description="Datetime when the item was created (from createdDateTime).",
        is_created_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="Datetime when the item was last modified (from lastModifiedDateTime).",
        is_updated_at=True,
    )

    size: Optional[int] = AirweaveField(None, description="Size of the item in bytes.")
    web_url: Optional[str] = AirweaveField(
        None, description="URL that displays the resource in the browser."
    )

    # Microsoft Graph API specific fields
    file: Optional[Dict[str, Any]] = AirweaveField(
        None, description="File metadata if the item is a file (e.g., mimeType, hashes)."
    )
    folder: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Folder metadata if the item is a folder (e.g., childCount)."
    )

    # Parent reference typically contains info like driveId, id, path, etc.
    parent_reference: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description=(
            "Information about the parent of this item, such as driveId or parent folder path."
        ),
    )

    # Override FileEntity fields to provide OneDrive-specific defaults
    def __init__(self, **data):
        """Initialize OneDriveDriveItemEntity with OneDrive-specific defaults."""
        # Set default metadata if not provided
        if "metadata" not in data:
            data["metadata"] = {}

        # Extract MIME type from file facet if available
        if "file" in data and data["file"] and "mimeType" in data["file"]:
            data["metadata"]["mimeType"] = data["file"]["mimeType"]

        super().__init__(**data)
