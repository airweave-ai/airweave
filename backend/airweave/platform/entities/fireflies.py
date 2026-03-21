"""Entity schemas for Fireflies.

Based on the Fireflies GraphQL API (Transcript schema). We sync meeting transcripts
as searchable entities with title, organizer, participants, summary, and sentence-level
content.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


def _parse_epoch_ms(ms: Optional[float]) -> Optional[datetime]:
    """Convert milliseconds since epoch to UTC datetime."""
    if ms is None:
        return None
    try:
        return datetime.utcfromtimestamp(ms / 1000.0)
    except (OSError, ValueError):
        return None


def _normalize_action_items(value: Any) -> Optional[List[str]]:
    """Normalize action_items from API (string or list) to List[str]."""
    if value is None:
        return None
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [s.strip() for s in value.split("\n") if s.strip()] or None
    return None


class FirefliesTranscriptEntity(BaseEntity):
    """Schema for a Fireflies meeting transcript.

    Maps to the Transcript type in the Fireflies GraphQL API.
    See https://docs.fireflies.ai/schema/transcript
    """

    transcript_id: str = AirweaveField(
        ..., description="Unique identifier of the transcript.", is_entity_id=True
    )
    title: str = AirweaveField(
        ..., description="Title of the meeting/transcript.", embeddable=True, is_name=True
    )
    organizer_email: Optional[str] = AirweaveField(
        None, description="Email address of the meeting organizer.", embeddable=True
    )
    transcript_url: Optional[str] = AirweaveField(
        None,
        description="URL to view the transcript in the Fireflies dashboard.",
        embeddable=False,
        unhashable=True,
    )
    participants: List[str] = AirweaveField(
        default_factory=list,
        description="Email addresses of meeting participants.",
        embeddable=True,
    )
    duration: Optional[float] = AirweaveField(
        None, description="Duration of the audio in minutes.", embeddable=True
    )
    date: Optional[float] = AirweaveField(
        None,
        description="Date the transcript was created (milliseconds since epoch, UTC).",
        embeddable=False,
    )
    date_string: Optional[str] = AirweaveField(
        None,
        description="ISO 8601 date-time string when the transcript was created.",
        embeddable=True,
    )
    created_time: Optional[datetime] = AirweaveField(
        None,
        description="Parsed creation timestamp for the transcript.",
        is_created_at=True,
        embeddable=True,
    )
    speakers: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Speakers in the transcript (id, name).",
        embeddable=True,
    )
    summary_overview: Optional[str] = AirweaveField(
        None,
        description="AI-generated summary overview of the meeting.",
        embeddable=True,
    )
    summary_keywords: List[str] = AirweaveField(
        default_factory=list,
        description="Keywords extracted from the meeting.",
        embeddable=True,
    )
    summary_action_items: Optional[List[str]] = AirweaveField(
        None,
        description="Action items from the meeting summary.",
        embeddable=True,
    )
    content: Optional[str] = AirweaveField(
        None,
        description="Full transcript text (concatenated sentences) for search.",
        embeddable=True,
    )
    fireflies_users: List[str] = AirweaveField(
        default_factory=list,
        description="Emails of Fireflies users who participated.",
        embeddable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the transcript in Fireflies."""
        return self.transcript_url or ""

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> FirefliesTranscriptEntity:
        """Build from a Fireflies GraphQL transcript object."""
        transcript_id = data.get("id") or ""
        title = data.get("title") or "Untitled meeting"
        date_ms = data.get("date")
        created_time = _parse_epoch_ms(date_ms)

        summary = data.get("summary") or {}
        sentences = data.get("sentences") or []
        content_parts = [
            raw
            for s in sentences
            if (raw := (s.get("raw_text") or s.get("text") or "").strip())
        ]
        content = "\n".join(content_parts) if content_parts else None

        return cls(
            entity_id=transcript_id,
            breadcrumbs=[],
            name=title,
            created_at=created_time,
            updated_at=created_time,
            transcript_id=transcript_id,
            title=title,
            organizer_email=data.get("organizer_email"),
            transcript_url=data.get("transcript_url"),
            participants=data.get("participants") or [],
            duration=data.get("duration"),
            date=date_ms,
            date_string=data.get("dateString"),
            created_time=created_time,
            speakers=data.get("speakers") or [],
            summary_overview=summary.get("overview") or summary.get("short_summary"),
            summary_keywords=summary.get("keywords") or [],
            summary_action_items=_normalize_action_items(summary.get("action_items")),
            content=content,
            fireflies_users=data.get("fireflies_users") or [],
        )
