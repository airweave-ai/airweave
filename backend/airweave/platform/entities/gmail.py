"""Gmail entity schemas.

Defines entity schemas for Gmail resources:
  - Thread
  - Message
  - Attachment
"""

from datetime import datetime
from typing import List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, DeletionEntity, EmailEntity, FileEntity


class GmailThreadEntity(BaseEntity):
    """Schema for Gmail thread entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.threads
    """

    thread_key: str = AirweaveField(
        ...,
        description="Stable Airweave thread key (thread_<gmail_id>)",
        is_entity_id=True,
    )
    gmail_thread_id: str = AirweaveField(
        ..., description="Native Gmail thread ID", embeddable=False
    )
    title: str = AirweaveField(
        ...,
        description="Display title derived from snippet",
        is_name=True,
        embeddable=True,
    )
    last_message_at: Optional[datetime] = AirweaveField(
        None,
        description="Timestamp of the most recent message in the thread",
        is_updated_at=True,
    )
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

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Direct link to open the thread in Gmail."""
        return f"https://mail.google.com/mail/u/0/#inbox/{self.gmail_thread_id}"


class GmailMessageEntity(EmailEntity):
    """Schema for Gmail message entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.messages
    """

    message_key: str = AirweaveField(
        ...,
        description="Stable Airweave message key (msg_<gmail_id>)",
        is_entity_id=True,
    )
    message_id: str = AirweaveField(..., description="Native Gmail message ID", embeddable=False)
    subject: str = AirweaveField(
        ...,
        description="Subject line (fallback applied if missing)",
        is_name=True,
        embeddable=True,
    )
    sent_at: datetime = AirweaveField(
        ...,
        description="Timestamp from the Date header (or internal date fallback)",
        is_created_at=True,
    )
    internal_timestamp: datetime = AirweaveField(
        ...,
        description="Gmail internal timestamp representing last modification",
        is_updated_at=True,
    )
    thread_id: str = AirweaveField(
        ..., description="ID of the thread this message belongs to", embeddable=False
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
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Direct Gmail URL for the message",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Direct link to open the message in Gmail."""
        return self.web_url_value or f"https://mail.google.com/mail/u/0/#inbox/{self.message_id}"


class GmailAttachmentEntity(FileEntity):
    """Schema for Gmail attachment entities.

    Reference: https://developers.google.com/gmail/api/reference/rest/v1/users.messages.attachments
    """

    attachment_key: str = AirweaveField(
        ...,
        description="Stable Airweave attachment key (attach_<message>_<filename>)",
        is_entity_id=True,
    )
    filename: str = AirweaveField(
        ..., description="Attachment filename", is_name=True, embeddable=True
    )
    message_id: str = AirweaveField(
        ..., description="ID of the message this attachment belongs to", embeddable=False
    )
    attachment_id: str = AirweaveField(..., description="Gmail's attachment ID", embeddable=False)
    thread_id: str = AirweaveField(
        ..., description="ID of the thread containing the message", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the parent message in Gmail",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the parent message view in Gmail."""
        return self.web_url_value or f"https://mail.google.com/mail/u/0/#inbox/{self.message_id}"


class GmailMessageDeletionEntity(DeletionEntity):
    """Deletion signal for a Gmail message.

    Emitted when the Gmail History API reports a messageDeleted. The entity_id matches the
    message entity's ID format (msg_{message_id}) so downstream deletion removes the
    correct parent/children.
    """

    message_key: str = AirweaveField(
        ...,
        description="Stable Airweave message key (msg_<gmail_id>)",
        is_entity_id=True,
    )
    label: str = AirweaveField(
        ...,
        description="Human-readable deletion label",
        is_name=True,
        embeddable=True,
    )
    message_id: str = AirweaveField(
        ..., description="The Gmail message ID that was deleted", embeddable=False
    )
    thread_id: Optional[str] = AirweaveField(
        None,
        description="Thread ID (optional if not provided by change record)",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Fallback link to Gmail inbox for the deleted message."""
        return f"https://mail.google.com/mail/u/0/#inbox/{self.message_id}"
