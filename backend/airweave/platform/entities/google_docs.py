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

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import FileEntity


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

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to open the document in Google Docs."""
        if self.web_url_value:
            return self.web_url_value
        return f"https://docs.google.com/document/d/{self.document_key}/edit"
