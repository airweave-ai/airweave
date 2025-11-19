"""OneDrive entity schemas.

Based on the Microsoft Graph API reference for OneDrive,
we define entity schemas for the following core objects:
  • Drive
  • DriveItem

References:
  https://learn.microsoft.com/en-us/graph/api/resources/drive?view=graph-rest-1.0
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem?view=graph-rest-1.0
"""

from typing import Any, Dict, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


class OneDriveDriveEntity(BaseEntity):
    """Schema for a OneDrive Drive object.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/drive?view=graph-rest-1.0
    """

    id: str = AirweaveField(
        ...,
        description="Drive ID.",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Drive name or drive type.",
        embeddable=True,
        is_name=True,
    )
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
        embeddable=False,
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="URL to open the drive.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        if self.web_url_override:
            return self.web_url_override
        return f"https://onedrive.live.com/?id={self.id}"


class OneDriveDriveItemEntity(FileEntity):
    """Schema for a OneDrive DriveItem object (file or folder).

    Inherits from FileEntity to support file processing capabilities.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/driveitem?view=graph-rest-1.0
    """

    id: str = AirweaveField(
        ...,
        description="Drive item ID.",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Item name.",
        embeddable=True,
        is_name=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="Description of the item (if available).", embeddable=True
    )
    etag: Optional[str] = AirweaveField(
        None,
        description="An eTag for the content of the item. Used for change tracking.",
        embeddable=False,
    )
    ctag: Optional[str] = AirweaveField(
        None,
        description="A cTag for the content of the item. Used for internal sync.",
        embeddable=False,
    )
    web_url_override: Optional[str] = AirweaveField(
        None, description="URL that displays the resource in the browser.", embeddable=False
    )
    file: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="File metadata if the item is a file (e.g., mimeType, hashes).",
        embeddable=False,
    )
    folder: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Folder metadata if the item is a folder (e.g., childCount).",
        embeddable=False,
    )
    parent_reference: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description=(
            "Information about the parent of this item, such as driveId or parent folder path."
        ),
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        if self.web_url_override:
            return self.web_url_override
        return f"https://onedrive.live.com/?id={self.id}"
