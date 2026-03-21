"""HubSpot entity schemas.

Based on the HubSpot CRM API reference, we define entity schemas for common
HubSpot objects like Contacts, Companies, Deals, and Tickets.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import computed_field, field_validator

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


def _safe_float(value: Any) -> Optional[float]:
    """Safely convert a value to float, handling empty strings and None."""
    if not value or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_hubspot_datetime(value: Any) -> Optional[datetime]:
    """Parse HubSpot datetime value, handling empty strings and various formats.

    Args:
        value: The datetime value from HubSpot API (could be string, datetime, or None)

    Returns:
        Parsed datetime object or None if empty/invalid
    """
    if not value or value == "":
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            # HubSpot typically returns ISO format datetime strings
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    return None


class HubspotContactEntity(BaseEntity):
    """Schema for HubSpot contact entities with flexible property handling.

    Reference:
        https://developers.hubspot.com/docs/api/crm/contacts
    """

    contact_id: str = AirweaveField(..., description="The HubSpot contact ID.", is_entity_id=True)
    display_name: str = AirweaveField(
        ...,
        description="Display name derived from first/last name or email.",
        embeddable=True,
        is_name=True,
    )
    created_time: datetime = AirweaveField(
        ..., description="When the contact was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the contact was last updated.", is_updated_at=True
    )
    first_name: Optional[str] = AirweaveField(
        default=None, description="The contact's first name", embeddable=True
    )
    last_name: Optional[str] = AirweaveField(
        default=None, description="The contact's last name", embeddable=True
    )
    email: Optional[str] = AirweaveField(
        default=None, description="The contact's email address", embeddable=True
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from HubSpot contact object",
        embeddable=True,
    )
    archived: bool = AirweaveField(
        default=False, description="Whether the contact is archived", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view this contact in HubSpot.", embeddable=False, unhashable=True
    )

    @field_validator("created_time", "updated_time", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Normalize HubSpot datetime inputs to timezone-aware datetimes."""
        return parse_hubspot_datetime(value)

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        cleaned_properties: Dict[str, Any],
        web_url_value: Optional[str] = None,
    ) -> HubspotContactEntity:
        """Build from a HubSpot API contact object.

        Args:
            data: Raw contact dict from the HubSpot CRM API (id, createdAt, …).
            cleaned_properties: Pre-cleaned properties dict.
            web_url_value: Pre-built HubSpot UI URL (requires portal ID).
        """
        first_name = cleaned_properties.get("firstname")
        last_name = cleaned_properties.get("lastname")
        email = cleaned_properties.get("email")

        if first_name and last_name:
            contact_name = f"{first_name} {last_name}"
        elif first_name:
            contact_name = first_name
        elif last_name:
            contact_name = last_name
        elif email:
            contact_name = email
        else:
            contact_name = f"Contact {data['id']}"

        created_time = parse_hubspot_datetime(data.get("createdAt")) or datetime.utcnow()
        updated_time = parse_hubspot_datetime(data.get("updatedAt")) or created_time

        return cls(
            entity_id=data["id"],
            breadcrumbs=[],
            name=contact_name,
            created_at=created_time,
            updated_at=updated_time,
            contact_id=data["id"],
            display_name=contact_name,
            created_time=created_time,
            updated_time=updated_time,
            first_name=first_name,
            last_name=last_name,
            email=email,
            properties=cleaned_properties,
            archived=data.get("archived", False),
            web_url_value=web_url_value,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the HubSpot contact UI."""
        return self.web_url_value or ""


class HubspotCompanyEntity(BaseEntity):
    """Schema for HubSpot company entities with flexible property handling.

    Reference:
        https://developers.hubspot.com/docs/api/crm/companies
    """

    company_id: str = AirweaveField(..., description="The HubSpot company ID.", is_entity_id=True)
    company_name: str = AirweaveField(
        ..., description="Display name of the company.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the company was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the company was last updated.", is_updated_at=True
    )
    domain: Optional[str] = AirweaveField(
        default=None, description="The company's domain name", embeddable=True
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from HubSpot company object",
        embeddable=True,
    )
    archived: bool = AirweaveField(
        default=False, description="Whether the company is archived", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view this company in HubSpot.", embeddable=False, unhashable=True
    )

    @field_validator("created_time", "updated_time", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Normalize HubSpot datetime inputs to timezone-aware datetimes."""
        return parse_hubspot_datetime(value)

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        cleaned_properties: Dict[str, Any],
        web_url_value: Optional[str] = None,
    ) -> HubspotCompanyEntity:
        """Build from a HubSpot API company object.

        Args:
            data: Raw company dict from the HubSpot CRM API.
            cleaned_properties: Pre-cleaned properties dict.
            web_url_value: Pre-built HubSpot UI URL (requires portal ID).
        """
        company_name = cleaned_properties.get("name") or f"Company {data['id']}"

        created_time = parse_hubspot_datetime(data.get("createdAt")) or datetime.utcnow()
        updated_time = parse_hubspot_datetime(data.get("updatedAt")) or created_time

        return cls(
            entity_id=data["id"],
            breadcrumbs=[],
            name=company_name,
            created_at=created_time,
            updated_at=updated_time,
            company_id=data["id"],
            company_name=company_name,
            created_time=created_time,
            updated_time=updated_time,
            domain=cleaned_properties.get("domain"),
            properties=cleaned_properties,
            archived=data.get("archived", False),
            web_url_value=web_url_value,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the HubSpot company UI."""
        return self.web_url_value or ""


class HubspotDealEntity(BaseEntity):
    """Schema for HubSpot deal entities with flexible property handling.

    Reference:
        https://developers.hubspot.com/docs/api/crm/deals
    """

    deal_id: str = AirweaveField(..., description="The HubSpot deal ID.", is_entity_id=True)
    deal_name: str = AirweaveField(
        ..., description="The name of the deal.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the deal was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the deal was last updated.", is_updated_at=True
    )
    amount: Optional[float] = AirweaveField(
        default=None, description="The monetary value of the deal", embeddable=True
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="All properties from HubSpot deal object", embeddable=True
    )
    archived: bool = AirweaveField(
        default=False, description="Whether the deal is archived", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view this deal in HubSpot.", embeddable=False, unhashable=True
    )

    @field_validator("created_time", "updated_time", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Normalize HubSpot datetime inputs to timezone-aware datetimes."""
        return parse_hubspot_datetime(value)

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        cleaned_properties: Dict[str, Any],
        web_url_value: Optional[str] = None,
    ) -> HubspotDealEntity:
        """Build from a HubSpot API deal object.

        Args:
            data: Raw deal dict from the HubSpot CRM API.
            cleaned_properties: Pre-cleaned properties dict.
            web_url_value: Pre-built HubSpot UI URL (requires portal ID).
        """
        deal_name = cleaned_properties.get("dealname") or f"Deal {data['id']}"

        created_time = parse_hubspot_datetime(data.get("createdAt")) or datetime.utcnow()
        updated_time = parse_hubspot_datetime(data.get("updatedAt")) or created_time

        return cls(
            entity_id=data["id"],
            breadcrumbs=[],
            name=deal_name,
            created_at=created_time,
            updated_at=updated_time,
            deal_id=data["id"],
            deal_name=deal_name,
            created_time=created_time,
            updated_time=updated_time,
            amount=_safe_float(cleaned_properties.get("amount")),
            properties=cleaned_properties,
            archived=data.get("archived", False),
            web_url_value=web_url_value,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the HubSpot deal UI."""
        return self.web_url_value or ""


class HubspotTicketEntity(BaseEntity):
    """Schema for HubSpot ticket entities with flexible property handling.

    Reference:
        https://developers.hubspot.com/docs/api/crm/tickets
    """

    ticket_id: str = AirweaveField(..., description="The HubSpot ticket ID.", is_entity_id=True)
    ticket_name: str = AirweaveField(
        ..., description="Display name for the ticket.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the ticket was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the ticket was last updated.", is_updated_at=True
    )
    subject: Optional[str] = AirweaveField(
        default=None, description="The subject of the support ticket", embeddable=True
    )
    content: Optional[str] = AirweaveField(
        default=None, description="The content or description of the ticket", embeddable=True
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from HubSpot ticket object",
        embeddable=True,
    )
    archived: bool = AirweaveField(
        default=False, description="Whether the ticket is archived", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view this ticket in HubSpot.", embeddable=False, unhashable=True
    )

    @field_validator("created_time", "updated_time", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Normalize HubSpot datetime inputs to timezone-aware datetimes."""
        return parse_hubspot_datetime(value)

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        cleaned_properties: Dict[str, Any],
        web_url_value: Optional[str] = None,
    ) -> HubspotTicketEntity:
        """Build from a HubSpot API ticket object.

        Args:
            data: Raw ticket dict from the HubSpot CRM API.
            cleaned_properties: Pre-cleaned properties dict.
            web_url_value: Pre-built HubSpot UI URL (requires portal ID).
        """
        ticket_name = cleaned_properties.get("subject") or f"Ticket {data['id']}"

        created_time = parse_hubspot_datetime(data.get("createdAt")) or datetime.utcnow()
        updated_time = parse_hubspot_datetime(data.get("updatedAt")) or created_time

        return cls(
            entity_id=data["id"],
            breadcrumbs=[],
            name=ticket_name,
            created_at=created_time,
            updated_at=updated_time,
            ticket_id=data["id"],
            ticket_name=ticket_name,
            created_time=created_time,
            updated_time=updated_time,
            subject=cleaned_properties.get("subject"),
            content=cleaned_properties.get("content"),
            properties=cleaned_properties,
            archived=data.get("archived", False),
            web_url_value=web_url_value,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the HubSpot ticket UI."""
        return self.web_url_value or ""
