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

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Optional

from pydantic import BaseModel
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError, SourceEntityNotFoundError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import ZoomAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.zoom import (
    ZoomMeetingEntity,
    ZoomMeetingParticipantEntity,
    ZoomRecordingEntity,
    ZoomTranscriptEntity,
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


def _parse_dt(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return None


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
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: BaseModel,
    ) -> ZoomSource:
        """Create a ZoomSource instance."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    async def _authed_headers(self) -> Dict[str, str]:
        token = await self.auth.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def _refresh_and_get_headers(self) -> Dict[str, str]:
        new_token = await self.auth.force_refresh()
        return {
            "Authorization": f"Bearer {new_token}",
            "Accept": "application/json",
        }

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[dict] = None) -> Any:
        headers = await self._authed_headers()
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning("Received 401 from Zoom — attempting token refresh")
            headers = await self._refresh_and_get_headers()
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _get_current_user(self) -> Dict[str, Any]:
        url = f"{self.ZOOM_BASE_URL}/users/me"
        return await self._get(url)

    async def _generate_meeting_entities(
        self, user_id: str
    ) -> AsyncGenerator[ZoomMeetingEntity, None]:
        self.logger.info("Starting meeting entity generation")
        url = f"{self.ZOOM_BASE_URL}/users/{user_id}/meetings"
        params = {
            "page_size": 100,
            "type": "scheduled",
        }

        meeting_count = 0
        next_page_token = None

        while True:
            if next_page_token:
                params["next_page_token"] = next_page_token

            data = await self._get(url, params=params)
            meetings = data.get("meetings", [])

            for meeting_data in meetings:
                meeting_count += 1
                meeting_id = str(meeting_data.get("id"))
                topic = meeting_data.get("topic", f"Meeting {meeting_id}")

                yield ZoomMeetingEntity(
                    breadcrumbs=[],
                    name=topic,
                    created_at=_parse_dt(meeting_data.get("start_time")),
                    updated_at=_parse_dt(meeting_data.get("created_at")),
                    meeting_id=meeting_id,
                    topic=topic,
                    meeting_type=meeting_data.get("type"),
                    start_time=_parse_dt(meeting_data.get("start_time")),
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

            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break

        self.logger.info(f"Completed meeting generation. Total meetings: {meeting_count}")

    async def _generate_past_meeting_entities(
        self, user_id: str
    ) -> AsyncGenerator[ZoomMeetingEntity, None]:
        self.logger.info("Starting past meeting entity generation")

        from_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        url = f"{self.ZOOM_BASE_URL}/users/{user_id}/meetings"
        params = {
            "page_size": 100,
            "type": "previous_meetings",
            "from": from_date,
            "to": to_date,
        }

        meeting_count = 0
        next_page_token = None

        while True:
            if next_page_token:
                params["next_page_token"] = next_page_token

            data = await self._get(url, params=params)
            meetings = data.get("meetings", [])

            for meeting_data in meetings:
                meeting_count += 1
                meeting_id = str(meeting_data.get("id"))
                topic = meeting_data.get("topic", f"Meeting {meeting_id}")

                yield ZoomMeetingEntity(
                    breadcrumbs=[],
                    name=topic,
                    created_at=_parse_dt(meeting_data.get("start_time")),
                    updated_at=_parse_dt(meeting_data.get("end_time")),
                    meeting_id=meeting_id,
                    topic=topic,
                    meeting_type=meeting_data.get("type"),
                    start_time=_parse_dt(meeting_data.get("start_time")),
                    duration=meeting_data.get("duration"),
                    timezone=meeting_data.get("timezone"),
                    host_id=meeting_data.get("host_id"),
                    host_email=meeting_data.get("host_email"),
                    status="finished",
                    uuid=meeting_data.get("uuid"),
                )

            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break

        self.logger.info(f"Completed past meeting generation. Total meetings: {meeting_count}")

    async def _generate_participant_entities(
        self,
        meeting_id: str,
        meeting_uuid: str,
        meeting_topic: str,
        meeting_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ZoomMeetingParticipantEntity, None]:
        self.logger.info(f"Fetching participants for meeting: {meeting_topic}")

        uuid_encoded = meeting_uuid.replace("/", "%2F").replace("+", "%2B")
        url = f"{self.ZOOM_BASE_URL}/past_meetings/{uuid_encoded}/participants"
        params = {"page_size": 100}

        try:
            participant_count = 0
            next_page_token = None

            while True:
                if next_page_token:
                    params["next_page_token"] = next_page_token

                data = await self._get(url, params=params)
                participants = data.get("participants", [])

                for participant_data in participants:
                    participant_count += 1
                    user_id = participant_data.get("user_id", participant_data.get("id", ""))
                    name = participant_data.get("name", "Unknown Participant")
                    participant_id = f"{meeting_id}_{user_id}"

                    yield ZoomMeetingParticipantEntity(
                        breadcrumbs=[meeting_breadcrumb],
                        name=name,
                        created_at=_parse_dt(participant_data.get("join_time")),
                        updated_at=_parse_dt(participant_data.get("leave_time")),
                        participant_id=participant_id,
                        participant_name=name,
                        meeting_id=meeting_id,
                        user_id=user_id,
                        user_email=participant_data.get("user_email"),
                        join_time=_parse_dt(participant_data.get("join_time")),
                        leave_time=_parse_dt(participant_data.get("leave_time")),
                        duration=participant_data.get("duration"),
                        registrant_id=participant_data.get("registrant_id"),
                        status=participant_data.get("status"),
                    )

                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break

            self.logger.info(
                f"Completed participant generation for {meeting_topic}. Total: {participant_count}"
            )

        except SourceAuthError:
            raise
        except SourceEntityNotFoundError:
            self.logger.debug(f"No participant data available for meeting {meeting_id}")
        except Exception as e:
            self.logger.warning(f"Error generating participant entities for {meeting_topic}: {e}")

    async def _generate_recording_entities(
        self, user_id: str
    ) -> AsyncGenerator[ZoomRecordingEntity | ZoomTranscriptEntity, None]:
        self.logger.info("Starting recording entity generation")

        from_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        url = f"{self.ZOOM_BASE_URL}/users/{user_id}/recordings"
        params = {
            "page_size": 100,
            "from": from_date,
            "to": to_date,
        }

        recording_count = 0
        transcript_count = 0
        next_page_token = None

        while True:
            if next_page_token:
                params["next_page_token"] = next_page_token

            data = await self._get(url, params=params)
            meetings = data.get("meetings", [])

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

                    if file_type in ("TRANSCRIPT", "CC"):
                        transcript_count += 1
                        transcript_name = f"{meeting_topic} - Transcript"

                        yield ZoomTranscriptEntity(
                            breadcrumbs=[meeting_breadcrumb],
                            name=transcript_name,
                            created_at=_parse_dt(recording_file.get("recording_start")),
                            updated_at=_parse_dt(recording_file.get("recording_end")),
                            transcript_id=recording_id,
                            transcript_name=transcript_name,
                            meeting_id=meeting_id,
                            meeting_topic=meeting_topic,
                            recording_start=_parse_dt(recording_file.get("recording_start")),
                            download_url=recording_file.get("download_url"),
                            file_type=file_type,
                        )
                    else:
                        recording_count += 1
                        recording_name = f"{meeting_topic} - {recording_type or file_type}"

                        yield ZoomRecordingEntity(
                            breadcrumbs=[meeting_breadcrumb],
                            name=recording_name,
                            created_at=_parse_dt(recording_file.get("recording_start")),
                            updated_at=_parse_dt(recording_file.get("recording_end")),
                            recording_id=recording_id,
                            recording_name=recording_name,
                            meeting_id=meeting_id,
                            meeting_topic=meeting_topic,
                            recording_start=_parse_dt(recording_file.get("recording_start")),
                            recording_end=_parse_dt(recording_file.get("recording_end")),
                            file_type=file_type,
                            file_size=recording_file.get("file_size"),
                            file_extension=recording_file.get("file_extension"),
                            play_url=recording_file.get("play_url"),
                            download_url=recording_file.get("download_url"),
                            status=recording_file.get("status"),
                            recording_type=recording_type,
                        )

            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break

        self.logger.info(
            f"Completed recording generation. Recordings: {recording_count}, "
            f"Transcripts: {transcript_count}"
        )

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities for Zoom meetings, participants, and recordings."""
        self.logger.info("Starting Zoom entity generation")
        entity_count = 0

        user = await self._get_current_user()
        user_id = user.get("id", "me")
        self.logger.info(f"Authenticated as user: {user.get('email', user_id)}")

        async for meeting_entity in self._generate_meeting_entities(user_id):
            entity_count += 1
            yield meeting_entity

        past_meetings = []
        async for meeting_entity in self._generate_past_meeting_entities(user_id):
            entity_count += 1
            yield meeting_entity
            past_meetings.append(meeting_entity)

        for meeting in past_meetings:
            if meeting.uuid:
                meeting_breadcrumb = Breadcrumb(
                    entity_id=meeting.meeting_id,
                    name=meeting.topic,
                    entity_type="ZoomMeetingEntity",
                )
                async for participant_entity in self._generate_participant_entities(
                    meeting.meeting_id,
                    meeting.uuid,
                    meeting.topic,
                    meeting_breadcrumb,
                ):
                    entity_count += 1
                    yield participant_entity

        async for recording_entity in self._generate_recording_entities(user_id):
            entity_count += 1
            yield recording_entity

        self.logger.info(f"Zoom entity generation complete: {entity_count} entities")

    async def validate(self) -> None:
        """Validate credentials by pinging the Zoom current-user endpoint."""
        await self._get(f"{self.ZOOM_BASE_URL}/users/me")
