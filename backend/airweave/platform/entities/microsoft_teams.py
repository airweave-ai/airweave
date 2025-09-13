"""Microsoft Teams entity schemas (delegated)."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import ChunkEntity


class TeamsTeamEntity(ChunkEntity):
    """Entity representing a Microsoft Teams team (group).

    Teams are the top-level organizational unit in Microsoft Teams,
    containing channels where team members collaborate.
    """

    team_id: str = AirweaveField(..., description="Team (Group) ID (GUID).")
    display_name: Optional[str] = AirweaveField(None, description="Team name.", embeddable=True)
    description: Optional[str] = AirweaveField(None, description="Team description.")
    visibility: Optional[str] = AirweaveField(None, description="public/private (if provided).")


class TeamsChannelEntity(ChunkEntity):
    """Entity representing a Microsoft Teams channel within a team.

    Channels are spaces within teams where conversations, files,
    and other collaborative content are organized by topic.
    """

    channel_id: str = AirweaveField(..., description="Channel ID (e.g., 19:...@thread.tacv2).")
    team_id: str = AirweaveField(..., description="Parent Team (Group) ID.")
    display_name: Optional[str] = AirweaveField(None, description="Channel name.", embeddable=True)
    description: Optional[str] = AirweaveField(None, description="Channel description.")
    membership_type: Optional[str] = AirweaveField(None, description="standard/private/shared.")
    is_archived: Optional[bool] = AirweaveField(None, description="Channel archived flag.")


class TeamsMessageEntity(ChunkEntity):
    """Covers both channel and chat messages (channel_id or chat_id will be set)."""

    message_id: str = AirweaveField(..., description="Message ID.")
    team_id: Optional[str] = AirweaveField(None, description="Team (Group) ID if channel message.")
    channel_id: Optional[str] = AirweaveField(None, description="Channel ID if channel message.")
    chat_id: Optional[str] = AirweaveField(
        None, description="Chat ID if 1:1/group/meeting message."
    )
    reply_to_id: Optional[str] = AirweaveField(None, description="Parent message ID (for replies).")

    author_id: Optional[str] = AirweaveField(None, description="Sender AAD object ID.")
    author_display: Optional[str] = AirweaveField(
        None, description="Sender display name/UPN.", embeddable=True
    )

    content: Optional[str] = AirweaveField(
        None, description="HTML/text body content.", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Created datetime.", is_created_at=True
    )
    last_modified_at: Optional[datetime] = AirweaveField(
        None, description="Last modified datetime.", is_updated_at=True
    )
    deleted_at: Optional[datetime] = AirweaveField(
        None, description="Deletion datetime (if deleted)."
    )

    attachments: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Attachment metadata."
    )
    hosted_contents: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Hosted content IDs/types."
    )
    reactions: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Reactions summary."
    )
