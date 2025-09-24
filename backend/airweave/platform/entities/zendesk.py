"""Zendesk entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import ChunkEntity, FileEntity


class ZendeskTicketEntity(ChunkEntity):
    """Schema for Zendesk ticket entities."""

    ticket_id: int = Field(..., description="Unique identifier of the ticket")
    subject: str = AirweaveField(..., description="The subject of the ticket", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="The description of the ticket (first comment)", embeddable=True
    )
    requester_id: Optional[int] = Field(None, description="ID of the user who requested the ticket")
    requester_name: Optional[str] = AirweaveField(
        None, description="Name of the user who requested the ticket", embeddable=True
    )
    requester_email: Optional[str] = Field(
        None, description="Email of the user who requested the ticket"
    )
    assignee_id: Optional[int] = Field(None, description="ID of the user assigned to the ticket")
    assignee_name: Optional[str] = AirweaveField(
        None, description="Name of the user assigned to the ticket", embeddable=True
    )
    assignee_email: Optional[str] = Field(
        None, description="Email of the user assigned to the ticket"
    )
    status: str = AirweaveField(..., description="Current status of the ticket", embeddable=True)
    priority: Optional[str] = AirweaveField(
        None, description="Priority level of the ticket", embeddable=True
    )
    created_at: datetime = AirweaveField(
        ..., description="When the ticket was created", embeddable=True, is_created_at=True
    )
    updated_at: datetime = AirweaveField(
        ..., description="When the ticket was last updated", embeddable=True, is_updated_at=True
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with the ticket", embeddable=True
    )
    custom_fields: List[Dict[str, Any]] = Field(
        default_factory=list, description="Custom field values for the ticket"
    )
    organization_id: Optional[int] = Field(
        None, description="ID of the organization associated with the ticket"
    )
    organization_name: Optional[str] = AirweaveField(
        None, description="Name of the organization associated with the ticket", embeddable=True
    )
    group_id: Optional[int] = Field(None, description="ID of the group the ticket belongs to")
    group_name: Optional[str] = AirweaveField(
        None, description="Name of the group the ticket belongs to", embeddable=True
    )
    ticket_type: Optional[str] = AirweaveField(
        None, description="Type of the ticket (question, incident, problem, task)", embeddable=True
    )
    url: Optional[str] = Field(None, description="URL to view the ticket in Zendesk")


class ZendeskCommentEntity(ChunkEntity):
    """Schema for Zendesk comment entities."""

    comment_id: int = Field(..., description="Unique identifier of the comment")
    ticket_id: int = Field(..., description="ID of the ticket this comment belongs to")
    ticket_subject: str = AirweaveField(
        ..., description="Subject of the ticket this comment belongs to", embeddable=True
    )
    author_id: int = Field(..., description="ID of the user who wrote the comment")
    author_name: str = AirweaveField(
        ..., description="Name of the user who wrote the comment", embeddable=True
    )
    author_email: Optional[str] = Field(None, description="Email of the user who wrote the comment")
    body: str = AirweaveField(..., description="The content of the comment", embeddable=True)
    html_body: Optional[str] = AirweaveField(
        None, description="HTML formatted content of the comment", embeddable=True
    )
    public: bool = Field(False, description="Whether the comment is public or internal")
    created_at: datetime = AirweaveField(
        ..., description="When the comment was created", embeddable=True, is_created_at=True
    )
    attachments: List[Dict[str, Any]] = Field(
        default_factory=list, description="Attachments associated with this comment"
    )


class ZendeskUserEntity(ChunkEntity):
    """Schema for Zendesk user entities."""

    user_id: int = Field(..., description="Unique identifier of the user")
    name: str = AirweaveField(..., description="Full name of the user", embeddable=True)
    email: str = AirweaveField(..., description="Email address of the user", embeddable=True)
    role: str = AirweaveField(
        ..., description="Role of the user (end-user, agent, admin)", embeddable=True
    )
    active: bool = AirweaveField(
        ..., description="Whether the user account is active", embeddable=True
    )
    created_at: datetime = AirweaveField(
        ..., description="When the user account was created", embeddable=True, is_created_at=True
    )
    updated_at: datetime = AirweaveField(
        ...,
        description="When the user account was last updated",
        embeddable=True,
        is_updated_at=True,
    )
    last_login_at: Optional[datetime] = AirweaveField(
        None, description="When the user last logged in", embeddable=True
    )
    organization_id: Optional[int] = Field(
        None, description="ID of the organization the user belongs to"
    )
    organization_name: Optional[str] = AirweaveField(
        None, description="Name of the organization the user belongs to", embeddable=True
    )
    phone: Optional[str] = Field(None, description="Phone number of the user")
    time_zone: Optional[str] = Field(None, description="Time zone of the user")
    locale: Optional[str] = Field(None, description="Locale of the user")
    custom_fields: List[Dict[str, Any]] = Field(
        default_factory=list, description="Custom field values for the user"
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with the user", embeddable=True
    )
    user_fields: Dict[str, Any] = Field(
        default_factory=dict, description="User-specific custom fields"
    )


class ZendeskOrganizationEntity(ChunkEntity):
    """Schema for Zendesk organization entities."""

    organization_id: int = Field(..., description="Unique identifier of the organization")
    name: str = AirweaveField(..., description="Name of the organization", embeddable=True)
    created_at: datetime = AirweaveField(
        ..., description="When the organization was created", embeddable=True, is_created_at=True
    )
    updated_at: datetime = AirweaveField(
        ...,
        description="When the organization was last updated",
        embeddable=True,
        is_updated_at=True,
    )
    domain_names: List[str] = AirweaveField(
        default_factory=list,
        description="Domain names associated with the organization",
        embeddable=True,
    )
    details: Optional[str] = AirweaveField(
        None, description="Details about the organization", embeddable=True
    )
    notes: Optional[str] = AirweaveField(
        None, description="Notes about the organization", embeddable=True
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with the organization", embeddable=True
    )
    custom_fields: List[Dict[str, Any]] = Field(
        default_factory=list, description="Custom field values for the organization"
    )
    organization_fields: Dict[str, Any] = Field(
        default_factory=dict, description="Organization-specific custom fields"
    )


class ZendeskAttachmentEntity(FileEntity):
    """Schema for Zendesk attachment entities."""

    attachment_id: int = Field(..., description="Unique identifier of the attachment")
    ticket_id: Optional[int] = Field(
        None, description="ID of the ticket this attachment belongs to"
    )
    comment_id: Optional[int] = Field(
        None, description="ID of the comment this attachment belongs to"
    )
    ticket_subject: Optional[str] = Field(
        None, description="Subject of the ticket this attachment belongs to"
    )
    content_type: str = Field(..., description="MIME type of the attachment")
    size: int = Field(..., description="Size of the attachment in bytes")
    file_name: str = Field(..., description="Original filename of the attachment")
    thumbnails: List[Dict[str, Any]] = Field(
        default_factory=list, description="Thumbnail information for the attachment"
    )
    created_at: datetime = AirweaveField(
        ..., description="When the attachment was created", embeddable=True, is_created_at=True
    )
    # Override FileEntity fields to match Zendesk API - use str for file_id for consistency
    file_id: str = Field(..., description="ID of the file in the source system")
    name: str = Field(..., description="Name of the file")
    mime_type: Optional[str] = Field(None, description="MIME type of the file")
    download_url: str = Field(..., description="URL to download the file")
