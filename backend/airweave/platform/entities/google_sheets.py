"""Google Sheets entity schemas.

Entity schemas for Google Sheets API integration.
Spreadsheets contain sheets (tabs), which contain the actual cell data.

References:
    https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets
    https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class GoogleSheetsSpreadsheetEntity(BaseEntity):
    """Schema for a Google Sheets spreadsheet.

    Represents a Google Sheets spreadsheet file with its metadata.
    Individual sheets (tabs) are represented as child entities.

    Reference:
        https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets
    """

    spreadsheet_id: str = AirweaveField(
        ...,
        description="Unique identifier for the spreadsheet.",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Title of the spreadsheet.",
        embeddable=True,
        is_name=True,
    )
    created_timestamp: datetime = AirweaveField(
        ...,
        description="Spreadsheet creation timestamp.",
        is_created_at=True,
    )
    modified_timestamp: datetime = AirweaveField(
        ...,
        description="Last modification timestamp.",
        is_updated_at=True,
    )
    locale: Optional[str] = AirweaveField(
        None,
        description="The locale of the spreadsheet (e.g., 'en_US').",
        embeddable=False,
    )
    time_zone: Optional[str] = AirweaveField(
        None,
        description="The time zone of the spreadsheet (e.g., 'America/New_York').",
        embeddable=False,
    )
    sheet_count: int = AirweaveField(
        0,
        description="Number of sheets (tabs) in the spreadsheet.",
        embeddable=False,
    )
    owners: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="List of owners of the spreadsheet.",
        embeddable=True,
    )
    shared: bool = AirweaveField(
        False,
        description="Whether the spreadsheet is shared with others.",
        embeddable=False,
    )
    web_view_link: Optional[str] = AirweaveField(
        None,
        description="Link to view the spreadsheet in Google Sheets.",
        embeddable=False,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Direct link to the spreadsheet.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to open the spreadsheet in Google Sheets."""
        if self.web_url_value:
            return self.web_url_value
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit"


class GoogleSheetsSheetEntity(BaseEntity):
    """Schema for a Google Sheets sheet (tab within a spreadsheet).

    Represents an individual sheet within a spreadsheet, including
    its metadata and cell data content.

    Reference:
        https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets#Sheet
    """

    sheet_id: str = AirweaveField(
        ...,
        description="Unique identifier combining spreadsheet ID and sheet ID.",
        is_entity_id=True,
    )
    sheet_title: str = AirweaveField(
        ...,
        description="Title of the sheet (tab name).",
        embeddable=True,
        is_name=True,
    )
    created_timestamp: datetime = AirweaveField(
        ...,
        description="Sheet creation timestamp (uses spreadsheet creation time).",
        is_created_at=True,
    )
    modified_timestamp: datetime = AirweaveField(
        ...,
        description="Last modification timestamp.",
        is_updated_at=True,
    )
    spreadsheet_id: str = AirweaveField(
        ...,
        description="ID of the parent spreadsheet.",
        embeddable=False,
    )
    spreadsheet_title: str = AirweaveField(
        ...,
        description="Title of the parent spreadsheet.",
        embeddable=True,
    )
    sheet_index: int = AirweaveField(
        0,
        description="Index of the sheet within the spreadsheet (0-based).",
        embeddable=False,
    )
    sheet_type: str = AirweaveField(
        "GRID",
        description="Type of the sheet (GRID, OBJECT, DATA_SOURCE).",
        embeddable=False,
    )
    row_count: int = AirweaveField(
        0,
        description="Number of rows in the sheet.",
        embeddable=False,
    )
    column_count: int = AirweaveField(
        0,
        description="Number of columns in the sheet.",
        embeddable=False,
    )
    frozen_row_count: int = AirweaveField(
        0,
        description="Number of frozen rows.",
        embeddable=False,
    )
    frozen_column_count: int = AirweaveField(
        0,
        description="Number of frozen columns.",
        embeddable=False,
    )
    hidden: bool = AirweaveField(
        False,
        description="Whether the sheet is hidden.",
        embeddable=False,
    )
    headers: List[str] = AirweaveField(
        default_factory=list,
        description="Column headers from the first row.",
        embeddable=True,
    )
    data_preview: Optional[str] = AirweaveField(
        None,
        description="Preview of sheet data (first few rows as formatted text).",
        embeddable=True,
    )
    cell_data: Optional[str] = AirweaveField(
        None,
        description="Full cell data as formatted text for embedding.",
        embeddable=True,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Direct link to the sheet.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to open the sheet in Google Sheets."""
        if self.web_url_value:
            return self.web_url_value
        # Extract the numeric sheet_id from the composite ID (spreadsheet_id:sheet_id)
        parts = self.sheet_id.split(":")
        numeric_sheet_id = parts[1] if len(parts) > 1 else "0"
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit#gid={numeric_sheet_id}"
