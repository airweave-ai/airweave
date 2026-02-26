"""Freshdesk entity schemas.

Reference: https://developers.freshdesk.com/api/
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


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
