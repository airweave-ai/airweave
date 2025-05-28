"""Outlook Calendar entity schemas.

Comprehensive schemas based on the Microsoft Graph API Calendar and Event resources.

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/calendar?view=graph-rest-1.0
  https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity


class OutlookCalendarCalendarEntity(ChunkEntity):
    """Schema for an Outlook Calendar object.

    Based on the Microsoft Graph Calendar resource.
    """

    name: Optional[str] = Field(None, description="The display name of the calendar.")
    color: Optional[str] = Field(
        None, description="Color theme to distinguish the calendar (auto, lightBlue, etc.)."
    )
    hex_color: Optional[str] = Field(
        None, description="Calendar color in hex format (e.g., #FF0000)."
    )
    change_key: Optional[str] = Field(
        None, description="Version identifier that changes when the calendar is modified."
    )
    can_edit: bool = Field(False, description="Whether the user can write to the calendar.")
    can_share: bool = Field(False, description="Whether the user can share the calendar.")
    can_view_private_items: bool = Field(
        False, description="Whether the user can view private events in the calendar."
    )
    is_default_calendar: bool = Field(
        False, description="Whether this is the default calendar for new events."
    )
    is_removable: bool = Field(
        True, description="Whether this calendar can be deleted from the mailbox."
    )
    is_tallying_responses: bool = Field(
        False, description="Whether this calendar supports tracking meeting responses."
    )
    owner: Optional[Dict[str, Any]] = Field(
        None, description="Information about the calendar owner (name and email)."
    )
    allowed_online_meeting_providers: List[str] = Field(
        default_factory=list,
        description="Online meeting providers that can be used (teamsForBusiness, etc.).",
    )
    default_online_meeting_provider: Optional[str] = Field(
        None, description="Default online meeting provider for this calendar."
    )


class OutlookCalendarEventEntity(ChunkEntity):
    """Schema for an Outlook Calendar Event object.

    Based on the Microsoft Graph Event resource.
    """

    subject: Optional[str] = Field(None, description="The subject/title of the event.")
    body_preview: Optional[str] = Field(None, description="Preview of the event body content.")
    body_content: Optional[str] = Field(None, description="Full body content of the event.")
    body_content_type: Optional[str] = Field(
        None, description="Content type of the body (html or text)."
    )

    # Date/time fields
    start_datetime: Optional[datetime] = Field(
        None, description="Start date and time of the event."
    )
    start_timezone: Optional[str] = Field(None, description="Timezone for the start time.")
    end_datetime: Optional[datetime] = Field(None, description="End date and time of the event.")
    end_timezone: Optional[str] = Field(None, description="Timezone for the end time.")

    # Status flags
    is_all_day: bool = Field(False, description="Whether the event lasts all day.")
    is_cancelled: bool = Field(False, description="Whether the event has been cancelled.")
    is_draft: bool = Field(False, description="Whether the event is a draft.")
    is_online_meeting: bool = Field(False, description="Whether this is an online meeting.")
    is_organizer: bool = Field(False, description="Whether the user is the organizer.")
    is_reminder_on: bool = Field(True, description="Whether a reminder is set.")

    # Display and importance
    show_as: Optional[str] = Field(
        None, description="How to show time (free, busy, tentative, oof, etc.)."
    )
    importance: Optional[str] = Field(None, description="Importance level (low, normal, high).")
    sensitivity: Optional[str] = Field(
        None, description="Sensitivity level (normal, personal, private, confidential)."
    )

    # People and responses
    response_status: Optional[Dict[str, Any]] = Field(
        None, description="Response status of the user to the event."
    )
    organizer: Optional[Dict[str, Any]] = Field(
        None, description="Event organizer information (name and email)."
    )
    attendees: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of event attendees with their response status."
    )

    # Location
    location: Optional[Dict[str, Any]] = Field(
        None, description="Primary location information for the event."
    )
    locations: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of all locations associated with the event."
    )

    # Categorization
    categories: List[str] = Field(
        default_factory=list, description="Categories assigned to the event."
    )

    # Timestamps
    created_at: Optional[datetime] = Field(None, description="When the event was created.")
    updated_at: Optional[datetime] = Field(None, description="When the event was last modified.")

    # Links and online meeting
    web_link: Optional[str] = Field(
        None, description="URL to open the event in Outlook on the web."
    )
    online_meeting_url: Optional[str] = Field(None, description="URL to join the online meeting.")
    online_meeting_provider: Optional[str] = Field(
        None, description="Online meeting provider (teamsForBusiness, etc.)."
    )
    online_meeting: Optional[Dict[str, Any]] = Field(
        None, description="Online meeting details and join information."
    )

    # Recurrence and series
    series_master_id: Optional[str] = Field(
        None, description="ID of the master event if this is part of a recurring series."
    )
    recurrence: Optional[Dict[str, Any]] = Field(
        None, description="Recurrence pattern for recurring events."
    )

    # Additional metadata
    reminder_minutes_before_start: Optional[int] = Field(
        None, description="Minutes before start time when reminder fires."
    )
    has_attachments: bool = Field(False, description="Whether the event has attachments.")
    ical_uid: Optional[str] = Field(None, description="Unique identifier across calendars.")
    change_key: Optional[str] = Field(
        None, description="Version identifier that changes when event is modified."
    )
    original_start_timezone: Optional[str] = Field(
        None, description="Start timezone when event was originally created."
    )
    original_end_timezone: Optional[str] = Field(
        None, description="End timezone when event was originally created."
    )
    allow_new_time_proposals: bool = Field(
        True, description="Whether invitees can propose new meeting times."
    )
    hide_attendees: bool = Field(False, description="Whether attendees are hidden from each other.")


class OutlookCalendarAttachmentEntity(FileEntity):
    """Schema for Outlook Calendar Event attachments.

    Represents files attached to calendar events.
    """

    event_id: str = Field(..., description="ID of the event this attachment belongs to")
    attachment_id: str = Field(..., description="Microsoft Graph attachment ID")
    content_type: Optional[str] = Field(None, description="MIME type of the attachment")
    is_inline: bool = Field(False, description="Whether the attachment is inline")
    content_id: Optional[str] = Field(None, description="Content ID for inline attachments")
    last_modified_at: Optional[str] = Field(
        None, description="When the attachment was last modified"
    )

    # Add the metadata field that the file processing pipeline expects
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata about the attachment"
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }
