"""Word-specific generation schemas."""

from pydantic import BaseModel, Field


class WordDocumentContent(BaseModel):
    """Schema for Word document content generation."""

    title: str = Field(description="Document title")
    content: str = Field(description="Document content in markdown format")
    summary: str = Field(description="Brief summary of the document")

