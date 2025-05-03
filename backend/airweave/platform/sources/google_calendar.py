"""Google Calendar source implementation.

Retrieves data from a user's Google Calendar (read-only mode):
  - CalendarList entries (the user's list of calendars)
  - Each underlying Calendar resource
  - Events belonging to each Calendar
  - (Optionally) Free/Busy data for each Calendar

Follows the same structure and pattern as other connector implementations
(e.g., Gmail, Asana, Todoist, HubSpot). The entity schemas are defined in
entities/google_calendar.py.

Reference:
    https://developers.google.com/calendar/api/v3/reference
"""

from datetime import datetime, timedelta
from typing import AsyncGenerator, Dict, List, Optional

import httpx

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.google_calendar import (
    GoogleCalendarCalendarEntity,
    GoogleCalendarEventEntity,
    GoogleCalendarFreeBusyEntity,
    GoogleCalendarListEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    "Google Calendar",
    "google_calendar",
    AuthType.oauth2_with_refresh,
    auth_config_class="GoogleAuthConfig",
    labels=["Productivity", "Calendar"],
)
class GoogleCalendarSource(BaseSource):
    """Google Calendar source implementation (read-only).

    Retrieves and yields Google Calendar objects (CalendarList entries,
    Calendars, Events, and Free/Busy data) as entity schemas defined in
    entities/google_calendar.py.
    """

    @classmethod
    async def create(cls, access_token: str) -> "GoogleCalendarSource":
        """Create a new Google Calendar source instance with the provided OAuth access token."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict] = None
    ) -> Dict:
        """Make an authenticated GET request to the Google Calendar API."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def _post_with_auth(self, client: httpx.AsyncClient, url: str, json_data: Dict) -> Dict:
        """Make an authenticated POST request to the Google Calendar API."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        response = await client.post(url, headers=headers, json=json_data)
        response.raise_for_status()
        return response.json()

    async def _generate_calendar_list_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[GoogleCalendarListEntity, None]:
        """Yield GoogleCalendarListEntity objects for each calendar in the user's CalendarList."""
        url = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
        params = {"maxResults": 100}
        while True:
            data = await self._get_with_auth(client, url, params=params)
            items = data.get("items", [])
            for cal in items:
                yield GoogleCalendarListEntity(
                    entity_id=cal["id"],
                    breadcrumbs=[],  # top level entity
                    calendar_id=cal["id"],
                    summary=cal.get("summary"),
                    summary_override=cal.get("summaryOverride"),
                    color_id=cal.get("colorId"),
                    background_color=cal.get("backgroundColor"),
                    foreground_color=cal.get("foregroundColor"),
                    hidden=cal.get("hidden", False),
                    selected=cal.get("selected", False),
                    access_role=cal.get("accessRole"),
                    primary=cal.get("primary", False),
                    deleted=cal.get("deleted", False),
                )
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token

    async def _generate_calendar_entities(
        self, client: httpx.AsyncClient, calendar_id: str
    ) -> AsyncGenerator[GoogleCalendarCalendarEntity, None]:
        """Yield a GoogleCalendarCalendarEntity for the specified calendar_id."""
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}"
        data = await self._get_with_auth(client, url)
        yield GoogleCalendarCalendarEntity(
            entity_id=data["id"],
            breadcrumbs=[],  # each calendar is top-level (matching the underlying resource)
            calendar_id=data["id"],
            summary=data.get("summary"),
            description=data.get("description"),
            location=data.get("location"),
            time_zone=data.get("timeZone"),
        )

    async def _generate_event_entities(
        self, client: httpx.AsyncClient, calendar_list_entry: GoogleCalendarListEntity
    ) -> AsyncGenerator[GoogleCalendarEventEntity, None]:
        """Yield GoogleCalendarEventEntities for all events in the given calendar."""
        base_url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_list_entry.calendar_id}/events"
        params = {"maxResults": 100}
        # Create a breadcrumb for this calendar to attach to events
        cal_breadcrumb = Breadcrumb(
            entity_id=calendar_list_entry.calendar_id,
            name=(calendar_list_entry.summary_override or calendar_list_entry.summary or "")[:50],
            type="calendar",
        )
        while True:
            data = await self._get_with_auth(client, base_url, params=params)
            for event in data.get("items", []):
                event_id = event["id"]
                # Extract date/time fields
                start_info = event.get("start", {})
                end_info = event.get("end", {})
                start_datetime = start_info.get("dateTime")
                start_date = start_info.get("date")
                end_datetime = end_info.get("dateTime")
                end_date = end_info.get("date")
                created_at_str = event.get("created")
                updated_at_str = event.get("updated")

                # Convert created/updated to datetime if present
                created_at = (
                    datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    if created_at_str
                    else None
                )
                updated_at = (
                    datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                    if updated_at_str
                    else None
                )

                yield GoogleCalendarEventEntity(
                    entity_id=event_id,
                    breadcrumbs=[cal_breadcrumb],
                    event_id=event_id,
                    status=event.get("status"),
                    html_link=event.get("htmlLink"),
                    created_at=created_at,
                    updated_at=updated_at,
                    summary=event.get("summary"),
                    description=event.get("description"),
                    location=event.get("location"),
                    color_id=event.get("colorId"),
                    start_datetime=start_datetime,
                    start_date=start_date,
                    end_datetime=end_datetime,
                    end_date=end_date,
                    recurrence=event.get("recurrence"),
                    recurring_event_id=event.get("recurringEventId"),
                    organizer=event.get("organizer"),
                    creator=event.get("creator"),
                    attendees=event.get("attendees"),
                    transparency=event.get("transparency"),
                    visibility=event.get("visibility"),
                    conference_data=event.get("conferenceData"),
                    event_type=event.get("eventType"),
                )

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token

    async def _generate_freebusy_entities(
        self, client: httpx.AsyncClient, calendar_list_entry: GoogleCalendarListEntity
    ) -> AsyncGenerator[GoogleCalendarFreeBusyEntity, None]:
        """Yield a GoogleCalendarFreeBusyEntity for the next 7 days for each calendar."""
        url = "https://www.googleapis.com/calendar/v3/freeBusy"
        now = datetime.utcnow()
        in_7_days = now + timedelta(days=7)

        request_body = {
            "timeMin": now.isoformat() + "Z",
            "timeMax": in_7_days.isoformat() + "Z",
            "items": [{"id": calendar_list_entry.calendar_id}],
        }
        data = await self._post_with_auth(client, url, request_body)
        cal_busy_info = data.get("calendars", {}).get(calendar_list_entry.calendar_id, {})
        busy_ranges = cal_busy_info.get("busy", [])

        yield GoogleCalendarFreeBusyEntity(
            entity_id=calendar_list_entry.calendar_id + "_freebusy",
            breadcrumbs=[],
            calendar_id=calendar_list_entry.calendar_id,
            busy=busy_ranges,
        )

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Google Calendar entities.

        Yields entities in the following order:
          - CalendarList entries
          - Underlying Calendar resources
          - Events for each calendar
          - FreeBusy data for each calendar (7-day window)
        """
        async with httpx.AsyncClient() as client:
            # 1) Get the user's calendarList
            #    For each item, yield a CalendarList entity and store in memory for subsequent calls
            calendar_list_entries: List[GoogleCalendarListEntity] = []
            async for cal_list_entity in self._generate_calendar_list_entities(client):
                yield cal_list_entity
                calendar_list_entries.append(cal_list_entity)

            # 2) For each calendar in the user's calendarList, yield its Calendar resource
            for cal_list_entity in calendar_list_entries:
                async for calendar_entity in self._generate_calendar_entities(
                    client, cal_list_entity.calendar_id
                ):
                    yield calendar_entity

            # 3) For each calendar, yield event entities
            for cal_list_entity in calendar_list_entries:
                async for event_entity in self._generate_event_entities(client, cal_list_entity):
                    yield event_entity

            # 4) (Optionally) yield free/busy data for each calendar
            for cal_list_entity in calendar_list_entries:
                async for freebusy_entity in self._generate_freebusy_entities(
                    client, cal_list_entity
                ):
                    yield freebusy_entity
