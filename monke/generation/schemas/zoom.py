"""Zoom-specific Pydantic schemas used for LLM structured generation."""

from pydantic import BaseModel, Field


class ZoomMeetingSpec(BaseModel):
    """Metadata for meeting generation."""

    token: str = Field(description="Unique verification token to embed in the content")
    meeting_type: int = Field(default=2, description="Meeting type (2=scheduled)")


class ZoomMeetingContent(BaseModel):
    """Content for generated meeting."""

    topic: str = Field(
        description="Meeting topic/title with verification token embedded"
    )
    agenda: str = Field(
        description="Meeting agenda/description with verification token embedded"
    )
    duration: int = Field(default=60, description="Meeting duration in minutes")


class ZoomMeeting(BaseModel):
    """Schema for generating Zoom meeting content."""

    spec: ZoomMeetingSpec
    content: ZoomMeetingContent
