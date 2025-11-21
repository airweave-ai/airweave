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
from airweave.platform.entities._base import BaseEntity, DeletionEntity, EmailEntity, FileEntity


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
