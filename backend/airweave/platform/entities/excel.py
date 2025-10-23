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

from pydantic import Field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import ChunkEntity


class ExcelWorkbookEntity(ChunkEntity):
    """Schema for a Microsoft Excel workbook (file).

    Represents the Excel file itself with metadata.
    Based on the Microsoft Graph driveItem resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/driveitem
    """

    name: str = AirweaveField(..., description="The name of the workbook file.", embeddable=True)
    file_name: str = AirweaveField(
        ..., description="The full file name including extension.", embeddable=True
    )
    web_url: Optional[str] = AirweaveField(
        None, description="URL to open the workbook in Excel Online.", embeddable=False
    )
    size: Optional[int] = Field(None, description="Size of the file in bytes.")
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Timestamp at which the workbook was created.",
        is_created_at=True,
        embeddable=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Timestamp at which the workbook was last modified.",
        is_updated_at=True,
        embeddable=True,
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
        embeddable=True,
    )
    drive_id: Optional[str] = Field(None, description="ID of the drive containing this workbook.")
    description: Optional[str] = AirweaveField(
        None, description="Description of the workbook if available.", embeddable=True
    )


class ExcelWorksheetEntity(ChunkEntity):
    """Schema for a Microsoft Excel worksheet (sheet/tab).

    Represents individual sheets within an Excel workbook.
    Based on the Microsoft Graph worksheet resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/worksheet
    """

    workbook_id: str = Field(..., description="ID of the parent workbook.")
    workbook_name: str = AirweaveField(
        ..., description="Name of the parent workbook.", embeddable=True
    )
    name: str = AirweaveField(..., description="The name of the worksheet.", embeddable=True)
    position: Optional[int] = AirweaveField(
        None, description="The zero-based position of the worksheet within the workbook."
    )
    visibility: Optional[str] = AirweaveField(
        None,
        description="The visibility of the worksheet (Visible, Hidden, VeryHidden).",
        embeddable=True,
    )
    range_address: Optional[str] = AirweaveField(
        None,
        description="The address of the used range (e.g., 'A1:Z100').",
        embeddable=True,
    )
    cell_content: Optional[str] = AirweaveField(
        None,
        description="Formatted text representation of the cell content in the used range.",
        embeddable=True,
    )
    row_count: Optional[int] = AirweaveField(
        None, description="Number of rows with data in the worksheet.", embeddable=True
    )
    column_count: Optional[int] = AirweaveField(
        None, description="Number of columns with data in the worksheet.", embeddable=True
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Timestamp at which the worksheet was last modified.",
        is_updated_at=True,
        embeddable=True,
    )


class ExcelTableEntity(ChunkEntity):
    """Schema for a Microsoft Excel table.

    Represents structured data tables within worksheets.
    Based on the Microsoft Graph table resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/table
    """

    workbook_id: str = Field(..., description="ID of the parent workbook.")
    workbook_name: str = AirweaveField(
        ..., description="Name of the parent workbook.", embeddable=True
    )
    worksheet_id: str = Field(..., description="ID of the parent worksheet.")
    worksheet_name: str = AirweaveField(
        ..., description="Name of the parent worksheet.", embeddable=True
    )
    name: str = AirweaveField(..., description="The name of the table.", embeddable=True)
    display_name: Optional[str] = AirweaveField(
        None, description="Display name of the table.", embeddable=True
    )
    show_headers: Optional[bool] = Field(
        None, description="Indicates whether the header row is visible."
    )
    show_totals: Optional[bool] = Field(
        None, description="Indicates whether the total row is visible."
    )
    style: Optional[str] = AirweaveField(None, description="Style name of the table.")
    highlight_first_column: Optional[bool] = Field(
        None, description="Indicates whether the first column contains special formatting."
    )
    highlight_last_column: Optional[bool] = Field(
        None, description="Indicates whether the last column contains special formatting."
    )
    row_count: Optional[int] = AirweaveField(
        None, description="Number of rows in the table.", embeddable=True
    )
    column_count: Optional[int] = AirweaveField(
        None, description="Number of columns in the table.", embeddable=True
    )
    column_names: Optional[List[str]] = AirweaveField(
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
        is_updated_at=True,
        embeddable=True,
    )
