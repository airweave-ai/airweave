"""Microsoft Word entity schemas.

Entity schemas for Microsoft Word documents based on Microsoft Graph API.

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem
  https://learn.microsoft.com/en-us/graph/api/driveitem-get-content
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import FileEntity

WORD_EXTENSIONS = (".docx", ".doc", ".docm", ".dotx", ".dotm")


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse Microsoft Graph ISO8601 timestamps into timezone-aware datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class WordDocumentEntity(FileEntity):
    """Schema for a Microsoft Word document as a file entity.

    Represents Word documents (.docx, .doc) stored in OneDrive/SharePoint.
    Extends FileEntity to leverage Airweave's file processing pipeline which will:
    - Download the Word document
    - Convert it to markdown using document converters
    - Chunk the content for indexing

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/driveitem
    """

    id: str = AirweaveField(
        ...,
        description="Drive item ID for the Word document.",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Human-readable title for the document.",
        is_name=True,
        embeddable=True,
    )
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="When the document was created.",
        embeddable=False,
        is_created_at=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="When the document was last modified.",
        embeddable=False,
        is_updated_at=True,
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="URL to open the document in Word Online.",
        embeddable=False,
        unhashable=True,
    )
    content_download_url: Optional[str] = AirweaveField(
        None,
        description="Direct download URL for the document content.",
        embeddable=False,
        unhashable=True,
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the document.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who last modified the document.", embeddable=True
    )
    parent_reference: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Information about the parent folder/drive location.",
        embeddable=False,
    )
    drive_id: Optional[str] = AirweaveField(
        None, description="ID of the drive containing this document.", embeddable=False
    )
    folder_path: Optional[str] = AirweaveField(
        None, description="Full path to the parent folder.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Description of the document if available.", embeddable=True
    )
    shared: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about sharing status of the document.", embeddable=True
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, graph_base_url: str) -> WordDocumentEntity:
        """Construct from a Microsoft Graph DriveItem response."""
        document_id = data["id"]
        file_name = data.get("name", "Unknown")

        title = file_name
        for ext in WORD_EXTENSIONS:
            if file_name.lower().endswith(ext):
                title = file_name[: -len(ext)]
                break

        content_download_url = f"{graph_base_url}/me/drive/items/{document_id}/content"

        parent_ref = data.get("parentReference", {})
        folder_path = parent_ref.get("path", "")
        if folder_path and "/root:" in folder_path:
            folder_path = folder_path.split("/root:", 1)[1]

        mime_type = data.get("file", {}).get("mimeType") or (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        created = _parse_dt(data.get("createdDateTime"))
        modified = _parse_dt(data.get("lastModifiedDateTime"))

        return cls(
            breadcrumbs=[],
            name=file_name,
            id=document_id,
            title=title,
            created_at=created,
            updated_at=modified,
            created_datetime=created,
            last_modified_datetime=modified,
            url=content_download_url,
            size=data.get("size", 0),
            file_type="microsoft_word_doc",
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
        """URL exposed to the UI to open the document."""
        if self.web_url_override:
            return self.web_url_override
        if self.url:
            return self.url
        return f"https://graph.microsoft.com/v1.0/me/drive/items/{self.id}"
