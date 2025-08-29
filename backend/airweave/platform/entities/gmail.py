"""Gmail entity schemas.

Defines entity schemas for Gmail resources:
  - Thread
  - Message
  - Attachment
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import ChunkEntity, FileEntity


class GmailThreadEntity(ChunkEntity):
    """Schema for Gmail thread entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.threads
    """

    snippet: Optional[str] = AirweaveField(
        None, description="A short snippet from the thread", embeddable=True
    )
    history_id: Optional[str] = AirweaveField(None, description="The thread's history ID")
    message_count: Optional[int] = AirweaveField(0, description="Number of messages in the thread")
    label_ids: List[str] = AirweaveField(
        default_factory=list, description="Labels applied to this thread", embeddable=True
    )
    last_message_date: Optional[datetime] = AirweaveField(
        None, description="Date of the last message", is_updated_at=True
    )


class GmailMessageEntity(ChunkEntity):
    """Schema for Gmail message entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.messages
    """

    thread_id: str = AirweaveField(..., description="ID of the thread this message belongs to")
    subject: Optional[str] = AirweaveField(
        None, description="Subject line of the message", embeddable=True
    )
    sender: Optional[str] = AirweaveField(
        None, description="Email address of the sender", embeddable=True
    )
    to: List[str] = AirweaveField(
        default_factory=list, description="Recipients of the message", embeddable=True
    )
    cc: List[str] = AirweaveField(
        default_factory=list, description="CC recipients", embeddable=True
    )
    bcc: List[str] = AirweaveField(default_factory=list, description="BCC recipients")
    date: Optional[datetime] = AirweaveField(
        None, description="Date the message was sent", is_created_at=True
    )
    snippet: Optional[str] = AirweaveField(
        None, description="Brief snippet of the message content", embeddable=True
    )
    body_plain: Optional[str] = AirweaveField(
        None, description="Plain text message body", embeddable=True
    )
    body_html: Optional[str] = AirweaveField(None, description="HTML message body", embeddable=True)
    label_ids: List[str] = AirweaveField(
        default_factory=list, description="Labels applied to this message", embeddable=True
    )
    internal_date: Optional[datetime] = AirweaveField(
        None, description="Internal Gmail timestamp", is_updated_at=True
    )
    size_estimate: Optional[int] = AirweaveField(None, description="Estimated size in bytes")


class GmailAttachmentEntity(FileEntity):
    """Schema for Gmail attachment entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.messages.attachments
    """

    message_id: str = AirweaveField(..., description="ID of the message this attachment belongs to")
    attachment_id: str = AirweaveField(..., description="Gmail's attachment ID")
    thread_id: str = AirweaveField(..., description="ID of the thread containing the message")
    metadata: Optional[Dict[str, Any]] = AirweaveField(
        default_factory=dict, description="Additional metadata about the attachment"
    )

    # Override name and mime_type to remove redundant fields (they're already in FileEntity)
    # This ensures we don't have duplicate fields


class GmailMessageDeletionEntity(ChunkEntity):
    """Deletion signal for a Gmail message.

    Emitted when the Gmail History API reports a messageDeleted. The entity_id matches the
    message entity's ID format so downstream deletion removes the correct parent/children.
    """

    message_id: str = AirweaveField(..., description="The Gmail message ID that was deleted")
    thread_id: str | None = AirweaveField(
        None, description="Thread ID (optional if not provided by change record)"
    )
    deletion_status: str = AirweaveField(
        ..., description="Status indicating the message was removed (e.g., 'removed')"
    )
