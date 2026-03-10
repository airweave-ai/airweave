"""Zoom source implementation.

Retrieves data from Zoom, including:
 - Meetings (scheduled and past)
 - Meeting participants
 - Cloud recordings
 - Meeting transcripts

Reference:
  https://developers.zoom.us/docs/api/
  https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#operation/meetings
  https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#operation/recordingGet
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import ZoomAuthConfig
from airweave.platform.cursors import ZoomCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.zoom import (
    ZoomMeetingEntity,
    ZoomMeetingParticipantEntity,
    ZoomRecordingEntity,
    ZoomTranscriptEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Zoom",
    short_name="zoom",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=ZoomAuthConfig,
    config_class=None,
    labels=["Communication", "Meetings", "Video"],
    supports_continuous=True,
    cursor_class=ZoomCursor,
    rate_limit_level=RateLimitLevel.ORG,
)
class ZoomSource(BaseSource):
    """Zoom source connector integrates with the Zoom API.

    Synchronizes data from Zoom including meetings, participants, recordings,
    and transcripts. Provides comprehensive access to meeting context with
    proper token refresh and rate limiting.
    """

    ZOOM_BASE_URL = "https://api.zoom.us/v2"
    access_token: str = ""

    @classmethod
    async def create(
        cls, credentials: Optional[Any] = None, config: Optional[Dict[str, Any]] = None
    ) -> "ZoomSource":
        """Create a new Zoom source instance.

        For OAuth-based Zoom sources, `credentials` is expected to be an access
        token string or an auth config object exposing an `access_token`
        attribute. The config dict is currently unused but accepted for
        compatibility with BaseSource.create.
        """
        instance = cls()
        access_token: Optional[str] = None
        if isinstance(credentials, str):
            access_token = credentials
        elif hasattr(credentials, "access_token"):
            access_token = credentials.access_token

        if not access_token:
            raise ValueError("ZoomSource.create requires an access token in credentials")

        instance.access_token = access_token
        return instance

    def _get_last_synced_at(self) -> Optional[datetime]:
        """Return the last synced-at timestamp from the cursor, if available."""
        cursor_data = self.cursor.data if getattr(self, "cursor", None) else {}
        raw = cursor_data.get("last_synced_at") or ""
        if not raw:
            return None
        try:
            # Support both plain ISO strings and Z-suffixed values
            if raw.endswith("Z"):
                raw = raw.replace("Z", "+00:00")
            return datetime.fromisoformat(raw)
        except Exception:
            # If parsing fails, fall back to no cursor to avoid skipping data
            return None

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[dict] = None
    ) -> dict:
        """Make an authenticated GET request to Zoom API.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response data
        """
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 Unauthorized - token might have expired
            if response.status_code == 401:
                self.logger.warning(
                    f"Got 401 Unauthorized from Zoom API at {url}, refreshing token..."
                )
                if self.token_provider:
                    try:
                        new_token = await self.token_provider.force_refresh()
                        headers["Authorization"] = f"Bearer {new_token}"
                        self.logger.debug(f"Retrying with refreshed token: {url}")
                        response = await client.get(url, headers=headers, params=params)
                    except TokenRefreshError as e:
                        self.logger.error(f"Failed to refresh Zoom token: {str(e)}")
                        response.raise_for_status()
                else:
                    self.logger.error("No token manager available to refresh expired token")
                    response.raise_for_status()

            # Handle 429 Rate Limit
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                self.logger.warning(
                    f"Rate limit hit for {url}, waiting {retry_after} seconds before retry"
                )

                await asyncio.sleep(float(retry_after))
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error in API request to {url}: {str(e)}")
            raise

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from Zoom API format.

        Args:
            dt_str: DateTime string from API

        Returns:
            Parsed datetime object or None
        """
        if not dt_str:
            return None
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error parsing datetime {dt_str}: {str(e)}")
            return None

    async def _get_current_user(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Get current authenticated user info.

        Args:
            client: HTTP client for API requests

        Returns:
            User info dictionary
        """
        url = f"{self.ZOOM_BASE_URL}/users/me"
        return await self._get_with_auth(client, url)

    async def _generate_meeting_entities(
        self, client: httpx.AsyncClient, user_id: str
    ) -> AsyncGenerator[ZoomMeetingEntity, None]:
        """Generate ZoomMeetingEntity objects for user's meetings.

        Args:
            client: HTTP client for API requests
            user_id: Zoom user ID

        Yields:
            ZoomMeetingEntity objects
        """
        self.logger.info("Starting meeting entity generation")
        url = f"{self.ZOOM_BASE_URL}/users/{user_id}/meetings"
        params = {
            "page_size": 100,
            "type": "scheduled",  # Get scheduled meetings
        }

        try:
            meeting_count = 0
            next_page_token = None

            while True:
                if next_page_token:
                    params["next_page_token"] = next_page_token

                self.logger.debug(f"Fetching meetings from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                meetings = data.get("meetings", [])
                self.logger.info(f"Retrieved {len(meetings)} meetings")

                for meeting_data in meetings:
                    meeting_count += 1
                    meeting_id = str(meeting_data.get("id"))
                    topic = meeting_data.get("topic", f"Meeting {meeting_id}")

                    self.logger.debug(f"Processing meeting #{meeting_count}: {topic}")

                    yield ZoomMeetingEntity(
                        breadcrumbs=[],
                        name=topic,
                        created_at=self._parse_datetime(meeting_data.get("start_time")),
                        updated_at=self._parse_datetime(meeting_data.get("created_at")),
                        meeting_id=meeting_id,
                        topic=topic,
                        meeting_type=meeting_data.get("type"),
                        start_time=self._parse_datetime(meeting_data.get("start_time")),
                        duration=meeting_data.get("duration"),
                        timezone=meeting_data.get("timezone"),
                        agenda=meeting_data.get("agenda"),
                        host_id=meeting_data.get("host_id"),
                        host_email=meeting_data.get("host_email"),
                        status=meeting_data.get("status"),
                        join_url=meeting_data.get("join_url"),
                        password=meeting_data.get("password"),
                        uuid=meeting_data.get("uuid"),
                    )

                # Handle pagination
                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break

            self.logger.info(f"Completed meeting generation. Total meetings: {meeting_count}")

        except Exception as e:
            self.logger.error(f"Error generating meeting entities: {str(e)}")
            # Re-raise so sync fails visibly; otherwise we yield 0 and orphan cleanup removes all
            raise

    async def _generate_past_meeting_entities(
        self, client: httpx.AsyncClient, user_id: str
    ) -> AsyncGenerator[ZoomMeetingEntity, None]:
        """Generate ZoomMeetingEntity objects for past meetings with participants.

        Args:
            client: HTTP client for API requests
            user_id: Zoom user ID

        Yields:
            ZoomMeetingEntity objects
        """
        self.logger.info("Starting past meeting entity generation")

        # Get meetings from the last 30 days
        from_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        url = f"{self.ZOOM_BASE_URL}/users/{user_id}/meetings"
        params = {
            "page_size": 100,
            "type": "previous_meetings",
            "from": from_date,
            "to": to_date,
        }

        try:
            meeting_count = 0
            next_page_token = None

            while True:
                if next_page_token:
                    params["next_page_token"] = next_page_token

                self.logger.debug(f"Fetching past meetings from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                meetings = data.get("meetings", [])
                self.logger.info(f"Retrieved {len(meetings)} past meetings")

                for meeting_data in meetings:
                    meeting_count += 1
                    meeting_id = str(meeting_data.get("id"))
                    topic = meeting_data.get("topic", f"Meeting {meeting_id}")

                    self.logger.debug(f"Processing past meeting #{meeting_count}: {topic}")

                    yield ZoomMeetingEntity(
                        breadcrumbs=[],
                        name=topic,
                        created_at=self._parse_datetime(meeting_data.get("start_time")),
                        updated_at=self._parse_datetime(meeting_data.get("end_time")),
                        meeting_id=meeting_id,
                        topic=topic,
                        meeting_type=meeting_data.get("type"),
                        start_time=self._parse_datetime(meeting_data.get("start_time")),
                        duration=meeting_data.get("duration"),
                        timezone=meeting_data.get("timezone"),
                        host_id=meeting_data.get("host_id"),
                        host_email=meeting_data.get("host_email"),
                        status="finished",
                        uuid=meeting_data.get("uuid"),
                    )

                # Handle pagination
                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break

            self.logger.info(f"Completed past meeting generation. Total meetings: {meeting_count}")

        except Exception as e:
            self.logger.error(f"Error generating past meeting entities: {str(e)}")
            raise

    async def _generate_participant_entities(
        self,
        client: httpx.AsyncClient,
        meeting_id: str,
        meeting_uuid: str,
        meeting_topic: str,
        meeting_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ZoomMeetingParticipantEntity, None]:
        """Generate ZoomMeetingParticipantEntity objects for a past meeting.

        Args:
            client: HTTP client for API requests
            meeting_id: Meeting ID
            meeting_uuid: Meeting UUID (for past meeting details)
            meeting_topic: Meeting topic for breadcrumb
            meeting_breadcrumb: Breadcrumb for the meeting

        Yields:
            ZoomMeetingParticipantEntity objects
        """
        self.logger.info(f"Fetching participants for meeting: {meeting_topic}")

        # Use meeting UUID for past meeting participants (double URL encode if needed)
        uuid_encoded = meeting_uuid.replace("/", "%2F").replace("+", "%2B")
        url = f"{self.ZOOM_BASE_URL}/past_meetings/{uuid_encoded}/participants"
        params = {"page_size": 100}

        try:
            participant_count = 0
            next_page_token = None

            while True:
                if next_page_token:
                    params["next_page_token"] = next_page_token

                self.logger.debug(f"Fetching participants from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                participants = data.get("participants", [])
                self.logger.info(f"Retrieved {len(participants)} participants for {meeting_topic}")

                for participant_data in participants:
                    participant_count += 1
                    user_id = participant_data.get("user_id", participant_data.get("id", ""))
                    name = participant_data.get("name", "Unknown Participant")

                    # Create unique participant ID
                    participant_id = f"{meeting_id}_{user_id}"

                    self.logger.debug(f"Processing participant #{participant_count}: {name}")

                    yield ZoomMeetingParticipantEntity(
                        breadcrumbs=[meeting_breadcrumb],
                        name=name,
                        created_at=self._parse_datetime(participant_data.get("join_time")),
                        updated_at=self._parse_datetime(participant_data.get("leave_time")),
                        participant_id=participant_id,
                        participant_name=name,
                        meeting_id=meeting_id,
                        user_id=user_id,
                        user_email=participant_data.get("user_email"),
                        join_time=self._parse_datetime(participant_data.get("join_time")),
                        leave_time=self._parse_datetime(participant_data.get("leave_time")),
                        duration=participant_data.get("duration"),
                        registrant_id=participant_data.get("registrant_id"),
                        status=participant_data.get("status"),
                    )

                # Handle pagination
                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break

            self.logger.info(
                f"Completed participant generation for {meeting_topic}. Total: {participant_count}"
            )

        except httpx.HTTPStatusError as e:
            # 404 means no participant data available for this meeting
            if e.response.status_code == 404:
                self.logger.debug(f"No participant data available for meeting {meeting_id}")
            else:
                self.logger.error(f"Error fetching participants for {meeting_topic}: {str(e)}")
        except Exception as e:
            self.logger.error(
                f"Error generating participant entities for {meeting_topic}: {str(e)}"
            )

    async def _generate_recording_entities(
        self, client: httpx.AsyncClient, user_id: str
    ) -> AsyncGenerator[ZoomRecordingEntity | ZoomTranscriptEntity, None]:
        """Generate recording and transcript entities for user's cloud recordings.

        Args:
            client: HTTP client for API requests
            user_id: Zoom user ID

        Yields:
            ZoomRecordingEntity and ZoomTranscriptEntity objects
        """
        self.logger.info("Starting recording entity generation")

        # Get recordings from the last 30 days
        from_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        to_date = datetime.utcnow().strftime("%Y-%m-%d")

        url = f"{self.ZOOM_BASE_URL}/users/{user_id}/recordings"
        params = {
            "page_size": 100,
            "from": from_date,
            "to": to_date,
        }

        try:
            recording_count = 0
            transcript_count = 0
            next_page_token = None

            while True:
                if next_page_token:
                    params["next_page_token"] = next_page_token

                self.logger.debug(f"Fetching recordings from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                meetings = data.get("meetings", [])
                self.logger.info(f"Retrieved recordings for {len(meetings)} meetings")

                for meeting_data in meetings:
                    meeting_id = str(meeting_data.get("id"))
                    meeting_topic = meeting_data.get("topic", f"Meeting {meeting_id}")

                    meeting_breadcrumb = Breadcrumb(
                        entity_id=meeting_id,
                        name=meeting_topic,
                        entity_type="ZoomMeetingEntity",
                    )

                    recording_files = meeting_data.get("recording_files", [])

                    for recording_file in recording_files:
                        recording_id = recording_file.get("id")
                        file_type = recording_file.get("file_type", "")
                        recording_type = recording_file.get("recording_type", "")

                        # Check if this is a transcript file
                        if file_type in ("TRANSCRIPT", "CC"):
                            transcript_count += 1
                            transcript_name = f"{meeting_topic} - Transcript"

                            yield ZoomTranscriptEntity(
                                breadcrumbs=[meeting_breadcrumb],
                                name=transcript_name,
                                created_at=self._parse_datetime(
                                    recording_file.get("recording_start")
                                ),
                                updated_at=self._parse_datetime(
                                    recording_file.get("recording_end")
                                ),
                                transcript_id=recording_id,
                                transcript_name=transcript_name,
                                meeting_id=meeting_id,
                                meeting_topic=meeting_topic,
                                recording_start=self._parse_datetime(
                                    recording_file.get("recording_start")
                                ),
                                download_url=recording_file.get("download_url"),
                                file_type=file_type,
                            )
                        else:
                            recording_count += 1
                            recording_name = f"{meeting_topic} - {recording_type or file_type}"

                            yield ZoomRecordingEntity(
                                breadcrumbs=[meeting_breadcrumb],
                                name=recording_name,
                                created_at=self._parse_datetime(
                                    recording_file.get("recording_start")
                                ),
                                updated_at=self._parse_datetime(
                                    recording_file.get("recording_end")
                                ),
                                recording_id=recording_id,
                                recording_name=recording_name,
                                meeting_id=meeting_id,
                                meeting_topic=meeting_topic,
                                recording_start=self._parse_datetime(
                                    recording_file.get("recording_start")
                                ),
                                recording_end=self._parse_datetime(
                                    recording_file.get("recording_end")
                                ),
                                file_type=file_type,
                                file_size=recording_file.get("file_size"),
                                file_extension=recording_file.get("file_extension"),
                                play_url=recording_file.get("play_url"),
                                download_url=recording_file.get("download_url"),
                                status=recording_file.get("status"),
                                recording_type=recording_type,
                            )

                # Handle pagination
                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break

            self.logger.info(
                f"Completed recording generation. Recordings: {recording_count}, "
                f"Transcripts: {transcript_count}"
            )

        except Exception as e:
            self.logger.error(f"Error generating recording entities: {str(e)}")
            raise

    async def _yield_scheduled_meetings_incremental(
        self,
        client: httpx.AsyncClient,
        user_id: str,
        last_synced_at: Optional[datetime],
        update_max: Any,
    ) -> AsyncGenerator[ZoomMeetingEntity, None]:
        """Yield scheduled meeting entities, skipping those already synced."""
        async for meeting_entity in self._generate_meeting_entities(client, user_id):
            effective_ts = meeting_entity.start_time or meeting_entity.created_at
            update_max(effective_ts)
            if last_synced_at and effective_ts and effective_ts <= last_synced_at:
                continue
            yield meeting_entity

    async def _yield_past_meetings_and_participants_incremental(
        self,
        client: httpx.AsyncClient,
        user_id: str,
        last_synced_at: Optional[datetime],
        update_max: Any,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield past meeting entities and their participants, skipping already synced."""
        past_meetings: list[ZoomMeetingEntity] = []
        async for meeting_entity in self._generate_past_meeting_entities(client, user_id):
            effective_ts = (
                meeting_entity.updated_at or meeting_entity.start_time or meeting_entity.created_at
            )
            update_max(effective_ts)
            if last_synced_at and effective_ts and effective_ts <= last_synced_at:
                continue
            yield meeting_entity
            past_meetings.append(meeting_entity)

        for meeting in past_meetings:
            if not meeting.uuid:
                continue
            meeting_breadcrumb = Breadcrumb(
                entity_id=meeting.meeting_id,
                name=meeting.topic,
                entity_type="ZoomMeetingEntity",
            )
            async for participant_entity in self._generate_participant_entities(
                client,
                meeting.meeting_id,
                meeting.uuid,
                meeting.topic,
                meeting_breadcrumb,
            ):
                yield participant_entity

    async def _yield_recording_entities_incremental(
        self,
        client: httpx.AsyncClient,
        user_id: str,
        last_synced_at: Optional[datetime],
        update_max: Any,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield recording and transcript entities, skipping already synced."""
        async for recording_entity in self._generate_recording_entities(client, user_id):
            effective_ts: Optional[datetime] = None
            if isinstance(recording_entity, ZoomRecordingEntity):
                effective_ts = (
                    recording_entity.recording_end
                    or recording_entity.recording_start
                    or recording_entity.created_at
                )
            elif isinstance(recording_entity, ZoomTranscriptEntity):
                effective_ts = recording_entity.recording_start or recording_entity.created_at
            update_max(effective_ts)
            if last_synced_at and effective_ts and effective_ts <= last_synced_at:
                continue
            yield recording_entity

    def _persist_cursor_on_success(
        self,
        max_seen_timestamp: Optional[datetime],
        entity_count: int,
    ) -> None:
        """Update cursor with last_synced_at only when we have a successful run with data."""
        if not self.cursor or not max_seen_timestamp or entity_count <= 0:
            return
        ts = (
            max_seen_timestamp
            if max_seen_timestamp.tzinfo
            else max_seen_timestamp.replace(tzinfo=timezone.utc)
        )
        self.cursor.update(last_synced_at=ts.isoformat())

    async def _stream_all_entities_incremental(
        self,
        client: httpx.AsyncClient,
        user_id: str,
        last_synced_at: Optional[datetime],
        update_max: Any,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield all Zoom entities in order (scheduled, past+participants, recordings)."""
        self.logger.info("Generating scheduled meeting entities...")
        async for entity in self._yield_scheduled_meetings_incremental(
            client, user_id, last_synced_at, update_max
        ):
            yield entity
        self.logger.info("Generating past meeting entities...")
        async for entity in self._yield_past_meetings_and_participants_incremental(
            client, user_id, last_synced_at, update_max
        ):
            yield entity
        self.logger.info("Generating recording entities...")
        async for entity in self._yield_recording_entities_incremental(
            client, user_id, last_synced_at, update_max
        ):
            yield entity

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Zoom entities.

        Yields entities in the following order:
          - ZoomMeetingEntity for scheduled meetings
          - ZoomMeetingEntity for past meetings
          - ZoomMeetingParticipantEntity for participants in past meetings
          - ZoomRecordingEntity for cloud recordings
          - ZoomTranscriptEntity for meeting transcripts
        """
        self.logger.info("===== STARTING ZOOM ENTITY GENERATION =====")
        entity_count = 0
        last_synced_at = self._get_last_synced_at()
        self.logger.info(
            f"Incremental sync since {last_synced_at.isoformat()}"
            if last_synced_at
            else "Full 30-day sync (no cursor found)"
        )
        max_seen_timestamp: Optional[datetime] = last_synced_at

        def _update_max(ts: Optional[datetime]) -> None:
            nonlocal max_seen_timestamp
            if ts is None:
                return
            if max_seen_timestamp is None or ts > max_seen_timestamp:
                max_seen_timestamp = ts

        try:
            async with self.http_client() as client:
                self.logger.info("HTTP client created, starting entity generation")
                user = await self._get_current_user(client)
                user_id = user.get("id", "me")
                self.logger.info(f"Authenticated as user: {user.get('email', user_id)}")
                async for entity in self._stream_all_entities_incremental(
                    client, user_id, last_synced_at, _update_max
                ):
                    entity_count += 1
                    label = getattr(
                        entity, "topic", getattr(entity, "participant_name", type(entity).__name__)
                    )
                    self.logger.debug(f"Yielding entity #{entity_count}: {label}")
                    yield entity
        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        else:
            self._persist_cursor_on_success(max_seen_timestamp, entity_count)
        finally:
            self.logger.info(
                f"===== ZOOM ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def validate(self) -> bool:
        """Verify Zoom OAuth2 token by pinging the users/me endpoint.

        Returns:
            True if token is valid, False otherwise
        """
        return await self._validate_oauth2(
            ping_url=f"{self.ZOOM_BASE_URL}/users/me",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
