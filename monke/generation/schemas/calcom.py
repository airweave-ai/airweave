"""Pydantic schemas for Cal.com Monke test content generation."""

from typing import List

from pydantic import BaseModel, Field


class CalBookingContent(BaseModel):
    """Content structure for a generated Cal.com booking description."""

    summary: str = Field(
        ...,
        description="High-level summary of the meeting, must include the verification token.",
    )
    agenda: List[str] = Field(
        ...,
        description="Bullet-point agenda for the meeting.",
    )
    expected_outcomes: List[str] = Field(
        ...,
        description="Key expected outcomes for the meeting.",
    )


class CalBookingSpec(BaseModel):
    """Metadata for booking generation."""

    title: str = Field(..., description="Booking title.")
    token: str = Field(..., description="Verification token to embed in the content.")
    attendee_name: str = Field(
        default="Test Attendee",
        description="Display name of the attendee.",
    )
    attendee_email: str = Field(
        default="test.attendee@example.com",
        description="Email address for the attendee.",
    )
    attendee_time_zone: str = Field(
        default="America/New_York",
        description="Time zone ID for the attendee (IANA tz database name).",
    )


class CalBookingArtifact(BaseModel):
    """Complete structure for Cal.com booking generation."""

    spec: CalBookingSpec
    content: CalBookingContent
