"""Google Docs entity schemas.

Entity schemas for Google Docs based on Google Drive API.
Google Docs documents are exported as DOCX and represented as FileEntity objects
that get processed through Airweave's file processing pipeline.

References:
    https://developers.google.com/drive/api/v3/reference/files
    https://developers.google.com/drive/api/guides/manage-downloads
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import FileEntity


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse RFC3339 timestamps returned by Google APIs."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GoogleDocsDocumentEntity(FileEntity):
    """Schema for a Google Docs document.

    Represents a Google Doc file retrieved via the Google Drive API.
    The document content is exported as DOCX and processed through
    Airweave's file processing pipeline to create searchable chunks.

    Reference:
        https://developers.google.com/drive/api/v3/reference/files
        https://developers.google.com/drive/api/guides/manage-downloads
    """

    document_key: str = AirweaveField(
        ...,
        description="Stable Google Docs file ID.",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Display title of the document (without .docx extension).",
        embeddable=True,
        is_name=True,
    )
    created_timestamp: datetime = AirweaveField(
        ...,
        description="Document creation timestamp.",
        is_created_at=True,
    )
    modified_timestamp: datetime = AirweaveField(
        ...,
        description="Last modification timestamp.",
        is_updated_at=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="Optional description of the document.", embeddable=True
    )
    starred: bool = AirweaveField(
        False, description="Whether the user has starred this document.", embeddable=True
    )
    trashed: bool = AirweaveField(
        False, description="Whether the document is in the trash.", embeddable=False
    )
    explicitly_trashed: bool = AirweaveField(
        False,
        description="Whether the document was explicitly trashed by the user.",
        embeddable=False,
    )
    shared: bool = AirweaveField(
        False, description="Whether the document is shared with others.", embeddable=True
    )
    shared_with_me_time: Optional[datetime] = AirweaveField(
        None, description="Time when this document was shared with the user.", embeddable=False
    )
    sharing_user: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who shared this document.", embeddable=True
    )
    owners: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Owners of the document.", embeddable=True
    )
    permissions: Optional[List[Dict[str, Any]]] = AirweaveField(
        None, description="Permissions for this document.", embeddable=False
    )
    parents: List[str] = AirweaveField(
        default_factory=list,
        description="IDs of parent folders containing this document.",
        embeddable=False,
    )
    web_view_link: Optional[str] = AirweaveField(
        None, description="Link to open the document in Google Docs editor.", embeddable=False
    )
    icon_link: Optional[str] = AirweaveField(
        None, description="Link to the document's icon.", embeddable=False
    )
    created_time: Optional[datetime] = AirweaveField(
        None, description="When the document was created.", embeddable=False
    )
    modified_time: Optional[datetime] = AirweaveField(
        None, description="When the document was last modified.", embeddable=False
    )
    modified_by_me_time: Optional[datetime] = AirweaveField(
        None, description="Last time the user modified the document.", embeddable=False
    )
    viewed_by_me_time: Optional[datetime] = AirweaveField(
        None, description="Last time the user viewed the document.", embeddable=False
    )
    version: Optional[int] = AirweaveField(
        None, description="Version number of the document.", embeddable=True
    )
    export_mime_type: Optional[str] = AirweaveField(
        default="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        description="MIME type used for exporting the document content (DOCX).",
        embeddable=False,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Direct link to the Google Docs editor.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> GoogleDocsDocumentEntity:
        """Create entity from Google Drive API file metadata."""
        file_id = data["id"]
        export_mime = "application%2Fvnd.openxmlformats-officedocument.wordprocessingml.document"
        export_url = (
            f"https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType={export_mime}"
        )

        created_time = _parse_dt(data.get("createdTime")) or datetime.utcnow()
        modified_time = _parse_dt(data.get("modifiedTime")) or created_time

        doc_name = data.get("name", "Untitled Document")
        doc_name_with_ext = f"{doc_name}.docx" if not doc_name.endswith(".docx") else doc_name

        return cls(
            breadcrumbs=[],
            document_key=file_id,
            title=doc_name,
            created_timestamp=created_time,
            modified_timestamp=modified_time,
            name=doc_name_with_ext,
            created_at=created_time,
            updated_at=modified_time,
            url=export_url,
            size=int(data.get("size") or 0),
            file_type="google_doc",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            local_path=None,
            description=data.get("description"),
            starred=data.get("starred", False),
            trashed=data.get("trashed", False),
            explicitly_trashed=data.get("explicitlyTrashed", False),
            shared=data.get("shared", False),
            shared_with_me_time=_parse_dt(data.get("sharedWithMeTime")),
            sharing_user=data.get("sharingUser"),
            owners=data.get("owners", []),
            permissions=data.get("permissions"),
            parents=data.get("parents", []),
            web_view_link=data.get("webViewLink"),
            icon_link=data.get("iconLink"),
            created_time=created_time,
            modified_time=modified_time,
            modified_by_me_time=_parse_dt(data.get("modifiedByMeTime")),
            viewed_by_me_time=_parse_dt(data.get("viewedByMeTime")),
            version=data.get("version"),
            export_mime_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            web_url_value=data.get("webViewLink"),
            source_hash=f"version:{data['version']}" if data.get("version") is not None else None,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to open the document in Google Docs."""
        if self.web_url_value:
            return self.web_url_value
        return f"https://docs.google.com/document/d/{self.document_key}/edit"
