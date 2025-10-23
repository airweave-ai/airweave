"""Excel-specific generation schemas."""

from typing import List

from pydantic import BaseModel, Field


class ExcelWorksheetData(BaseModel):
    """Schema for Excel worksheet content generation."""

    name: str = Field(description="Worksheet name/title")
    headers: List[str] = Field(description="Column headers for the worksheet")
    rows: List[List[str]] = Field(
        description="Row data (each row is a list of cell values)"
    )


class ExcelWorkbookSpec(BaseModel):
    """Schema for Excel workbook metadata."""

    filename: str = Field(description="Name of the Excel workbook file")
    worksheets: List[ExcelWorksheetData] = Field(
        description="List of worksheets to create in the workbook"
    )
