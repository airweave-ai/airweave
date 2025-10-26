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

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class GoogleCalendarCalendarEntity(BaseEntity):
    """Schema for a Google Calendar object (the underlying calendar resource).

    See: https://developers.google.com/calendar/api/v3/reference/calendars
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the calendar ID)
    # - breadcrumbs (empty - calendars are top-level)
    # - name (from summary)
    # - created_at (None - calendars don't have creation timestamp)
    # - updated_at (None - calendars don't have modification timestamp)

    # API fields
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


class GoogleCalendarListEntity(BaseEntity):
    """Schema for a CalendarList entry, i.e., how the user sees a calendar.

    See: https://developers.google.com/calendar/api/v3/reference/calendarList
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the calendar ID)
    # - breadcrumbs (empty - calendar list entries are top-level)
    # - name (from summary_override or summary)
    # - created_at (None - calendar list entries don't have timestamps)
    # - updated_at (None - calendar list entries don't have timestamps)

    # API fields
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


class GoogleCalendarEventEntity(BaseEntity):
    """Schema for a Google Calendar Event.

    See: https://developers.google.com/calendar/api/v3/reference/events
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the event ID)
    # - breadcrumbs (calendar breadcrumb)
    # - name (from summary)
    # - created_at (from created timestamp)
    # - updated_at (from updated timestamp)

    # API fields
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


class GoogleCalendarFreeBusyEntity(BaseEntity):
    """Schema for a FreeBusy response entity for a given calendar.

    See: https://developers.google.com/calendar/api/v3/reference/freebusy
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (calendar_id + "_freebusy")
    # - breadcrumbs (empty - free/busy entries are top-level)
    # - name (generic name for free/busy)
    # - created_at (None - free/busy queries don't have timestamps)
    # - updated_at (None - free/busy queries don't have timestamps)

    # API fields
    calendar_id: str = AirweaveField(
        ..., description="ID of the calendar for which free/busy is returned.", embeddable=False
    )
    busy: List[Dict[str, str]] = AirweaveField(
        default_factory=list,
        description="List of time ranges during which this calendar is busy.",
        embeddable=True,
    )
