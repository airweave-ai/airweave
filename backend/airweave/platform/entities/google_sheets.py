"""Google Sheets entity schemas.

Entity schemas for Google Sheets based on Google Drive API and Sheets API.
Google Sheets spreadsheets are exported as Excel/CSV and represented as FileEntity objects
that get processed through Airweave's file processing pipeline.

References:
    https://developers.google.com/sheets/api/reference/rest
    https://developers.google.com/drive/api/v3/reference/files
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import FileEntity
from airweave.platform.entities.utils import _determine_file_type_from_mime


class GoogleSheetsSpreadsheetEntity(FileEntity):
    """Schema for a Google Sheets spreadsheet.

    Represents a Google Sheets file retrieved via the Google Drive API.
    The spreadsheet content is exported as Excel/CSV and processed through
    Airweave's file processing pipeline to create searchable chunks.

    Reference:
        https://developers.google.com/drive/api/v3/reference/files
    """

    file_id: str = AirweaveField(..., description="Unique ID of the Google Sheets spreadsheet.")
    name: str = AirweaveField(
        ..., description="Filename with extension for file processing (includes .xlsx or .csv)."
    )
    title: Optional[str] = AirweaveField(
        None,
        description="Display title of the spreadsheet (without extension).",
        embeddable=True,
    )
    mime_type: Optional[str] = AirweaveField(
        default="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        description="MIME type for Excel export format.",
    )

    description: Optional[str] = AirweaveField(
        None, description="Optional description of the spreadsheet.", embeddable=True
    )
    starred: bool = AirweaveField(
        False, description="Whether the user has starred this spreadsheet.", embeddable=True
    )
    trashed: bool = AirweaveField(False, description="Whether the spreadsheet is in the trash.")
    explicitly_trashed: bool = AirweaveField(
        False, description="Whether the spreadsheet was explicitly trashed by the user."
    )

    shared: bool = AirweaveField(
        False, description="Whether the spreadsheet is shared with others.", embeddable=True
    )
    shared_with_me_time: Optional[datetime] = AirweaveField(
        None, description="Time when this spreadsheet was shared with the user."
    )
    sharing_user: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who shared this spreadsheet.", embeddable=True
    )
    owners: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Owners of the spreadsheet.", embeddable=True
    )
    permissions: Optional[List[Dict[str, Any]]] = AirweaveField(
        None, description="Permissions for this spreadsheet."
    )

    parents: List[str] = AirweaveField(
        default_factory=list, description="IDs of parent folders containing this spreadsheet."
    )
    web_view_link: Optional[str] = AirweaveField(
        None, description="Link to open the spreadsheet in Google Sheets editor."
    )
    icon_link: Optional[str] = AirweaveField(None, description="Link to the spreadsheet's icon.")

    created_time: Optional[datetime] = AirweaveField(
        None,
        description="When the spreadsheet was created.",
        is_created_at=True,
        embeddable=True,
    )
    modified_time: Optional[datetime] = AirweaveField(
        None,
        description="When the spreadsheet was last modified.",
        is_updated_at=True,
        embeddable=True,
    )
    modified_by_me_time: Optional[datetime] = AirweaveField(
        None, description="Last time the user modified the spreadsheet."
    )
    viewed_by_me_time: Optional[datetime] = AirweaveField(
        None, description="Last time the user viewed the spreadsheet."
    )

    size: Optional[int] = AirweaveField(None, description="Size of the spreadsheet in bytes.")
    version: Optional[int] = AirweaveField(
        None, description="Version number of the spreadsheet.", embeddable=True
    )

    # Spreadsheet-specific metadata
    sheet_count: Optional[int] = AirweaveField(
        None, description="Number of sheets in the spreadsheet.", embeddable=True
    )
    locale: Optional[str] = AirweaveField(
        None, description="The locale of the spreadsheet.", embeddable=True
    )
    time_zone: Optional[str] = AirweaveField(
        None, description="The time zone of the spreadsheet.", embeddable=True
    )
    auto_recalc: Optional[str] = AirweaveField(
        None, description="The automatic recalculation setting of the spreadsheet.", embeddable=True
    )

    # Export and download information (set by source connector)
    export_mime_type: Optional[str] = AirweaveField(
        default="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        description="MIME type used for exporting the spreadsheet content (Excel or CSV).",
    )

    def __init__(self, **data):
        """Initialize the Google Sheets spreadsheet entity.

        Sets appropriate defaults for file processing:
        - mime_type for Excel processing
        - file_type as google_sheets
        - export_mime_type for Excel content retrieval
        - Ensures name has .xlsx extension for proper file processing
        """
        # Set Excel-specific values for Google Sheets export (mirrors Google Drive approach)
        data.setdefault(
            "mime_type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        data.setdefault("file_type", "google_sheets")
        data.setdefault(
            "export_mime_type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Store original name as title (for UI display)
        original_name = data.get("name", "Untitled Spreadsheet")
        data.setdefault("title", original_name)

        # Ensure name has .xlsx extension for proper file processing
        if not original_name.endswith(".xlsx"):
            data["name"] = f"{original_name}.xlsx"

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
