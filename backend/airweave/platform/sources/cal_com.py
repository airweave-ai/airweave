"""Cal.com source implementation for syncing event types and bookings."""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.cal_com import (
    CalComBookingEntity,
    CalComEventTypeEntity,
    CalComScheduleEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Cal.com",
    short_name="cal_com",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=None,
    config_class="CalComConfig",
    labels=["Scheduling"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class CalComSource(BaseSource):
    """Cal.com source connector integrates with the Cal.com API to extract and synchronize data.

    Connects to your Cal.com account to sync event types and bookings.
    """

    BASE_URL = "https://api.cal.com/v2"
    API_VERSION = "2024-06-14"

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "CalComSource":
        """Create a new Cal.com source.

        Args:
            access_token: OAuth access token for Cal.com API
            config: Optional configuration parameters

        Returns:
            Configured CalComSource instance
        """
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Make authenticated GET request to Cal.com API with retry logic.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response data
        """
        # Get a valid token (will refresh if needed)
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError("No access token available")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "cal-api-version": self.API_VERSION,
            "Content-Type": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 Unauthorized - token might have expired
            if response.status_code == 401:
                self.logger.warning(f"Received 401 Unauthorized for {url}, refreshing token...")

                # If we have a token manager, try to refresh
                if self.token_manager:
                    try:
                        # Force refresh the token
                        new_token = await self.token_manager.refresh_on_unauthorized()
                        headers["Authorization"] = f"Bearer {new_token}"

                        # Retry the request with the new token
                        self.logger.debug(f"Retrying request with refreshed token: {url}")
                        response = await client.get(url, headers=headers, params=params)

                    except TokenRefreshError as e:
                        self.logger.error(f"Failed to refresh token: {str(e)}")
                        response.raise_for_status()
                else:
                    # No token manager, can't refresh
                    self.logger.error("No token manager available to refresh expired token")
                    response.raise_for_status()

            # Raise for other HTTP errors
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Cal.com API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Cal.com API: {url}, {str(e)}")
            raise

    async def _generate_schedule_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[CalComScheduleEntity, None]:
        """Generate schedule entities."""
        url = f"{self.BASE_URL}/schedules"
        schedules_data = await self._get_with_auth(client, url)

        # Cal.com API returns data in a 'data' field
        if not isinstance(schedules_data, dict):
            self.logger.error(f"Invalid response format from Cal.com API: {type(schedules_data)}")
            return
        schedules_raw = schedules_data.get("data", [])
        schedules = schedules_raw if isinstance(schedules_raw, list) else []
        if not schedules:
            self.logger.info("No schedules found")
            return

        for schedule in schedules:
            if not isinstance(schedule, dict):
                self.logger.warning(f"Skipping invalid schedule (not a dict): {schedule}")
                continue

            yield CalComScheduleEntity(
                id=schedule["id"],
                name=schedule.get("name", ""),
                owner_id=schedule.get("ownerId"),
                time_zone=schedule.get("timeZone", "UTC"),
                is_default=schedule.get("isDefault", False),
                availability=schedule.get("availability", []),
                overrides=schedule.get("overrides", []),
                created_at=self._parse_datetime(schedule.get("createdAt")),
                updated_at=self._parse_datetime(schedule.get("updatedAt")),
                breadcrumbs=[],  # Root entity
            )

    async def _generate_event_type_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[CalComEventTypeEntity, None]:
        """Generate event type entities."""
        url = f"{self.BASE_URL}/event-types"
        event_types_data = await self._get_with_auth(client, url)

        # Cal.com API returns data in a 'data' field with status
        if not isinstance(event_types_data, dict):
            self.logger.error(f"Invalid response format from Cal.com API: {type(event_types_data)}")
            return
        event_types_raw = event_types_data.get("data", [])
        event_types = event_types_raw if isinstance(event_types_raw, list) else []
        if not event_types:
            self.logger.info("No event types found")
            return

        for event_type in event_types:
            if not isinstance(event_type, dict):
                self.logger.warning(f"Skipping invalid event type (not a dict): {event_type}")
                continue

            # Extract owner information if available
            owner = event_type.get("owner", {})
            owner_name = owner.get("name") if isinstance(owner, dict) else None
            owner_email = owner.get("email") if isinstance(owner, dict) else None

            # Extract user emails from users array (may be objects or strings)
            users_data = event_type.get("users", [])
            user_emails = []
            for user in users_data:
                if isinstance(user, str):
                    user_emails.append(user)
                elif isinstance(user, dict):
                    email = user.get("email") or user.get("username")
                    if email:
                        user_emails.append(email)

            yield CalComEventTypeEntity(
                id=event_type["id"],
                title=event_type.get("title", ""),
                slug=event_type.get("slug", ""),
                description=event_type.get("description"),
                length_in_minutes=event_type.get("lengthInMinutes", 30),
                created_at=self._parse_datetime(event_type.get("createdAt")),
                updated_at=self._parse_datetime(event_type.get("updatedAt")),
                breadcrumbs=[],  # Root entity
                schedule_id=event_type.get("scheduleId"),
                locations=event_type.get("locations", []),
                booking_fields=event_type.get("bookingFields", []),
                price=event_type.get("price"),
                currency=event_type.get("currency"),
                minimum_booking_notice=event_type.get("minimumBookingNotice"),
                before_event_buffer=event_type.get("beforeEventBuffer"),
                after_event_buffer=event_type.get("afterEventBuffer"),
                hidden=event_type.get("hidden", False),
                booking_requires_authentication=event_type.get(
                    "bookingRequiresAuthentication", False
                ),
                owner_id=event_type.get("ownerId"),
                owner_name=owner_name,
                owner_email=owner_email,
                users=user_emails,
                recurrence=event_type.get("recurrence"),
                metadata=event_type.get("metadata", {}),
            )

    async def _generate_booking_entities(
        self,
        client: httpx.AsyncClient,
        event_type: Optional[Dict[str, Any]] = None,
        event_type_breadcrumb: Optional[Breadcrumb] = None,
    ) -> AsyncGenerator[CalComBookingEntity, None]:
        """Generate booking entities.

        Args:
            client: HTTP client
            event_type: Optional event type to filter bookings
            event_type_breadcrumb: Optional breadcrumb for the event type
        """
        url = f"{self.BASE_URL}/bookings"
        params: Dict[str, Any] = {}

        # If filtering by event type, add it to params
        if event_type:
            params["eventTypeId"] = event_type["id"]

        bookings_data = await self._get_with_auth(client, url, params=params)

        # Cal.com API returns data in a 'data' field
        if not isinstance(bookings_data, dict):
            self.logger.error(f"Invalid response format from Cal.com API: {type(bookings_data)}")
            return
        bookings_raw = bookings_data.get("data", [])
        bookings = bookings_raw if isinstance(bookings_raw, list) else []
        if not bookings:
            if event_type:
                self.logger.debug(f"No bookings found for event type {event_type.get('id')}")
            else:
                self.logger.info("No bookings found")
            return

        breadcrumbs = []
        if event_type_breadcrumb:
            breadcrumbs = [event_type_breadcrumb]

        for booking in bookings:
            if not isinstance(booking, dict):
                self.logger.warning(f"Skipping invalid booking (not a dict): {booking}")
                continue

            # Extract attendee information
            attendees_raw = booking.get("attendees", [])
            attendees = attendees_raw if isinstance(attendees_raw, list) else []
            user_email = None
            user_name = None
            if attendees:
                primary_attendee = attendees[0]
                if isinstance(primary_attendee, dict):
                    user_email = primary_attendee.get("email")
                    user_name = primary_attendee.get("name")
                elif isinstance(primary_attendee, str):
                    user_email = primary_attendee

            # Extract organizer information
            organizer = booking.get("organizer", {})
            organizer_email = organizer.get("email") if isinstance(organizer, dict) else None
            organizer_name = organizer.get("name") if isinstance(organizer, dict) else None

            # Extract location information
            location_obj = booking.get("location")
            location_str = None
            location_type = None
            meeting_url = None

            if isinstance(location_obj, str):
                location_str = location_obj
            elif isinstance(location_obj, dict):
                location_type = location_obj.get("type")
                location_str = location_obj.get("address") or location_obj.get("displayLocation")
                meeting_url = location_obj.get("url") or location_obj.get("meetingUrl")

            # Extract event type information
            event_type_obj = booking.get("eventType")
            event_type_title = None
            event_type_slug = None
            if isinstance(event_type_obj, dict):
                event_type_title = event_type_obj.get("title")
                event_type_slug = event_type_obj.get("slug")

            yield CalComBookingEntity(
                id=booking["id"],
                uid=booking.get("uid", ""),
                title=booking.get("title", ""),
                description=booking.get("description"),
                start_time=self._parse_datetime(booking.get("startTime")),
                end_time=self._parse_datetime(booking.get("endTime")),
                created_at=self._parse_datetime(booking.get("createdAt")),
                updated_at=self._parse_datetime(booking.get("updatedAt")),
                breadcrumbs=breadcrumbs,
                event_type_id=booking.get("eventTypeId"),
                event_type_title=event_type_title,
                event_type_slug=event_type_slug,
                attendees=attendees,
                user_email=user_email,
                user_name=user_name,
                organizer_email=organizer_email,
                organizer_name=organizer_name,
                status=booking.get("status", "pending"),
                paid=booking.get("paid", False),
                payment_required=booking.get("paymentRequired", False),
                location=location_str,
                location_type=location_type,
                meeting_url=meeting_url,
                metadata=booking.get("metadata", {}),
                cancellation_reason=booking.get("cancellationReason"),
                rescheduled=booking.get("rescheduled", False),
                recurring_event_id=booking.get("recurringEventId"),
            )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Cal.com.

        This is the main entry point called by the sync engine.
        """
        async with self.http_client() as client:
            # First, generate all schedules
            async for schedule_entity in self._generate_schedule_entities(client):
                yield schedule_entity

            # Track event types we've seen to avoid duplicate bookings
            seen_event_type_ids = set()

            # Generate all event types
            async for event_type_entity in self._generate_event_type_entities(client):
                yield event_type_entity

                # Create breadcrumb for this event type
                event_type_breadcrumb = Breadcrumb(
                    entity_id=str(event_type_entity.id),
                    name=event_type_entity.title,
                    entity_type="CalComEventTypeEntity",
                )

                # Generate bookings for this event type
                event_type_dict = {
                    "id": event_type_entity.id,
                    "title": event_type_entity.title,
                }
                seen_event_type_ids.add(event_type_entity.id)
                async for booking_entity in self._generate_booking_entities(
                    client, event_type_dict, event_type_breadcrumb
                ):
                    yield booking_entity

            # Also generate all bookings without event type filter
            # This ensures we capture bookings that might not be associated with event types
            # or bookings for event types we haven't seen
            async for booking_entity in self._generate_booking_entities(client):
                # Only yield if we haven't already seen this booking's event type
                # (to avoid duplicates from the per-event-type generation above)
                if (
                    booking_entity.event_type_id is None
                    or booking_entity.event_type_id not in seen_event_type_ids
                ):
                    yield booking_entity

    async def validate(self) -> bool:
        """Validate the connection to Cal.com API."""
        return await self._validate_oauth2(
            ping_url=f"{self.BASE_URL}/event-types",
            headers={
                "cal-api-version": self.API_VERSION,
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[Any]:
        """Parse datetime string from Cal.com API.

        Cal.com returns ISO 8601 datetime strings.
        """
        if not dt_str:
            return None

        try:
            # Handle ISO 8601 format with timezone
            if "T" in dt_str:
                # Try parsing with timezone
                if dt_str.endswith("Z"):
                    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                elif "+" in dt_str or dt_str.count("-") > 2:
                    return datetime.fromisoformat(dt_str)
                else:
                    # No timezone, assume UTC
                    return datetime.fromisoformat(dt_str + "+00:00")
            else:
                # Date only
                return datetime.fromisoformat(dt_str)
        except (ValueError, AttributeError) as e:
            self.logger.warning(f"Failed to parse datetime '{dt_str}': {str(e)}")
            return None
