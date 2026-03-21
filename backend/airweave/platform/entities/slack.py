"""Slack entity schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb


def _parse_slack_ts(ts_str: Any) -> Optional[datetime]:
    """Parse Slack message timestamp string to datetime."""
    if not ts_str:
        return None
    try:
        return datetime.fromtimestamp(float(ts_str))
    except (ValueError, TypeError):
        return None


class SlackMessageEntity(BaseEntity):
    """Schema for Slack message entities from federated search.

    Reference:
        https://api.slack.com/methods/search.messages
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (message IID or timestamp)
    # - breadcrumbs (channel breadcrumb)
    # - name (from text preview)
    # - created_at (from timestamp)
    # - updated_at (None - messages don't have update timestamp)

    # API fields
    text: str = AirweaveField(
        ..., description="The text content of the message", embeddable=True, is_name=True
    )
    user: Optional[str] = AirweaveField(
        None, description="User ID of the message author", embeddable=False
    )
    username: Optional[str] = AirweaveField(
        None, description="Username of the message author", embeddable=True
    )
    ts: str = AirweaveField(
        ...,
        description="Message timestamp (unique identifier)",
        embeddable=False,
        is_entity_id=True,
    )
    channel_id: str = AirweaveField(
        ..., description="ID of the channel containing this message", embeddable=False
    )
    channel_name: Optional[str] = AirweaveField(
        None, description="Name of the channel", embeddable=True
    )
    channel_is_private: Optional[bool] = AirweaveField(
        None, description="Whether the channel is private", embeddable=False
    )
    type: str = AirweaveField(
        default="message", description="Type of the message", embeddable=False
    )
    permalink: Optional[str] = AirweaveField(
        None, description="Permalink to the message in Slack", embeddable=False
    )
    team: Optional[str] = AirweaveField(None, description="Team/workspace ID", embeddable=False)
    previous_message: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Previous message for context", embeddable=False
    )
    next_message: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Next message for context", embeddable=False
    )
    score: Optional[float] = AirweaveField(
        None, description="Search relevance score from Slack", embeddable=False
    )
    iid: Optional[str] = AirweaveField(None, description="Internal search ID", embeddable=False)
    url: Optional[str] = AirweaveField(
        None, description="URL to view the message in Slack", embeddable=False
    )
    message_time: datetime = AirweaveField(
        ..., description="Timestamp converted to datetime for hashing checks.", is_created_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="Permalink to open the message.", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        breadcrumbs: List[Breadcrumb],
    ) -> SlackMessageEntity:
        """Build from a Slack search.messages match object."""
        channel_info = data.get("channel", {})
        ts = data.get("ts", "0")
        created_at = _parse_slack_ts(ts)

        text = data.get("text", "")
        preview = text[:50] + "..." if len(text) > 50 else text
        name = preview or f"Slack message {ts}"

        return cls(
            entity_id=data.get("iid", data.get("ts", "")),
            breadcrumbs=breadcrumbs,
            name=name,
            created_at=created_at,
            updated_at=None,
            text=text or name,
            user=data.get("user"),
            username=data.get("username"),
            ts=ts,
            channel_id=channel_info.get("id", "unknown"),
            channel_name=channel_info.get("name"),
            channel_is_private=channel_info.get("is_private", False),
            type=data.get("type", "message"),
            permalink=data.get("permalink"),
            team=data.get("team"),
            previous_message=data.get("previous"),
            next_message=data.get("next"),
            score=float(data.get("score", 0)),
            iid=data.get("iid"),
            url=data.get("permalink"),
            message_time=created_at or datetime.utcnow(),
            web_url_value=data.get("permalink"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Permalink for the Slack message."""
        return self.web_url_value or self.url or ""
