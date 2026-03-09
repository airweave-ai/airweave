"""Cal.com bongo implementation.

Creates, updates, and (optionally) deletes test bookings via the real Cal.com API.
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger

CAL_API_BASE = "https://api.cal.com"
CAL_API_VERSION = "2024-08-13"
CAL_SLOTS_API_VERSION = "2024-09-04"


def _rfc3339_utc(dt: datetime) -> str:
    """Return RFC3339 timestamp in UTC with trailing Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CalComBongo(BaseBongo):
    """Bongo for Cal.com connector.

    Responsibilities:
    - Create test bookings for a given event type (provided via config).
    - Embed unique verification tokens into booking descriptions.
    - Update some bookings to test incremental sync.
    - Optionally delete created bookings for cleanup.
    """

    connector_type = "calcom"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Cal.com bongo.

        Args:
            credentials: Dict with either `api_key` or `access_token` for Cal.com.
            **kwargs: Configuration from test config file (event_type_id, etc.).
        """
        super().__init__(credentials)

        # Credentials: support both direct api_key and generic access_token.
        api_key = credentials.get("api_key") or credentials.get("access_token")
        if not api_key:
            raise ValueError("CalComBongo requires an 'api_key' or 'access_token' credential")
        self.api_key: str = api_key

        # Test configuration
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.event_type_id: Optional[int] = (
            int(kwargs["event_type_id"]) if "event_type_id" in kwargs and kwargs["event_type_id"] else None
        )
        self.attendee_time_zone: str = kwargs.get("attendee_time_zone", "America/New_York")

        if self.event_type_id is None:
            raise ValueError(
                "CalComBongo requires `event_type_id` in config_fields to know which event type to book."
            )

        # Runtime tracking of created entities
        self._bookings: List[Dict[str, Any]] = []

        # Simple rate limiting
        self.last_request_time = 0.0
        self.min_delay = 0.2  # 200ms between requests

        self.logger = get_logger("calcom_bongo")

    def _headers(self, api_version: str = CAL_API_VERSION) -> Dict[str, str]:
        """Return auth headers for Cal.com API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "cal-api-version": api_version,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _rate_limit(self):
        """Simple client-side rate limiting."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_delay:
            await asyncio.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()

    async def _get_available_slot_starts(
        self,
        client: httpx.AsyncClient,
        count: int,
    ) -> List[str]:
        """Fetch available slot start times for the configured event type.

        Calls GET /v2/slots with eventTypeId and a date range, then returns
        the first `count` slot start times (ISO8601 strings) in chronological order.
        """
        now = datetime.now(timezone.utc)
        start_date = (now + timedelta(days=1)).date()
        end_date = (now + timedelta(days=14)).date()
        params = {
            "eventTypeId": self.event_type_id,
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "format": "range",
            "timeZone": "UTC",
        }
        resp = await client.get(
            "/v2/slots",
            headers=self._headers(api_version=CAL_SLOTS_API_VERSION),
            params=params,
        )
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data") or {}
        # Flatten: data is { "YYYY-MM-DD": [ { "start": "...", "end": "..." }, ... ], ... }
        starts: List[str] = []
        for _date in sorted(data.keys()):
            for slot in data[_date]:
                if isinstance(slot, dict) and slot.get("start"):
                    starts.append(slot["start"])
                elif isinstance(slot, str):
                    starts.append(slot)
        starts.sort()
        if len(starts) < count:
            raise ValueError(
                f"Not enough available slots for event_type_id={self.event_type_id}. "
                f"Need {count}, got {len(starts)} in the next 14 days. "
                "Check the host's schedule and event type availability."
            )
        return starts[:count]

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test bookings for the configured event type.

        Fetches available slots from Cal.com first, then creates one booking per slot
        so times are always within the host's schedule.
        """
        from monke.generation.calcom import generate_cal_booking

        self.logger.info(
            f"🥁 Creating {self.entity_count} Cal.com bookings for event_type_id={self.event_type_id}"
        )

        entities: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(base_url=CAL_API_BASE) as client:
            await self._rate_limit()
            slot_starts = await self._get_available_slot_starts(client, self.entity_count)
            self.logger.info(
                f"Using {len(slot_starts)} available slot(s): %s ...",
                slot_starts[0] if slot_starts else "none",
            )

            for i in range(self.entity_count):
                await self._rate_limit()
                token = str(uuid.uuid4())[:8]
                self.logger.info(f"Generating Cal.com booking content with token={token}")

                data = await generate_cal_booking(self.openai_model, token)
                # Use slot start from Cal.com so the time is within host availability
                start_iso = slot_starts[i]

                payload: Dict[str, Any] = {
                    "start": start_iso,
                    "attendee": {
                        "name": data["attendee_name"],
                        "email": data["attendee_email"],
                        "timeZone": data["attendee_time_zone"],
                    },
                    "eventTypeId": self.event_type_id,
                    "bookingFieldsResponses": {},
                    "metadata": {"monke_token": token},
                }

                # We embed the token into the description and, where possible,
                # into bookingFieldsResponses so it ends up in embeddable fields.
                payload["bookingFieldsResponses"]["monke_token"] = token

                # Cal.com title/description are derived from event type, but our
                # connector extracts rich descriptions from metadata & responses,
                # so the token will still be searchable.

                self.logger.debug(f"Creating booking payload: {payload}")
                resp = await client.post(
                    "/v2/bookings",
                    headers=self._headers(),
                    json=payload,
                )
                if resp.status_code not in (200, 201):
                    self.logger.error(
                        f"Failed to create booking: {resp.status_code} - {resp.text}"
                    )
                resp.raise_for_status()
                body = resp.json()
                booking_data = body.get("data")
                if isinstance(booking_data, list):
                    # Recurring bookings can return a list – take the first for verification.
                    booking = booking_data[0]
                else:
                    booking = booking_data

                descriptor = {
                    "type": "booking",
                    "id": booking["id"],
                    "uid": booking["uid"],
                    "token": token,
                    "expected_content": token,
                    "path": f"calcom/booking/{booking['uid']}",
                    "start": start_iso,  # stored for v2 reschedule (update step)
                }
                entities.append(descriptor)
                self._bookings.append(descriptor)

        self.created_entities = entities
        self.logger.info(f"✅ Created {len(self._bookings)} Cal.com bookings")
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a subset of bookings to test incremental sync.

        Uses v2 POST /v2/bookings/{uid}/reschedule (v1 PATCH is discontinued Feb 2026).
        Rescheduling to a new slot updates the booking and changes updatedAt so the
        connector's next sync sees the change. v2 has no endpoint to update title/description.
        """
        if not self._bookings:
            return []

        self.logger.info("🥁 Updating a subset of Cal.com bookings via v2 reschedule")
        updated: List[Dict[str, Any]] = []
        count = min(2, len(self._bookings))

        async with httpx.AsyncClient(base_url=CAL_API_BASE) as client:
            await self._rate_limit()
            # Fetch enough new slots so we can reschedule each updated booking to a distinct time.
            new_slots = await self._get_available_slot_starts(client, count + 2)
            used_starts: set = set()

            for i in range(count):
                booking = self._bookings[i]
                uid = booking["uid"]
                token = booking["token"]
                current_start = booking.get("start")
                await self._rate_limit()

                # Pick a new slot different from this booking's current start and from already used.
                new_start = next(
                    (s for s in new_slots if s != current_start and s not in used_starts),
                    new_slots[i],
                )
                used_starts.add(new_start)

                resp = await client.post(
                    f"/v2/bookings/{uid}/reschedule",
                    headers=self._headers(),
                    json={
                        "start": new_start,
                        "reschedulingReason": "Monke test update for incremental sync",
                    },
                )
                if resp.status_code not in (200, 201):
                    raise RuntimeError(
                        f"Failed to reschedule booking {uid} via v2: "
                        f"{resp.status_code} - {resp.text}"
                    )
                body = resp.json()
                data = body.get("data")
                if isinstance(data, list):
                    data = data[0] if data else {}
                new_uid = data.get("uid") or uid
                new_id = data.get("id") or booking.get("id")
                new_start_resp = data.get("start") or new_start
                self.logger.info(
                    "Rescheduled booking %s via v2 -> new uid %s",
                    uid,
                    new_uid,
                )
                # Descriptor must use new uid/id so partial_delete cancels the active booking.
                new_descriptor = {
                    **booking,
                    "uid": new_uid,
                    "id": new_id,
                    "start": new_start_resp,
                    "path": f"calcom/booking/{new_uid}",
                    "expected_content": token,
                }
                self._bookings[i] = new_descriptor
                if i < len(self.created_entities):
                    self.created_entities[i] = new_descriptor
                updated.append(new_descriptor)

        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all created test bookings."""
        self.logger.info("🥁 Deleting all Cal.com test bookings")
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete a specific list of bookings by UID."""
        deleted: List[str] = []

        async with httpx.AsyncClient(base_url=CAL_API_BASE) as client:
            for booking in entities:
                uid = booking.get("uid")
                if not uid:
                    continue
                await self._rate_limit()
                resp = await client.post(
                    f"/v2/bookings/{uid}/cancel",
                    headers=self._headers(),
                    json={"cancellationReason": "Monke test cleanup"},
                )
                if resp.status_code in (200, 201):
                    deleted.append(str(booking.get("id") or uid))
                    self.logger.info(f"🗑️ Cancelled booking {uid}")
                elif resp.status_code == 400:
                    # Reschedule in v2 can leave the original booking cancelled; idempotent treat as success.
                    body = resp.json() if resp.text else {}
                    msg = (body.get("error") or {}).get("message") or body.get("message") or resp.text
                    if "cancelled already" in (msg or "").lower():
                        deleted.append(str(booking.get("id") or uid))
                        self.logger.info(f"🗑️ Booking {uid} already cancelled (e.g. by reschedule), skipping")
                    else:
                        raise RuntimeError(
                            f"Failed to cancel booking {uid}: 400 - {resp.text}"
                        )
                else:
                    raise RuntimeError(
                        f"Failed to cancel booking {uid}: {resp.status_code} - {resp.text}"
                    )

        return deleted

    async def cleanup(self):
        """Cleanup of current session test data.

        Fail fast if cleanup cannot be completed, since leftover bookings can
        cause future test runs to fail availability checks.
        """
        self.logger.info("🧹 Cleaning up Cal.com test bookings")
        if self._bookings:
            await self.delete_specific_entities(self._bookings)
