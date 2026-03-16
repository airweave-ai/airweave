"""Cal.com source implementation.

Syncs bookings from Cal.com using the public API v2.

Primary entity:
    - CalBookingEntity: one entity per booking (regular, recurring, or seated)

Authentication:
    - API key (Settings → Security) provided via CalComAuthConfig.

Data model reference:
- Introduction: https://cal.com/docs/api-reference/v2/introduction
- List bookings: https://cal.com/docs/api-reference/v2/bookings/get-all-bookings
"""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Optional, cast

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import CalComAuthConfig
from airweave.platform.configs.config import CalComConfig
from airweave.platform.cursors import CalComCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.calcom import (
    CalBookingDeletionEntity,
    CalBookingEntity,
    CalEventTypeEntity,
    CalScheduleEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

DEFAULT_CAL_API_BASE = "https://api.cal.com"
# API versions per endpoint family (see Cal.com v2 docs)
CAL_BOOKINGS_API_VERSION = "2024-08-13"
CAL_EVENT_TYPES_API_VERSION = "2024-06-14"
CAL_SCHEDULES_API_VERSION = "2024-06-11"


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO8601 timestamp into a timezone-aware datetime (UTC) when possible."""
    if not value:
        return None
    try:
        # Cal.com timestamps are typically RFC3339 / ISO8601 with Z
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@source(
    name="Cal.com",
    short_name="calcom",
    auth_methods=[
        AuthenticationMethod.DIRECT,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=CalComAuthConfig,
    config_class=CalComConfig,
    labels=["Calendar", "Scheduling"],
    supports_continuous=True,
    cursor_class=CalComCursor,
    rate_limit_level=RateLimitLevel.ORG,
)
class CalSource(BaseSource):
    """Cal.com source connector.

    Syncs bookings from the Cal.com API into searchable entities.

    The connector:
    - Uses the Bookings API with `cal-api-version=2024-08-13`
    - Paginates with `take`/`skip`
    - Supports incremental sync via `afterUpdatedAt` cursor watermark
    """

    @classmethod
    async def create(
        cls,
        credentials: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> "CalSource":
        """Create and configure the Cal.com source.

        Args:
            credentials: Either a raw API key string or a CalComAuthConfig instance
                (or any object with an ``api_key`` attribute) when using DIRECT auth.
            config: Optional configuration (currently unused).

        Returns:
            Configured CalSource instance.
        """
        instance = cls()

        # Config: allow self-hosted Cal.com instances by overriding host/base URL.
        cfg = config or {}
        host = cfg.get("host") or cfg.get("base_url") or DEFAULT_CAL_API_BASE
        if not isinstance(host, str):
            raise ValueError("Cal.com host must be a string")
        host = host.strip()
        if not host:
            host = DEFAULT_CAL_API_BASE
        if not host.startswith(("http://", "https://")):
            host = f"https://{host}"
        instance.base_url = host.rstrip("/")

        # DIRECT auth via API key can pass either:
        # - A plain string API key, or
        # - A CalComAuthConfig (APIKeyAuthConfig) object with an api_key field.
        if isinstance(credentials, str):
            api_key = credentials.strip()
        elif hasattr(credentials, "api_key"):
            api_key = str(getattr(credentials, "api_key", "")).strip()
        else:
            raise ValueError(
                "credentials must be a string (Cal.com API key) or CalComAuthConfig with api_key"
            )

        if not api_key:
            raise ValueError("Cal.com API key is required.")

        # Store the API key as access_token so BaseSource.get_access_token works.
        instance.access_token = api_key

        # No connector-specific config yet, but keep the hook for future filters.
        return instance

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated GET request to the Cal.com API.

        Handles:
        - API key authentication
        - Basic retries on transient HTTP errors
        """
        token = await self.get_access_token()
        if not token:
            raise ValueError("No Cal.com API key available")

        base = getattr(self, "base_url", DEFAULT_CAL_API_BASE)
        url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
        request_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        response = await client.get(url, headers=request_headers, params=params or {})
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    async def _list_bookings(
        self,
        client: httpx.AsyncClient,
        after_updated_at: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield all bookings from Cal.com, optionally incrementally.

        Uses cursor-based incremental sync via the `afterUpdatedAt` query parameter
        and CalComCursor.last_updated_at watermark.

        Always requests all statuses (upcoming, recurring, past, cancelled, unconfirmed)
        so that full sync sees every booking. Otherwise the API may default to a subset
        (e.g. only recently updated or non-cancelled), causing remaining bookings to be
        missing from the stream and wrongly deleted as orphans during orphan cleanup.
        """
        params: Dict[str, Any] = {
            "take": 100,
            "skip": 0,
            # Request all statuses so full sync returns every booking (required for
            # correct orphan detection; omitting status can return a subset only).
            "status": "upcoming,recurring,past,cancelled,unconfirmed",
            # Sort by updated time ascending so the cursor watermark is monotonic.
            "sortUpdatedAt": "asc",
        }
        if after_updated_at:
            params["afterUpdatedAt"] = after_updated_at

        while True:
            data = await self._get_with_auth(
                client,
                "/v2/bookings",
                params=params,
                headers={"cal-api-version": CAL_BOOKINGS_API_VERSION},
            )
            items = data.get("data", []) or []
            for item in items:
                yield item

            pagination = data.get("pagination") or {}
            has_next = pagination.get("hasNextPage")
            returned_items = pagination.get("returnedItems", len(items))

            if not items or not has_next or returned_items == 0:
                break

            # Advance skip by number of items returned on this page.
            params["skip"] = params.get("skip", 0) + int(returned_items)

    def _booking_to_entity(self, booking: Dict[str, Any]) -> CalBookingEntity:
        """Transform a Cal.com booking JSON object into a CalBookingEntity."""
        created_at = _parse_iso8601(booking.get("createdAt"))
        updated_at = _parse_iso8601(booking.get("updatedAt"))
        start = _parse_iso8601(booking.get("start"))
        end = _parse_iso8601(booking.get("end"))

        duration_minutes = None
        if booking.get("duration") is not None:
            try:
                duration_minutes = int(booking["duration"])
            except (TypeError, ValueError):
                duration_minutes = None

        # Location preference:
        # - Prefer unified `location` field when present
        # - Fallback to meetingUrl (deprecated upstream) for backwards compatibility
        location = booking.get("location") or booking.get("meetingUrl")

        entity = CalBookingEntity(
            # BaseEntity fields
            breadcrumbs=[],
            # Core identifiers
            uid=str(booking.get("uid") or ""),
            booking_id=int(booking.get("id")),
            # Display
            title=str(booking.get("title") or "Cal.com Booking"),
            description=booking.get("description"),
            # Status & lifecycle
            status=booking.get("status"),
            cancellation_reason=booking.get("cancellationReason"),
            cancelled_by_email=booking.get("cancelledByEmail"),
            rescheduling_reason=booking.get("reschedulingReason"),
            rescheduled_by_email=booking.get("rescheduledByEmail"),
            rescheduled_from_uid=booking.get("rescheduledFromUid"),
            rescheduled_to_uid=booking.get("rescheduledToUid"),
            # Timing
            start=start,
            end=end,
            duration_minutes=duration_minutes,
            created_at=created_at,
            updated_at=updated_at,
            # Participants & event type
            hosts=booking.get("hosts") or [],
            attendees=booking.get("attendees") or [],
            guests=booking.get("guests") or [],
            absent_host=booking.get("absentHost"),
            event_type_id=booking.get("eventTypeId"),
            event_type=booking.get("eventType"),
            # Location & conferencing
            location=location,
            meeting_url=booking.get("meetingUrl"),
            # Metadata & scoring
            metadata=booking.get("metadata") or {},
            rating=booking.get("rating"),
            ics_uid=booking.get("icsUid"),
            booking_fields_responses=booking.get("bookingFieldsResponses") or {},
            # Recurring
            recurring_booking_uid=booking.get("recurringBookingUid"),
            # Web URL (optional explicit value if Cal adds one later)
            web_url_value=None,
        )
        return entity

    async def _list_event_types(
        self,
        client: httpx.AsyncClient,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield all event types from Cal.com with pagination.

        Event types describe the bookable meeting templates (duration, locations,
        booking page URL, etc.). Uses take/skip and pagination metadata when present.
        """
        params: Dict[str, Any] = {
            "take": 100,
            "skip": 0,
            "sortCreatedAt": "asc",
        }
        while True:
            data = await self._get_with_auth(
                client,
                "/v2/event-types",
                params=params,
                headers={"cal-api-version": CAL_EVENT_TYPES_API_VERSION},
            )
            items = data.get("data", []) or []
            for item in items:
                yield item

            pagination = data.get("pagination") or {}
            has_next = pagination.get("hasNextPage")
            returned_items = pagination.get("returnedItems", len(items))

            if not items or not has_next or returned_items == 0:
                break

            params["skip"] = params.get("skip", 0) + int(returned_items)

    def _event_type_to_entity(self, et: Dict[str, Any]) -> CalEventTypeEntity:
        """Transform a Cal.com event type JSON object into a CalEventTypeEntity."""
        return CalEventTypeEntity(
            breadcrumbs=[],
            event_type_id=int(et.get("id")),
            title=str(et.get("title") or "Cal.com Event Type"),
            slug=str(et.get("slug") or ""),
            description=et.get("description"),
            length_in_minutes=int(et.get("lengthInMinutes") or 0),
            metadata=et.get("metadata") or {},
            booking_url=et.get("bookingUrl"),
            schedule_id=et.get("scheduleId"),
            hidden=bool(et.get("hidden", False)),
            booking_requires_authentication=bool(et.get("bookingRequiresAuthentication", False)),
        )

    async def _list_schedules(
        self,
        client: httpx.AsyncClient,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield all schedules for the authenticated user from Cal.com.

        The v2/schedules endpoint returns all schedules in a single response;
        no pagination parameters are documented.
        """
        data = await self._get_with_auth(
            client,
            "/v2/schedules",
            headers={"cal-api-version": CAL_SCHEDULES_API_VERSION},
        )
        for item in data.get("data", []) or []:
            yield item

    def _schedule_to_entity(self, schedule: Dict[str, Any]) -> CalScheduleEntity:
        """Transform a Cal.com schedule JSON object into a CalScheduleEntity."""
        return CalScheduleEntity(
            breadcrumbs=[],
            schedule_id=int(schedule.get("id")),
            owner_id=int(schedule.get("ownerId")),
            name=str(schedule.get("name") or "Default schedule"),
            time_zone=str(schedule.get("timeZone") or ""),
            availability=schedule.get("availability") or [],
            is_default=bool(schedule.get("isDefault", False)),
            overrides=schedule.get("overrides") or [],
        )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all booking entities from Cal.com.

        Uses incremental sync when a cursor is available; otherwise performs
        a full sync.
        """
        cursor_data = self.cursor.data if self.cursor else {}
        last_updated_at = cursor_data.get("last_updated_at")

        if last_updated_at:
            self.logger.info("Cal.com: incremental sync from updatedAt=%s", last_updated_at)
        else:
            self.logger.info("Cal.com: full sync (no existing cursor)")

        async with self.http_client() as client:
            # First, sync configuration-style entities that are typically small and
            # do not need incremental cursors.
            async for event_type in self._list_event_types(client):
                yield self._event_type_to_entity(event_type)

            async for schedule in self._list_schedules(client):
                yield self._schedule_to_entity(schedule)

            # Then sync bookings with incremental cursor support.
            latest_watermark: Optional[str] = last_updated_at

            async for booking in self._list_bookings(client, after_updated_at=last_updated_at):
                entity = self._booking_to_entity(booking)

                # Treat cancelled bookings as deletions during incremental sync so
                # destinations remove them (instead of keeping a "cancelled" record).
                if (entity.status or "").lower() == "cancelled":
                    yield CalBookingDeletionEntity(
                        breadcrumbs=[],
                        uid=entity.uid,
                        booking_id=entity.booking_id,
                        label=f"Deleted booking {entity.uid}",
                        deletion_status="removed",
                    )
                else:
                    yield entity

                # Update cursor watermark incrementally based on updated_at.
                if self.cursor:
                    updated_at = entity.updated_at or entity.created_at
                    if updated_at:
                        iso = updated_at.astimezone(timezone.utc).isoformat()
                        if latest_watermark is None or iso > latest_watermark:
                            latest_watermark = iso
                            self.cursor.update(last_updated_at=latest_watermark)

    async def validate(self) -> bool:
        """Verify Cal.com API key by pinging the bookings endpoint."""
        base = getattr(self, "base_url", DEFAULT_CAL_API_BASE)
        return await self._validate_oauth2(
            ping_url=f"{base}/v2/bookings?take=1&skip=0",
            headers={
                "Accept": "application/json",
                "cal-api-version": CAL_BOOKINGS_API_VERSION,
            },
            timeout=10.0,
        )
