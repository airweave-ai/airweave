"""Microsoft Excel entity schemas.

Entity schemas for Microsoft Excel objects based on Microsoft Graph API:
 - Workbook (Excel file)
 - Worksheet (individual sheets/tabs)
 - Table (structured data tables within worksheets)

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/excel
  https://learn.microsoft.com/en-us/graph/api/resources/workbook
  https://learn.microsoft.com/en-us/graph/api/resources/worksheet
  https://learn.microsoft.com/en-us/graph/api/resources/table
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class ExcelWorkbookEntity(BaseEntity):
    """Schema for a Microsoft Excel workbook (file).

    Represents the Excel file itself with metadata.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/driveitem
    """

    id: str = AirweaveField(
        ...,
        description="Drive item ID for the workbook.",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Workbook name (without extension).",
        is_name=True,
        embeddable=True,
    )
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="When the workbook was created.",
        embeddable=False,
        is_created_at=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="When the workbook was last modified.",
        embeddable=False,
        is_updated_at=True,
    )
    file_name: str = AirweaveField(
        ..., description="The full file name including extension.", embeddable=True
    )
    size: Optional[int] = AirweaveField(
        None, description="Size of the file in bytes.", embeddable=False
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the workbook.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who last modified the workbook.", embeddable=True
    )
    parent_reference: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Information about the parent folder/drive location.",
        embeddable=False,
    )
    drive_id: Optional[str] = AirweaveField(
        None, description="ID of the drive containing this workbook.", embeddable=False
    )
    description: Optional[str] = AirweaveField(
        None, description="Description of the workbook if available.", embeddable=True
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="Direct URL to open the workbook in Excel Online.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL exposed to Airweave clients."""
        if self.web_url_override:
            return self.web_url_override
        if self.drive_id:
            return f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/items/{self.id}"
        return f"https://graph.microsoft.com/v1.0/me/drive/items/{self.id}"


class ExcelWorksheetEntity(BaseEntity):
    """Schema for a Microsoft Excel worksheet (sheet/tab).

    Represents individual sheets within an Excel workbook.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/worksheet
    """

    id: str = AirweaveField(
        ...,
        description="Worksheet ID within the workbook.",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Worksheet display name.",
        is_name=True,
        embeddable=True,
    )
    workbook_id: str = AirweaveField(
        ..., description="ID of the parent workbook.", embeddable=False
    )
    workbook_name: str = AirweaveField(
        ..., description="Name of the parent workbook.", embeddable=True
    )
    position: Optional[int] = AirweaveField(
        None,
        description="The zero-based position of the worksheet within the workbook.",
        embeddable=False,
    )
    visibility: Optional[str] = AirweaveField(
        None,
        description="The visibility of the worksheet (Visible, Hidden, VeryHidden).",
        embeddable=False,
    )
    range_address: Optional[str] = AirweaveField(
        None,
        description="The address of the used range (e.g., 'A1:Z100').",
        embeddable=False,
    )
    cell_content: Optional[str] = AirweaveField(
        None,
        description="Formatted text representation of the cell content in the used range.",
        embeddable=True,
    )
    row_count: Optional[int] = AirweaveField(
        None, description="Number of rows with data in the worksheet.", embeddable=False
    )
    column_count: Optional[int] = AirweaveField(
        None, description="Number of columns with data in the worksheet.", embeddable=False
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Timestamp at which the worksheet was last modified.",
        embeddable=False,
        is_updated_at=True,
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="URL that opens the containing workbook focused on this sheet.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to open the worksheet context in Excel Online."""
        if self.web_url_override:
            return self.web_url_override
        return f"https://graph.microsoft.com/v1.0/me/drive/items/{self.workbook_id}/workbook/worksheets/{self.id}"


class ExcelTableEntity(BaseEntity):
    """Schema for a Microsoft Excel table.

    Represents structured data tables within worksheets.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/table
    """

    id: str = AirweaveField(
        ...,
        description="Table ID within the workbook.",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Table name as defined in Excel.",
        is_name=True,
        embeddable=True,
    )
    workbook_id: str = AirweaveField(
        ..., description="ID of the parent workbook.", embeddable=False
    )
    workbook_name: str = AirweaveField(
        ..., description="Name of the parent workbook.", embeddable=True
    )
    worksheet_id: str = AirweaveField(
        ..., description="ID of the parent worksheet.", embeddable=False
    )
    worksheet_name: str = AirweaveField(
        ..., description="Name of the parent worksheet.", embeddable=True
    )
    display_name: Optional[str] = AirweaveField(
        None, description="Display name of the table.", embeddable=True
    )
    show_headers: Optional[bool] = AirweaveField(
        None, description="Indicates whether the header row is visible.", embeddable=False
    )
    show_totals: Optional[bool] = AirweaveField(
        None, description="Indicates whether the total row is visible.", embeddable=False
    )
    style: Optional[str] = AirweaveField(
        None, description="Style name of the table.", embeddable=False
    )
    highlight_first_column: Optional[bool] = AirweaveField(
        None,
        description="Indicates whether the first column contains special formatting.",
        embeddable=False,
    )
    highlight_last_column: Optional[bool] = AirweaveField(
        None,
        description="Indicates whether the last column contains special formatting.",
        embeddable=False,
    )
    row_count: Optional[int] = AirweaveField(
        None, description="Number of rows in the table.", embeddable=False
    )
    column_count: Optional[int] = AirweaveField(
        None, description="Number of columns in the table.", embeddable=False
    )
    column_names: List[str] = AirweaveField(
        default_factory=list,
        description="Names of the columns in the table.",
        embeddable=True,
    )
    table_data: Optional[str] = AirweaveField(
        None,
        description="The actual table data as formatted text (rows and columns).",
        embeddable=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Timestamp at which the table was last modified.",
        embeddable=False,
        is_updated_at=True,
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="URL that opens the workbook focused on this table.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to open the table context in Excel Online."""
        if self.web_url_override:
            return self.web_url_override
        return f"https://graph.microsoft.com/v1.0/me/drive/items/{self.workbook_id}/workbook/tables/{self.id}"
