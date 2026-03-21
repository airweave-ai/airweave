"""Outlook Mail entity schemas.

Simplified entity schemas for Outlook mail objects:
 - MailFolder
 - Message
 - Attachment

Following the same patterns as Gmail entities for consistency.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import (
    BaseEntity,
    Breadcrumb,
    DeletionEntity,
    EmailEntity,
    FileEntity,
)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse Microsoft Graph ISO8601 timestamps into timezone-aware datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class OutlookMailFolderEntity(BaseEntity):
    """Schema for an Outlook mail folder.

    See:
      https://learn.microsoft.com/en-us/graph/api/resources/mailfolder?view=graph-rest-1.0
    """

    id: str = AirweaveField(
        ...,
        description="Mail folder ID from Microsoft Graph.",
        is_entity_id=True,
    )
    display_name: str = AirweaveField(
        ...,
        description="Display name of the mail folder (e.g., 'Inbox').",
        embeddable=True,
        is_name=True,
    )
    parent_folder_id: Optional[str] = AirweaveField(
        None, description="ID of the parent mail folder, if any."
    )
    child_folder_count: Optional[int] = AirweaveField(
        None, description="Number of child mail folders under this folder."
    )
    total_item_count: Optional[int] = AirweaveField(
        None, description="Total number of items (messages) in this folder."
    )
    unread_item_count: Optional[int] = AirweaveField(
        None, description="Number of unread items in this folder."
    )
    well_known_name: Optional[str] = AirweaveField(
        None, description="Well-known name of this folder if applicable (e.g., 'inbox')."
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="URL to open this folder in Outlook on the web.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Best-effort URL for launching the folder in Outlook."""
        if self.web_url_override:
            return self.web_url_override
        if self.well_known_name:
            return f"https://outlook.office.com/mail/{self.well_known_name}"
        return f"https://outlook.office.com/mail/folder/{self.id}"


class OutlookMessageEntity(EmailEntity):
    """Schema for Outlook message entities.

    Reference: https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0
    """

    id: str = AirweaveField(
        ...,
        description="Message ID from Microsoft Graph.",
        is_entity_id=True,
    )
    folder_name: str = AirweaveField(
        ..., description="Name of the folder containing this message", embeddable=True
    )
    subject: str = AirweaveField(
        ...,
        description="Subject line of the message.",
        embeddable=True,
        is_name=True,
    )
    sender: Optional[str] = AirweaveField(
        None, description="Email address of the sender", embeddable=True
    )
    to_recipients: List[str] = AirweaveField(
        default_factory=list, description="Recipients of the message", embeddable=True
    )
    cc_recipients: List[str] = AirweaveField(
        default_factory=list, description="CC recipients", embeddable=True
    )
    sent_date: Optional[datetime] = AirweaveField(
        None,
        description="Date the message was sent",
        embeddable=True,
        is_created_at=True,
    )
    received_date: Optional[datetime] = AirweaveField(
        None,
        description="Date the message was received",
        embeddable=True,
        is_updated_at=True,
    )
    body_preview: Optional[str] = AirweaveField(
        None, description="Brief snippet of the message content", embeddable=True
    )
    is_read: bool = AirweaveField(False, description="Whether the message has been read")
    is_draft: bool = AirweaveField(False, description="Whether the message is a draft")
    importance: Optional[str] = AirweaveField(
        None, description="Importance level (Low, Normal, High)"
    )
    has_attachments: bool = AirweaveField(False, description="Whether the message has attachments")
    internet_message_id: Optional[str] = AirweaveField(None, description="Internet message ID")
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="Link to the message in Outlook on the web.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        folder_name: str,
        folder_breadcrumb: Breadcrumb,
    ) -> "OutlookMessageEntity":
        """Construct from a Microsoft Graph ``message`` resource."""
        message_id = data["id"]
        subject = data.get("subject")

        from_data = data.get("from")
        sender = from_data.get("emailAddress", {}).get("address") if from_data else None

        to_recipients = [
            r.get("emailAddress", {}).get("address")
            for r in data.get("toRecipients", [])
            if r.get("emailAddress") and r.get("emailAddress", {}).get("address")
        ]
        cc_recipients = [
            r.get("emailAddress", {}).get("address")
            for r in data.get("ccRecipients", [])
            if r.get("emailAddress") and r.get("emailAddress", {}).get("address")
        ]

        sent_date = _parse_dt(data.get("sentDateTime"))
        received_date = _parse_dt(data.get("receivedDateTime"))

        body_obj = data.get("body") or {}
        body_content = body_obj.get("content", "")
        body_content_type = body_obj.get("contentType", "html").lower()

        is_plain_text = body_content_type == "text"
        file_type = "text" if is_plain_text else "html"
        mime_type = "text/plain" if is_plain_text else "text/html"

        subject_value = subject or f"Message {message_id}"
        message_url = f"https://outlook.office.com/mail/inbox/id/{message_id}"

        return cls(
            id=message_id,
            breadcrumbs=[folder_breadcrumb],
            name=subject_value,
            sent_date=sent_date,
            received_date=received_date,
            url=message_url,
            size=len(body_content.encode("utf-8")) if body_content else 0,
            file_type=file_type,
            mime_type=mime_type,
            local_path=None,
            folder_name=folder_name,
            subject=subject_value,
            sender=sender,
            to_recipients=to_recipients,
            cc_recipients=cc_recipients,
            body_preview=data.get("bodyPreview", ""),
            is_read=data.get("isRead", False),
            is_draft=data.get("isDraft", False),
            importance=data.get("importance"),
            has_attachments=data.get("hasAttachments", False),
            internet_message_id=data.get("internetMessageId"),
            web_url_override=data.get("webLink") or message_url,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Best-effort URL to open the message."""
        if self.web_url_override:
            return self.web_url_override
        return self.url


class OutlookAttachmentEntity(FileEntity):
    """Schema for Outlook attachment entities.

    Reference: https://learn.microsoft.com/en-us/graph/api/resources/fileattachment?view=graph-rest-1.0
    """

    composite_id: str = AirweaveField(
        ...,
        description="Composite attachment ID (message + attachment).",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Attachment filename.",
        embeddable=True,
        is_name=True,
    )
    message_id: str = AirweaveField(..., description="ID of the message this attachment belongs to")
    attachment_id: str = AirweaveField(..., description="Outlook's attachment ID")
    content_type: Optional[str] = AirweaveField(None, description="Content type of the attachment")
    is_inline: bool = AirweaveField(False, description="Whether this is an inline attachment")
    content_id: Optional[str] = AirweaveField(None, description="Content ID for inline attachments")
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Additional metadata about the attachment"
    )
    message_web_url: Optional[str] = AirweaveField(
        None,
        description="URL to the parent message in Outlook on the web.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the parent Outlook message."""
        if self.message_web_url:
            return self.message_web_url
        return f"https://outlook.office.com/mail/id/{self.message_id}"


class OutlookMessageDeletionEntity(DeletionEntity):
    """Deletion signal for an Outlook message.

    Emitted when the Graph delta API reports a message was removed.
    The `entity_id` (derived from `message_id`) matches the original message's id
    so downstream deletion can target the correct parent/children.
    """

    deletes_entity_class = OutlookMessageEntity

    message_id: str = AirweaveField(
        ...,
        description="ID of the deleted message",
        is_entity_id=True,
    )
    label: str = AirweaveField(
        ...,
        description="Human-readable deletion label",
        is_name=True,
        embeddable=True,
    )


class OutlookMailFolderDeletionEntity(DeletionEntity):
    """Deletion signal for an Outlook mail folder.

    Emitted when the Graph delta API reports a folder was removed.
    The `entity_id` (derived from `folder_id`) matches the original folder's id.
    """

    deletes_entity_class = OutlookMailFolderEntity

    folder_id: str = AirweaveField(
        ...,
        description="ID of the deleted folder",
        is_entity_id=True,
    )
    label: str = AirweaveField(
        ...,
        description="Human-readable deletion label",
        is_name=True,
        embeddable=True,
    )
