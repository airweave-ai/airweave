"""Google Docs-specific generation schema."""

from pydantic import BaseModel, Field


class GoogleDocsDocument(BaseModel):
    """Schema for Google Docs document generation."""

    title: str = Field(description="Document title")
    content: str = Field(description="Document content in plain text format")
