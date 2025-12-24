"""Calendly entity schemas.

Based on the Calendly API v2 reference,
we define entity schemas for:
 - Users (Calendly account holders)
 - Event Types (the types of events that can be scheduled)
 - Scheduled Events (actual scheduled meetings)
 - Event Invitees (people invited to scheduled events)

Reference:
    https://developer.calendly.com/api-docs
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class CalendlyUserEntity(BaseEntity):
    """Schema for a Calendly User.

    Users represent individual Calendly account holders.
    See: https://developer.calendly.com/api-docs/ZG9jOjM2MzE2MDM4-users
    """

    uri: str = AirweaveField(
        ...,
        description="Unique identifier for the user (Calendly URI).",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Full name of the user.",
        is_name=True,
        embeddable=True,
    )
    email: Optional[str] = AirweaveField(
        None,
        description="Email address of the user.",
        embeddable=True,
    )
    scheduling_url: Optional[str] = AirweaveField(
        None,
        description="Public scheduling URL for the user.",
        embeddable=False,
        unhashable=True,
    )
    timezone: Optional[str] = AirweaveField(
        None,
        description="Timezone of the user.",
        embeddable=True,
    )
    avatar_url: Optional[str] = AirweaveField(
        None,
        description="URL to the user's avatar image.",
        embeddable=False,
        unhashable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the user account was created.",
        is_created_at=True,
        embeddable=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the user account was last updated.",
        is_updated_at=True,
        embeddable=True,
    )
    current_organization: Optional[str] = Field(
        None,
        description="URI of the user's current organization.",
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable user URL."""
        if self.scheduling_url:
            return self.scheduling_url
        user_slug = self.uri.split("/")[-1]
        return f"https://calendly.com/{user_slug}"


class CalendlyEventTypeEntity(BaseEntity):
    """Schema for a Calendly Event Type.

    Event types define the types of meetings that can be scheduled.
    See: https://developer.calendly.com/api-docs/ZG9jOjM2MzE2MDM4-event-types
    """

    uri: str = AirweaveField(
        ...,
        description="Unique identifier for the event type (Calendly URI).",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Name of the event type.",
        is_name=True,
        embeddable=True,
    )
    active: bool = AirweaveField(
        True,
        description="Whether the event type is active and can be scheduled.",
        embeddable=True,
    )
    slug: Optional[str] = AirweaveField(
        None,
        description="Slug for the event type used in scheduling URLs.",
        embeddable=True,
    )
    scheduling_url: Optional[str] = AirweaveField(
        None,
        description="Public scheduling URL for this event type.",
        embeddable=False,
        unhashable=True,
    )
    duration: Optional[int] = Field(
        None,
        description="Duration of the event in minutes.",
    )
    kind: Optional[str] = AirweaveField(
        None,
        description="Kind of event type (e.g., 'solo', 'group', 'collective').",
        embeddable=True,
    )
    pooling_type: Optional[str] = AirweaveField(
        None,
        description="Pooling type for the event (e.g., 'round_robin', 'collective').",
        embeddable=True,
    )
    type: Optional[str] = AirweaveField(
        None,
        description="Type of event (e.g., 'StandardEventType').",
        embeddable=True,
    )
    color: Optional[str] = AirweaveField(
        None,
        description="Color associated with the event type.",
        embeddable=False,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the event type was created.",
        is_created_at=True,
        embeddable=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the event type was last updated.",
        is_updated_at=True,
        embeddable=True,
    )
    internal_note: Optional[str] = AirweaveField(
        None,
        description="Internal note about the event type (not visible to invitees).",
        embeddable=True,
    )
    description_plain: Optional[str] = AirweaveField(
        None,
        description="Plain text description of the event type.",
        embeddable=True,
    )
    description_html: Optional[str] = AirweaveField(
        None,
        description="HTML description of the event type.",
        embeddable=True,
    )
    profile: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Profile information for the event type owner.",
        embeddable=True,
    )
    owner: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Owner of the event type.",
        embeddable=True,
    )
    custom_questions: Optional[List[Dict[str, Any]]] = AirweaveField(
        None,
        description="Custom questions configured for the event type.",
        embeddable=True,
    )
    deleted_at: Optional[datetime] = Field(
        None,
        description="When the event type was deleted (if applicable).",
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable event type URL."""
        if self.scheduling_url:
            return self.scheduling_url
        if self.slug:
            return f"https://calendly.com/{self.slug}"
        return f"https://calendly.com/event_types/{self.uri.split('/')[-1]}"


class CalendlyScheduledEventEntity(BaseEntity):
    """Schema for a Calendly Scheduled Event.

    Scheduled events are actual meetings that have been scheduled.
    See: https://developer.calendly.com/api-docs/ZG9jOjM2MzE2MDM4-scheduled-events
    """

    uri: str = AirweaveField(
        ...,
        description="Unique identifier for the scheduled event (Calendly URI).",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Name of the scheduled event (usually event type name).",
        is_name=True,
        embeddable=True,
    )
    status: Optional[str] = AirweaveField(
        None,
        description="Status of the event (e.g., 'active', 'canceled').",
        embeddable=True,
    )
    start_time: Optional[datetime] = AirweaveField(
        None,
        description="Start time of the scheduled event.",
        embeddable=True,
    )
    end_time: Optional[datetime] = AirweaveField(
        None,
        description="End time of the scheduled event.",
        embeddable=True,
    )
    event_type: Optional[str] = Field(
        None,
        description="URI of the event type for this scheduled event.",
    )
    event_type_name: Optional[str] = AirweaveField(
        None,
        description="Name of the event type.",
        embeddable=True,
    )
    location: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Location information for the event (e.g., Zoom, Google Meet, physical address).",
        embeddable=True,
    )
    invitees_counter: Optional[int] = Field(
        None,
        description="Number of invitees for this event.",
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the scheduled event was created.",
        is_created_at=True,
        embeddable=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the scheduled event was last updated.",
        is_updated_at=True,
        embeddable=True,
    )
    canceled_at: Optional[datetime] = AirweaveField(
        None,
        description="When the event was canceled (if applicable).",
        embeddable=True,
    )
    canceler_name: Optional[str] = AirweaveField(
        None,
        description="Name of the person who canceled the event.",
        embeddable=True,
    )
    cancel_reason: Optional[str] = AirweaveField(
        None,
        description="Reason for cancellation.",
        embeddable=True,
    )
    calendar_event: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Information about the calendar event (e.g., Google Calendar, Outlook).",
        embeddable=True,
    )
    meeting_notes: Optional[str] = AirweaveField(
        None,
        description="Meeting notes for the event.",
        embeddable=True,
    )
    meeting_notes_plain: Optional[str] = AirweaveField(
        None,
        description="Plain text meeting notes.",
        embeddable=True,
    )
    meeting_notes_html: Optional[str] = AirweaveField(
        None,
        description="HTML meeting notes.",
        embeddable=True,
    )
    event_guests: Optional[List[Dict[str, Any]]] = AirweaveField(
        None,
        description="Additional guests for the event.",
        embeddable=True,
    )
    event_memberships: Optional[List[Dict[str, Any]]] = AirweaveField(
        None,
        description="Memberships associated with the event.",
        embeddable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable scheduled event URL."""
        event_id = self.uri.split("/")[-1]
        return f"https://calendly.com/scheduled_events/{event_id}"


class CalendlyEventInviteeEntity(BaseEntity):
    """Schema for a Calendly Event Invitee.

    Event invitees are people who have been invited to scheduled events.
    See: https://developer.calendly.com/api-docs/ZG9jOjM2MzE2MDM4-event-invitees
    """

    uri: str = AirweaveField(
        ...,
        description="Unique identifier for the event invitee (Calendly URI).",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Name of the invitee (constructed from name or email).",
        is_name=True,
        embeddable=True,
    )
    event: str = Field(
        ...,
        description="URI of the scheduled event this invitee belongs to.",
    )
    event_name: Optional[str] = AirweaveField(
        None,
        description="Name of the scheduled event.",
        embeddable=True,
    )
    email: Optional[str] = AirweaveField(
        None,
        description="Email address of the invitee.",
        embeddable=True,
    )
    first_name: Optional[str] = AirweaveField(
        None,
        description="First name of the invitee.",
        embeddable=True,
    )
    last_name: Optional[str] = AirweaveField(
        None,
        description="Last name of the invitee.",
        embeddable=True,
    )
    name_field: Optional[str] = AirweaveField(
        None,
        description="Full name of the invitee.",
        embeddable=True,
    )
    status: Optional[str] = AirweaveField(
        None,
        description="Status of the invitee (e.g., 'active', 'canceled').",
        embeddable=True,
    )
    text_reminder_number: Optional[str] = Field(
        None,
        description="Phone number for text reminders.",
    )
    timezone: Optional[str] = AirweaveField(
        None,
        description="Timezone of the invitee.",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the invitee was created.",
        is_created_at=True,
        embeddable=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the invitee was last updated.",
        is_updated_at=True,
        embeddable=True,
    )
    canceled_at: Optional[datetime] = AirweaveField(
        None,
        description="When the invitee was canceled (if applicable).",
        embeddable=True,
    )
    canceler_name: Optional[str] = AirweaveField(
        None,
        description="Name of the person who canceled the invitee.",
        embeddable=True,
    )
    cancel_reason: Optional[str] = AirweaveField(
        None,
        description="Reason for cancellation.",
        embeddable=True,
    )
    payment: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Payment information for the invitee.",
        embeddable=True,
    )
    questions_and_answers: Optional[List[Dict[str, Any]]] = AirweaveField(
        None,
        description="Questions and answers provided by the invitee.",
        embeddable=True,
    )
    rescheduled: bool = Field(
        False,
        description="Whether the invitee has rescheduled.",
    )
    old_invitee: Optional[str] = Field(
        None,
        description="URI of the old invitee if this is a rescheduled invitee.",
    )
    new_invitee: Optional[str] = Field(
        None,
        description="URI of the new invitee if this invitee was rescheduled.",
    )
    tracking: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Tracking information for the invitee.",
        embeddable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable invitee URL."""
        invitee_id = self.uri.split("/")[-1]
        return f"https://calendly.com/invitees/{invitee_id}"
