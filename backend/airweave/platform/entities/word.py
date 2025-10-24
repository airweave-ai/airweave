"""Microsoft Word entity schemas.

Entity schemas for Microsoft Word documents based on Microsoft Graph API:
 - WordDocument (Word file with full metadata)

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem
  https://learn.microsoft.com/en-us/graph/api/driveitem-get-content
"""

from datetime import datetime
from typing import Any, Dict, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import FileEntity


class WordDocumentEntity(FileEntity):
    """Schema for a Microsoft Word document as a file entity.

    Represents Word documents (.docx, .doc) stored in OneDrive/SharePoint.
    Extends FileEntity to leverage Airweave's file processing pipeline which will:
    - Download the Word document
    - Convert it to markdown using document converters
    - Chunk the content for indexing

    Based on the Microsoft Graph driveItem resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/driveitem
    """

    # Core Word document fields
    title: str = AirweaveField(..., description="The title/name of the document.", embeddable=True)
    web_url: Optional[str] = AirweaveField(
        None, description="URL to open the document in Word Online.", embeddable=False
    )

    # Timestamps
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Timestamp at which the document was created.",
        is_created_at=True,
        embeddable=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Timestamp at which the document was last modified.",
        is_updated_at=True,
        embeddable=True,
    )

    # Authorship and collaboration
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the document.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who last modified the document.", embeddable=True
    )

    # Location and organization
    parent_reference: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Information about the parent folder/drive location.",
        embeddable=True,
    )
    drive_id: Optional[str] = AirweaveField(
        None, description="ID of the drive containing this document."
    )
    folder_path: Optional[str] = AirweaveField(
        None, description="Full path to the parent folder.", embeddable=True
    )

    # Document metadata
    description: Optional[str] = AirweaveField(
        None, description="Description of the document if available.", embeddable=True
    )

    # Sharing and permissions
    shared: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about sharing status of the document.", embeddable=True
    )

    def __init__(self, **data):
        """Initialize the entity and set file_type and mime_type for Word processing."""
        # Set Word-specific values
        if "mime_type" not in data or not data["mime_type"]:
            # Default MIME type for .docx files
            data.setdefault(
                "mime_type",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        # Set file_type for categorization
        data.setdefault("file_type", "microsoft_word_doc")

        # Ensure download_url is set
        data.setdefault("download_url", data.get("content_download_url", ""))

        # Ensure file_id matches entity_id
        data.setdefault("file_id", data.get("entity_id", ""))

        # Ensure name includes the title
        if "title" in data and "name" not in data:
            title = data["title"]
            # Ensure .docx extension
            if not title.endswith((".docx", ".doc")):
                title = f"{title}.docx"
            data["name"] = title

        super().__init__(**data)
