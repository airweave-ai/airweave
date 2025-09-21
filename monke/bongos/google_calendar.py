"""Google Calendar-specific bongo implementation (robust timeouts + retries)."""

import asyncio
import time
import uuid
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


def rfc3339_utc(dt: datetime) -> str:
    """Return strict RFC3339 with Z (no microseconds)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class GoogleCalendarBongo(BaseBongo):
    """Google Calendar-specific bongo implementation.

    Creates, updates, and deletes test events via the real Google Calendar API.
    """

    connector_type = "google_calendar"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Google Calendar bongo."""
        super().__init__(credentials)
        self.access_token = credentials["access_token"]

        # Config from kwargs
        self.entity_count = kwargs.get("entity_count", 10)
        self.llm_model = kwargs.get("llm_model", None)

        # Test data tracking
        self.test_events: List[Dict[str, Any]] = []
        self.test_calendar_id: Optional[str] = None
        self._test_calendar_summary: Optional[str] = None

        # Rate limiting (conservative)
        self.last_request_time = 0.0
        self.rate_limit_delay = 0.5

        # HTTP client with explicit timeouts (fixes ReadTimeout flakes)
        # httpx defaults to ~5s inactivity timeout; we raise it here.
        self._timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=30.0)
        self._client = httpx.AsyncClient(
            base_url="https://www.googleapis.com/calendar/v3",
            timeout=self._timeout,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        self.logger = get_logger("google_calendar_bongo")

    # ---------- Public API ----------

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test events in Google Calendar."""
        self.logger.info(f"🥁 Creating {self.entity_count} test events in Google Calendar")
        entities: List[Dict[str, Any]] = []

        # Ensure or create a dedicated test calendar
        await self._ensure_test_calendar()

        from monke.generation.google_calendar import generate_google_calendar_artifact

        for i in range(self.entity_count):
            token = str(uuid.uuid4())[:8]
            title, description, duration_hours = await generate_google_calendar_artifact(
                self.llm_model, token
            )

            start_time = datetime.now(timezone.utc) + timedelta(days=i + 1)
            end_time = start_time + timedelta(hours=duration_hours)

            event = await self._create_test_event(
                self.test_calendar_id, title, description, start_time, end_time
            )

            entities.append(
                {
                    "type": "event",
                    "id": event["id"],
                    "calendar_id": self.test_calendar_id,
                    "title": title,
                    "token": token,
                    "expected_content": token,
                }
            )
            self.logger.info(f"📅 Created test event: {event['id']}")

            if self.entity_count > 10:
                await asyncio.sleep(0.5)

        self.test_events = entities
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a few test events (title/description) in Google Calendar."""
        self.logger.info("🥁 Updating test events in Google Calendar")
        updated: List[Dict[str, Any]] = []

        if not self.test_events:
            return updated

        from monke.generation.google_calendar import generate_google_calendar_artifact

        for event_info in self.test_events[: min(3, self.entity_count)]:
            token = event_info.get("token") or str(uuid.uuid4())[:8]
            title, description, _ = await generate_google_calendar_artifact(
                self.llm_model, token, is_update=True
            )

            await self._update_test_event(
                self.test_calendar_id, event_info["id"], title, description
            )

            updated.append(
                {
                    "type": "event",
                    "id": event_info["id"],
                    "calendar_id": self.test_calendar_id,
                    "title": title,
                    "token": token,
                    "expected_content": token,
                    "updated": True,
                }
            )
            self.logger.info(f"📝 Updated test event: {event_info['id']}")

            if self.entity_count > 10:
                await asyncio.sleep(0.5)

        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all test entities from Google Calendar."""
        self.logger.info("🥁 Deleting all test events from Google Calendar")
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete specific entities from Google Calendar."""
        self.logger.info(f"🥁 Deleting {len(entities)} specific events from Google Calendar")
        deleted_ids: List[str] = []

        for entity in entities:
            try:
                ev_id = entity["id"]
                await self._delete_test_event(self.test_calendar_id, ev_id)
                deleted_ids.append(ev_id)
                self.logger.info(f"🗑️ Deleted test event: {ev_id}")

                if len(entities) > 10:
                    await asyncio.sleep(0.5)
            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete entity {entity.get('id')}: {e}")

        # Verify deletion
        self.logger.info(
            "🔍 VERIFYING: Checking if events are actually deleted from Google Calendar"
        )
        for entity in entities:
            ev_id = entity["id"]
            if ev_id in deleted_ids:
                is_deleted = await self._verify_event_deleted(self.test_calendar_id, ev_id)
                if is_deleted:
                    self.logger.info(f"✅ Event {ev_id} confirmed deleted from Google Calendar")
                else:
                    self.logger.warning(f"⚠️ Event {ev_id} still exists in Google Calendar!")

        return deleted_ids

    async def cleanup(self):
        """Clean up any remaining test data and close the HTTP client."""
        self.logger.info("🧹 Cleaning up remaining test events in Google Calendar")

        # Force delete any remaining test events (best-effort)
        for test_event in list(self.test_events):
            try:
                await self._force_delete_event(self.test_calendar_id, test_event["id"])
                self.logger.info(f"🧹 Force deleted event: {test_event['id']}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not force delete event {test_event['id']}: {e}")

        # Delete the test calendar if not primary
        if self.test_calendar_id and self.test_calendar_id != "primary":
            try:
                await self._delete_test_calendar(self.test_calendar_id)
                self.logger.info(f"🧹 Deleted test calendar: {self.test_calendar_id}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete test calendar: {e}")

        # Close HTTP client
        try:
            await self._client.aclose()
        except Exception:
            pass

    # ---------- Private helpers ----------

    async def _ensure_test_calendar(self):
        """Ensure a dedicated test calendar exists; create one if needed."""
        await self._rate_limit()

        self._test_calendar_summary = f"Monke Test Calendar - {str(uuid.uuid4())[:8]}"

        payload = {
            "summary": self._test_calendar_summary,
            "description": "Temporary calendar for Monke testing",
            "timeZone": "UTC",
        }

        try:
            resp = await self._request_with_retry("POST", "/calendars", json=payload)
            data = resp.json()
            self.test_calendar_id = data["id"]
            self.logger.info(f"📅 Created test calendar: {self.test_calendar_id}")
            return
        except Exception as e:
            # If the POST may have succeeded but response timed out, try to find it by summary.
            self.logger.warning(
                f"Could not create test calendar directly ({e}); attempting fallback"
            )
            cal_id = await self._find_calendar_by_summary(self._test_calendar_summary)
            if cal_id:
                self.test_calendar_id = cal_id
                self.logger.info(
                    f"📅 Found created test calendar via list: {self.test_calendar_summary} -> {cal_id}"
                )
                return

            # Last resort: use primary
            self.logger.warning("Could not create/find test calendar; falling back to 'primary'")
            self.test_calendar_id = "primary"

    async def _find_calendar_by_summary(self, summary: str) -> Optional[str]:
        """Search the user's calendar list for a calendar by its summary/title."""
        page_token = None
        for _ in range(10):  # avoid infinite loops
            params = {"pageToken": page_token} if page_token else None
            resp = await self._request_with_retry("GET", "/users/me/calendarList", params=params)
            data = resp.json()
            for item in data.get("items", []):
                if item.get("summary") == summary:
                    # calendarList items expose the actual calendar ID as 'id'
                    return item.get("id")
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return None

    async def _create_test_event(
        self,
        calendar_id: str,
        title: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Any]:
        """Create a test event via Google Calendar API."""
        await self._rate_limit()

        event_data = {
            "summary": title,
            "description": description,
            "start": {"dateTime": rfc3339_utc(start_time)},  # RFC3339 with Z
            "end": {"dateTime": rfc3339_utc(end_time)},
        }

        resp = await self._request_with_retry(
            "POST", f"/calendars/{calendar_id}/events", json=event_data
        )
        if not resp.is_success:
            raise Exception(f"Failed to create event: {resp.status_code} - {resp.text}")

        result = resp.json()
        self.created_entities.append({"id": result["id"], "calendar_id": calendar_id})
        return result

    async def _update_test_event(
        self, calendar_id: str, event_id: str, title: str, description: str
    ) -> Dict[str, Any]:
        """Update a test event via Google Calendar API (GET → PUT with ETag)."""
        await self._rate_limit()

        # Fetch current event to obtain ETag (for atomic update)
        get_resp = await self._request_with_retry(
            "GET", f"/calendars/{calendar_id}/events/{event_id}"
        )
        if not get_resp.is_success:
            raise Exception(f"Failed to get event: {get_resp.status_code} - {get_resp.text}")
        event = get_resp.json()
        etag = event.get("etag")

        # Apply updates
        event["summary"] = title
        event["description"] = description

        headers = {"If-Match": etag} if etag else None
        put_resp = await self._request_with_retry(
            "PUT",
            f"/calendars/{calendar_id}/events/{event_id}",
            json=event,
            headers=headers,
        )
        if not put_resp.is_success:
            raise Exception(f"Failed to update event: {put_resp.status_code} - {put_resp.text}")
        return put_resp.json()

    async def _delete_test_event(self, calendar_id: str, event_id: str):
        """Delete a test event via Google Calendar API."""
        await self._rate_limit()

        resp = await self._request_with_retry(
            "DELETE", f"/calendars/{calendar_id}/events/{event_id}"
        )
        # 204 success; also accept 410 Gone (already deleted).
        if resp.status_code not in (204,):
            # Best-effort: some servers may return 410 for already-deleted
            if resp.status_code == 410:
                return
            raise Exception(f"Failed to delete event: {resp.status_code} - {resp.text}")

    async def _verify_event_deleted(self, calendar_id: str, event_id: str) -> bool:
        """Verify if an event is deleted/absent from Google Calendar."""
        try:
            resp = await self._request_with_retry(
                "GET", f"/calendars/{calendar_id}/events/{event_id}"
            )
            if resp.status_code == 404 or resp.status_code == 410:
                return True
            if resp.is_success:
                data = resp.json()
                return data.get("status") == "cancelled"
            return False
        except Exception:
            return False

    async def _force_delete_event(self, calendar_id: str, event_id: str):
        """Force delete an event (best-effort)."""
        try:
            await self._delete_test_event(calendar_id, event_id)
        except Exception as e:
            self.logger.warning(f"Could not force delete {event_id}: {e}")

    async def _delete_test_calendar(self, calendar_id: str):
        """Delete the test calendar."""
        await self._rate_limit()
        resp = await self._request_with_retry("DELETE", f"/calendars/{calendar_id}")
        if resp.status_code not in (204, 404):
            raise Exception(f"Failed to delete calendar: {resp.status_code} - {resp.text}")

    async def _rate_limit(self):
        """Simple spacing between calls."""
        now = time.time()
        dt = now - self.last_request_time
        if dt < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - dt)
        self.last_request_time = time.time()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        json: Any = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        max_attempts: int = 3,
    ) -> httpx.Response:
        """HTTP request with retry/backoff on ReadTimeout, 429, and 5xx."""
        attempt = 0
        while True:
            attempt += 1
            try:
                await self._rate_limit()
                resp = await self._client.request(
                    method, url, json=json, headers=headers, params=params
                )
                # Retry on 429 or 5xx
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt >= max_attempts:
                        return resp
                    backoff = min(8.0, 0.5 * (2 ** (attempt - 1)))
                    await asyncio.sleep(backoff + random.uniform(0, 0.25))
                    continue
                return resp

            except httpx.ReadTimeout:
                if attempt >= max_attempts:
                    raise
                backoff = min(8.0, 0.5 * (2 ** (attempt - 1)))
                await asyncio.sleep(backoff + random.uniform(0, 0.25))
