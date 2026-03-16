"""Fathom source implementation.

Syncs meeting recordings and speaker-attributed transcripts from the Fathom Video
REST API. Uses a team-level API key for authentication (requires Fathom team plan).

Fathom API docs: https://fathom.video/api/docs

Endpoints used:
  - GET /api/v1/calls   — list meetings with pagination
  - GET /api/v1/calls/{recording_id}/transcript — full transcript with speakers
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from airweave.platform.configs.auth import FathomAuthConfig
from airweave.platform.configs.config import FathomConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.fathom import FathomCallEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

FATHOM_API_BASE = "https://api.fathom.video/api/v1"
CALLS_PAGE_SIZE = 50


@source(
    name="Fathom",
    short_name="fathom",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class=FathomAuthConfig,
    config_class=FathomConfig,
    labels=["Meetings", "Transcription", "Productivity"],
    supports_continuous=False,
)
class FathomSource(BaseSource):
    """Fathom source connector.

    Syncs meeting recordings and transcripts from Fathom Video. Uses the REST API
    with API key authentication (team plan required).
    """

    @classmethod
    async def create(
        cls,
        credentials: FathomAuthConfig,
        config: Optional[Dict[str, Any]] = None,
    ) -> "FathomSource":
        """Create and configure the Fathom source.

        Args:
            credentials: Fathom team API key.
            config: Optional source configuration (meeting_type filter).

        Returns:
            Configured FathomSource instance.
        """
        instance = cls()
        api_key = (credentials.api_key or "").strip()
        if not api_key:
            raise ValueError(
                "Fathom API key is required. Get it from https://fathom.video/settings/api "
                "(requires team plan)."
            )
        instance.api_key = api_key
        instance.config = config or {}
        return instance

    def _headers(self) -> Dict[str, str]:
        """Build request headers with API key authentication."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def _list_meetings(
        self, client: httpx.AsyncClient, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch a page of meetings from the Fathom API.

        Args:
            client: HTTP client.
            cursor: Pagination cursor from previous response.

        Returns:
            Response JSON with items[] and next_cursor.
        """
        params: Dict[str, Any] = {
            "limit": CALLS_PAGE_SIZE,
        }

        meeting_type = self.config.get("meeting_type", "all")
        if meeting_type and meeting_type != "all":
            params["meeting_type"] = meeting_type

        if cursor:
            params["cursor"] = cursor

        response = await client.get(
            f"{FATHOM_API_BASE}/calls",
            params=params,
            headers=self._headers(),
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

    async def _get_transcript(
        self, client: httpx.AsyncClient, recording_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch the full transcript for a specific recording.

        Args:
            client: HTTP client.
            recording_id: Fathom recording ID.

        Returns:
            List of transcript segments with speaker, text, and timestamp.
        """
        response = await client.get(
            f"{FATHOM_API_BASE}/calls/{recording_id}/transcript",
            headers=self._headers(),
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("transcript", [])

    @staticmethod
    def _parse_datetime(iso_string: Optional[str]) -> Optional[datetime]:
        """Parse an ISO 8601 datetime string to UTC datetime."""
        if not iso_string:
            return None
        try:
            return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _calc_duration_minutes(
        start: Optional[str], end: Optional[str]
    ) -> Optional[int]:
        """Calculate duration in minutes from start/end ISO timestamps."""
        if not start or not end:
            return None
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            delta = end_dt - start_dt
            return max(1, int(delta.total_seconds() / 60))
        except (ValueError, AttributeError):
            return None

    def _build_transcript_text(self, segments: List[Dict[str, Any]]) -> Optional[str]:
        """Build a speaker-attributed transcript string from segments.

        Format: [HH:MM:SS] Speaker Name: text

        Args:
            segments: Transcript segments from the Fathom API.

        Returns:
            Formatted transcript text, or None if no segments.
        """
        if not segments:
            return None

        lines = []
        for seg in segments:
            speaker = seg.get("speaker", {})
            display_name = speaker.get("display_name", "Unknown")
            text = (seg.get("text") or "").strip()
            timestamp = seg.get("timestamp", "")
            if text:
                lines.append(f"[{timestamp}] {display_name}: {text}")

        return "\n".join(lines) if lines else None

    def _meeting_to_entity(
        self,
        meeting: Dict[str, Any],
        transcript_segments: List[Dict[str, Any]],
    ) -> FathomCallEntity:
        """Map a meeting object + transcript to a FathomCallEntity.

        Args:
            meeting: Meeting metadata from list_meetings API.
            transcript_segments: Full transcript from get_transcript API.

        Returns:
            FathomCallEntity ready for indexing.
        """
        recording_id = str(meeting.get("recording_id", ""))
        title = meeting.get("title") or meeting.get("meeting_title") or "Untitled meeting"
        invitees = meeting.get("calendar_invitees") or []
        call_time = self._parse_datetime(meeting.get("recording_start_time"))
        duration = self._calc_duration_minutes(
            meeting.get("recording_start_time"),
            meeting.get("recording_end_time"),
        )

        # Extract unique speaker names from transcript
        speaker_names = list(
            {
                seg.get("speaker", {}).get("display_name", "")
                for seg in transcript_segments
                if seg.get("speaker", {}).get("display_name")
            }
        )

        # Build full transcript text for embedding and search
        content = self._build_transcript_text(transcript_segments)

        return FathomCallEntity(
            entity_id=recording_id,
            breadcrumbs=[],
            name=title,
            created_at=call_time,
            updated_at=call_time,
            recording_id=recording_id,
            title=title,
            participants=[inv.get("email", "") for inv in invitees if inv.get("email")],
            participant_names=[inv.get("name", "") for inv in invitees if inv.get("name")],
            speakers=speaker_names,
            duration_minutes=duration,
            call_time=call_time,
            share_url=meeting.get("share_url"),
            meeting_type=meeting.get("calendar_invitees_domains_type"),
            content=content,
        )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate call entities from the Fathom API.

        Paginates through meetings using cursor-based pagination. For each meeting,
        fetches the full transcript and yields a FathomCallEntity.
        """
        cursor = None
        async with self.http_client() as client:
            while True:
                data = await self._list_meetings(client, cursor=cursor)
                items = data.get("items") or []
                if not items:
                    break

                for meeting in items:
                    recording_id = str(meeting.get("recording_id", ""))
                    if not recording_id:
                        continue

                    # Fetch full transcript for this recording
                    try:
                        transcript_segments = await self._get_transcript(
                            client, recording_id
                        )
                    except httpx.HTTPStatusError:
                        # Skip recordings where transcript is unavailable
                        transcript_segments = []

                    yield self._meeting_to_entity(meeting, transcript_segments)

                # Check for next page
                cursor = data.get("next_cursor")
                if not cursor:
                    break

    async def validate(self) -> bool:
        """Validate credentials by listing one meeting.

        Returns:
            True if the API key is valid and returns data.
        """
        try:
            async with self.http_client() as client:
                response = await client.get(
                    f"{FATHOM_API_BASE}/calls",
                    params={"limit": 1},
                    headers=self._headers(),
                    timeout=15.0,
                )
                response.raise_for_status()
                return True
        except (httpx.HTTPStatusError, httpx.RequestError):
            return False
