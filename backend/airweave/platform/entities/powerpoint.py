"""Microsoft PowerPoint entity schemas.

Entity schemas for Microsoft PowerPoint presentations based on Microsoft Graph API:
 - PowerPointPresentationEntity (PowerPoint file with full metadata)

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem
  https://learn.microsoft.com/en-us/graph/api/driveitem-get-content
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import FileEntity


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse Microsoft Graph ISO8601 timestamps into timezone-aware datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class PowerPointPresentationEntity(FileEntity):
    """Schema for a Microsoft PowerPoint presentation as a file entity.

    Represents PowerPoint presentations (.pptx, .ppt, .pptm) stored in OneDrive/SharePoint.
    Extends FileEntity to leverage Airweave's file processing.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/driveitem
    """

    id: str = AirweaveField(
        ...,
        description="Drive item ID for the PowerPoint presentation.",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Human-readable title for the presentation.",
        is_name=True,
        embeddable=True,
    )
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="When the presentation was created.",
        embeddable=False,
        is_created_at=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="When the presentation was last modified.",
        embeddable=False,
        is_updated_at=True,
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="URL to open the presentation in PowerPoint Online.",
        embeddable=False,
        unhashable=True,
    )
    content_download_url: Optional[str] = AirweaveField(
        None,
        description="Direct download URL for the presentation content.",
        embeddable=False,
        unhashable=True,
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Identity of the user who created the presentation.",
        embeddable=True,
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Identity of the user who last modified the presentation.",
        embeddable=True,
    )
    parent_reference: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Information about the parent folder/drive location.",
        embeddable=False,
    )
    drive_id: Optional[str] = AirweaveField(
        None,
        description="ID of the drive containing this presentation.",
        embeddable=False,
    )
    folder_path: Optional[str] = AirweaveField(
        None,
        description="Full path to the parent folder.",
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None,
        description="Description of the presentation if available.",
        embeddable=True,
    )
    shared: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Information about sharing status of the presentation.",
        embeddable=True,
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        graph_base_url: str,
    ) -> "PowerPointPresentationEntity":
        """Construct from a Microsoft Graph DriveItem response for a PowerPoint file."""
        document_id = data.get("id")
        file_name = data.get("name", "Unknown")
        title, _ = os.path.splitext(file_name)

        content_download_url = f"{graph_base_url}/me/drive/items/{document_id}/content"

        parent_ref = data.get("parentReference", {})
        folder_path = parent_ref.get("path", "")
        if folder_path and "/root:" in folder_path:
            folder_path = folder_path.split("/root:", 1)[1].lstrip(":")

        mime_type = data.get("file", {}).get("mimeType") or (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

        return cls(
            breadcrumbs=[],
            name=file_name,
            id=document_id,
            title=title,
            created_datetime=_parse_dt(data.get("createdDateTime")),
            last_modified_datetime=_parse_dt(data.get("lastModifiedDateTime")),
            url=content_download_url,
            size=data.get("size", 0),
            file_type="microsoft_powerpoint",
            mime_type=mime_type,
            local_path=None,
            web_url_override=data.get("webUrl"),
            content_download_url=content_download_url,
            created_by=data.get("createdBy"),
            last_modified_by=data.get("lastModifiedBy"),
            parent_reference=parent_ref,
            drive_id=parent_ref.get("driveId"),
            folder_path=folder_path,
            description=data.get("description"),
            shared=data.get("shared"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL exposed to the UI to open the presentation."""
        if self.web_url_override:
            return self.web_url_override
        if self.url:
            return self.url
        return f"https://graph.microsoft.com/v1.0/me/drive/items/{self.id}"
