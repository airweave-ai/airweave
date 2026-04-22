"""Zoom bongo implementation.

Creates, updates, and deletes test meetings via the Zoom API.
API reference: https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/
Delete meeting requires OAuth scope meeting:delete.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class ZoomBongo(BaseBongo):
    """Bongo for Zoom that creates test entities for E2E testing.

    Key responsibilities:
    - Create test meetings with verification tokens
    - Update meetings to test incremental sync
    - Delete meetings to test deletion detection
    - Clean up all test data

    Note: Recording and transcript creation requires actual meetings to occur,
    so we focus on meeting creation for testing.
    """

    connector_type = "zoom"

    ZOOM_BASE_URL = "https://api.zoom.us/v2"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Zoom bongo.

        Args:
            credentials: Dict with "access_token" for Zoom API
            **kwargs: Configuration from test config file
        """
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]

        # Test configuration
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.max_concurrency: int = int(kwargs.get("max_concurrency", 2))

        # Simple rate limiting
        self.last_request_time = 0.0
        self.min_delay = 0.5  # 500ms between requests

        # Runtime state - track ALL created entities
        self._meetings: List[Dict[str, Any]] = []
        self._user_id: Optional[str] = None

        self.logger = get_logger(f"{self.connector_type}_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test meetings with verification tokens.

        Returns:
            List of entity descriptors with verification tokens
        """
        self.logger.info(f"🥁 Creating {self.entity_count} test meetings")

        from monke.generation.zoom import generate_zoom_meeting

        all_entities: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async with httpx.AsyncClient() as client:
            # Get current user ID
            await self._ensure_user(client)

            async def create_meeting(idx: int):
                async with semaphore:
                    meeting_token = str(uuid.uuid4())[:8]

                    self.logger.info(
                        f"Creating meeting {idx + 1}/{self.entity_count} "
                        f"with token {meeting_token}"
                    )

                    meeting_data = await generate_zoom_meeting(
                        self.openai_model, meeting_token
                    )

                    # Schedule meeting for 1 week from now
                    from datetime import datetime, timedelta

                    start_time = (
                        datetime.utcnow() + timedelta(days=7, hours=idx)
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")

                    resp = await self._request_with_retries(
                        client,
                        "POST",
                        f"{self.ZOOM_BASE_URL}/users/{self._user_id}/meetings",
                        headers=self._headers(),
                        json={
                            "topic": meeting_data["topic"],
                            "type": 2,  # Scheduled meeting
                            "start_time": start_time,
                            "duration": meeting_data["duration"],
                            "timezone": "UTC",
                            "agenda": meeting_data["agenda"],
                            "settings": {
                                "host_video": True,
                                "participant_video": True,
                                "join_before_host": True,
                                "mute_upon_entry": False,
                            },
                        },
                    )
                    resp.raise_for_status()
                    meeting = resp.json()

                    meeting_descriptor = {
                        "type": "meeting",
                        "id": str(meeting["id"]),
                        "topic": meeting_data["topic"],
                        "token": meeting_token,
                        "expected_content": meeting_token,
                        "path": f"zoom/meeting/{meeting['id']}",
                    }
                    return meeting_descriptor

            # Create meetings in parallel
            meeting_tasks = [create_meeting(i) for i in range(self.entity_count)]
            meeting_results = await asyncio.gather(*meeting_tasks, return_exceptions=True)

            first_error: Optional[BaseException] = None
            for result in meeting_results:
                if isinstance(result, Exception):
                    # Track the error but still collect any successful creates so they
                    # remain tracked for cleanup later in the run.
                    if first_error is None:
                        first_error = result
                elif result:
                    self._meetings.append(result)
                    all_entities.append(result)
                    self.logger.info(
                        f"✅ Created meeting with token {result['token']}"
                    )

        self.created_entities = all_entities
        if first_error is not None:
            raise first_error

        self.logger.info(f"✅ Created {len(self._meetings)} meetings")
        return all_entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update meetings to test incremental sync.

        Returns:
            List of updated entity descriptors
        """
        self.logger.info("🥁 Updating meetings for incremental sync test")

        if not self._meetings:
            return []

        from monke.generation.zoom import generate_zoom_meeting

        updated_entities: List[Dict[str, Any]] = []

        async with httpx.AsyncClient() as client:
            for i, meeting in enumerate(self._meetings[:2]):
                meeting_data = await generate_zoom_meeting(
                    self.openai_model, meeting["token"]
                )
                resp = await self._request_with_retries(
                    client,
                    "PATCH",
                    f"{self.ZOOM_BASE_URL}/meetings/{meeting['id']}",
                    headers=self._headers(),
                    json={
                        "topic": meeting_data["topic"],
                        "agenda": f"[UPDATED] {meeting_data['agenda']}",
                    },
                )
                resp.raise_for_status()
                meeting["topic"] = meeting_data["topic"]
                updated_entities.append(meeting)
                self.logger.info(
                    f"✅ Updated meeting {i + 1} with token {meeting['token']}"
                )
        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all created test meetings.

        Returns:
            List of deleted meeting IDs
        """
        self.logger.info("🥁 Deleting all test meetings")
        deleted_ids = []

        async with httpx.AsyncClient() as client:
            for meeting in self._meetings:
                resp = await self._request_with_retries(
                    client,
                    "DELETE",
                    f"{self.ZOOM_BASE_URL}/meetings/{meeting['id']}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                deleted_ids.append(meeting["id"])
                self.logger.info(f"Deleted meeting: {meeting['id']}")

        self._meetings = []
        return deleted_ids

    def _meeting_id_from_entity(self, entity: Dict[str, Any]) -> Optional[str]:
        """Get meeting ID from entity descriptor (id or path like zoom/meeting/123)."""
        mid = entity.get("id")
        if mid is not None and str(mid).strip():
            return str(mid)
        path = entity.get("path") or ""
        parts = (path or "").strip().split("/")
        if len(parts) >= 3 and parts[0] == "zoom" and parts[1] == "meeting":
            return parts[-1]
        return None

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific meetings by ID.

        Args:
            entities: List of entity descriptors to delete (id or path zoom/meeting/<id>)

        Returns:
            List of successfully deleted meeting IDs
        """
        self.logger.info(f"🥁 Deleting {len(entities)} specific meetings")
        deleted_ids = []

        async with httpx.AsyncClient() as client:
            for entity in entities:
                entity_id = self._meeting_id_from_entity(entity)
                if not entity_id:
                    raise ValueError(
                        "Entity missing id or path zoom/meeting/<id>: %s"
                        % {k: entity.get(k) for k in ("id", "path", "type")}
                    )
                resp = await self._request_with_retries(
                    client,
                    "DELETE",
                    f"{self.ZOOM_BASE_URL}/meetings/{entity_id}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                deleted_ids.append(entity_id)
                self._meetings = [
                    m for m in self._meetings if m["id"] != entity_id
                ]
        return deleted_ids

    async def cleanup(self):
        """Comprehensive cleanup of ALL test data.

        This should:
        1. Delete current session meetings
        2. Find orphaned test meetings from failed runs
        3. Delete test meetings
        """
        self.logger.info("🧹 Starting comprehensive workspace cleanup")

        cleanup_stats = {
            "meetings_deleted": 0,
            "errors": 0,
        }

        try:
            async with httpx.AsyncClient() as client:
                # Ensure we have user ID
                await self._ensure_user(client)

                # 1. Clean up current session meetings
                for meeting in self._meetings:
                    try:
                        await self._rate_limit()
                        resp = await client.delete(
                            f"{self.ZOOM_BASE_URL}/meetings/{meeting['id']}",
                            headers=self._headers(),
                        )
                        if resp.status_code in (200, 204):
                            cleanup_stats["meetings_deleted"] += 1
                    except Exception as e:
                        self.logger.debug(f"Failed to delete meeting: {e}")
                        cleanup_stats["errors"] += 1

                # 2. Find and clean up orphaned test meetings
                orphaned_meetings = await self._find_test_meetings(client)
                for meeting in orphaned_meetings:
                    try:
                        await self._rate_limit()
                        resp = await client.delete(
                            f"{self.ZOOM_BASE_URL}/meetings/{meeting['id']}",
                            headers=self._headers(),
                        )
                        if resp.status_code in (200, 204):
                            cleanup_stats["meetings_deleted"] += 1
                    except Exception as e:
                        self.logger.debug(f"Failed to delete orphaned meeting: {e}")
                        cleanup_stats["errors"] += 1

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['meetings_deleted']} meetings "
                f"deleted, {cleanup_stats['errors']} errors"
            )

        except Exception as e:
            self.logger.error(f"❌ Error during cleanup: {e}")
            # Don't re-raise - cleanup is best-effort

    async def _ensure_user(self, client: httpx.AsyncClient):
        """Ensure we have the user ID."""
        if self._user_id:
            return

        resp = await self._request_with_retries(
            client,
            "GET",
            f"{self.ZOOM_BASE_URL}/users/me",
            headers=self._headers(),
        )
        resp.raise_for_status()
        user = resp.json()
        self._user_id = user.get("id", "me")
        self.logger.info(f"Using user: {user.get('email', self._user_id)}")

    async def _find_test_meetings(
        self, client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """Find orphaned monke test meetings."""
        test_meetings = []

        try:
            await self._rate_limit()
            resp = await client.get(
                f"{self.ZOOM_BASE_URL}/users/{self._user_id}/meetings",
                headers=self._headers(),
                params={"page_size": 100, "type": "scheduled"},
            )
            resp.raise_for_status()

            meetings = resp.json().get("meetings", [])
            for meeting in meetings:
                topic = meeting.get("topic", "")
                # Look for meetings with our token pattern [xxxxxxxx]
                if "[" in topic and "]" in topic:
                    # Check if it looks like a monke test token (8 char hex)
                    import re

                    if re.search(r"\[[a-f0-9]{8}\]", topic.lower()):
                        test_meetings.append(meeting)

        except Exception as e:
            self.logger.warning(f"Error finding test meetings: {e}")

        return test_meetings

    def _headers(self) -> Dict[str, str]:
        """Return auth headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request_with_retries(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        max_attempts: int = 5,
        **kwargs: Any,
    ) -> httpx.Response:
        """Perform HTTP request with retries on 429 (rate limit).

        Uses Retry-After header when present, otherwise exponential backoff.
        Raises after max_attempts. Other 4xx/5xx are not retried (caller handles).
        """
        last_response: Optional[httpx.Response] = None
        for attempt in range(1, max_attempts + 1):
            await self._rate_limit()
            resp = await client.request(method, url, **kwargs)
            if resp.status_code != 429:
                return resp
            last_response = resp
            # Retry-After can be seconds (int) or HTTP-date
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.strip().isdigit():
                delay = float(retry_after.strip())
            else:
                delay = min(60.0, 2.0 ** attempt)
            self.logger.info(
                "Zoom API 429 rate limit, retry %s/%s in %.1fs",
                attempt,
                max_attempts,
                delay,
            )
            await asyncio.sleep(delay)
        if last_response is not None:
            last_response.raise_for_status()
        raise RuntimeError("_request_with_retries: no response")

    async def _rate_limit(self):
        """Simple rate limiting."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_delay:
            await asyncio.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()
