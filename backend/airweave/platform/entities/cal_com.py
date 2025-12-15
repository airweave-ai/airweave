"""Cal.com entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import ChunkEntity


class CalComScheduleEntity(ChunkEntity):
    """Schema for Cal.com schedule entities."""

    id: int = AirweaveField(..., description="Schedule ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Schedule name", is_name=True, embeddable=True)
    owner_id: int = AirweaveField(..., description="ID of the schedule owner", embeddable=True)
    time_zone: str = AirweaveField(..., description="Time zone for the schedule", embeddable=True)
    is_default: bool = AirweaveField(
        False, description="Whether this is the default schedule", embeddable=True
    )
    availability: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Regular availability windows (days and times)",
        embeddable=True,
    )
    overrides: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Date-specific availability overrides",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created at", is_created_at=True, embeddable=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Last updated at", is_updated_at=True, embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this schedule."""
        return f"https://cal.com/settings/availability/schedule/{self.id}"


class CalComEventTypeEntity(ChunkEntity):
    """Schema for Cal.com event type entities."""

    id: int = AirweaveField(..., description="Event type ID", is_entity_id=True)
    title: str = AirweaveField(..., description="Event type title", is_name=True, embeddable=True)
    slug: str = AirweaveField(..., description="Event type slug", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Event type description", embeddable=True
    )
    length_in_minutes: int = AirweaveField(
        ..., description="Duration of the event in minutes", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created at", is_created_at=True, embeddable=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Last updated at", is_updated_at=True, embeddable=True
    )

    # Schedule reference
    schedule_id: Optional[int] = Field(None, description="ID of the associated schedule")

    # Location information
    locations: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="List of locations where the event can take place",
        embeddable=True,
    )

    # Booking configuration
    booking_fields: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Custom fields required for booking",
        embeddable=True,
    )
    price: Optional[float] = AirweaveField(
        None, description="Price for the event type", embeddable=True
    )
    currency: Optional[str] = AirweaveField(
        None, description="Currency for the price", embeddable=True
    )

    # Scheduling settings
    minimum_booking_notice: Optional[int] = AirweaveField(
        None,
        description="Minimum notice required before booking (in minutes)",
        embeddable=True,
    )
    before_event_buffer: Optional[int] = AirweaveField(
        None, description="Buffer time before event (in minutes)", embeddable=True
    )
    after_event_buffer: Optional[int] = AirweaveField(
        None, description="Buffer time after event (in minutes)", embeddable=True
    )

    # Status and visibility
    hidden: bool = AirweaveField(
        False, description="Whether the event type is hidden", embeddable=True
    )
    booking_requires_authentication: bool = AirweaveField(
        False,
        description="Whether booking requires user authentication",
        embeddable=True,
    )

    # Owner and users
    owner_id: Optional[int] = Field(None, description="ID of the event type owner")
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the event type owner", embeddable=True
    )
    owner_email: Optional[str] = AirweaveField(
        None, description="Email of the event type owner", embeddable=True
    )
    users: List[str] = AirweaveField(
        default_factory=list,
        description="List of user emails who can host this event",
        embeddable=True,
    )

    # Recurrence settings
    recurrence: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Recurrence settings for the event", embeddable=True
    )

    # Additional metadata
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Additional metadata", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this event type."""
        return f"https://cal.com/{self.slug}"


class CalComBookingEntity(ChunkEntity):
    """Schema for Cal.com booking entities."""

    id: int = AirweaveField(..., description="Booking ID", is_entity_id=True)
    uid: str = AirweaveField(..., description="Unique booking identifier", embeddable=True)
    title: str = AirweaveField(..., description="Booking title", is_name=True, embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Booking description or notes", embeddable=True
    )
    start_time: datetime = AirweaveField(
        ..., description="Start time of the booking", embeddable=True, is_created_at=True
    )
    end_time: datetime = AirweaveField(..., description="End time of the booking", embeddable=True)
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created at", is_created_at=True, embeddable=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Last updated at", is_updated_at=True, embeddable=True
    )

    # Event type reference
    event_type_id: Optional[int] = Field(None, description="ID of the associated event type")
    event_type_title: Optional[str] = AirweaveField(
        None, description="Title of the associated event type", embeddable=True
    )
    event_type_slug: Optional[str] = AirweaveField(
        None, description="Slug of the associated event type", embeddable=True
    )

    # Attendee information
    attendees: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="List of attendees for the booking",
        embeddable=True,
    )
    user_email: Optional[str] = AirweaveField(
        None, description="Email of the user who made the booking", embeddable=True
    )
    user_name: Optional[str] = AirweaveField(
        None, description="Name of the user who made the booking", embeddable=True
    )

    # Organizer information
    organizer_email: Optional[str] = AirweaveField(
        None, description="Email of the event organizer", embeddable=True
    )
    organizer_name: Optional[str] = AirweaveField(
        None, description="Name of the event organizer", embeddable=True
    )

    # Status
    status: str = AirweaveField(
        ...,
        description="Booking status (e.g., 'accepted', 'pending', 'cancelled')",
        embeddable=True,
    )
    paid: bool = AirweaveField(False, description="Whether the booking is paid", embeddable=True)
    payment_required: bool = AirweaveField(
        False, description="Whether payment is required", embeddable=True
    )

    # Location
    location: Optional[str] = AirweaveField(
        None, description="Location of the booking", embeddable=True
    )
    location_type: Optional[str] = AirweaveField(
        None,
        description="Type of location (e.g., 'integrations:zoom', 'address')",
        embeddable=True,
    )
    meeting_url: Optional[str] = AirweaveField(
        None, description="Meeting URL if virtual", embeddable=True, unhashable=True
    )

    # Additional metadata
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Additional booking metadata", embeddable=True
    )
    cancellation_reason: Optional[str] = AirweaveField(
        None, description="Reason for cancellation if cancelled", embeddable=True
    )
    rescheduled: bool = Field(False, description="Whether the booking was rescheduled")
    recurring_event_id: Optional[str] = Field(
        None, description="ID of the recurring event if part of a series"
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this booking."""
        return f"https://cal.com/bookings/{self.uid}"
