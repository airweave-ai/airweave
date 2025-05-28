"""Outlook Mail entity schemas.

Simplified entity schemas for Outlook mail objects:
 - MailFolder
 - Message
 - Attachment

Following the same patterns as Gmail entities for consistency.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity


class OutlookMailFolderEntity(ChunkEntity):
    """Schema for an Outlook mail folder.

    See:
      https://learn.microsoft.com/en-us/graph/api/resources/mailfolder?view=graph-rest-1.0
    """

    display_name: str = Field(..., description="Display name of the mail folder (e.g., 'Inbox').")
    parent_folder_id: Optional[str] = Field(
        None, description="ID of the parent mail folder, if any."
    )
    child_folder_count: Optional[int] = Field(
        None, description="Number of child mail folders under this folder."
    )
    total_item_count: Optional[int] = Field(
        None, description="Total number of items (messages) in this folder."
    )
    unread_item_count: Optional[int] = Field(
        None, description="Number of unread items in this folder."
    )
    well_known_name: Optional[str] = Field(
        None, description="Well-known name of this folder if applicable (e.g., 'inbox')."
    )


class OutlookMessageEntity(ChunkEntity):
    """Schema for Outlook message entities.

    Reference: https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0
    """

    folder_name: str = Field(..., description="Name of the folder containing this message")
    subject: Optional[str] = Field(None, description="Subject line of the message")
    sender: Optional[str] = Field(None, description="Email address of the sender")
    to_recipients: List[str] = Field(default_factory=list, description="Recipients of the message")
    cc_recipients: List[str] = Field(default_factory=list, description="CC recipients")
    sent_date: Optional[datetime] = Field(None, description="Date the message was sent")
    received_date: Optional[datetime] = Field(None, description="Date the message was received")
    body_preview: Optional[str] = Field(None, description="Brief snippet of the message content")
    body_content: Optional[str] = Field(None, description="Full message body content")
    is_read: bool = Field(False, description="Whether the message has been read")
    is_draft: bool = Field(False, description="Whether the message is a draft")
    importance: Optional[str] = Field(None, description="Importance level (Low, Normal, High)")
    has_attachments: bool = Field(False, description="Whether the message has attachments")
    internet_message_id: Optional[str] = Field(None, description="Internet message ID")


class OutlookAttachmentEntity(FileEntity):
    """Schema for Outlook attachment entities.

    Reference: https://learn.microsoft.com/en-us/graph/api/resources/fileattachment?view=graph-rest-1.0
    """

    message_id: str = Field(..., description="ID of the message this attachment belongs to")
    attachment_id: str = Field(..., description="Outlook's attachment ID")
    content_type: Optional[str] = Field(None, description="Content type of the attachment")
    is_inline: bool = Field(False, description="Whether this is an inline attachment")
    content_id: Optional[str] = Field(None, description="Content ID for inline attachments")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the attachment"
    )
