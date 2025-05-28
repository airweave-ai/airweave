"""OneDrive entity schemas.

Based on the Microsoft Graph API reference for OneDrive,
we define entity schemas for the following core objects:
  • Drive
  • DriveItem

Each schema inherits from ChunkEntity, which provides an entity_id field to
store the OneDrive object's unique ID (e.g., drive.id or driveItem.id).

References:
  https://learn.microsoft.com/en-us/graph/api/resources/drive?view=graph-rest-1.0
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem?view=graph-rest-1.0
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity


class OneDriveDriveEntity(ChunkEntity):
    """Schema for a OneDrive Drive object.

    The inherited entity_id stores the drive's unique ID. Additional key fields come
    from the Microsoft Graph drive resource.
    """

    drive_type: Optional[str] = Field(
        None,
        description=(
            "Describes the type of drive represented by this resource "
            "(e.g., personal, business, documentLibrary)."
        ),
    )
    owner: Optional[Dict[str, Any]] = Field(
        None, description="Information about the user or application that owns this drive."
    )
    quota: Optional[Dict[str, Any]] = Field(
        None,
        description="Information about the drive's storage quota (total, used, remaining, etc.).",
    )

    created_at: Optional[datetime] = Field(
        None, description="Datetime when the drive was created (from createdDateTime)."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Datetime when the drive was last modified (from lastModifiedDateTime)."
    )


class OneDriveDriveItemEntity(FileEntity):
    """Schema for a OneDrive DriveItem object (file or folder).

    Inherits from FileEntity to support file processing capabilities.
    The inherited entity_id stores the DriveItem's unique ID.
    """

    name: Optional[str] = Field(None, description="The name of the item (folder or file).")
    description: Optional[str] = Field(None, description="Description of the item (if available).")
    etag: Optional[str] = Field(
        None, description="An eTag for the content of the item. Used for change tracking."
    )
    ctag: Optional[str] = Field(
        None, description="A cTag for the content of the item. Used for internal sync."
    )

    created_at: Optional[datetime] = Field(
        None, description="Datetime when the item was created (from createdDateTime)."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Datetime when the item was last modified (from lastModifiedDateTime)."
    )

    size: Optional[int] = Field(None, description="Size of the item in bytes.")
    web_url: Optional[str] = Field(
        None, description="URL that displays the resource in the browser."
    )

    # Microsoft Graph API specific fields
    file: Optional[Dict[str, Any]] = Field(
        None, description="File metadata if the item is a file (e.g., mimeType, hashes)."
    )
    folder: Optional[Dict[str, Any]] = Field(
        None, description="Folder metadata if the item is a folder (e.g., childCount)."
    )

    # Parent reference typically contains info like driveId, id, path, etc.
    parent_reference: Optional[Dict[str, Any]] = Field(
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
