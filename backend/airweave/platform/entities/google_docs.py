"""Google Docs entity schemas.

Entity schemas for Google Docs based on Google Drive API.
Google Docs documents are exported as DOCX and represented as FileEntity objects
that get processed through Airweave's file processing pipeline.

References:
    https://developers.google.com/drive/api/v3/reference/files
    https://developers.google.com/drive/api/guides/manage-downloads
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import FileEntity
from airweave.platform.entities.utils import _determine_file_type_from_mime


class GoogleDocsDocumentEntity(FileEntity):
    """Schema for a Google Docs document.

    Represents a Google Doc file retrieved via the Google Drive API.
    The document content is exported as DOCX and processed through
    Airweave's file processing pipeline to create searchable chunks.

    Reference:
        https://developers.google.com/drive/api/v3/reference/files
        https://developers.google.com/drive/api/guides/manage-downloads
    """

    # Core file identification (inherited from FileEntity but customized)
    file_id: str = AirweaveField(..., description="Unique ID of the Google Doc.")
    name: str = AirweaveField(
        ..., description="Filename with extension for file processing (includes .docx)."
    )
    title: Optional[str] = AirweaveField(
        None,
        description="Display title of the document (without .docx extension).",
        embeddable=True,
    )
    mime_type: Optional[str] = AirweaveField(
        default="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        description="MIME type for DOCX export format.",
    )

    # Document metadata
    description: Optional[str] = AirweaveField(
        None, description="Optional description of the document.", embeddable=True
    )
    starred: bool = AirweaveField(
        False, description="Whether the user has starred this document.", embeddable=True
    )
    trashed: bool = AirweaveField(False, description="Whether the document is in the trash.")
    explicitly_trashed: bool = AirweaveField(
        False, description="Whether the document was explicitly trashed by the user."
    )

    # Sharing and permissions
    shared: bool = AirweaveField(
        False, description="Whether the document is shared with others.", embeddable=True
    )
    shared_with_me_time: Optional[datetime] = AirweaveField(
        None, description="Time when this document was shared with the user."
    )
    sharing_user: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who shared this document.", embeddable=True
    )
    owners: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Owners of the document.", embeddable=True
    )
    permissions: Optional[List[Dict[str, Any]]] = AirweaveField(
        None, description="Permissions for this document."
    )

    # Location and organization
    parents: List[str] = AirweaveField(
        default_factory=list, description="IDs of parent folders containing this document."
    )
    web_view_link: Optional[str] = AirweaveField(
        None, description="Link to open the document in Google Docs editor."
    )
    icon_link: Optional[str] = AirweaveField(None, description="Link to the document's icon.")

    # Timestamps
    created_time: Optional[datetime] = AirweaveField(
        None,
        description="When the document was created.",
        is_created_at=True,
        embeddable=True,
    )
    modified_time: Optional[datetime] = AirweaveField(
        None,
        description="When the document was last modified.",
        is_updated_at=True,
        embeddable=True,
    )
    modified_by_me_time: Optional[datetime] = AirweaveField(
        None, description="Last time the user modified the document."
    )
    viewed_by_me_time: Optional[datetime] = AirweaveField(
        None, description="Last time the user viewed the document."
    )

    # Content metadata
    size: Optional[int] = AirweaveField(None, description="Size of the document in bytes.")
    version: Optional[int] = AirweaveField(
        None, description="Version number of the document.", embeddable=True
    )

    # Export and download information (set by source connector)
    export_mime_type: Optional[str] = AirweaveField(
        default="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        description="MIME type used for exporting the document content (DOCX).",
    )

    def __init__(self, **data):
        """Initialize the Google Docs document entity.

        Sets appropriate defaults for file processing:
        - mime_type for DOCX processing
        - file_type as google_doc
        - export_mime_type for DOCX content retrieval
        - Ensures name has .docx extension while keeping title clean
        """
        # Set DOCX-specific values for Google Docs export
        data.setdefault(
            "mime_type",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        data.setdefault("file_type", "google_doc")
        data.setdefault(
            "export_mime_type",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        # Store original name as title (for UI display)
        original_name = data.get("name", "Untitled Document")
        data.setdefault("title", original_name)

        # Ensure name has .docx extension for proper file processing
        if not original_name.endswith(".docx"):
            data["name"] = f"{original_name}.docx"

        # Ensure download_url is set (will be the export URL)
        if "download_url" not in data or not data.get("download_url"):
            # This will be set by the source connector
            data.setdefault("download_url", "")

        super().__init__(**data)

        # Update file_type based on mime_type if not already set
        if not self.file_type or self.file_type == "unknown":
            self.file_type = _determine_file_type_from_mime(self.mime_type)

    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:
        """Override model_dump to handle special field conversions."""
        data = super().model_dump(*args, **kwargs)

        # Convert size to string if present
        if data.get("size") is not None:
            data["size"] = str(data["size"])

        # Convert version to string if present
        if data.get("version") is not None:
            data["version"] = str(data["version"])

        return data
