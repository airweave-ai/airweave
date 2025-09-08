"""Confluence-specific generation schema."""

from datetime import datetime
from pydantic import BaseModel, Field


class ConfluenceArtifact(BaseModel):
    """Schema for Confluence page generation."""

    title: str = Field(description="Page title")
    content: str = Field(description="Page content")
    created_at: datetime = Field(default_factory=datetime.now)
