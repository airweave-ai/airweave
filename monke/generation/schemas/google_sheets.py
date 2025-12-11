"""Google Sheets-specific generation schema."""

from typing import List

from pydantic import BaseModel, Field


class GoogleSheetsSpreadsheet(BaseModel):
    """Schema for Google Sheets spreadsheet generation."""

    title: str = Field(description="Spreadsheet title")
    headers: List[str] = Field(description="Column headers for the spreadsheet")
    rows: List[List[str]] = Field(description="Data rows (list of lists of cell values)")
