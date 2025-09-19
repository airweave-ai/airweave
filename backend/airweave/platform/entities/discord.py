"""Discord entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import ChunkEntity


class DiscordGuildEntity(ChunkEntity):
    """Discord guild (server)."""

    guild_id: str = AirweaveField(..., description="Guild ID (snowflake).")
    name: Optional[str] = AirweaveField(None, description="Guild name.", embeddable=True)
    description: Optional[str] = AirweaveField(None, description="Guild description.")
    owner_id: Optional[str] = AirweaveField(None, description="Owner user ID.")
    icon: Optional[str] = AirweaveField(None, description="Guild icon hash.")
    features: List[str] = AirweaveField(default_factory=list, description="Guild features list.")


class DiscordChannelEntity(ChunkEntity):
    """Discord channel (text/announcement/thread)."""

    channel_id: str = AirweaveField(..., description="Channel ID (snowflake).")
    guild_id: str = AirweaveField(..., description="Parent guild ID.")
    name: Optional[str] = AirweaveField(None, description="Channel name.", embeddable=True)
    topic: Optional[str] = AirweaveField(None, description="Channel topic.", embeddable=True)
    type: int = AirweaveField(..., description="Discord ChannelType integer.")
    parent_id: Optional[str] = AirweaveField(None, description="Parent category/forum ID.")
    nsfw: Optional[bool] = AirweaveField(None, description="NSFW flag.")
    archived: Optional[bool] = AirweaveField(None, description="(Threads) archived flag.")
    auto_archive_duration: Optional[int] = AirweaveField(
        None, description="(Threads) auto-archive duration (minutes)."
    )


class DiscordMessageEntity(ChunkEntity):
    """Individual Discord message."""

    message_id: str = AirweaveField(..., description="Message ID (snowflake).")
    channel_id: str = AirweaveField(..., description="Channel ID (snowflake).")
    guild_id: str = AirweaveField(..., description="Guild ID (snowflake).")

    author_id: str = AirweaveField(..., description="Author user ID.")
    author_username: Optional[str] = AirweaveField(
        None, description="Author username.", embeddable=True
    )
    author_display: Optional[str] = AirweaveField(None, description="Author display/global name.")
    author_is_bot: Optional[bool] = AirweaveField(None, description="Author is a bot.")

    content: Optional[str] = AirweaveField(None, description="Message content.", embeddable=True)
    timestamp: Optional[datetime] = AirweaveField(
        None, description="Created at.", is_created_at=True
    )
    edited_timestamp: Optional[datetime] = AirweaveField(
        None, description="Last edit.", is_updated_at=True
    )
    pinned: Optional[bool] = AirweaveField(None, description="Pinned flag.")
    type: Optional[int] = AirweaveField(None, description="Discord Message.type enum.")

    mentions: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Mention objects."
    )
    attachments: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Attachment metadata only."
    )
    embeds: List[Dict[str, Any]] = AirweaveField(default_factory=list, description="Embeds.")
    reactions: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Reaction summaries."
    )
    reference: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Message reference (reply/jump)."
    )
