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
