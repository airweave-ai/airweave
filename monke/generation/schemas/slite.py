"""Slite-specific Pydantic schemas used for LLM structured generation."""

from pydantic import BaseModel, Field


class SliteNoteSpec(BaseModel):
    """Metadata for Slite note generation."""

    title: str = Field(description="Note title")
    token: str = Field(description="Unique verification token to embed in the content")


class SliteNoteContent(BaseModel):
    """Content for generated Slite note."""

    markdown: str = Field(
        description="Note body in markdown; MUST include the verification token"
    )


class SliteNote(BaseModel):
    """Schema for generating Slite note content."""

    spec: SliteNoteSpec
    content: SliteNoteContent
