"""Gmail entity schemas.

Defines entity schemas for Gmail resources:
  - Thread
  - Message
  - Attachment
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity


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


class GmailAttachmentEntity(FileEntity):
    """Schema for Gmail attachment entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.messages.attachments
    """

    message_id: str = Field(..., description="ID of the message this attachment belongs to")
    attachment_id: str = Field(..., description="Gmail's attachment ID")
    thread_id: str = Field(..., description="ID of the thread containing the message")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata about the attachment"
    )

    # Override name and mime_type to remove redundant fields (they're already in FileEntity)
    # This ensures we don't have duplicate fields
