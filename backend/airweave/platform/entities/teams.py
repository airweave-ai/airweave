"""Microsoft Teams entity schemas.

Entity schemas for Microsoft Teams objects based on Microsoft Graph API:
 - Team (top-level organization)
 - Channel (topic-based discussion spaces)
 - Chat (1:1, group, meeting chats)
 - ChatMessage (messages in channels and chats)
 - User (team members)

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/team
  https://learn.microsoft.com/en-us/graph/api/resources/channel
  https://learn.microsoft.com/en-us/graph/api/resources/chat
  https://learn.microsoft.com/en-us/graph/api/resources/chatmessage
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class TeamsUserEntity(BaseEntity):
    """Schema for a Microsoft Teams user.

    Based on the Microsoft Graph user resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/user
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (user ID)
    # - breadcrumbs (empty - users are top-level)
    # - name (from display_name)
    # - created_at (None - users don't have creation timestamp in Teams API)
    # - updated_at (None - users don't have update timestamp in Teams API)

    # API fields
    display_name: Optional[str] = AirweaveField(
        None, description="The name displayed in the address book for the user.", embeddable=True
    )
    user_principal_name: Optional[str] = AirweaveField(
        None,
        description="The user principal name (UPN) of the user (e.g., user@contoso.com).",
        embeddable=True,
    )
    mail: Optional[str] = AirweaveField(
        None, description="The SMTP address for the user.", embeddable=True
    )
    job_title: Optional[str] = AirweaveField(
        None, description="The user's job title.", embeddable=True
    )
    department: Optional[str] = AirweaveField(
        None, description="The department in which the user works.", embeddable=True
    )
    office_location: Optional[str] = AirweaveField(
        None, description="The office location in the user's place of business.", embeddable=True
    )


class TeamsTeamEntity(BaseEntity):
    """Schema for a Microsoft Teams team.

    Based on the Microsoft Graph team resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/team
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (team ID)
    # - breadcrumbs (empty - teams are top-level)
    # - name (from display_name)
    # - created_at (from created_datetime)
    # - updated_at (None - teams don't have update timestamp)

    # API fields
    display_name: str = AirweaveField(..., description="The name of the team.", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="An optional description for the team.", embeddable=True
    )
    visibility: Optional[str] = AirweaveField(
        None,
        description="The visibility of the group and team (Public, Private, HiddenMembership).",
        embeddable=True,
    )
    is_archived: Optional[bool] = AirweaveField(
        None, description="Whether this team is in read-only mode.", embeddable=False
    )
    web_url: Optional[str] = AirweaveField(
        None, description="A hyperlink that goes to the team in Microsoft Teams.", embeddable=False
    )
    classification: Optional[str] = AirweaveField(
        None,
        description="Classification for the team (e.g., low, medium, high business impact).",
        embeddable=True,
    )
    specialization: Optional[str] = AirweaveField(
        None,
        description="Indicates whether the team is intended for a particular use case.",
        embeddable=True,
    )
    internal_id: Optional[str] = AirweaveField(
        None, description="A unique ID for the team used in audit logs.", embeddable=False
    )


class TeamsChannelEntity(BaseEntity):
    """Schema for a Microsoft Teams channel.

    Based on the Microsoft Graph channel resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/channel
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (channel ID)
    # - breadcrumbs (team breadcrumb)
    # - name (from display_name)
    # - created_at (from created_datetime)
    # - updated_at (None - channels don't have update timestamp)

    # API fields
    team_id: str = AirweaveField(
        ..., description="ID of the team this channel belongs to.", embeddable=False
    )
    display_name: str = AirweaveField(
        ..., description="Channel name as it appears to users.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Optional textual description for the channel.", embeddable=True
    )
    email: Optional[str] = AirweaveField(
        None, description="The email address for sending messages to the channel.", embeddable=False
    )
    membership_type: Optional[str] = AirweaveField(
        None,
        description="The type of the channel (standard, private, shared).",
        embeddable=True,
    )
    is_archived: Optional[bool] = AirweaveField(
        None, description="Indicates whether the channel is archived.", embeddable=False
    )
    is_favorite_by_default: Optional[bool] = AirweaveField(
        None,
        description="Indicates whether the channel is recommended for all team members.",
        embeddable=False,
    )
    web_url: Optional[str] = AirweaveField(
        None,
        description="A hyperlink that goes to the channel in Microsoft Teams.",
        embeddable=False,
    )


class TeamsChatEntity(BaseEntity):
    """Schema for a Microsoft Teams chat (1:1, group, or meeting chat).

    Based on the Microsoft Graph chat resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/chat
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (chat ID)
    # - breadcrumbs (empty - chats are top-level)
    # - name (from topic or chat_type)
    # - created_at (from created_datetime)
    # - updated_at (from last_updated_datetime)

    # API fields
    chat_type: str = AirweaveField(
        ...,
        description="Type of chat (oneOnOne, group, meeting).",
        embeddable=True,
    )
    topic: Optional[str] = AirweaveField(
        None,
        description="Subject or topic for the chat (only for group chats).",
        embeddable=True,
    )
    web_url: Optional[str] = AirweaveField(
        None, description="The URL for the chat in Microsoft Teams.", embeddable=False
    )


class TeamsMessageEntity(BaseEntity):
    """Schema for a Microsoft Teams message (in channel or chat).

    Based on the Microsoft Graph chatMessage resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/chatmessage
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (message ID)
    # - breadcrumbs (team/channel or chat breadcrumbs)
    # - name (from subject or body preview)
    # - created_at (from created_datetime)
    # - updated_at (from last_modified_datetime)

    # API fields
    team_id: Optional[str] = AirweaveField(
        None, description="ID of the team (if this is a channel message).", embeddable=False
    )
    channel_id: Optional[str] = AirweaveField(
        None, description="ID of the channel (if this is a channel message).", embeddable=False
    )
    chat_id: Optional[str] = AirweaveField(
        None, description="ID of the chat (if this is a chat message).", embeddable=False
    )
    reply_to_id: Optional[str] = AirweaveField(
        None, description="ID of the parent message (for replies).", embeddable=False
    )
    message_type: Optional[str] = AirweaveField(
        None,
        description="Type of message (message, chatEvent, systemEventMessage).",
        embeddable=True,
    )
    subject: Optional[str] = AirweaveField(
        None, description="The subject of the chat message.", embeddable=True
    )
    body_content: Optional[str] = AirweaveField(
        None, description="The content of the message body.", embeddable=True
    )
    body_content_type: Optional[str] = AirweaveField(
        None, description="The type of the content (html or text).", embeddable=False
    )
    from_user: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Details of the sender of the message.", embeddable=True
    )
    last_edited_datetime: Optional[datetime] = AirweaveField(
        None, description="Timestamp when edits to the message were made.", embeddable=False
    )
    deleted_datetime: Optional[datetime] = AirweaveField(
        None, description="Timestamp at which the message was deleted.", embeddable=False
    )
    importance: Optional[str] = AirweaveField(
        None, description="The importance of the message (normal, high, urgent).", embeddable=True
    )
    mentions: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="List of entities mentioned in the message.",
        embeddable=True,
    )
    attachments: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="References to attached objects like files, tabs, meetings.",
        embeddable=True,
    )
    reactions: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Reactions for this message (e.g., Like).",
        embeddable=True,
    )
    web_url: Optional[str] = AirweaveField(
        None, description="Link to the message in Microsoft Teams.", embeddable=False
    )
