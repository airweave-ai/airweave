"""Zendesk entity schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb, FileEntity


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse Zendesk ISO8601 timestamps into timezone-aware datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_ticket_url(subdomain: str, ticket_id: int) -> str:
    return f"https://{subdomain}.zendesk.com/agent/tickets/{ticket_id}"


def _build_user_url(subdomain: str, user_id: int) -> str:
    return f"https://{subdomain}.zendesk.com/agent/users/{user_id}"


def _build_org_url(subdomain: str, org_id: int) -> str:
    return f"https://{subdomain}.zendesk.com/agent/organizations/{org_id}"


class ZendeskTicketEntity(BaseEntity):
    """Schema for Zendesk ticket entities.

    Reference:
        https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/
    """

    ticket_id: int = AirweaveField(
        ..., description="Unique identifier of the ticket", embeddable=False, is_entity_id=True
    )
    subject: str = AirweaveField(
        ..., description="The subject of the ticket", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the ticket was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the ticket was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="UI URL to open the ticket in Zendesk.",
        embeddable=False,
        unhashable=True,
    )

    description: Optional[str] = AirweaveField(
        None, description="The description of the ticket (first comment)", embeddable=True
    )
    requester_id: Optional[int] = AirweaveField(
        None, description="ID of the user who requested the ticket", embeddable=False
    )
    requester_name: Optional[str] = AirweaveField(
        None, description="Name of the user who requested the ticket", embeddable=True
    )
    requester_email: Optional[str] = AirweaveField(
        None, description="Email of the user who requested the ticket", embeddable=True
    )
    assignee_id: Optional[int] = AirweaveField(
        None, description="ID of the user assigned to the ticket", embeddable=False
    )
    assignee_name: Optional[str] = AirweaveField(
        None, description="Name of the user assigned to the ticket", embeddable=True
    )
    assignee_email: Optional[str] = AirweaveField(
        None, description="Email of the user assigned to the ticket", embeddable=True
    )
    status: str = AirweaveField(..., description="Current status of the ticket", embeddable=True)
    priority: Optional[str] = AirweaveField(
        None, description="Priority level of the ticket", embeddable=True
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with the ticket", embeddable=True
    )
    custom_fields: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Custom field values for the ticket", embeddable=False
    )
    organization_id: Optional[int] = AirweaveField(
        None, description="ID of the organization associated with the ticket", embeddable=False
    )
    organization_name: Optional[str] = AirweaveField(
        None, description="Name of the organization associated with the ticket", embeddable=True
    )
    group_id: Optional[int] = AirweaveField(
        None, description="ID of the group the ticket belongs to", embeddable=False
    )
    group_name: Optional[str] = AirweaveField(
        None, description="Name of the group the ticket belongs to", embeddable=True
    )
    ticket_type: Optional[str] = AirweaveField(
        None, description="Type of the ticket (question, incident, problem, task)", embeddable=True
    )
    url: Optional[str] = AirweaveField(
        None, description="URL to view the ticket in Zendesk", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, subdomain: str) -> ZendeskTicketEntity:
        """Construct from Zendesk API ticket object."""
        ticket_id = data["id"]
        created = _parse_dt(data.get("created_at")) or _now()
        updated = _parse_dt(data.get("updated_at")) or created
        subject = data.get("subject", f"Ticket {ticket_id}")

        return cls(
            entity_id=str(ticket_id),
            breadcrumbs=[],
            name=subject,
            created_at=created,
            updated_at=updated,
            ticket_id=ticket_id,
            subject=subject,
            created_time=created,
            updated_time=updated,
            web_url_value=_build_ticket_url(subdomain, ticket_id),
            description=data.get("description"),
            requester_id=data.get("requester_id"),
            requester_name=None,
            requester_email=None,
            assignee_id=data.get("assignee_id"),
            assignee_name=None,
            assignee_email=None,
            status=data.get("status", "new"),
            priority=data.get("priority"),
            tags=data.get("tags", []),
            custom_fields=data.get("custom_fields", []),
            organization_id=data.get("organization_id"),
            organization_name=None,
            group_id=data.get("group_id"),
            group_name=None,
            ticket_type=data.get("type"),
            url=data.get("url"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Zendesk ticket URL."""
        return self.web_url_value or self.url or ""


class ZendeskCommentEntity(BaseEntity):
    """Schema for Zendesk comment entities.

    Reference:
        https://developer.zendesk.com/api-reference/ticketing/tickets/ticket-comments/
    """

    comment_id: int = AirweaveField(
        ..., description="Unique identifier of the comment", embeddable=False, is_entity_id=True
    )
    ticket_id: int = AirweaveField(
        ..., description="ID of the ticket this comment belongs to", embeddable=False
    )
    ticket_subject: str = AirweaveField(
        ..., description="Subject of the ticket this comment belongs to", embeddable=True
    )
    author_id: int = AirweaveField(
        ..., description="ID of the user who wrote the comment", embeddable=False
    )
    author_name: str = AirweaveField(
        ..., description="Name of the user who wrote the comment", embeddable=True
    )
    author_email: Optional[str] = AirweaveField(
        None, description="Email of the user who wrote the comment", embeddable=True
    )
    body: str = AirweaveField(
        ..., description="The content of the comment", embeddable=True, is_name=True
    )
    html_body: Optional[str] = AirweaveField(
        None, description="HTML formatted content of the comment", embeddable=True
    )
    public: bool = AirweaveField(
        False, description="Whether the comment is public or internal", embeddable=False
    )
    attachments: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Attachments associated with this comment",
        embeddable=False,
    )
    created_time: datetime = AirweaveField(
        ..., description="When the comment was created.", is_created_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this comment (falls back to ticket).",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        ticket_id: int,
        ticket_subject: str,
        ticket_breadcrumb: Breadcrumb,
        users_map: Dict[int, Dict[str, Any]],
        subdomain: str,
    ) -> ZendeskCommentEntity:
        """Construct from Zendesk API comment object."""
        author_id = data.get("author_id")
        if not author_id:
            author_id = 0
            author_name = "System"
            author_email = None
        else:
            user = users_map.get(author_id, {})
            author_name = user.get("name", f"User {author_id}")
            author_email = user.get("email")

        body = data.get("body", "")
        comment_name = body[:50] + "..." if len(body) > 50 else body
        if not comment_name:
            comment_name = f"Comment {data['id']}"

        created = _parse_dt(data.get("created_at")) or _now()

        return cls(
            entity_id=f"{ticket_id}_{data['id']}",
            breadcrumbs=[ticket_breadcrumb],
            name=comment_name,
            created_at=created,
            updated_at=created,
            comment_id=data["id"],
            ticket_id=ticket_id,
            ticket_subject=ticket_subject,
            author_id=author_id,
            author_name=author_name,
            author_email=author_email,
            body=body,
            html_body=data.get("html_body"),
            public=data.get("public", False),
            attachments=data.get("attachments", []),
            created_time=created,
            web_url_value=_build_ticket_url(subdomain, ticket_id),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Zendesk comment URL."""
        return self.web_url_value or ""


class ZendeskUserEntity(BaseEntity):
    """Schema for Zendesk user entities.

    Reference:
        https://developer.zendesk.com/api-reference/ticketing/users/users/
    """

    user_id: int = AirweaveField(
        ..., description="Unique identifier of the user", embeddable=False, is_entity_id=True
    )
    display_name: str = AirweaveField(
        ..., description="Display name of the user.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the user was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the user was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to the user's profile in Zendesk.",
        embeddable=False,
        unhashable=True,
    )

    email: str = AirweaveField(..., description="Email address of the user", embeddable=True)
    role: str = AirweaveField(
        ..., description="Role of the user (end-user, agent, admin)", embeddable=True
    )
    active: bool = AirweaveField(
        ..., description="Whether the user account is active", embeddable=False
    )
    last_login_at: Optional[Any] = AirweaveField(
        None, description="When the user last logged in", embeddable=False
    )
    organization_id: Optional[int] = AirweaveField(
        None, description="ID of the organization the user belongs to", embeddable=False
    )
    organization_name: Optional[str] = AirweaveField(
        None,
        description="Name of the organization the user belongs to",
        embeddable=True,
    )
    phone: Optional[str] = AirweaveField(
        None, description="Phone number of the user", embeddable=True
    )
    time_zone: Optional[str] = AirweaveField(
        None, description="Time zone of the user", embeddable=False
    )
    locale: Optional[str] = AirweaveField(None, description="Locale of the user", embeddable=False)
    custom_fields: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Custom field values for the user",
        embeddable=False,
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with the user", embeddable=True
    )
    user_fields: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="User-specific custom fields", embeddable=False
    )
    profile_url: Optional[str] = AirweaveField(
        None, description="API URL to the user resource", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, subdomain: str) -> ZendeskUserEntity:
        """Construct from Zendesk API user object."""
        user_id = data["id"]
        created = _parse_dt(data.get("created_at")) or _now()
        updated = _parse_dt(data.get("updated_at")) or created
        display_name = data.get("name") or data.get("email") or f"User {user_id}"

        return cls(
            entity_id=str(user_id),
            breadcrumbs=[],
            name=display_name,
            created_at=created,
            updated_at=updated,
            user_id=user_id,
            display_name=display_name,
            created_time=created,
            updated_time=updated,
            web_url_value=_build_user_url(subdomain, user_id),
            email=data["email"],
            role=data.get("role", "end-user"),
            active=data.get("active", True),
            last_login_at=data.get("last_login_at"),
            organization_id=data.get("organization_id"),
            organization_name=None,
            phone=data.get("phone"),
            time_zone=data.get("time_zone"),
            locale=data.get("locale"),
            custom_fields=data.get("custom_fields", []),
            tags=data.get("tags", []),
            user_fields=data.get("user_fields", {}),
            profile_url=data.get("url"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Zendesk user URL."""
        return self.web_url_value or self.profile_url or ""


class ZendeskOrganizationEntity(BaseEntity):
    """Schema for Zendesk organization entities.

    Reference:
        https://developer.zendesk.com/api-reference/ticketing/organizations/organizations/
    """

    organization_id: int = AirweaveField(
        ...,
        description="Unique identifier of the organization",
        embeddable=False,
        is_entity_id=True,
    )
    organization_name: str = AirweaveField(
        ..., description="Display name of the organization.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the organization was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the organization was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the organization in Zendesk.",
        embeddable=False,
        unhashable=True,
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
        default_factory=list,
        description="Tags associated with the organization",
        embeddable=True,
    )
    custom_fields: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Custom field values for the organization",
        embeddable=False,
    )
    organization_fields: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Organization-specific custom fields",
        embeddable=False,
    )
    api_url: Optional[str] = AirweaveField(
        None,
        description="API URL for this organization resource.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, subdomain: str) -> ZendeskOrganizationEntity:
        """Construct from Zendesk API organization object."""
        org_id = data["id"]
        org_name = data.get("name", "Organization")
        created = _parse_dt(data.get("created_at")) or _now()
        updated = _parse_dt(data.get("updated_at")) or created

        return cls(
            entity_id=str(org_id),
            breadcrumbs=[],
            name=org_name,
            created_at=created,
            updated_at=updated,
            organization_id=org_id,
            organization_name=org_name,
            created_time=created,
            updated_time=updated,
            web_url_value=_build_org_url(subdomain, org_id),
            domain_names=data.get("domain_names", []),
            details=data.get("details"),
            notes=data.get("notes"),
            tags=data.get("tags", []),
            custom_fields=data.get("custom_fields", []),
            organization_fields=data.get("organization_fields", {}),
            api_url=data.get("url"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Zendesk organization URL."""
        return self.web_url_value or self.api_url or ""


class ZendeskAttachmentEntity(FileEntity):
    """Schema for Zendesk attachment entities.

    Reference:
        https://developer.zendesk.com/api-reference/ticketing/tickets/ticket-attachments/
    """

    attachment_id: int = AirweaveField(
        ..., description="Unique identifier of the attachment", embeddable=False, is_entity_id=True
    )
    ticket_id: Optional[int] = AirweaveField(
        None, description="ID of the ticket this attachment belongs to", embeddable=False
    )
    comment_id: Optional[int] = AirweaveField(
        None, description="ID of the comment this attachment belongs to", embeddable=False
    )
    ticket_subject: Optional[str] = AirweaveField(
        None,
        description="Subject of the ticket this attachment belongs to",
        embeddable=True,
    )
    content_type: str = AirweaveField(
        ..., description="MIME type of the attachment", embeddable=False
    )
    file_name: str = AirweaveField(
        ..., description="Original filename of the attachment", embeddable=True, is_name=True
    )
    thumbnails: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Thumbnail information for the attachment",
        embeddable=False,
    )
    created_time: datetime = AirweaveField(
        ..., description="When the attachment was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the attachment metadata was updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to download the attachment.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        ticket_id: int,
        ticket_subject: str,
        ticket_breadcrumb: Breadcrumb,
        comment_breadcrumb: Breadcrumb,
        comment_created_at: Optional[datetime],
        subdomain: str,
    ) -> ZendeskAttachmentEntity:
        """Construct from Zendesk API attachment object."""
        attachment_created_at = _parse_dt(data.get("created_at")) or comment_created_at or _now()

        mime_type = data.get("content_type") or "application/octet-stream"
        if mime_type and "/" in mime_type:
            file_type = mime_type.split("/")[0]
        else:
            import os

            ext = os.path.splitext(data.get("file_name", ""))[1].lower().lstrip(".")
            file_type = ext if ext else "file"

        return cls(
            entity_id=str(data["id"]),
            breadcrumbs=[ticket_breadcrumb, comment_breadcrumb],
            name=data.get("file_name", ""),
            created_at=attachment_created_at,
            updated_at=attachment_created_at,
            url=data.get("content_url"),
            size=data.get("size", 0),
            file_type=file_type,
            mime_type=mime_type,
            local_path=None,
            attachment_id=data["id"],
            ticket_id=ticket_id,
            comment_id=None,
            ticket_subject=ticket_subject,
            content_type=data.get("content_type"),
            file_name=data.get("file_name", ""),
            thumbnails=data.get("thumbnails", []),
            created_time=attachment_created_at,
            updated_time=attachment_created_at,
            web_url_value=data.get("content_url"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Zendesk attachment URL."""
        return self.web_url_value or self.url or ""
