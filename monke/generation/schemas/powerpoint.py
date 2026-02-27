"""PowerPoint-specific generation schema."""

from pydantic import BaseModel, Field


class PowerPointPresentationContent(BaseModel):
    """Schema for PowerPoint presentation content generation."""

    title: str = Field(description="Presentation title")
    content: str = Field(description="Presentation content in plain text format")
