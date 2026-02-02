from datetime import datetime
from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb


class GoogleSheetsSpreadsheetEntity(BaseEntity):
    """Entity representing a Google Sheets spreadsheet file."""

    spreadsheet_id: str = AirweaveField(
        description="The ID of the spreadsheet",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        description="The title of the spreadsheet",
        is_searchable=True,
        is_name=True,
    )
    owner: Optional[str] = AirweaveField(
        default=None,
        description="Owner email address",
    )
    created_time: Optional[datetime] = AirweaveField(
        default=None,
        description="Creation time",
    )
    modified_time: Optional[datetime] = AirweaveField(
        default=None,
        description="Last modified time",
    )
    url: Optional[str] = AirweaveField(
        default=None,
        description="Web view link",
    )

    def to_breadcrumbs(self) -> list[Breadcrumb]:
        return [
            Breadcrumb(
                entity_id=self.spreadsheet_id,
                name=self.title,
                entity_type="google_sheet_spreadsheet",
            )
        ]


class GoogleSheetsWorksheetEntity(BaseEntity):
    """Entity representing a single worksheet within a Google Sheet."""

    spreadsheet_id: str = AirweaveField(description="Parent spreadsheet ID")
    sheet_id: int = AirweaveField(
        description="The ID of the worksheet",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        description="The title of the worksheet",
        is_searchable=True,
        is_name=True,
    )
    index: int = AirweaveField(description="The index of the sheet")
    row_count: Optional[int] = AirweaveField(default=None, description="Number of rows")
    column_count: Optional[int] = AirweaveField(default=None, description="Number of columns")
    values: Optional[str] = AirweaveField(
        default=None,
        description="Formatted text content of the sheet",
        is_searchable=True,
    )
    url: Optional[str] = AirweaveField(default=None, description="Web view link to the specific sheet")

    def to_breadcrumbs(self) -> list[Breadcrumb]:
        return [
            Breadcrumb(
                entity_id=self.spreadsheet_id,
                name="Spreadsheet",  # Placeholder, should be parent's name ideally
                entity_type="google_sheet_spreadsheet",
            ),
            Breadcrumb(
                entity_id=str(self.sheet_id),
                name=self.title,
                entity_type="google_sheet_worksheet",
            ),
        ]
