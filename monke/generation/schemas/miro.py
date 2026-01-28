"""Miro-specific Pydantic schemas used for LLM structured generation.

Covers all main Miro entity types that can be created via API:
- Sticky notes
- Cards
- Text items
- Frames
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class MiroStickyNoteSpec(BaseModel):
    """Specification for a Miro sticky note."""

    token: str = Field(description="Unique verification token to embed in the content")
    color: str = Field(
        default="yellow",
        description="Sticky note color (yellow, green, blue, red, orange, pink, purple, gray)"
    )


class MiroStickyNoteContent(BaseModel):
    """Content for a Miro sticky note."""

    content: str = Field(
        description="The text content of the sticky note. Should be concise but meaningful."
    )


class MiroStickyNote(BaseModel):
    """Schema for generating Miro sticky note content."""

    spec: MiroStickyNoteSpec
    content: MiroStickyNoteContent


class MiroCardSpec(BaseModel):
    """Specification for a Miro card."""

    token: str = Field(description="Unique verification token to embed in the content")
    title: str = Field(description="Card title - should be clear and actionable")


class MiroCardContent(BaseModel):
    """Content for a Miro card."""

    description: str = Field(description="Detailed card description with context and details")
    due_date: Optional[str] = Field(
        default=None,
        description="Optional due date in ISO format (YYYY-MM-DD)"
    )


class MiroCard(BaseModel):
    """Schema for generating Miro card content."""

    spec: MiroCardSpec
    content: MiroCardContent


class MiroTextSpec(BaseModel):
    """Specification for a Miro text item."""

    token: str = Field(description="Unique verification token to embed in the content")


class MiroTextContent(BaseModel):
    """Content for a Miro text item."""

    content: str = Field(
        description="The text content. Can be longer form text, headings, or notes."
    )


class MiroText(BaseModel):
    """Schema for generating Miro text content."""

    spec: MiroTextSpec
    content: MiroTextContent


class MiroFrameSpec(BaseModel):
    """Specification for a Miro frame."""

    token: str = Field(description="Unique verification token to embed in the title")
    title: str = Field(description="Frame title describing the contents or purpose")


class MiroFrameContent(BaseModel):
    """Content metadata for a Miro frame."""

    format: str = Field(
        default="custom",
        description="Frame format (custom, a4, letter, etc.)"
    )


class MiroFrame(BaseModel):
    """Schema for generating Miro frame content."""

    spec: MiroFrameSpec
    content: MiroFrameContent


class MiroTagSpec(BaseModel):
    """Specification for a Miro tag."""

    token: str = Field(description="Unique verification token to embed in the title")
    title: str = Field(description="Tag title - short label for categorization")


class MiroTag(BaseModel):
    """Schema for generating Miro tag content."""

    spec: MiroTagSpec


class MiroDocumentSpec(BaseModel):
    """Specification for a Miro document (PDF upload)."""

    token: str = Field(description="Unique verification token to embed in the content")
    title: str = Field(description="Document title")


class MiroDocumentContent(BaseModel):
    """Content for generating a document to upload."""

    text_content: str = Field(
        description="The text content of the document. Should be meaningful technical content."
    )
    sections: List[str] = Field(
        default_factory=list,
        description="List of section headings in the document"
    )


class MiroDocument(BaseModel):
    """Schema for generating Miro document content."""

    spec: MiroDocumentSpec
    content: MiroDocumentContent


class MiroImageSpec(BaseModel):
    """Specification for a Miro image."""

    token: str = Field(description="Unique verification token to embed in the image alt text")
    title: str = Field(description="Image title/filename")


class MiroImageContent(BaseModel):
    """Content for generating an image to upload."""

    alt_text: str = Field(
        description="Alt text description of the image with the verification token"
    )
    diagram_type: str = Field(
        default="flowchart",
        description="Type of diagram to represent (flowchart, architecture, sequence, etc.)"
    )


class MiroImage(BaseModel):
    """Schema for generating Miro image metadata."""

    spec: MiroImageSpec
    content: MiroImageContent
