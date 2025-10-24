"""PowerPoint-specific generation schemas."""

from typing import List

from pydantic import BaseModel, Field


class PowerPointSlideContent(BaseModel):
    """Schema for a single PowerPoint slide."""

    title: str = Field(description="Slide title")
    content: List[str] = Field(
        description="List of bullet points or content blocks for the slide"
    )


class PowerPointPresentationContent(BaseModel):
    """Schema for PowerPoint presentation content generation."""

    title: str = Field(description="Presentation title")
    subtitle: str = Field(description="Presentation subtitle")
    slides: List[PowerPointSlideContent] = Field(
        description="List of slides in the presentation"
    )
