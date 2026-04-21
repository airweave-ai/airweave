"""OneDrive entity schemas.

Based on the Microsoft Graph API reference for OneDrive,
we define entity schemas for the following core objects:
  • Drive
  • DriveItem

References:
  https://learn.microsoft.com/en-us/graph/api/resources/drive?view=graph-rest-1.0
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem?view=graph-rest-1.0
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb, FileEntity


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse Microsoft Graph ISO8601 timestamps into timezone-aware datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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
        """Return the OneDrive web URL for this drive."""
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

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        drive_name: str,
        drive_id: str,
        download_url: Optional[str] = None,
    ) -> Optional["OneDriveDriveItemEntity"]:
        """Construct from a Microsoft Graph DriveItem response.

        Returns None for folders or items without a download URL.
        """
        if "folder" in data:
            return None
        if not download_url:
            return None

        drive_breadcrumb = Breadcrumb(
            entity_id=drive_id,
            name=drive_name,
            entity_type="OneDriveDriveEntity",
        )

        file_info = data.get("file", {})
        parent_ref = data.get("parentReference", {})
        mime_type = file_info.get("mimeType") or "application/octet-stream"
        size = data.get("size", 0)

        if mime_type and "/" in mime_type:
            file_type = mime_type.split("/")[0]
        else:
            ext = os.path.splitext(data.get("name", ""))[1].lower().lstrip(".")
            file_type = ext if ext else "file"

        return cls(
            id=data["id"],
            breadcrumbs=[drive_breadcrumb],
            name=data.get("name"),
            created_at=_parse_dt(data.get("createdDateTime")),
            updated_at=_parse_dt(data.get("lastModifiedDateTime")),
            url=download_url,
            size=size,
            file_type=file_type,
            mime_type=mime_type,
            local_path=None,
            description=None,
            etag=data.get("eTag"),
            ctag=data.get("cTag"),
            web_url_override=data.get("webUrl"),
            file=file_info,
            folder=data.get("folder"),
            parent_reference=parent_ref,
            source_hash=f"ctag:{data['cTag']}" if data.get("cTag") else None,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the OneDrive web URL for this drive item."""
        if self.web_url_override:
            return self.web_url_override
        return f"https://onedrive.live.com/?id={self.id}"
