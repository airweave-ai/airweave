"""Google Slides-specific generation schema."""

from pydantic import BaseModel, Field


class GoogleSlidesPresentation(BaseModel):
    """Schema for Google Slides presentation generation."""

    title: str = Field(description="Presentation title")
    content: str = Field(description="Presentation content in plain text format")
