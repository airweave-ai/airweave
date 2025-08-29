"""Google Calendar-specific generation schema."""

from datetime import datetime
from pydantic import BaseModel, Field


class GoogleCalendarArtifact(BaseModel):
    """Schema for Google Calendar event generation."""

    title: str = Field(description="Event title")
    description: str = Field(description="Event description")
    duration_hours: float = Field(description="Event duration in hours", default=1.0)
    created_at: datetime = Field(default_factory=datetime.now)
