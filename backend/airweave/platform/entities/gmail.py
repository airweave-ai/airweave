"""Gmail entity schemas.

Defines entity schemas for Gmail resources:
  - Thread
  - Message
  - Attachment
"""

from datetime import datetime
from typing import List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, DeletionEntity, EmailEntity, FileEntity


class GmailThreadEntity(BaseEntity):
    """Schema for Gmail thread entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.threads
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (thread_{thread_id})
    # - breadcrumbs (empty - threads are top-level)
    # - name (from snippet preview)
    # - created_at (None - threads don't have creation timestamp)
    # - updated_at (from last_message_date)

    # API fields
    snippet: Optional[str] = AirweaveField(
        None, description="A short snippet from the thread", embeddable=True
    )
    history_id: Optional[str] = AirweaveField(
        None, description="The thread's history ID", embeddable=False
    )
    message_count: Optional[int] = AirweaveField(
        0, description="Number of messages in the thread", embeddable=False
    )
    label_ids: List[str] = AirweaveField(
        default_factory=list, description="Labels applied to this thread", embeddable=True
    )


class GmailMessageEntity(EmailEntity):
    """Schema for Gmail message entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.messages
    """

    # Base fields are inherited from BaseEntity:
    # - entity_id (msg_{message_id})
    # - breadcrumbs (thread breadcrumb)
    # - name (from subject)
    # - created_at (from date)
    # - updated_at (from internal_date)

    # File fields are inherited from FileEntity (required):
    # - url (link to message in Gmail)
    # - size (message size in bytes)
    # - file_type (set to "html")
    # - mime_type (set to "text/html")
    # - local_path (set after downloading HTML body)

    # Email body content is NOT stored in entity fields
    # It is saved to local_path file for conversion

    # API fields
    thread_id: str = AirweaveField(
        ..., description="ID of the thread this message belongs to", embeddable=False
    )
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
    bcc: List[str] = AirweaveField(
        default_factory=list, description="BCC recipients", embeddable=True
    )
    date: Optional[datetime] = AirweaveField(
        None, description="Date the message was sent", embeddable=True
    )
    snippet: Optional[str] = AirweaveField(
        None, description="Brief snippet of the message content", embeddable=True
    )
    label_ids: List[str] = AirweaveField(
        default_factory=list, description="Labels applied to this message", embeddable=True
    )
    internal_date: Optional[datetime] = AirweaveField(
        None, description="Internal Gmail timestamp", embeddable=False
    )


class GmailAttachmentEntity(FileEntity):
    """Schema for Gmail attachment entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.messages.attachments
    """

    # Base fields are inherited from BaseEntity:
    # - entity_id (attach_{message_id}_{attachment_id})
    # - breadcrumbs (thread and message breadcrumbs)
    # - name (filename)
    # - created_at (None - attachments don't have timestamps)
    # - updated_at (None - attachments don't have timestamps)

    # File fields are inherited from FileEntity:
    # - url (dummy URL for Gmail attachments)
    # - size (from attachment size)
    # - file_type (determined from mime_type)
    # - mime_type
    # - local_path (set after processing bytes)

    # API fields (Gmail-specific)
    message_id: str = AirweaveField(
        ..., description="ID of the message this attachment belongs to", embeddable=False
    )
    attachment_id: str = AirweaveField(..., description="Gmail's attachment ID", embeddable=False)
    thread_id: str = AirweaveField(
        ..., description="ID of the thread containing the message", embeddable=False
    )


class GmailMessageDeletionEntity(DeletionEntity):
    """Deletion signal for a Gmail message.

    Emitted when the Gmail History API reports a messageDeleted. The entity_id matches the
    message entity's ID format (msg_{message_id}) so downstream deletion removes the
    correct parent/children.
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (msg_{message_id})
    # - breadcrumbs (empty - deletions are top-level signals)
    # - name (generic deletion name)
    # - created_at (None - deletions don't have timestamps)
    # - updated_at (None - deletions don't have timestamps)
    # - deletion_status (inherited from DeletionEntity)

    # API fields
    message_id: str = AirweaveField(
        ..., description="The Gmail message ID that was deleted", embeddable=False
    )
    thread_id: Optional[str] = AirweaveField(
        None,
        description="Thread ID (optional if not provided by change record)",
        embeddable=False,
    )
