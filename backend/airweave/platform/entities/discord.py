"""Discord entity definitions for Airweave.

This module defines schemas for Discord entities including:
- Guilds
- Channels
- Messages
- Users

These entities are authenticated using the Discord OAuth2 configuration.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity

class DiscordGuildEntity(ChunkEntity):
    """Discord guild entity (analogous to ClickUp Workspace)."""

    entity_id: str = Field(..., description="Unique Entity ID")
    guild_id: str = Field(..., description="Guild ID")
    name: str = Field(..., description="Guild name")
    icon: Optional[str] = Field(None, description="Guild icon URL")
    owner_id: str = Field(..., description="ID of the guild owner")
    members: List[Dict[str, Any]] = Field(default_factory=list, description="List of guild members")
    roles: List[Dict[str, Any]] = Field(default_factory=list, description="List of guild roles")
    region: Optional[str] = Field(None, description="Guild voice region")


class DiscordChannelEntity(ChunkEntity):
    """Discord channel entity (analogous to ClickUp Space/Folder)."""

    channel_id: str = Field(..., description="Channel ID")
    guild_id: str = Field(..., description="Parent guild ID")
    name: str = Field(..., description="Channel name")
    type: int = Field(..., description="Channel type (e.g., 0 for text, 2 for voice)")
    private: bool = Field(False, description="Whether the channel is private (DM or restricted)")
    permissions: Dict[str, Any] = Field(default_factory=dict, description="Channel permission overwrites")
    topic: Optional[str] = Field(None, description="Channel topic/description")
    position: int = Field(0, description="Channel position in the guild")


class DiscordMessageEntity(ChunkEntity):
    """Discord message entity (analogous to ClickUp Task)."""

    message_id: str = Field(..., description="Message ID")
    channel_id: str = Field(..., description="Parent channel ID")
    guild_id: Optional[str] = Field(None, description="Parent guild ID (null for DMs)")
    content: str = Field("", description="Message content")
    author: Dict[str, Any] = Field(..., description="Message author information")
    timestamp: datetime = Field(..., description="Message creation timestamp")
    edited_timestamp: Optional[datetime] = Field(None, description="Message edit timestamp")
    mentions: List[Dict[str, Any]] = Field(default_factory=list, description="List of mentioned users")
    reactions: List[Dict[str, Any]] = Field(default_factory=list, description="List of message reactions")
    attachments: List[Dict[str, Any]] = Field(default_factory=list, description="List of message attachments")
    embeds: List[Dict[str, Any]] = Field(default_factory=list, description="List of message embeds")
    pinned: bool = Field(False, description="Whether the message is pinned")
    type: int = Field(0, description="Message type (e.g., 0 for default, 19 for reply)")


class DiscordUserEntity(ChunkEntity):
    """Discord user entity (analogous to ClickUp Comment)."""

    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="User's username")
    discriminator: Optional[str] = Field(None, description="User's discriminator (e.g., #0001)")
    global_name: Optional[str] = Field(None, description="User's global display name")
    avatar: Optional[str] = Field(None, description="User's avatar URL")
    bot: bool = Field(False, description="Whether the user is a bot")
    roles: List[str] = Field(default_factory=list, description="List of role IDs (in guild context)")
    joined_at: Optional[datetime] = Field(None, description="Timestamp when user joined the guild")
    guild_id: Optional[str] = Field(None, description="Parent guild ID (null for non-guild context)")