"""Cal.com booking entity schemas.

Maps Cal.com booking objects (regular, recurring, seated) into a single
searchable entity for Airweave.

API reference:
- Bookings list: https://cal.com/docs/api-reference/v2/bookings/get-all-bookings
- Bookings create: https://cal.com/docs/api-reference/v2/bookings/create-a-booking
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, DeletionEntity


class CalBookingEntity(BaseEntity):
    """Schema for Cal.com bookings (single or recurring instances)."""

    # Core identifiers
    uid: str = AirweaveField(
        ...,
        description="Cal.com booking UID (stable identifier used in APIs and redirects).",
        is_entity_id=True,
    )
    booking_id: int = Field(
        ...,
        description="Numeric Cal.com booking ID.",
    )

    # Primary display fields
    title: str = AirweaveField(
        ...,
        description="Title of the booking.",
        is_name=True,
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None,
        description="Description of the booking (agenda, context, etc.).",
        embeddable=True,
    )

    # Status & lifecycle
    status: Optional[str] = AirweaveField(
        None,
        description="Booking status (accepted, cancelled, rejected, pending).",
        embeddable=True,
    )
    cancellation_reason: Optional[str] = AirweaveField(
        None,
        description="Reason provided when the booking was cancelled.",
        embeddable=True,
    )
    cancelled_by_email: Optional[str] = AirweaveField(
        None,
        description="Email address of the user who cancelled the booking.",
        embeddable=True,
    )
    rescheduling_reason: Optional[str] = AirweaveField(
        None,
        description="Reason provided when the booking was rescheduled.",
        embeddable=True,
    )
    rescheduled_by_email: Optional[str] = AirweaveField(
        None,
        description="Email address of the user who rescheduled the booking.",
        embeddable=True,
    )
    rescheduled_from_uid: Optional[str] = Field(
        None,
        description="UID of the previous booking this one was rescheduled from.",
    )
    rescheduled_to_uid: Optional[str] = Field(
        None,
        description="UID of the booking this one was rescheduled to.",
    )

    # Timing
    start: Optional[datetime] = AirweaveField(
        None,
        description="Start time of the booking (UTC).",
        embeddable=True,
    )
    end: Optional[datetime] = AirweaveField(
        None,
        description="End time of the booking (UTC).",
        embeddable=True,
    )
    duration_minutes: Optional[int] = AirweaveField(
        None,
        description="Duration of the booking in minutes.",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When this booking was created.",
        embeddable=True,
        is_created_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When this booking was last updated (status changes, reschedules, etc.).",
        embeddable=True,
        is_updated_at=True,
    )

    # Participants & event type
    hosts: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Hosts for this booking (name, email, username, timezone).",
        embeddable=True,
    )
    attendees: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Primary attendees for this booking.",
        embeddable=True,
    )
    guests: List[str] = AirweaveField(
        default_factory=list,
        description="Additional guest email addresses for this booking.",
        embeddable=True,
    )
    absent_host: Optional[bool] = Field(
        None,
        description="Whether the host was marked absent for this booking.",
    )

    event_type_id: Optional[int] = Field(
        None,
        description="Cal.com event type ID (deprecated upstream in favor of event_type.id).",
    )
    event_type: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Embedded event type object (id, slug).",
        embeddable=True,
    )

    # Location & conferencing
    location: Optional[str] = AirweaveField(
        None,
        description="Resolved meeting location or conferencing URL.",
        embeddable=True,
    )
    meeting_url: Optional[str] = Field(
        None,
        description="Deprecated meeting URL field (kept for backwards compatibility).",
    )

    # Metadata & scoring
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Arbitrary metadata attached to the booking (CRM IDs, tags, etc.).",
        embeddable=True,
    )
    rating: Optional[float] = AirweaveField(
        None,
        description="Post-meeting rating, if collected.",
        embeddable=True,
    )
    ics_uid: Optional[str] = Field(
        None,
        description="UID of the underlying calendar event in ICS format.",
    )
    booking_fields_responses: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description=(
            "Responses for custom booking fields (keyed by booking field slug). "
            "These often contain rich, user-provided context."
        ),
        embeddable=True,
    )

    # Recurring bookings
    recurring_booking_uid: Optional[str] = Field(
        None,
        description="Recurring booking UID when this booking is part of a recurring series.",
    )

    # Web URL (user-facing link)
    web_url_value: Optional[str] = AirweaveField(
        None,
        description=(
            "User-facing URL associated with this booking. "
            "If not provided, falls back to the conferencing/location URL when available."
        ),
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Best-effort user-facing link for this booking.

        Preference order:
        1. Explicit web_url_value if provided
        2. Location/meeting URL when it looks like an HTTP(S) URL
        3. Empty string (no stable UI URL available)
        """
        if self.web_url_value:
            return self.web_url_value

        candidate = self.location or self.meeting_url
        if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
            return candidate

        return ""


class CalBookingDeletionEntity(DeletionEntity):
    """Deletion signal for a Cal.com booking.

    Emitted during incremental sync when a booking is cancelled and should be removed
    from destinations.
    """

    deletes_entity_class = CalBookingEntity

    uid: str = AirweaveField(
        ...,
        description="Cal.com booking UID (stable identifier). Matches CalBookingEntity.uid.",
        is_entity_id=True,
    )
    label: str = AirweaveField(
        ...,
        description="Human-readable deletion label.",
        is_name=True,
        embeddable=True,
    )
    booking_id: Optional[int] = Field(
        None,
        description="Numeric Cal.com booking ID (optional, for debugging).",
    )


class CalEventTypeEntity(BaseEntity):
    """Schema for Cal.com event types.

    Event types represent reusable booking templates (duration, locations, booking page).
    """

    event_type_id: int = AirweaveField(
        ...,
        description="Numeric Cal.com event type ID.",
        is_entity_id=True,
    )

    title: str = AirweaveField(
        ...,
        description="Human-readable title of the event type.",
        is_name=True,
        embeddable=True,
    )
    slug: str = Field(
        ...,
        description="URL slug for the event type (used in booking URLs).",
    )
    description: Optional[str] = AirweaveField(
        None,
        description="Long-form description shown on the booking page.",
        embeddable=True,
    )

    length_in_minutes: int = Field(
        ...,
        description="Primary meeting duration in minutes for this event type.",
    )

    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Arbitrary metadata attached to the event type.",
        embeddable=True,
    )

    booking_url: Optional[str] = AirweaveField(
        None,
        description="Full booking URL for this event type (e.g. https://cal.com/user/30min).",
        embeddable=False,
        unhashable=True,
    )

    schedule_id: Optional[int] = Field(
        None,
        description="ID of the primary schedule backing this event type, if any.",
    )

    hidden: bool = Field(
        False,
        description="Whether this event type is hidden from public listing.",
    )
    booking_requires_authentication: bool = Field(
        False,
        description=(
            "If true, only authenticated users (owner, org/team admin) "
            "can book this event type via API."
        ),
    )


class CalScheduleEntity(BaseEntity):
    """Schema for Cal.com schedules (availability definitions)."""

    schedule_id: int = AirweaveField(
        ...,
        description="Numeric Cal.com schedule ID.",
        is_entity_id=True,
    )

    owner_id: int = Field(
        ...,
        description="ID of the schedule owner (user or organization).",
    )

    name: str = AirweaveField(
        ...,
        description="Human-readable name of the schedule (e.g. 'Working hours').",
        is_name=True,
        embeddable=True,
    )

    time_zone: str = Field(
        ...,
        description="IANA time zone identifier used for this schedule.",
    )

    availability: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description=(
            "Weekly availability rules: days of week with startTime/endTime windows in HH:MM."
        ),
        embeddable=True,
    )

    is_default: bool = Field(
        False,
        description="Whether this is the user's default schedule.",
    )

    overrides: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description=("Date-specific overrides to the base schedule (date plus startTime/endTime)."),
        embeddable=True,
    )
