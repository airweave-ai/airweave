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

Now supports two flows:
  - Non-batching / sequential (default): preserves original behavior.
  - Batching / concurrent (opt-in): gated by `batch_generation` config and uses the
    bounded-concurrency driver in BaseSource across all major I/O points:
      * Per-calendar Calendar resource fetch
      * Per-calendar event listing (still sequential within a calendar due to pagination)
      * Per-calendar Free/Busy fetch

Config (all optional, shown with defaults):
    {
        "batch_generation": False,     # enable/disable concurrent generation
        "batch_size": 30,              # max concurrent workers (calendars processed in parallel)
        "max_queue_size": 200,         # backpressure queue size
        "preserve_order": False,       # maintain calendar order when yielding results
        "stop_on_error": False         # cancel all on first error
    }
"""

import urllib.parse
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import GoogleCalendarConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.google_calendar import (
    GoogleCalendarCalendarEntity,
    GoogleCalendarEventEntity,
    GoogleCalendarFreeBusyEntity,
    GoogleCalendarListEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Google Calendar",
    short_name="google_calendar",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    requires_byoc=True,
    auth_config_class=None,
    config_class=GoogleCalendarConfig,
    labels=["Productivity", "Calendar"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class GoogleCalendarSource(BaseSource):
    """Google Calendar source connector integrates with the Google Calendar API to extract data.

    Synchronizes calendars, events, and free/busy information.

    It provides comprehensive access to your
    Google Calendar scheduling information for productivity and time management insights.
    """

    # -----------------------
    # Construction / Config
    # -----------------------
    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "GoogleCalendarSource":
        """Create a new Google Calendar source instance with the provided OAuth access token."""
        instance = cls()
        instance.access_token = access_token

        # Concurrency configuration (opt-in; mirrors other connectors)
        config = config or {}
        instance.batch_generation = bool(config.get("batch_generation", False))
        instance.batch_size = int(config.get("batch_size", 30))
        instance.max_queue_size = int(config.get("max_queue_size", 200))
        instance.preserve_order = bool(config.get("preserve_order", False))
        instance.stop_on_error = bool(config.get("stop_on_error", False))

        return instance

    # -----------------------
    # HTTP helpers
    # -----------------------
    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict] = None
    ) -> Dict:
        """Make an authenticated GET request to the Google Calendar API."""
        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await client.get(url, headers=headers, params=params)

        # Handle 401 errors by refreshing token and retrying
        if response.status_code == 401:
            self.logger.warning(
                f"Got 401 Unauthorized from Google Calendar API at {url}, refreshing token..."
            )
            await self.refresh_on_unauthorized()

            # Get new token and retry
            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.get(url, headers=headers, params=params)

        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post_with_auth(self, client: httpx.AsyncClient, url: str, json_data: Dict) -> Dict:
        """Make an authenticated POST request to the Google Calendar API."""
        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = await client.post(url, headers=headers, json=json_data)

        # Handle 401 errors by refreshing token and retrying
        if response.status_code == 401:
            self.logger.warning(
                f"Got 401 Unauthorized from Google Calendar API at {url}, refreshing token..."
            )
            await self.refresh_on_unauthorized()

            # Get new token and retry
            access_token = await self.get_access_token()
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            response = await client.post(url, headers=headers, json=json_data)

        response.raise_for_status()
        return response.json()

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse Google Calendar RFC3339 timestamps into timezone-aware datetimes."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    # -----------------------
    # Listing / entity helpers
    # -----------------------
    async def _generate_calendar_list_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[GoogleCalendarListEntity, None]:
        """Yield GoogleCalendarListEntity objects for each calendar in the user's CalendarList."""
        url = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
        params = {"maxResults": 100}
        page = 0
        while True:
            page += 1
            self.logger.info(f"Fetching CalendarList page #{page} with params: {params}")
            data = await self._get_with_auth(client, url, params=params)
            items = data.get("items", []) or []
            self.logger.info(f"CalendarList page #{page} returned {len(items)} items")
            for cal in items:
                # Use summary_override if available, otherwise summary
                name = cal.get("summaryOverride") or cal.get("summary") or "Untitled Calendar"
                calendar_id = cal["id"]
                web_url = f"https://calendar.google.com/calendar/u/0/r?cid={urllib.parse.quote(calendar_id)}"

                yield GoogleCalendarListEntity(
                    breadcrumbs=[],
                    calendar_key=calendar_id,
                    display_name=name,
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
                    web_url_value=web_url,
                )
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                self.logger.info("No more CalendarList pages")
                break
            params["pageToken"] = next_page_token

    async def _generate_calendar_entity(
        self, client: httpx.AsyncClient, calendar_id: str
    ) -> AsyncGenerator[GoogleCalendarCalendarEntity, None]:
        """Yield a GoogleCalendarCalendarEntity for the specified calendar_id."""
        # URL encode the calendar_id to handle special characters like '#'
        encoded_calendar_id = urllib.parse.quote(calendar_id)
        url = f"https://www.googleapis.com/calendar/v3/calendars/{encoded_calendar_id}"
        self.logger.info(f"Fetching Calendar resource for calendar_id={calendar_id}")
        data = await self._get_with_auth(client, url)
        display_name = data.get("summary") or "Untitled Calendar"
        web_url = f"https://calendar.google.com/calendar/u/0/r?cid={encoded_calendar_id}"
        yield GoogleCalendarCalendarEntity(
            breadcrumbs=[],
            calendar_key=data["id"],
            display_name=display_name,
            summary=data.get("summary"),
            description=data.get("description"),
            location=data.get("location"),
            time_zone=data.get("timeZone"),
            web_url_value=web_url,
        )

    async def _generate_event_entities(
        self, client: httpx.AsyncClient, calendar_list_entry: GoogleCalendarListEntity
    ) -> AsyncGenerator[GoogleCalendarEventEntity, None]:
        """Yield GoogleCalendarEventEntities for all events in the given calendar."""
        # URL encode the calendar_id
        encoded_calendar_id = urllib.parse.quote(calendar_list_entry.calendar_key)
        base_url = f"https://www.googleapis.com/calendar/v3/calendars/{encoded_calendar_id}/events"
        params = {"maxResults": 100}
        # Create a breadcrumb for this calendar to attach to events
        cal_breadcrumb = Breadcrumb(
            entity_id=calendar_list_entry.calendar_key,
            name=calendar_list_entry.display_name,
            entity_type=GoogleCalendarListEntity.__name__,
        )
        page = 0
        while True:
            page += 1
            self.logger.info(
                f"Fetching events page #{page} for calendar_id={calendar_list_entry.calendar_key} "
                f"params={params}"
            )
            data = await self._get_with_auth(client, base_url, params=params)
            events = data.get("items", []) or []
            self.logger.info(
                f"Events page #{page} for calendar_id={calendar_list_entry.calendar_key}: "
                f"{len(events)} events"
            )
            for event in events:
                event_id = event["id"]
                # Extract date/time fields
                start_info = event.get("start", {}) or {}
                end_info = event.get("end", {}) or {}
                start_datetime = self._parse_datetime(start_info.get("dateTime"))
                start_date = start_info.get("date")
                end_datetime = self._parse_datetime(end_info.get("dateTime"))
                end_date = end_info.get("date")
                created_time = self._parse_datetime(event.get("created")) or datetime.utcnow()
                updated_time = self._parse_datetime(event.get("updated")) or created_time
                title = event.get("summary") or f"Event {event_id}"
                web_url = event.get("htmlLink")

                yield GoogleCalendarEventEntity(
                    breadcrumbs=[cal_breadcrumb],
                    event_key=event_id,
                    calendar_key=calendar_list_entry.calendar_key,
                    title=title,
                    created_time=created_time,
                    updated_time=updated_time,
                    status=event.get("status"),
                    html_link=event.get("htmlLink"),
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
                    web_url_value=web_url,
                )

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                self.logger.info(
                    f"No more event pages for calendar_id={calendar_list_entry.calendar_key}"
                )
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
            "items": [{"id": calendar_list_entry.calendar_key}],
        }
        self.logger.info(f"Fetching FreeBusy for calendar_id={calendar_list_entry.calendar_key}")
        data = await self._post_with_auth(client, url, request_body)
        cal_busy_info = data.get("calendars", {}).get(calendar_list_entry.calendar_key, {}) or {}
        busy_ranges = cal_busy_info.get("busy", []) or []
        web_url = (
            f"https://calendar.google.com/calendar/u/0/r?cid="
            f"{urllib.parse.quote(calendar_list_entry.calendar_key)}"
        )

        yield GoogleCalendarFreeBusyEntity(
            breadcrumbs=[],
            freebusy_key=f"{calendar_list_entry.calendar_key}_freebusy",
            label=f"Free/Busy for {calendar_list_entry.display_name}",
            calendar_id=calendar_list_entry.calendar_key,
            busy=busy_ranges,
            web_url_value=web_url,
        )

    async def _process_calendars_sequential(
        self, client: httpx.AsyncClient, calendar_list_entries: List[GoogleCalendarListEntity]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process calendars sequentially (original behavior)."""
        # 2) For each calendar in the user's calendarList, yield its Calendar resource
        for cal_list_entity in calendar_list_entries:
            async for calendar_entity in self._generate_calendar_entity(
                client, cal_list_entity.calendar_key
            ):
                yield calendar_entity

        # 3) For each calendar, yield event entities
        for cal_list_entity in calendar_list_entries:
            async for event_entity in self._generate_event_entities(client, cal_list_entity):
                yield event_entity

        # 4) Free/Busy for each calendar
        for cal_list_entity in calendar_list_entries:
            async for freebusy_entity in self._generate_freebusy_entities(client, cal_list_entity):
                yield freebusy_entity

    async def _process_calendars_concurrent(
        self, client: httpx.AsyncClient, calendar_list_entries: List[GoogleCalendarListEntity]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process calendars concurrently using bounded concurrency."""

        async def _calendar_worker(cal_list_entity: GoogleCalendarListEntity):
            """Emit Calendar resource, its events, then free/busy for a single calendar."""
            # 2) Calendar resource
            async for calendar_entity in self._generate_calendar_entity(
                client, cal_list_entity.calendar_key
            ):
                yield calendar_entity

            # 3) Events
            async for event_entity in self._generate_event_entities(client, cal_list_entity):
                yield event_entity

            # 4) Free/Busy
            async for freebusy_entity in self._generate_freebusy_entities(client, cal_list_entity):
                yield freebusy_entity

        async for ent in self.process_entities_concurrent(
            items=calendar_list_entries,
            worker=_calendar_worker,
            batch_size=getattr(self, "batch_size", 30),
            preserve_order=getattr(self, "preserve_order", False),
            stop_on_error=getattr(self, "stop_on_error", False),
            max_queue_size=getattr(self, "max_queue_size", 200),
        ):
            if ent is not None:
                yield ent

    # -----------------------
    # Top-level orchestration
    # -----------------------
    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Google Calendar entities.

        Yields entities in the following order:
          - CalendarList entries
          - Underlying Calendar resources
          - Events for each calendar
          - FreeBusy data for each calendar (7-day window)

        In concurrent mode, Step 2–4 are processed per-calendar using bounded concurrency.
        """
        async with self.http_client() as client:
            # 1) CalendarList (always sequential so we can materialize the list and also yield it)
            calendar_list_entries: List[GoogleCalendarListEntity] = []
            async for cal_list_entity in self._generate_calendar_list_entities(client):
                yield cal_list_entity
                calendar_list_entries.append(cal_list_entity)

            # Short-circuit if no calendars
            if not calendar_list_entries:
                self.logger.info("No calendars found in CalendarList; generation complete.")
                return

            # Choose processing path based on configuration
            if getattr(self, "batch_generation", False):
                async for entity in self._process_calendars_concurrent(
                    client, calendar_list_entries
                ):
                    yield entity
            else:
                async for entity in self._process_calendars_sequential(
                    client, calendar_list_entries
                ):
                    yield entity

    async def validate(self) -> bool:
        """Verify Google Calendar OAuth2 token by pinging the calendarList endpoint."""
        return await self._validate_oauth2(
            ping_url="https://www.googleapis.com/calendar/v3/users/me/calendarList?maxResults=1",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
