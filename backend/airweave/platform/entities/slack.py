"""Slack entity schemas."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import Field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import 


class SlackMessageEntity(BaseEntity):
    """Schema for Slack message entities from federated search."""

    # Core message fields
    text: str = AirweaveField(..., description="The text content of the message", embeddable=True)
    user: Optional[str] = AirweaveField(
        None, description="User ID of the message author", embeddable=True
    )
    username: Optional[str] = AirweaveField(
        None, description="Username of the message author", embeddable=True
    )
    ts: str = Field(..., description="Message timestamp (unique identifier)")

    # Channel context
    channel_id: str = Field(..., description="ID of the channel containing this message")
    channel_name: Optional[str] = AirweaveField(
        None, description="Name of the channel", embeddable=True
    )
    channel_is_private: Optional[bool] = Field(None, description="Whether the channel is private")

    # Message metadata
    type: str = Field(default="message", description="Type of the message")
    permalink: Optional[str] = Field(None, description="Permalink to the message in Slack")
    team: Optional[str] = Field(None, description="Team/workspace ID")

    # Surrounding context (for search relevance)
    previous_message: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Previous message for context", embeddable=False
    )
    next_message: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Next message for context", embeddable=False
    )

    # Search metadata
    score: Optional[float] = Field(None, description="Search relevance score from Slack")
    iid: Optional[str] = Field(None, description="Internal search ID")

    # Timestamps
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the message was created",
        embeddable=True,
        is_created_at=True,
    )
