"""Gmail entity schemas.

Defines entity schemas for Gmail resources:
  - Label
  - Thread
  - Message
  - Draft

Each entity represents a distinct Gmail object, with relationships maintained through
references and breadcrumbs rather than nested objects.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.platform.entities._base import ChunkEntity


class GmailLabelEntity(ChunkEntity):
    """Schema for Gmail label entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.labels
    """

    name: str = Field(..., description="The display name of the label")
    label_type: str = Field(..., description="Type of label: 'system' or 'user'")
    message_list_visibility: Optional[str] = Field(None, description="Show/hide in message list")
    label_list_visibility: Optional[str] = Field(None, description="Show/hide in label list")
    total_messages: Optional[int] = Field(0, description="Total number of messages with this label")
    unread_messages: Optional[int] = Field(
        0, description="Number of unread messages with this label"
    )


class GmailThreadEntity(ChunkEntity):
    """Schema for Gmail thread entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.threads
    """

    snippet: Optional[str] = Field(None, description="A short snippet from the thread")
    history_id: Optional[str] = Field(None, description="The thread's history ID")
    message_count: Optional[int] = Field(0, description="Number of messages in the thread")
    label_ids: List[str] = Field(default_factory=list, description="Labels applied to this thread")
    last_message_date: Optional[datetime] = Field(None, description="Date of the last message")


class GmailMessageEntity(ChunkEntity):
    """Schema for Gmail message entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.messages
    """

    thread_id: str = Field(..., description="ID of the thread this message belongs to")
    subject: Optional[str] = Field(None, description="Subject line of the message")
    sender: Optional[str] = Field(None, description="Email address of the sender")
    to: List[str] = Field(default_factory=list, description="Recipients of the message")
    cc: List[str] = Field(default_factory=list, description="CC recipients")
    bcc: List[str] = Field(default_factory=list, description="BCC recipients")
    date: Optional[datetime] = Field(None, description="Date the message was sent")
    snippet: Optional[str] = Field(None, description="Brief snippet of the message content")
    body_plain: Optional[str] = Field(None, description="Plain text message body")
    body_html: Optional[str] = Field(None, description="HTML message body")
    label_ids: List[str] = Field(default_factory=list, description="Labels applied to this message")
    internal_date: Optional[datetime] = Field(None, description="Internal Gmail timestamp")
    size_estimate: Optional[int] = Field(None, description="Estimated size in bytes")


class GmailDraftEntity(ChunkEntity):
    """Schema for Gmail draft entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.drafts
    """

    message_id: Optional[str] = Field(None, description="ID of the draft message")
    thread_id: Optional[str] = Field(None, description="ID of the thread if part of one")
    subject: Optional[str] = Field(None, description="Subject line of the draft")
    to: List[str] = Field(default_factory=list, description="Intended recipients")
    cc: List[str] = Field(default_factory=list, description="Intended CC recipients")
    bcc: List[str] = Field(default_factory=list, description="Intended BCC recipients")
    body_plain: Optional[str] = Field(None, description="Plain text draft content")
    body_html: Optional[str] = Field(None, description="HTML draft content")
    created_date: Optional[datetime] = Field(None, description="Date the draft was created")
    updated_date: Optional[datetime] = Field(None, description="Date the draft was last updated")
