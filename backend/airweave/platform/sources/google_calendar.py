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

from __future__ import annotations

import urllib.parse
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import GoogleCalendarConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.google_calendar import (
    GoogleCalendarCalendarEntity,
    GoogleCalendarEventEntity,
    GoogleCalendarFreeBusyEntity,
    GoogleCalendarListEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup


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
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: GoogleCalendarConfig,
    ) -> GoogleCalendarSource:
        """Create a new Google Calendar source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)

        config_dict = config.model_dump() if config else {}
        instance.batch_generation = bool(config_dict.get("batch_generation", False))
        instance.batch_size = int(config_dict.get("batch_size", 30))
        instance.max_queue_size = int(config_dict.get("max_queue_size", 200))
        instance.preserve_order = bool(config_dict.get("preserve_order", False))
        instance.stop_on_error = bool(config_dict.get("stop_on_error", False))

        return instance

    # -----------------------
    # HTTP helpers
    # -----------------------

    async def _authed_headers(self) -> Dict[str, str]:
        """Build Authorization headers with a fresh token."""
        token = await self.auth.get_token()
        return {"Authorization": f"Bearer {token}"}

    async def _refresh_and_get_headers(self) -> Dict[str, str]:
        """Force-refresh the token and return updated headers."""
        new_token = await self.auth.force_refresh()
        return {"Authorization": f"Bearer {new_token}"}

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make an authenticated GET request to the Google Calendar API."""
        headers = await self._authed_headers()
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning(
                f"Got 401 Unauthorized from Google Calendar API at {url}, refreshing token..."
            )
            headers = await self._refresh_and_get_headers()
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post(self, url: str, json_data: Dict) -> Dict:
        """Make an authenticated POST request to the Google Calendar API."""
        headers = await self._authed_headers()
        headers["Content-Type"] = "application/json"
        response = await self.http_client.post(url, headers=headers, json=json_data)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning(
                f"Got 401 Unauthorized from Google Calendar API at {url}, refreshing token..."
            )
            headers = await self._refresh_and_get_headers()
            headers["Content-Type"] = "application/json"
            response = await self.http_client.post(url, headers=headers, json=json_data)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # -----------------------
    # Listing / entity helpers
    # -----------------------
    async def _generate_calendar_list_entities(
        self,
    ) -> AsyncGenerator[GoogleCalendarListEntity, None]:
        """Yield GoogleCalendarListEntity objects for each calendar in the user's CalendarList."""
        url = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
        params: Dict[str, Any] = {"maxResults": 100}
        page = 0
        while True:
            page += 1
            self.logger.info(f"Fetching CalendarList page #{page} with params: {params}")
            data = await self._get(url, params=params)
            items = data.get("items", []) or []
            self.logger.info(f"CalendarList page #{page} returned {len(items)} items")
            for cal in items:
                yield GoogleCalendarListEntity.from_api(cal)
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                self.logger.info("No more CalendarList pages")
                break
            params["pageToken"] = next_page_token

    async def _generate_calendar_entity(
        self, calendar_id: str
    ) -> AsyncGenerator[GoogleCalendarCalendarEntity, None]:
        """Yield a GoogleCalendarCalendarEntity for the specified calendar_id."""
        encoded_calendar_id = urllib.parse.quote(calendar_id)
        url = f"https://www.googleapis.com/calendar/v3/calendars/{encoded_calendar_id}"
        self.logger.info(f"Fetching Calendar resource for calendar_id={calendar_id}")
        data = await self._get(url)
        yield GoogleCalendarCalendarEntity.from_api(data)

    async def _generate_event_entities(
        self, calendar_list_entry: GoogleCalendarListEntity
    ) -> AsyncGenerator[GoogleCalendarEventEntity, None]:
        """Yield GoogleCalendarEventEntities for all events in the given calendar."""
        encoded_calendar_id = urllib.parse.quote(calendar_list_entry.calendar_key)
        base_url = f"https://www.googleapis.com/calendar/v3/calendars/{encoded_calendar_id}/events"
        params: Dict[str, Any] = {"maxResults": 100}
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
            data = await self._get(base_url, params=params)
            events = data.get("items", []) or []
            self.logger.info(
                f"Events page #{page} for calendar_id={calendar_list_entry.calendar_key}: "
                f"{len(events)} events"
            )
            for event in events:
                yield GoogleCalendarEventEntity.from_api(
                    event,
                    calendar_key=calendar_list_entry.calendar_key,
                    breadcrumbs=[cal_breadcrumb],
                )

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                self.logger.info(
                    f"No more event pages for calendar_id={calendar_list_entry.calendar_key}"
                )
                break
            params["pageToken"] = next_page_token

    async def _generate_freebusy_entities(
        self, calendar_list_entry: GoogleCalendarListEntity
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
        data = await self._post(url, request_body)
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
        self, calendar_list_entries: List[GoogleCalendarListEntity]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process calendars sequentially (original behavior)."""
        for cal_list_entity in calendar_list_entries:
            async for calendar_entity in self._generate_calendar_entity(
                cal_list_entity.calendar_key
            ):
                yield calendar_entity

        for cal_list_entity in calendar_list_entries:
            async for event_entity in self._generate_event_entities(cal_list_entity):
                yield event_entity

        for cal_list_entity in calendar_list_entries:
            async for freebusy_entity in self._generate_freebusy_entities(cal_list_entity):
                yield freebusy_entity

    async def _process_calendars_concurrent(
        self, calendar_list_entries: List[GoogleCalendarListEntity]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process calendars concurrently using bounded concurrency."""

        async def _calendar_worker(cal_list_entity: GoogleCalendarListEntity):
            """Emit Calendar resource, its events, then free/busy for a single calendar."""
            async for calendar_entity in self._generate_calendar_entity(
                cal_list_entity.calendar_key
            ):
                yield calendar_entity

            async for event_entity in self._generate_event_entities(cal_list_entity):
                yield event_entity

            async for freebusy_entity in self._generate_freebusy_entities(cal_list_entity):
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
    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Google Calendar entities.

        Yields entities in the following order:
          - CalendarList entries
          - Underlying Calendar resources
          - Events for each calendar
          - FreeBusy data for each calendar (7-day window)

        In concurrent mode, Step 2-4 are processed per-calendar using bounded concurrency.
        """
        calendar_list_entries: List[GoogleCalendarListEntity] = []
        async for cal_list_entity in self._generate_calendar_list_entities():
            yield cal_list_entity
            calendar_list_entries.append(cal_list_entity)

        if not calendar_list_entries:
            self.logger.info("No calendars found in CalendarList; generation complete.")
            return

        if getattr(self, "batch_generation", False):
            async for entity in self._process_calendars_concurrent(calendar_list_entries):
                yield entity
        else:
            async for entity in self._process_calendars_sequential(calendar_list_entries):
                yield entity

    async def validate(self) -> None:
        """Validate credentials by pinging the Calendar API calendarList endpoint."""
        await self._get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            params={"maxResults": "1"},
        )
