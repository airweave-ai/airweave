"""Outlook Mail entity schemas.

Simplified entity schemas for Outlook mail objects:
 - MailFolder
 - Message
 - Attachment

Following the same patterns as Gmail entities for consistency.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import DeletionEntity, EmailEntity, FileEntity
from airweave.platform.entities._base import 


class OutlookMailFolderEntity(BaseEntity):
    """Schema for an Outlook mail folder.

    See:
      https://learn.microsoft.com/en-us/graph/api/resources/mailfolder?view=graph-rest-1.0
    """

    display_name: str = AirweaveField(
        ..., description="Display name of the mail folder (e.g., 'Inbox').", embeddable=True
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


class OutlookMessageEntity(EmailEntity):
    """Schema for Outlook message entities.

    Reference: https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0
    """

    # Base fields are inherited from BaseEntity:
    # - entity_id (message ID)
    # - breadcrumbs (folder breadcrumb)
    # - name (from subject)
    # - created_at (from sent_date)
    # - updated_at (from received_date)

    # File fields are inherited from FileEntity (required):
    # - url (link to message in Outlook)
    # - size (message size in bytes)
    # - file_type (set to "html")
    # - mime_type (set to "text/html")
    # - local_path (set after downloading HTML body)

    # Email body content is NOT stored in entity fields
    # It is saved to local_path file for conversion

    folder_name: str = AirweaveField(
        ..., description="Name of the folder containing this message", embeddable=True
    )
    subject: Optional[str] = AirweaveField(
        None, description="Subject line of the message", embeddable=True
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
        None, description="Date the message was sent", embeddable=True
    )
    received_date: Optional[datetime] = AirweaveField(
        None, description="Date the message was received", embeddable=True
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


class OutlookAttachmentEntity(FileEntity):
    """Schema for Outlook attachment entities.

    Reference: https://learn.microsoft.com/en-us/graph/api/resources/fileattachment?view=graph-rest-1.0
    """

    message_id: str = AirweaveField(..., description="ID of the message this attachment belongs to")
    attachment_id: str = AirweaveField(..., description="Outlook's attachment ID")
    content_type: Optional[str] = AirweaveField(None, description="Content type of the attachment")
    is_inline: bool = AirweaveField(False, description="Whether this is an inline attachment")
    content_id: Optional[str] = AirweaveField(None, description="Content ID for inline attachments")
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Additional metadata about the attachment"
    )


class OutlookMessageDeletionEntity(DeletionEntity):
    """Deletion signal for an Outlook message.

    Emitted when the Graph delta API reports a message was removed.
    The `entity_id` matches the original message's id so downstream deletion
    can target the correct parent/children.
    """

    message_id: str = AirweaveField(..., description="ID of the deleted message")


class OutlookMailFolderDeletionEntity(DeletionEntity):
    """Deletion signal for an Outlook mail folder.

    Emitted when the Graph delta API reports a folder was removed.
    The `entity_id` matches the original folder's id.
    """

    folder_id: str = AirweaveField(..., description="ID of the deleted folder")
