"""HERB Messaging entity schemas."""

from datetime import datetime
from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class HerbMessageEntity(BaseEntity):
    """Slack message from the HERB benchmark dataset."""

    message_id: str = AirweaveField(
        ...,
        description="HERB message ID (e.g. '20260421-0-921c4')",
        is_entity_id=True,
    )
    text: str = AirweaveField(
        ...,
        description="Message text content",
        is_name=True,
        embeddable=True,
    )
    sender_id: str = AirweaveField(
        ...,
        description="Sender user ID (e.g. 'eid_9b023657')",
        embeddable=True,
    )
    sender_name: Optional[str] = AirweaveField(
        None,
        description="Resolved sender name from employee directory",
        embeddable=True,
    )
    channel_name: str = AirweaveField(
        ...,
        description="Slack channel name",
        embeddable=True,
    )
    channel_id: str = AirweaveField(
        ...,
        description="Slack channel ID",
    )
    message_time: datetime = AirweaveField(
        ...,
        description="Message timestamp",
        is_created_at=True,
    )
    product_name: str = AirweaveField(
        ...,
        description="HERB product name this message belongs to",
        embeddable=True,
    )
