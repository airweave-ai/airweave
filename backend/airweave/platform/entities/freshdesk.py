"""Freshdesk entity schemas.

Reference: https://developers.freshdesk.com/api/
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse Freshdesk ISO8601 timestamps to timezone-aware datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class FreshdeskTicketEntity(BaseEntity):
    """Schema for Freshdesk ticket entities.

    Reference: https://developers.freshdesk.com/api/#tickets
    """

    ticket_id: int = AirweaveField(
        ..., description="Unique identifier of the ticket", embeddable=False, is_entity_id=True
    )
    subject: str = AirweaveField(
        ..., description="Subject of the ticket", embeddable=True, is_name=True
    )
    created_at_value: datetime = AirweaveField(
        ..., description="When the ticket was created.", is_created_at=True
    )
    updated_at_value: datetime = AirweaveField(
        ..., description="When the ticket was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="UI URL to open the ticket in Freshdesk.",
        embeddable=False,
        unhashable=True,
    )

    description: Optional[str] = AirweaveField(
        None, description="HTML content of the ticket", embeddable=True
    )
    description_text: Optional[str] = AirweaveField(
        None, description="Plain text content of the ticket", embeddable=True
    )
    status: Optional[int] = AirweaveField(
        None,
        description="Status of the ticket (2=Open, 3=Pending, 4=Resolved, 5=Closed)",
        embeddable=False,
    )
    priority: Optional[int] = AirweaveField(
        None, description="Priority (1=Low, 2=Medium, 3=High, 4=Urgent)", embeddable=False
    )
    requester_id: Optional[int] = AirweaveField(
        None, description="ID of the requester", embeddable=False
    )
    responder_id: Optional[int] = AirweaveField(
        None, description="ID of the assigned agent", embeddable=False
    )
    company_id: Optional[int] = AirweaveField(
        None, description="ID of the company", embeddable=False
    )
    group_id: Optional[int] = AirweaveField(None, description="ID of the group", embeddable=False)
    type: Optional[str] = AirweaveField(
        None, description="Ticket type (e.g. Question, Problem)", embeddable=True
    )
    source: Optional[int] = AirweaveField(
        None, description="Channel (1=Email, 2=Portal, 3=Phone, 7=Chat, etc.)", embeddable=False
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with the ticket", embeddable=True
    )
    custom_fields: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Custom field values", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the web URL for this entity in Freshdesk."""
        return self.web_url_value or ""

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: str,
    ) -> FreshdeskTicketEntity:
        """Build from a Freshdesk API ticket object."""
        ticket_id = data["id"]
        subject = data.get("subject") or f"Ticket #{ticket_id}"
        created_at = _parse_datetime(data.get("created_at")) or _now()
        updated_at = _parse_datetime(data.get("updated_at")) or created_at
        return cls(
            entity_id=str(ticket_id),
            breadcrumbs=[],
            name=subject,
            created_at=created_at,
            updated_at=updated_at,
            ticket_id=ticket_id,
            subject=subject,
            created_at_value=created_at,
            updated_at_value=updated_at,
            web_url_value=web_url,
            description=data.get("description"),
            description_text=data.get("description_text"),
            status=data.get("status"),
            priority=data.get("priority"),
            requester_id=data.get("requester_id"),
            responder_id=data.get("responder_id"),
            company_id=data.get("company_id"),
            group_id=data.get("group_id"),
            type=data.get("type"),
            source=data.get("source"),
            tags=data.get("tags") or [],
            custom_fields=data.get("custom_fields") or {},
        )


class FreshdeskConversationEntity(BaseEntity):
    """Schema for Freshdesk conversation entities (replies and notes on a ticket).

    Reference: https://developers.freshdesk.com/api/#list-all-conversations-of-a-ticket
    """

    conversation_id: int = AirweaveField(
        ...,
        description="Unique identifier of the conversation",
        embeddable=False,
        is_entity_id=True,
    )
    ticket_id: int = AirweaveField(
        ..., description="ID of the ticket this conversation belongs to", embeddable=False
    )
    ticket_subject: str = AirweaveField(
        ..., description="Subject of the parent ticket", embeddable=True
    )
    body: Optional[str] = AirweaveField(
        None, description="HTML content of the conversation", embeddable=True
    )
    body_text: str = AirweaveField(
        ..., description="Plain text content of the conversation", embeddable=True, is_name=True
    )
    created_at_value: datetime = AirweaveField(
        ..., description="When the conversation was created.", is_created_at=True
    )
    updated_at_value: Optional[datetime] = AirweaveField(
        None, description="When the conversation was last updated.", is_updated_at=True
    )
    user_id: Optional[int] = AirweaveField(
        None, description="ID of the user who created the conversation", embeddable=False
    )
    incoming: bool = AirweaveField(
        False, description="True if from outside (e.g. customer reply)", embeddable=False
    )
    private: bool = AirweaveField(
        False, description="True if the note is private", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to the ticket (conversations don't have direct URLs).",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the web URL for this entity in Freshdesk."""
        return self.web_url_value or ""

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        ticket_id: int,
        ticket_subject: str,
        ticket_url: str,
        breadcrumbs: List[Breadcrumb],
    ) -> FreshdeskConversationEntity:
        """Build from a Freshdesk API conversation object."""
        conv_id = data["id"]
        body_text = (
            data.get("body_text")
            or (data.get("body") or "").strip()
            or f"Conversation {conv_id}"
        )
        created_at = _parse_datetime(data.get("created_at")) or _now()
        updated_at = _parse_datetime(data.get("updated_at")) or created_at
        return cls(
            entity_id=f"{ticket_id}_{conv_id}",
            breadcrumbs=breadcrumbs,
            name=body_text[:200] if body_text else f"Conversation {conv_id}",
            created_at=created_at,
            updated_at=updated_at,
            conversation_id=conv_id,
            ticket_id=ticket_id,
            ticket_subject=ticket_subject,
            body=data.get("body"),
            body_text=body_text,
            created_at_value=created_at,
            updated_at_value=updated_at,
            user_id=data.get("user_id"),
            incoming=data.get("incoming", False),
            private=data.get("private", False),
            web_url_value=ticket_url,
        )


class FreshdeskContactEntity(BaseEntity):
    """Schema for Freshdesk contact entities.

    Reference: https://developers.freshdesk.com/api/#contacts
    """

    contact_id: int = AirweaveField(
        ..., description="Unique identifier of the contact", embeddable=False, is_entity_id=True
    )
    name: str = AirweaveField(..., description="Name of the contact", embeddable=True, is_name=True)
    email: Optional[str] = AirweaveField(None, description="Primary email address", embeddable=True)
    created_at_value: datetime = AirweaveField(
        ..., description="When the contact was created.", is_created_at=True
    )
    updated_at_value: datetime = AirweaveField(
        ..., description="When the contact was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to the contact in Freshdesk.",
        embeddable=False,
        unhashable=True,
    )

    company_id: Optional[int] = AirweaveField(
        None, description="ID of the primary company", embeddable=False
    )
    job_title: Optional[str] = AirweaveField(None, description="Job title", embeddable=True)
    phone: Optional[str] = AirweaveField(None, description="Phone number", embeddable=True)
    mobile: Optional[str] = AirweaveField(None, description="Mobile number", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Description of the contact", embeddable=True
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with the contact", embeddable=True
    )
    custom_fields: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Custom field values", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the web URL for this entity in Freshdesk."""
        return self.web_url_value or ""

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: str,
    ) -> FreshdeskContactEntity:
        """Build from a Freshdesk API contact object."""
        contact_id = data["id"]
        name = data.get("name") or data.get("email") or f"Contact {contact_id}"
        created_at = _parse_datetime(data.get("created_at")) or _now()
        updated_at = _parse_datetime(data.get("updated_at")) or created_at
        return cls(
            entity_id=str(contact_id),
            breadcrumbs=[],
            name=name,
            created_at=created_at,
            updated_at=updated_at,
            contact_id=contact_id,
            email=data.get("email"),
            created_at_value=created_at,
            updated_at_value=updated_at,
            web_url_value=web_url,
            company_id=data.get("company_id"),
            job_title=data.get("job_title"),
            phone=data.get("phone"),
            mobile=data.get("mobile"),
            description=data.get("description"),
            tags=data.get("tags") or [],
            custom_fields=data.get("custom_fields") or {},
        )


class FreshdeskCompanyEntity(BaseEntity):
    """Schema for Freshdesk company entities.

    Reference: https://developers.freshdesk.com/api/#companies
    """

    company_id: int = AirweaveField(
        ...,
        description="Unique identifier of the company",
        embeddable=False,
        is_entity_id=True,
    )
    name: str = AirweaveField(..., description="Name of the company", embeddable=True, is_name=True)
    created_at_value: datetime = AirweaveField(
        ..., description="When the company was created.", is_created_at=True
    )
    updated_at_value: datetime = AirweaveField(
        ..., description="When the company was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to the company in Freshdesk.",
        embeddable=False,
        unhashable=True,
    )

    description: Optional[str] = AirweaveField(
        None, description="Description of the company", embeddable=True
    )
    note: Optional[str] = AirweaveField(
        None, description="Notes about the company", embeddable=True
    )
    domains: List[str] = AirweaveField(
        default_factory=list,
        description="Domains associated with the company",
        embeddable=True,
    )
    custom_fields: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Custom field values", embeddable=False
    )
    industry: Optional[str] = AirweaveField(None, description="Industry", embeddable=True)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the web URL for this entity in Freshdesk."""
        return self.web_url_value or ""

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: str,
    ) -> FreshdeskCompanyEntity:
        """Build from a Freshdesk API company object."""
        company_id = data["id"]
        name = data.get("name") or f"Company {company_id}"
        created_at = _parse_datetime(data.get("created_at")) or _now()
        updated_at = _parse_datetime(data.get("updated_at")) or created_at
        return cls(
            entity_id=str(company_id),
            breadcrumbs=[],
            name=name,
            created_at=created_at,
            updated_at=updated_at,
            company_id=company_id,
            created_at_value=created_at,
            updated_at_value=updated_at,
            web_url_value=web_url,
            description=data.get("description"),
            note=data.get("note"),
            domains=data.get("domains") or [],
            custom_fields=data.get("custom_fields") or {},
            industry=data.get("industry"),
        )


class FreshdeskSolutionArticleEntity(BaseEntity):
    """Schema for Freshdesk solution/knowledge base article entities.

    Reference: https://developers.freshdesk.com/api/#articles
    """

    article_id: int = AirweaveField(
        ...,
        description="Unique identifier of the article",
        embeddable=False,
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ..., description="Title of the article", embeddable=True, is_name=True
    )
    created_at_value: datetime = AirweaveField(
        ..., description="When the article was created.", is_created_at=True
    )
    updated_at_value: datetime = AirweaveField(
        ..., description="When the article was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to the article in Freshdesk.",
        embeddable=False,
        unhashable=True,
    )

    description: Optional[str] = AirweaveField(
        None, description="HTML content of the article", embeddable=True
    )
    description_text: Optional[str] = AirweaveField(
        None, description="Plain text content of the article", embeddable=True
    )
    status: Optional[int] = AirweaveField(
        None, description="Status (1=draft, 2=published)", embeddable=False
    )
    folder_id: Optional[int] = AirweaveField(None, description="ID of the folder", embeddable=False)
    category_id: Optional[int] = AirweaveField(
        None, description="ID of the category", embeddable=False
    )
    folder_name: Optional[str] = AirweaveField(
        None, description="Name of the folder", embeddable=True
    )
    category_name: Optional[str] = AirweaveField(
        None, description="Name of the category", embeddable=True
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with the article", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the web URL for this entity in Freshdesk."""
        return self.web_url_value or ""

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: str,
        folder_id: int,
        folder_name: str,
        category_id: int,
        category_name: str,
        breadcrumbs: List[Breadcrumb],
    ) -> FreshdeskSolutionArticleEntity:
        """Build from a Freshdesk API article object."""
        article_id = data["id"]
        title = data.get("title") or f"Article {article_id}"
        created_at = _parse_datetime(data.get("created_at")) or _now()
        updated_at = _parse_datetime(data.get("updated_at")) or created_at
        return cls(
            entity_id=str(article_id),
            breadcrumbs=breadcrumbs,
            name=title,
            created_at=created_at,
            updated_at=updated_at,
            article_id=article_id,
            title=title,
            created_at_value=created_at,
            updated_at_value=updated_at,
            web_url_value=web_url,
            description=data.get("description"),
            description_text=data.get("description_text"),
            status=data.get("status"),
            folder_id=folder_id,
            category_id=category_id,
            folder_name=folder_name,
            category_name=category_name,
            tags=data.get("tags") or [],
        )
