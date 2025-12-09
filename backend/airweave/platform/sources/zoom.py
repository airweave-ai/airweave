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

from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
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
    auth_config_class=None,
    config_class=None,
    labels=["Communication", "Meetings", "Video"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class ZoomSource(BaseSource):
    """Zoom source connector integrates with the Zoom API.

    Synchronizes data from Zoom including meetings, participants, recordings,
    and transcripts. Provides comprehensive access to meeting context with
    proper token refresh and rate limiting.
    """

    ZOOM_BASE_URL = "https://api.zoom.us/v2"

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "ZoomSource":
        """Create a new Zoom source instance with the provided OAuth access token.

        Args:
            access_token: OAuth access token for Zoom API
            config: Optional configuration parameters

        Returns:
            Configured ZoomSource instance
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

            # Handle 401 errors by refreshing token and retrying
            if response.status_code == 401:
                self.logger.warning(
                    f"Got 401 Unauthorized from Zoom API at {url}, refreshing token..."
                )
                await self.refresh_on_unauthorized()

                # Get new token and retry
                access_token = await self.get_access_token()
                headers["Authorization"] = f"Bearer {access_token}"
                response = await client.get(url, headers=headers, params=params)

            # Handle 429 Rate Limit
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                self.logger.warning(
                    f"Rate limit hit for {url}, waiting {retry_after} seconds before retry"
                )
                import asyncio

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
                        id=meeting_id,
                        name=topic,
                        created_at=self._parse_datetime(meeting_data.get("start_time")),
                        updated_at=self._parse_datetime(meeting_data.get("created_at")),
                        # API fields
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
            # Don't raise - continue with other entities

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
        from_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        to_date = datetime.utcnow().strftime("%Y-%m-%d")

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
                        id=meeting_id,
                        name=topic,
                        created_at=self._parse_datetime(meeting_data.get("start_time")),
                        updated_at=self._parse_datetime(meeting_data.get("end_time")),
                        # API fields
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
                        id=participant_id,
                        name=name,
                        created_at=self._parse_datetime(participant_data.get("join_time")),
                        updated_at=self._parse_datetime(participant_data.get("leave_time")),
                        # API fields
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
                                id=recording_id,
                                name=transcript_name,
                                created_at=self._parse_datetime(
                                    recording_file.get("recording_start")
                                ),
                                updated_at=self._parse_datetime(
                                    recording_file.get("recording_end")
                                ),
                                # API fields
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
                                id=recording_id,
                                name=recording_name,
                                created_at=self._parse_datetime(
                                    recording_file.get("recording_start")
                                ),
                                updated_at=self._parse_datetime(
                                    recording_file.get("recording_end")
                                ),
                                # API fields
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

        try:
            async with self.http_client() as client:
                self.logger.info("HTTP client created, starting entity generation")

                # Get current user
                user = await self._get_current_user(client)
                user_id = user.get("id", "me")
                self.logger.info(f"Authenticated as user: {user.get('email', user_id)}")

                # 1) Generate scheduled meeting entities
                self.logger.info("Generating scheduled meeting entities...")
                async for meeting_entity in self._generate_meeting_entities(client, user_id):
                    entity_count += 1
                    self.logger.debug(
                        f"Yielding entity #{entity_count}: Meeting - {meeting_entity.topic}"
                    )
                    yield meeting_entity

                # 2) Generate past meeting entities and their participants
                self.logger.info("Generating past meeting entities...")
                past_meetings = []
                async for meeting_entity in self._generate_past_meeting_entities(client, user_id):
                    entity_count += 1
                    self.logger.debug(
                        f"Yielding entity #{entity_count}: Past Meeting - {meeting_entity.topic}"
                    )
                    yield meeting_entity
                    past_meetings.append(meeting_entity)

                # 3) Generate participant entities for past meetings
                for meeting in past_meetings:
                    if meeting.uuid:
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
                            entity_count += 1
                            self.logger.debug(
                                f"Yielding entity #{entity_count}: "
                                f"Participant - {participant_entity.participant_name}"
                            )
                            yield participant_entity

                # 4) Generate recording and transcript entities
                self.logger.info("Generating recording entities...")
                async for recording_entity in self._generate_recording_entities(client, user_id):
                    entity_count += 1
                    self.logger.debug(
                        f"Yielding entity #{entity_count}: {type(recording_entity).__name__}"
                    )
                    yield recording_entity

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
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
