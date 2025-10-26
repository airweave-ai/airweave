"""Outlook Calendar entity schemas.

Comprehensive schemas based on the Microsoft Graph API Calendar and Event resources.

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/calendar?view=graph-rest-1.0
  https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import FileEntity


class OutlookCalendarCalendarEntity(BaseEntity):
    """Schema for an Outlook Calendar object.

    Based on the Microsoft Graph Calendar resource.
    """

    name: Optional[str] = AirweaveField(
        None, description="The display name of the calendar.", embeddable=True
    )
    color: Optional[str] = AirweaveField(
        None, description="Color theme to distinguish the calendar (auto, lightBlue, etc.)."
    )
    hex_color: Optional[str] = AirweaveField(
        None, description="Calendar color in hex format (e.g., #FF0000)."
    )
    change_key: Optional[str] = AirweaveField(
        None, description="Version identifier that changes when the calendar is modified."
    )
    can_edit: bool = AirweaveField(False, description="Whether the user can write to the calendar.")
    can_share: bool = AirweaveField(False, description="Whether the user can share the calendar.")
    can_view_private_items: bool = AirweaveField(
        False, description="Whether the user can view private events in the calendar."
    )
    is_default_calendar: bool = AirweaveField(
        False, description="Whether this is the default calendar for new events."
    )
    is_removable: bool = AirweaveField(
        True, description="Whether this calendar can be deleted from the mailbox."
    )
    is_tallying_responses: bool = AirweaveField(
        False, description="Whether this calendar supports tracking meeting responses."
    )
    owner: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the calendar owner (name and email).", embeddable=True
    )
    allowed_online_meeting_providers: List[str] = AirweaveField(
        default_factory=list,
        description="Online meeting providers that can be used (teamsForBusiness, etc.).",
    )
    default_online_meeting_provider: Optional[str] = AirweaveField(
        None, description="Default online meeting provider for this calendar."
    )


class OutlookCalendarEventEntity(BaseEntity):
    """Schema for an Outlook Calendar Event object.

    Based on the Microsoft Graph Event resource.
    """

    subject: Optional[str] = AirweaveField(
        None, description="The subject/title of the event.", embeddable=True
    )
    body_preview: Optional[str] = AirweaveField(
        None, description="Preview of the event body content.", embeddable=True
    )
    body_content: Optional[str] = AirweaveField(
        None, description="Full body content of the event.", embeddable=True
    )
    body_content_type: Optional[str] = AirweaveField(
        None, description="Content type of the body (html or text)."
    )

    # Date/time fields
    start_datetime: Optional[datetime] = AirweaveField(
        None, description="Start date and time of the event.", embeddable=True
    )
    start_timezone: Optional[str] = AirweaveField(None, description="Timezone for the start time.")
    end_datetime: Optional[datetime] = AirweaveField(
        None, description="End date and time of the event.", embeddable=True
    )
    end_timezone: Optional[str] = AirweaveField(None, description="Timezone for the end time.")

    # Status flags
    is_all_day: bool = AirweaveField(False, description="Whether the event lasts all day.")
    is_cancelled: bool = AirweaveField(False, description="Whether the event has been cancelled.")
    is_draft: bool = AirweaveField(False, description="Whether the event is a draft.")
    is_online_meeting: bool = AirweaveField(False, description="Whether this is an online meeting.")
    is_organizer: bool = AirweaveField(False, description="Whether the user is the organizer.")
    is_reminder_on: bool = AirweaveField(True, description="Whether a reminder is set.")

    # Display and importance
    show_as: Optional[str] = AirweaveField(
        None, description="How to show time (free, busy, tentative, oof, etc.)."
    )
    importance: Optional[str] = AirweaveField(
        None, description="Importance level (low, normal, high)."
    )
    sensitivity: Optional[str] = AirweaveField(
        None, description="Sensitivity level (normal, personal, private, confidential)."
    )

    # People and responses
    response_status: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Response status of the user to the event."
    )
    organizer: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Event organizer information (name and email).", embeddable=True
    )
    attendees: Optional[List[Dict[str, Any]]] = AirweaveField(
        None, description="List of event attendees with their response status.", embeddable=True
    )

    # Location
    location: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Primary location information for the event.", embeddable=True
    )
    locations: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="List of all locations associated with the event.",
        embeddable=True,
    )

    # Categorization
    categories: List[str] = AirweaveField(
        default_factory=list, description="Categories assigned to the event.", embeddable=True
    )

    # Timestamps
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the event was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the event was last modified.", is_updated_at=True
    )

    # Links and online meeting
    web_link: Optional[str] = AirweaveField(
        None, description="URL to open the event in Outlook on the web."
    )
    online_meeting_url: Optional[str] = AirweaveField(
        None, description="URL to join the online meeting."
    )
    online_meeting_provider: Optional[str] = AirweaveField(
        None, description="Online meeting provider (teamsForBusiness, etc.)."
    )
    online_meeting: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Online meeting details and join information."
    )

    # Recurrence and series
    series_master_id: Optional[str] = AirweaveField(
        None, description="ID of the master event if this is part of a recurring series."
    )
    recurrence: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Recurrence pattern for recurring events."
    )

    # Additional metadata
    reminder_minutes_before_start: Optional[int] = AirweaveField(
        None, description="Minutes before start time when reminder fires."
    )
    has_attachments: bool = AirweaveField(False, description="Whether the event has attachments.")
    ical_uid: Optional[str] = AirweaveField(None, description="Unique identifier across calendars.")
    change_key: Optional[str] = AirweaveField(
        None, description="Version identifier that changes when event is modified."
    )
    original_start_timezone: Optional[str] = AirweaveField(
        None, description="Start timezone when event was originally created."
    )
    original_end_timezone: Optional[str] = AirweaveField(
        None, description="End timezone when event was originally created."
    )
    allow_new_time_proposals: bool = AirweaveField(
        True, description="Whether invitees can propose new meeting times."
    )
    hide_attendees: bool = AirweaveField(
        False, description="Whether attendees are hidden from each other."
    )


class OutlookCalendarAttachmentEntity(FileEntity):
    """Schema for Outlook Calendar Event attachments.

    Represents files attached to calendar events.
    """

    event_id: str = AirweaveField(..., description="ID of the event this attachment belongs to")
    attachment_id: str = AirweaveField(..., description="Microsoft Graph attachment ID")
    content_type: Optional[str] = AirweaveField(None, description="MIME type of the attachment")
    is_inline: bool = AirweaveField(False, description="Whether the attachment is inline")
    content_id: Optional[str] = AirweaveField(None, description="Content ID for inline attachments")
    last_modified_at: Optional[str] = AirweaveField(
        None, description="When the attachment was last modified"
    )

    # Add the metadata field that the file processing pipeline expects
    metadata: Optional[Dict[str, Any]] = AirweaveField(
        default_factory=dict, description="Additional metadata about the attachment"
    )
