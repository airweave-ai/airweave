"""Google Sheets-specific generation schema."""

from pydantic import BaseModel, Field


class GoogleSheetsSpreadsheet(BaseModel):
    """Schema for Google Sheets spreadsheet generation."""

    title: str = Field(description="Spreadsheet title")
    content: str = Field(description="Spreadsheet content in plain text format")
