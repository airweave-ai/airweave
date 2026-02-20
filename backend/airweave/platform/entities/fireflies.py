"""Entity schemas for Fireflies.

Based on the Fireflies GraphQL API (Transcript schema). We sync meeting transcripts
as searchable entities with title, organizer, participants, summary, and sentence-level
content.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


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
