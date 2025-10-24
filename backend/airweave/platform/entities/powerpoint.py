"""Microsoft PowerPoint entity schemas.

Entity schemas for Microsoft PowerPoint objects based on Microsoft Graph API:
 - Presentation (PowerPoint file)

PowerPoint presentations are treated as FileEntity objects that are:
- Downloaded from OneDrive/SharePoint
- Converted to markdown/text for processing
- Chunked for vector indexing
- Indexed for semantic search

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem
  https://learn.microsoft.com/en-us/graph/api/driveitem-list-children
  https://learn.microsoft.com/en-us/graph/api/driveitem-get-content
"""

from datetime import datetime
from typing import Any, Dict, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import FileEntity


class PowerPointPresentationEntity(FileEntity):
    """Schema for a Microsoft PowerPoint presentation file.

    Represents PowerPoint files (.pptx, .ppt, etc.) from OneDrive/SharePoint.
    Extends FileEntity to leverage Airweave's file processing pipeline which:
    - Downloads the presentation file
    - Converts to markdown/text for content extraction
    - Chunks the content for vector search
    - Indexes for semantic search

    Based on the Microsoft Graph driveItem resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/driveitem
    """

    title: str = AirweaveField(
        ...,
        description="The title of the presentation (filename without extension).",
        embeddable=True,
    )
    content_download_url: str = AirweaveField(
        ..., description="URL to download the presentation content.", embeddable=False
    )
    web_url: Optional[str] = AirweaveField(
        None, description="URL to open the presentation in PowerPoint Online.", embeddable=False
    )
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Timestamp at which the presentation was created.",
        is_created_at=True,
        embeddable=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Timestamp at which the presentation was last modified.",
        is_updated_at=True,
        embeddable=True,
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the presentation.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Identity of the user who last modified the presentation.",
        embeddable=True,
    )
    parent_reference: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Information about the parent folder/drive location.",
        embeddable=True,
    )
    drive_id: Optional[str] = AirweaveField(
        None, description="ID of the drive containing this presentation."
    )
    folder_path: Optional[str] = AirweaveField(
        None,
        description="Path to the folder containing this presentation.",
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="Description of the presentation if available.", embeddable=True
    )
    shared: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Sharing information for the presentation.", embeddable=True
    )

    def __init__(self, **data):
        """Initialize the entity and set file_type and mime_type for PPTX processing."""
        # Set PowerPoint-specific values
        if "mime_type" not in data or not data["mime_type"]:
            # Default MIME type for .pptx files
            data["mime_type"] = (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )

        # Set file_type for categorization
        data.setdefault("file_type", "pptx")

        # Ensure download_url is set from content_download_url
        data.setdefault("download_url", data.get("content_download_url", ""))

        # Ensure file_id matches entity_id
        data.setdefault("file_id", data.get("entity_id", ""))

        # Ensure name includes the title with .pptx extension
        if "title" in data and "name" not in data:
            title = data["title"]
            # Ensure .pptx extension
            if not title.endswith((".pptx", ".ppt", ".pptm")):
                title = f"{title}.pptx"
            data["name"] = title

        super().__init__(**data)
