"""Outlook Calendar entity schemas.

Comprehensive schemas based on the Microsoft Graph API Calendar and Event resources.

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/calendar?view=graph-rest-1.0
  https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb, FileEntity


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse Microsoft Graph simple datetime strings."""
    if not value:
        return None
    try:
        if "T" in value:
            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")
            return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        pass
    return None


def _parse_datetime_field(dt_obj: Optional[Dict]) -> Optional[datetime]:
    """Parse structured ``{dateTime, timeZone}`` datetime from Microsoft Graph."""
    if not dt_obj or not dt_obj.get("dateTime"):
        return None
    try:
        dt_str = dt_obj["dateTime"]
        if "T" in dt_str:
            if dt_str.endswith("Z"):
                dt_str = dt_str.replace("Z", "+00:00")
            elif "+" not in dt_str and "-" not in dt_str[-6:]:
                dt_str += "+00:00"
            return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        pass
    return None


class OutlookCalendarCalendarEntity(BaseEntity):
    """Schema for an Outlook Calendar object.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/calendar?view=graph-rest-1.0
    """

    id: str = AirweaveField(
        ...,
        description="Calendar ID from Microsoft Graph.",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Calendar display name.",
        is_name=True,
        embeddable=True,
    )
    color: Optional[str] = AirweaveField(
        None,
        description="Color theme to distinguish the calendar (auto, lightBlue, etc.).",
        embeddable=False,
    )
    hex_color: Optional[str] = AirweaveField(
        None, description="Calendar color in hex format (e.g., #FF0000).", embeddable=False
    )
    change_key: Optional[str] = AirweaveField(
        None,
        description="Version identifier that changes when the calendar is modified.",
        embeddable=False,
    )
    can_edit: bool = AirweaveField(
        False, description="Whether the user can write to the calendar.", embeddable=False
    )
    can_share: bool = AirweaveField(
        False, description="Whether the user can share the calendar.", embeddable=False
    )
    can_view_private_items: bool = AirweaveField(
        False,
        description="Whether the user can view private events in the calendar.",
        embeddable=False,
    )
    is_default_calendar: bool = AirweaveField(
        False, description="Whether this is the default calendar for new events.", embeddable=False
    )
    is_removable: bool = AirweaveField(
        True, description="Whether this calendar can be deleted from the mailbox.", embeddable=False
    )
    is_tallying_responses: bool = AirweaveField(
        False,
        description="Whether this calendar supports tracking meeting responses.",
        embeddable=False,
    )
    owner: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the calendar owner (name and email).", embeddable=True
    )
    allowed_online_meeting_providers: List[str] = AirweaveField(
        default_factory=list,
        description="Online meeting providers that can be used (teamsForBusiness, etc.).",
        embeddable=False,
    )
    default_online_meeting_provider: Optional[str] = AirweaveField(
        None, description="Default online meeting provider for this calendar.", embeddable=False
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="URL to open this calendar in Outlook on the web.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Best-effort calendar URL."""
        if self.web_url_override:
            return self.web_url_override
        return "https://outlook.office.com/calendar/"


class OutlookCalendarEventEntity(BaseEntity):
    """Schema for an Outlook Calendar Event object.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0
    """

    id: str = AirweaveField(
        ...,
        description="Event ID from Microsoft Graph.",
        is_entity_id=True,
    )
    subject: str = AirweaveField(
        ...,
        description="The subject/title of the event.",
        embeddable=True,
        is_name=True,
    )
    body_preview: Optional[str] = AirweaveField(
        None, description="Preview of the event body content.", embeddable=True
    )
    body_content: Optional[str] = AirweaveField(
        None, description="Full body content of the event.", embeddable=True
    )
    body_content_type: Optional[str] = AirweaveField(
        None, description="Content type of the body (html or text).", embeddable=False
    )
    start_datetime: Optional[Any] = AirweaveField(
        None, description="Start date and time of the event.", embeddable=True
    )
    start_timezone: Optional[str] = AirweaveField(
        None, description="Timezone for the start time.", embeddable=False
    )
    end_datetime: Optional[Any] = AirweaveField(
        None, description="End date and time of the event.", embeddable=True
    )
    end_timezone: Optional[str] = AirweaveField(
        None, description="Timezone for the end time.", embeddable=False
    )
    is_all_day: bool = AirweaveField(
        False, description="Whether the event lasts all day.", embeddable=False
    )
    is_cancelled: bool = AirweaveField(
        False, description="Whether the event has been cancelled.", embeddable=True
    )
    is_draft: bool = AirweaveField(
        False, description="Whether the event is a draft.", embeddable=False
    )
    is_online_meeting: bool = AirweaveField(
        False, description="Whether this is an online meeting.", embeddable=True
    )
    is_organizer: bool = AirweaveField(
        False, description="Whether the user is the organizer.", embeddable=False
    )
    is_reminder_on: bool = AirweaveField(
        True, description="Whether a reminder is set.", embeddable=False
    )
    show_as: Optional[str] = AirweaveField(
        None, description="How to show time (free, busy, tentative, oof, etc.).", embeddable=False
    )
    importance: Optional[str] = AirweaveField(
        None, description="Importance level (low, normal, high).", embeddable=True
    )
    sensitivity: Optional[str] = AirweaveField(
        None,
        description="Sensitivity level (normal, personal, private, confidential).",
        embeddable=False,
    )
    response_status: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Response status of the user to the event.", embeddable=False
    )
    organizer: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Event organizer information (name and email).", embeddable=True
    )
    attendees: Optional[List[Dict[str, Any]]] = AirweaveField(
        None, description="List of event attendees with their response status.", embeddable=True
    )
    location: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Primary location information for the event.", embeddable=True
    )
    locations: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="List of all locations associated with the event.",
        embeddable=True,
    )
    categories: List[str] = AirweaveField(
        default_factory=list, description="Categories assigned to the event.", embeddable=True
    )
    web_link: Optional[str] = AirweaveField(
        None, description="URL to open the event in Outlook on the web.", embeddable=False
    )
    online_meeting_url: Optional[str] = AirweaveField(
        None, description="URL to join the online meeting.", embeddable=True
    )
    online_meeting_provider: Optional[str] = AirweaveField(
        None, description="Online meeting provider (teamsForBusiness, etc.).", embeddable=False
    )
    online_meeting: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Online meeting details and join information.", embeddable=True
    )
    series_master_id: Optional[str] = AirweaveField(
        None,
        description="ID of the master event if this is part of a recurring series.",
        embeddable=False,
    )
    recurrence: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Recurrence pattern for recurring events.", embeddable=True
    )
    reminder_minutes_before_start: Optional[int] = AirweaveField(
        None, description="Minutes before start time when reminder fires.", embeddable=False
    )
    has_attachments: bool = AirweaveField(
        False, description="Whether the event has attachments.", embeddable=False
    )
    ical_uid: Optional[str] = AirweaveField(
        None, description="Unique identifier across calendars.", embeddable=False
    )
    change_key: Optional[str] = AirweaveField(
        None,
        description="Version identifier that changes when event is modified.",
        embeddable=False,
    )
    original_start_timezone: Optional[str] = AirweaveField(
        None, description="Start timezone when event was originally created.", embeddable=False
    )
    original_end_timezone: Optional[str] = AirweaveField(
        None, description="End timezone when event was originally created.", embeddable=False
    )
    allow_new_time_proposals: bool = AirweaveField(
        True, description="Whether invitees can propose new meeting times.", embeddable=False
    )
    hide_attendees: bool = AirweaveField(
        False, description="Whether attendees are hidden from each other.", embeddable=False
    )
    created_datetime: Optional[Any] = AirweaveField(
        None,
        description="When the event was created.",
        embeddable=False,
        is_created_at=True,
    )
    last_modified_datetime: Optional[Any] = AirweaveField(
        None,
        description="When the event was last modified.",
        embeddable=False,
        is_updated_at=True,
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="URL to open the event in Outlook on the web.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, cal_breadcrumb: Breadcrumb
    ) -> OutlookCalendarEventEntity:
        """Construct from a Microsoft Graph event resource."""
        event_id = data["id"]
        subject = data.get("subject", "No Subject")
        start_info = data.get("start", {})
        end_info = data.get("end", {})
        body = data.get("body") or {}
        created_dt = _parse_dt(data.get("createdDateTime"))
        updated_dt = _parse_dt(data.get("lastModifiedDateTime"))
        web_link = data.get("webLink")

        return cls(
            entity_id=event_id,
            breadcrumbs=[cal_breadcrumb],
            name=subject,
            created_at=created_dt,
            updated_at=updated_dt,
            id=event_id,
            subject=subject,
            body_preview=data.get("bodyPreview"),
            body_content=body.get("content"),
            body_content_type=body.get("contentType"),
            start_datetime=_parse_datetime_field(start_info),
            start_timezone=start_info.get("timeZone"),
            end_datetime=_parse_datetime_field(end_info),
            end_timezone=end_info.get("timeZone"),
            is_all_day=data.get("isAllDay", False),
            is_cancelled=data.get("isCancelled", False),
            is_draft=data.get("isDraft", False),
            is_online_meeting=data.get("isOnlineMeeting", False),
            is_organizer=data.get("isOrganizer", False),
            is_reminder_on=data.get("isReminderOn", True),
            show_as=data.get("showAs"),
            importance=data.get("importance"),
            sensitivity=data.get("sensitivity"),
            response_status=data.get("responseStatus"),
            organizer=data.get("organizer"),
            attendees=data.get("attendees"),
            location=data.get("location"),
            locations=data.get("locations", []),
            categories=data.get("categories", []),
            web_link=web_link,
            online_meeting_url=data.get("onlineMeetingUrl"),
            online_meeting_provider=data.get("onlineMeetingProvider"),
            online_meeting=data.get("onlineMeeting"),
            series_master_id=data.get("seriesMasterId"),
            recurrence=data.get("recurrence"),
            reminder_minutes_before_start=data.get("reminderMinutesBeforeStart"),
            has_attachments=data.get("hasAttachments", False),
            ical_uid=data.get("iCalUId"),
            change_key=data.get("changeKey"),
            original_start_timezone=data.get("originalStartTimeZone"),
            original_end_timezone=data.get("originalEndTimeZone"),
            allow_new_time_proposals=data.get("allowNewTimeProposals", True),
            hide_attendees=data.get("hideAttendees", False),
            created_datetime=created_dt,
            last_modified_datetime=updated_dt,
            web_url_override=web_link,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL exposed to clients for opening the event."""
        if self.web_url_override:
            return self.web_url_override
        if self.online_meeting_url:
            return self.online_meeting_url
        if self.web_link:
            return self.web_link
        return f"https://outlook.office.com/calendar/item/{self.id}"


class OutlookCalendarAttachmentEntity(FileEntity):
    """Schema for Outlook Calendar Event attachments.

    Represents files attached to calendar events.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/attachment?view=graph-rest-1.0
    """

    composite_id: str = AirweaveField(
        ...,
        description="Composite attachment ID (event + attachment).",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Attachment display name.",
        embeddable=True,
        is_name=True,
    )
    event_id: str = AirweaveField(
        ..., description="ID of the event this attachment belongs to", embeddable=False
    )
    attachment_id: str = AirweaveField(
        ..., description="Microsoft Graph attachment ID", embeddable=False
    )
    content_type: Optional[str] = AirweaveField(
        None, description="MIME type of the attachment", embeddable=False
    )
    is_inline: bool = AirweaveField(
        False, description="Whether the attachment is inline", embeddable=False
    )
    content_id: Optional[str] = AirweaveField(
        None, description="Content ID for inline attachments", embeddable=False
    )
    last_modified_at: Optional[str] = AirweaveField(
        None, description="When the attachment was last modified", embeddable=False
    )
    event_web_url: Optional[str] = AirweaveField(
        None,
        description="URL to the parent event.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        event_id: str,
        breadcrumbs: List[Breadcrumb],
        event_web_url: Optional[str] = None,
    ) -> Optional[OutlookCalendarAttachmentEntity]:
        """Construct from a Microsoft Graph attachment resource.

        Returns None for non-file attachments.
        """
        attachment_type = data.get("@odata.type", "")
        if "#microsoft.graph.fileAttachment" not in attachment_type:
            return None

        attachment_id = data["id"]
        attachment_name = data.get("name", "unknown")
        mime_type = data.get("contentType") or "application/octet-stream"
        size = data.get("size", 0)

        if mime_type and "/" in mime_type:
            file_type = mime_type.split("/")[0]
        else:
            ext = os.path.splitext(attachment_name)[1].lower().lstrip(".")
            file_type = ext if ext else "file"

        return cls(
            composite_id=f"{event_id}_attachment_{attachment_id}",
            breadcrumbs=list(breadcrumbs),
            name=attachment_name,
            url=f"outlook://calendar/attachment/{event_id}/{attachment_id}",
            size=size,
            file_type=file_type,
            mime_type=mime_type,
            local_path=None,
            event_id=event_id,
            attachment_id=attachment_id,
            content_type=data.get("contentType"),
            is_inline=data.get("isInline", False),
            content_id=data.get("contentId"),
            last_modified_at=data.get("lastModifiedDateTime"),
            event_web_url=event_web_url,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the parent event."""
        if self.event_web_url:
            return self.event_web_url
        return f"https://outlook.office.com/calendar/item/{self.event_id}"
