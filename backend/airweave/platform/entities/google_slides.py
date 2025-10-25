"""Google Slides entity schemas.

Entity schemas for Google Slides based on Google Slides API and Google Drive API.
Google Slides presentations are exported as PDF/PPTX and represented as FileEntity objects
that get processed through Airweave's file processing pipeline.

References:
    https://developers.google.com/slides/api/reference/rest
    https://developers.google.com/drive/api/v3/reference/files
    https://developers.google.com/drive/api/guides/manage-downloads
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import ChunkEntity, FileEntity
from airweave.platform.entities.utils import _determine_file_type_from_mime


class GoogleSlidesPresentationEntity(FileEntity):
    """Schema for a Google Slides presentation.

    Represents a Google Slides presentation retrieved via the Google Drive API.
    The presentation content is exported as PDF/PPTX and processed through
    Airweave's file processing pipeline to create searchable chunks.

    Reference:
        https://developers.google.com/slides/api/reference/rest/v1/presentations
        https://developers.google.com/drive/api/v3/reference/files
    """

    # Core file identification (inherited from FileEntity but customized)
    file_id: str = AirweaveField(..., description="Unique ID of the Google Slides presentation.")
    name: str = AirweaveField(
        ..., description="Filename with extension for file processing (includes .pdf or .pptx)."
    )
    title: Optional[str] = AirweaveField(
        None,
        description="Display title of the presentation (without file extension).",
        embeddable=True,
    )
    mime_type: Optional[str] = AirweaveField(
        default="application/pdf",
        description="MIME type for PDF export format (default) or PPTX.",
    )

    # Presentation metadata
    description: Optional[str] = AirweaveField(
        None, description="Optional description of the presentation.", embeddable=True
    )
    starred: bool = AirweaveField(
        False, description="Whether the user has starred this presentation.", embeddable=True
    )
    trashed: bool = AirweaveField(False, description="Whether the presentation is in the trash.")
    explicitly_trashed: bool = AirweaveField(
        False, description="Whether the presentation was explicitly trashed by the user."
    )

    # Sharing and permissions
    shared: bool = AirweaveField(
        False, description="Whether the presentation is shared with others.", embeddable=True
    )
    shared_with_me_time: Optional[datetime] = AirweaveField(
        None, description="Time when this presentation was shared with the user."
    )
    sharing_user: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who shared this presentation.", embeddable=True
    )
    owners: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Owners of the presentation.", embeddable=True
    )
    permissions: Optional[List[Dict[str, Any]]] = AirweaveField(
        None, description="Permissions for this presentation."
    )

    # Location and organization
    parents: List[str] = AirweaveField(
        default_factory=list, description="IDs of parent folders containing this presentation."
    )
    web_view_link: Optional[str] = AirweaveField(
        None, description="Link to open the presentation in Google Slides editor."
    )
    icon_link: Optional[str] = AirweaveField(None, description="Link to the presentation's icon.")

    # Timestamps
    created_time: Optional[datetime] = AirweaveField(
        None,
        description="When the presentation was created.",
        is_created_at=True,
        embeddable=True,
    )
    modified_time: Optional[datetime] = AirweaveField(
        None,
        description="When the presentation was last modified.",
        is_updated_at=True,
        embeddable=True,
    )
    modified_by_me_time: Optional[datetime] = AirweaveField(
        None, description="Last time the user modified the presentation."
    )
    viewed_by_me_time: Optional[datetime] = AirweaveField(
        None, description="Last time the user viewed the presentation."
    )

    # Content metadata
    size: Optional[int] = AirweaveField(None, description="Size of the presentation in bytes.")
    version: Optional[int] = AirweaveField(
        None, description="Version number of the presentation.", embeddable=True
    )

    # Presentation-specific metadata
    slide_count: Optional[int] = AirweaveField(
        None, description="Number of slides in the presentation.", embeddable=True
    )
    locale: Optional[str] = AirweaveField(
        None, description="The locale of the presentation.", embeddable=True
    )
    revision_id: Optional[str] = AirweaveField(
        None, description="The revision ID of the presentation."
    )

    # Export and download information (set by source connector)
    export_mime_type: Optional[str] = AirweaveField(
        default="application/pdf",
        description="MIME type used for exporting the presentation content (PDF or PPTX).",
    )

    def __init__(self, **data):
        """Initialize the Google Slides presentation entity.

        Sets appropriate defaults for file processing:
        - mime_type for PDF processing
        - file_type as google_slides
        - export_mime_type for PDF content retrieval
        - Ensures name has .pdf extension for proper file processing
        """
        # Set PDF-specific values for Google Slides export (mirrors Google Drive approach)
        data.setdefault("mime_type", "application/pdf")
        data.setdefault("file_type", "google_slides")
        data.setdefault("export_mime_type", "application/pdf")

        # Store original name as title (for UI display)
        original_name = data.get("name", "Untitled Presentation")
        data.setdefault("title", original_name)

        # Ensure name has .pdf extension for proper file processing
        if not original_name.endswith(".pdf"):
            data["name"] = f"{original_name}.pdf"

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

        # Convert slide_count to string if present
        if data.get("slide_count") is not None:
            data["slide_count"] = str(data["slide_count"])

        return data


class GoogleSlidesSlideEntity(ChunkEntity):
    """Schema for a Google Slides slide.

    Represents an individual slide within a Google Slides presentation.
    This entity captures slide-specific metadata and content for detailed
    indexing and search capabilities.

    Reference:
        https://developers.google.com/slides/api/reference/rest/v1/presentations.pages
    """

    # Core slide identification
    slide_id: str = AirweaveField(
        ..., description="Unique ID of the slide within the presentation."
    )
    presentation_id: str = AirweaveField(
        ..., description="ID of the parent presentation containing this slide."
    )
    slide_number: int = AirweaveField(
        ..., description="The zero-based index of the slide in the presentation.", embeddable=True
    )

    # Slide content and metadata
    title: Optional[str] = AirweaveField(
        None, description="Title of the slide if available.", embeddable=True
    )
    notes: Optional[str] = AirweaveField(
        None, description="Speaker notes for the slide.", embeddable=True
    )
    layout_type: Optional[str] = AirweaveField(
        None, description="The type of slide layout.", embeddable=True
    )
    master_properties: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Properties of the slide master."
    )

    # Slide elements and content
    elements: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="List of elements on the slide.", embeddable=True
    )
    text_content: Optional[str] = AirweaveField(
        None, description="Extracted text content from all elements on the slide.", embeddable=True
    )

    # Visual properties
    background: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Background properties of the slide."
    )
    color_scheme: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Color scheme of the slide."
    )

    # Timestamps
    created_time: Optional[datetime] = AirweaveField(
        None,
        description="When the slide was created.",
        is_created_at=True,
    )
    modified_time: Optional[datetime] = AirweaveField(
        None,
        description="When the slide was last modified.",
        is_updated_at=True,
    )

    # Parent presentation metadata (for context)
    presentation_title: Optional[str] = AirweaveField(
        None, description="Title of the parent presentation.", embeddable=True
    )
    presentation_url: Optional[str] = AirweaveField(
        None, description="URL to view the parent presentation."
    )

    def __init__(self, **data):
        """Initialize the Google Slides slide entity."""
        super().__init__(**data)

        # Extract text content from elements if not provided
        if not self.text_content and self.elements:
            text_parts = []
            for element in self.elements:
                if element.get("shape") and element["shape"].get("text"):
                    text_content = element["shape"]["text"].get("textElements", [])
                    for text_elem in text_content:
                        if text_elem.get("textRun"):
                            text_parts.append(text_elem["textRun"].get("content", ""))
            self.text_content = " ".join(text_parts).strip() if text_parts else None
