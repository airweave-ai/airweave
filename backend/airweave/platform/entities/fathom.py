"""Entity schemas for Fathom.

Based on the Fathom Video REST API. We sync meeting recordings as searchable
entities with title, participants, speaker-attributed transcript, and metadata.

Fathom API docs: https://fathom.video/api/docs
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class FathomCallEntity(BaseEntity):
    """Schema for a Fathom call recording with speaker-attributed transcript.

    Maps to the recording object from Fathom's list_meetings and
    get_recording_transcript endpoints.
    """

    recording_id: str = AirweaveField(
        ..., description="Unique Fathom recording ID.", is_entity_id=True
    )
    title: str = AirweaveField(
        ..., description="Meeting title.", embeddable=True, is_name=True
    )
    participants: List[str] = AirweaveField(
        default_factory=list,
        description="Email addresses of calendar invitees.",
        embeddable=True,
    )
    participant_names: List[str] = AirweaveField(
        default_factory=list,
        description="Display names of calendar invitees.",
        embeddable=True,
    )
    speakers: List[str] = AirweaveField(
        default_factory=list,
        description="Names of people who actually spoke in the call.",
        embeddable=True,
    )
    duration_minutes: Optional[int] = AirweaveField(
        None, description="Call duration in minutes.", embeddable=True
    )
    call_time: Optional[datetime] = AirweaveField(
        None,
        description="When the call started (UTC).",
        is_created_at=True,
        embeddable=True,
    )
    share_url: Optional[str] = AirweaveField(
        None,
        description="Fathom share link for the recording.",
        embeddable=False,
        unhashable=True,
    )
    meeting_type: Optional[str] = AirweaveField(
        None,
        description="Type based on attendees: 'only_internal' or 'one_or_more_external'.",
        embeddable=True,
    )
    content: Optional[str] = AirweaveField(
        None,
        description="Full speaker-attributed transcript text for search.",
        embeddable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the recording in Fathom."""
        return self.share_url or ""
