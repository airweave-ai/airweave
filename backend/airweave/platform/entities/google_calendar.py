"""Google Calendar entity schemas.

Based on the Google Calendar API reference (readonly scope),
we define entity schemas for:
 - Calendar objects
 - CalendarList objects
 - Event objects
 - FreeBusy responses

They follow a style similar to that of Asana, HubSpot, and Todoist entity schemas.

Reference:
    https://developers.google.com/calendar/api/v3/reference
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse Google Calendar RFC3339 timestamps into timezone-aware datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GoogleCalendarCalendarEntity(BaseEntity):
    """Schema for a Google Calendar object (the underlying calendar resource).

    See: https://developers.google.com/calendar/api/v3/reference/calendars
    """

    calendar_key: str = AirweaveField(
        ...,
        description="Stable calendar identifier (matches Google calendar ID).",
        is_entity_id=True,
    )
    display_name: str = AirweaveField(
        ...,
        description="Display name for the calendar.",
        is_name=True,
        embeddable=True,
    )
    summary: Optional[str] = AirweaveField(
        None, description="Title of the calendar.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Description of the calendar.", embeddable=True
    )
    location: Optional[str] = AirweaveField(
        None, description="Geographic location of the calendar.", embeddable=True
    )
    time_zone: Optional[str] = AirweaveField(
        None, description="The time zone of the calendar.", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Direct link to the calendar in Google Calendar.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> GoogleCalendarCalendarEntity:
        """Build from a Google Calendar API calendar resource JSON object."""
        calendar_id = data["id"]
        encoded = urllib.parse.quote(calendar_id)
        return cls(
            breadcrumbs=[],
            calendar_key=calendar_id,
            display_name=data.get("summary") or "Untitled Calendar",
            summary=data.get("summary"),
            description=data.get("description"),
            location=data.get("location"),
            time_zone=data.get("timeZone"),
            web_url_value=f"https://calendar.google.com/calendar/u/0/r?cid={encoded}",
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable calendar URL."""
        if self.web_url_value:
            return self.web_url_value
        encoded = urllib.parse.quote(self.calendar_key)
        return f"https://calendar.google.com/calendar/u/0/r?cid={encoded}"


class GoogleCalendarListEntity(BaseEntity):
    """Schema for a CalendarList entry, i.e., how the user sees a calendar.

    See: https://developers.google.com/calendar/api/v3/reference/calendarList
    """

    calendar_key: str = AirweaveField(
        ...,
        description="Calendar ID for this list entry.",
        is_entity_id=True,
    )
    display_name: str = AirweaveField(
        ...,
        description="Display name used by the user.",
        is_name=True,
        embeddable=True,
    )
    summary: Optional[str] = AirweaveField(
        None, description="Title of the calendar.", embeddable=True
    )
    summary_override: Optional[str] = AirweaveField(
        None, description="User-defined name for the calendar, if set.", embeddable=True
    )
    color_id: Optional[str] = AirweaveField(
        None, description="Color ID reference for the calendar.", embeddable=False
    )
    background_color: Optional[str] = AirweaveField(
        None, description="Background color in HEX.", embeddable=False
    )
    foreground_color: Optional[str] = AirweaveField(
        None, description="Foreground color in HEX.", embeddable=False
    )
    hidden: bool = AirweaveField(
        False, description="Whether the calendar is hidden from the UI.", embeddable=False
    )
    selected: bool = AirweaveField(
        False, description="Indicates if the calendar is selected in the UI.", embeddable=False
    )
    access_role: Optional[str] = AirweaveField(
        None,
        description=(
            "The effective access role that the authenticated user has on the calendar."
            " E.g., 'owner', 'reader', 'writer'."
        ),
        embeddable=False,
    )
    primary: bool = AirweaveField(
        False, description="Flag to indicate if this is the primary calendar.", embeddable=False
    )
    deleted: bool = AirweaveField(
        False, description="Flag to indicate if this calendar has been deleted.", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Direct link to the calendar in Google Calendar.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> GoogleCalendarListEntity:
        """Build from a Google Calendar API calendarList entry JSON object."""
        calendar_id = data["id"]
        name = data.get("summaryOverride") or data.get("summary") or "Untitled Calendar"
        web_url = f"https://calendar.google.com/calendar/u/0/r?cid={urllib.parse.quote(calendar_id)}"
        return cls(
            breadcrumbs=[],
            calendar_key=calendar_id,
            display_name=name,
            summary=data.get("summary"),
            summary_override=data.get("summaryOverride"),
            color_id=data.get("colorId"),
            background_color=data.get("backgroundColor"),
            foreground_color=data.get("foregroundColor"),
            hidden=data.get("hidden", False),
            selected=data.get("selected", False),
            access_role=data.get("accessRole"),
            primary=data.get("primary", False),
            deleted=data.get("deleted", False),
            web_url_value=web_url,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable calendar URL."""
        if self.web_url_value:
            return self.web_url_value
        encoded = urllib.parse.quote(self.calendar_key)
        return f"https://calendar.google.com/calendar/u/0/r?cid={encoded}"


class GoogleCalendarEventEntity(BaseEntity):
    """Schema for a Google Calendar Event.

    See: https://developers.google.com/calendar/api/v3/reference/events
    """

    event_key: str = AirweaveField(
        ...,
        description="Stable event identifier.",
        is_entity_id=True,
    )
    calendar_key: str = AirweaveField(
        ..., description="Calendar ID for this event.", embeddable=False
    )
    title: str = AirweaveField(
        ...,
        description="Display title of the event.",
        is_name=True,
        embeddable=True,
    )
    created_time: datetime = AirweaveField(
        ...,
        description="Creation timestamp for the event.",
        is_created_at=True,
    )
    updated_time: datetime = AirweaveField(
        ...,
        description="Last modification timestamp for the event.",
        is_updated_at=True,
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the event (e.g., 'confirmed').", embeddable=False
    )
    html_link: Optional[str] = AirweaveField(
        None,
        description="An absolute link to the event in the Google Calendar UI.",
        embeddable=False,
    )
    summary: Optional[str] = AirweaveField(None, description="Title of the event.", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Description of the event.", embeddable=True
    )
    location: Optional[str] = AirweaveField(
        None, description="Geographic location of the event.", embeddable=True
    )
    color_id: Optional[str] = AirweaveField(
        None, description="Color ID for this event.", embeddable=False
    )
    start_datetime: Optional[datetime] = AirweaveField(
        None,
        description=(
            "Start datetime if the event has a specific datetime. "
            "(DateTime from 'start' if 'dateTime' is present.)"
        ),
        embeddable=True,
    )
    start_date: Optional[str] = AirweaveField(
        None,
        description=(
            "Start date if the event is an all-day event. (Date from 'start' if 'date' is present.)"
        ),
        embeddable=True,
    )
    end_datetime: Optional[datetime] = AirweaveField(
        None,
        description=(
            "End datetime if the event has a specific datetime. "
            "(DateTime from 'end' if 'dateTime' is present.)"
        ),
        embeddable=True,
    )
    end_date: Optional[str] = AirweaveField(
        None,
        description=(
            "End date if the event is an all-day event. (Date from 'end' if 'date' is present.)"
        ),
        embeddable=True,
    )
    recurrence: Optional[List[str]] = AirweaveField(
        None,
        description="List of RRULE, EXRULE, RDATE, EXDATE lines for recurring events.",
        embeddable=False,
    )
    recurring_event_id: Optional[str] = AirweaveField(
        None,
        description="For recurring events, identifies the event ID of the recurring series.",
        embeddable=False,
    )
    organizer: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="The organizer of the event. Usually contains 'email' and 'displayName'.",
        embeddable=True,
    )
    creator: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="The creator of the event. Usually contains 'email' and 'displayName'.",
        embeddable=True,
    )
    attendees: Optional[List[Dict[str, Any]]] = AirweaveField(
        None,
        description=(
            "The attendees of the event (each dict typically has 'email', 'responseStatus', etc.)."
        ),
        embeddable=True,
    )
    transparency: Optional[str] = AirweaveField(
        None,
        description=(
            "Specifies whether the event blocks time on the calendar ('opaque') or not "
            "('transparent')."
        ),
        embeddable=False,
    )
    visibility: Optional[str] = AirweaveField(
        None, description="Visibility of the event (e.g., 'default', 'public').", embeddable=False
    )
    conference_data: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Conference data associated with the event, e.g., hangout or meet link.",
        embeddable=True,
    )
    event_type: Optional[str] = AirweaveField(
        None, description="Event type. E.g., 'default' or 'focus'.", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Direct link to the event in Google Calendar.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        calendar_key: str,
        breadcrumbs: List[Breadcrumb],
    ) -> GoogleCalendarEventEntity:
        """Build from a Google Calendar API event resource JSON object.

        Args:
            data: Event JSON from ``events.list``.
            calendar_key: ID of the parent calendar.
            breadcrumbs: Breadcrumb chain (typically [calendar_breadcrumb]).
        """
        event_id = data["id"]
        start_info = data.get("start", {}) or {}
        end_info = data.get("end", {}) or {}

        created_time = _parse_datetime(data.get("created")) or datetime.utcnow()
        updated_time = _parse_datetime(data.get("updated")) or created_time

        return cls(
            breadcrumbs=breadcrumbs,
            event_key=event_id,
            calendar_key=calendar_key,
            title=data.get("summary") or f"Event {event_id}",
            created_time=created_time,
            updated_time=updated_time,
            status=data.get("status"),
            html_link=data.get("htmlLink"),
            summary=data.get("summary"),
            description=data.get("description"),
            location=data.get("location"),
            color_id=data.get("colorId"),
            start_datetime=_parse_datetime(start_info.get("dateTime")),
            start_date=start_info.get("date"),
            end_datetime=_parse_datetime(end_info.get("dateTime")),
            end_date=end_info.get("date"),
            recurrence=data.get("recurrence"),
            recurring_event_id=data.get("recurringEventId"),
            organizer=data.get("organizer"),
            creator=data.get("creator"),
            attendees=data.get("attendees"),
            transparency=data.get("transparency"),
            visibility=data.get("visibility"),
            conference_data=data.get("conferenceData"),
            event_type=data.get("eventType"),
            web_url_value=data.get("htmlLink"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable event URL."""
        if self.web_url_value:
            return self.web_url_value
        return f"https://calendar.google.com/calendar/u/0/r/eventedit/{self.event_key}"


class GoogleCalendarFreeBusyEntity(BaseEntity):
    """Schema for a FreeBusy response entity for a given calendar.

    See: https://developers.google.com/calendar/api/v3/reference/freebusy
    """

    freebusy_key: str = AirweaveField(
        ...,
        description="Stable identifier for the free/busy snapshot.",
        is_entity_id=True,
    )
    label: str = AirweaveField(
        ...,
        description="Display label for the free/busy entry.",
        is_name=True,
        embeddable=True,
    )
    calendar_id: str = AirweaveField(
        ..., description="ID of the calendar for which free/busy is returned.", embeddable=False
    )
    busy: List[Dict[str, str]] = AirweaveField(
        default_factory=list,
        description="List of time ranges during which this calendar is busy.",
        embeddable=True,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Link back to the calendar UI.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable calendar URL for this free/busy entry."""
        if self.web_url_value:
            return self.web_url_value
        encoded = urllib.parse.quote(self.calendar_id)
        return f"https://calendar.google.com/calendar/u/0/r?cid={encoded}"
