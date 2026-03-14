"""HERB Meetings entity schemas."""

from datetime import datetime
from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class HerbMeetingTranscriptEntity(BaseEntity):
    """Meeting transcript from the HERB benchmark dataset."""

    meeting_id: str = AirweaveField(
        ...,
        description="HERB meeting transcript ID",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Meeting title (product + date)",
        is_name=True,
        embeddable=True,
    )
    transcript: str = AirweaveField(
        ...,
        description="Full meeting transcript with attendee names and dialogue",
        embeddable=True,
    )
    document_type: str = AirweaveField(
        ...,
        description="Document type classification",
        embeddable=True,
    )
    participant_ids: str = AirweaveField(
        ...,
        description="Comma-separated participant employee IDs",
        embeddable=True,
    )
    participant_names: Optional[str] = AirweaveField(
        None,
        description="Resolved participant names from employee directory",
        embeddable=True,
    )
    meeting_date: Optional[datetime] = AirweaveField(
        None,
        description="Meeting date",
        is_created_at=True,
    )
    product_name: str = AirweaveField(
        ...,
        description="HERB product name this meeting belongs to",
        embeddable=True,
    )


class HerbMeetingChatEntity(BaseEntity):
    """Meeting chat log from the HERB benchmark dataset."""

    chat_id: str = AirweaveField(
        ...,
        description="HERB meeting chat ID",
        is_entity_id=True,
    )
    text: str = AirweaveField(
        ...,
        description="Chat text content",
        is_name=True,
        embeddable=True,
    )
    product_name: str = AirweaveField(
        ...,
        description="HERB product name this chat belongs to",
        embeddable=True,
    )
