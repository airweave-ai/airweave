"""HubSpot entity schemas.

Based on the HubSpot CRM API reference, we define entity schemas for common
HubSpot objects like Contacts, Companies, Deals, and Tickets.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import field_validator

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


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

    # Base fields are inherited and set during entity creation:
    # - entity_id (the HubSpot contact ID)
    # - breadcrumbs (empty - contacts are top-level)
    # - name (from first_name + last_name or email)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields (HubSpot-specific)
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

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v):
        """Parse datetime fields."""
        return parse_hubspot_datetime(v)


class HubspotCompanyEntity(BaseEntity):
    """Schema for HubSpot company entities with flexible property handling.

    Reference:
        https://developers.hubspot.com/docs/api/crm/companies
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the HubSpot company ID)
    # - breadcrumbs (empty - companies are top-level)
    # - name (from company name property)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields (HubSpot-specific)
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

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v):
        """Parse datetime fields."""
        return parse_hubspot_datetime(v)


class HubspotDealEntity(BaseEntity):
    """Schema for HubSpot deal entities with flexible property handling.

    Reference:
        https://developers.hubspot.com/docs/api/crm/deals
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the HubSpot deal ID)
    # - breadcrumbs (empty - deals are top-level)
    # - name (from deal_name property)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields (HubSpot-specific)
    deal_name: Optional[str] = AirweaveField(
        default=None, description="The name of the deal", embeddable=True
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

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v):
        """Parse datetime fields."""
        return parse_hubspot_datetime(v)


class HubspotTicketEntity(BaseEntity):
    """Schema for HubSpot ticket entities with flexible property handling.

    Reference:
        https://developers.hubspot.com/docs/api/crm/tickets
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the HubSpot ticket ID)
    # - breadcrumbs (empty - tickets are top-level)
    # - name (from subject)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields (HubSpot-specific)
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

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v):
        """Parse datetime fields."""
        return parse_hubspot_datetime(v)
