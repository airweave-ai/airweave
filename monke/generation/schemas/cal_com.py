"""Cal.com-specific Pydantic schemas used for LLM structured generation."""

from typing import List, Optional
from pydantic import BaseModel, Field


class CalComEventTypeSpec(BaseModel):
    """Specification for generating a Cal.com event type."""

    title: str = Field(description="Event type title - should be clear and descriptive")
    token: str = Field(description="Unique verification token to embed in the content")
    duration_minutes: int = Field(default=30, description="Duration of the event in minutes")


class CalComEventTypeContent(BaseModel):
    """Content for generating a Cal.com event type."""

    description: str = Field(
        description="Event type description in markdown format - MUST include the token"
    )
    location_type: str = Field(
        default="integrations:zoom",
        description="Location type (e.g., 'integrations:zoom', 'address', 'phone')",
    )
    location_details: Optional[str] = Field(
        None, description="Additional location details if needed"
    )


class CalComEventType(BaseModel):
    """Schema for generating Cal.com event type content."""

    spec: CalComEventTypeSpec
    content: CalComEventTypeContent


class CalComBookingSpec(BaseModel):
    """Specification for generating a Cal.com booking."""

    token: str = Field(description="Unique verification token to embed in the content")
    attendee_name: str = Field(description="Name of the attendee")
    attendee_email: str = Field(description="Email of the attendee")


class CalComBookingContent(BaseModel):
    """Content for generating a Cal.com booking."""

    notes: str = Field(
        description="Booking notes or description - MUST include the token"
    )
    questions: List[str] = Field(
        default_factory=list, description="List of questions or additional information"
    )


class CalComBooking(BaseModel):
    """Schema for generating Cal.com booking content."""

    spec: CalComBookingSpec
    content: CalComBookingContent
