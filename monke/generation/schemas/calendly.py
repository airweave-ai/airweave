"""Calendly-specific Pydantic schemas used for LLM structured generation."""

from typing import List, Optional
from pydantic import BaseModel, Field


class CalendlyEventTypeSpec(BaseModel):
    """Specification for generating a Calendly event type."""

    name: str = Field(description="Name of the event type (e.g., '30 Minute Meeting')")
    token: str = Field(description="Unique verification token to embed in the content")
    duration_minutes: int = Field(
        default=30, description="Duration of the event in minutes (e.g., 15, 30, 60)"
    )


class CalendlyEventTypeContent(BaseModel):
    """Content for generating a Calendly event type."""

    description: str = Field(
        description="Description of the event type in markdown format. Must include the token."
    )
    internal_note: Optional[str] = Field(
        default=None, description="Internal note about the event type (not visible to invitees)"
    )


class CalendlyEventType(BaseModel):
    """Schema for generating Calendly event type content."""

    spec: CalendlyEventTypeSpec
    content: CalendlyEventTypeContent


class CalendlyScheduledEventSpec(BaseModel):
    """Specification for generating a Calendly scheduled event description."""

    token: str = Field(description="Unique verification token to embed in the content")
    event_type_name: str = Field(description="Name of the event type this event is for")


class CalendlyScheduledEventContent(BaseModel):
    """Content for generating a Calendly scheduled event."""

    meeting_notes: str = Field(
        description="Meeting notes for the scheduled event. Must include the token."
    )


class CalendlyScheduledEvent(BaseModel):
    """Schema for generating Calendly scheduled event content."""

    spec: CalendlyScheduledEventSpec
    content: CalendlyScheduledEventContent

