"""HubSpot entity schemas.

Based on the HubSpot CRM API reference, we define entity schemas for common
HubSpot objects like Contacts, Companies, Deals, and Tickets.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import field_validator

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base_legacy import ChunkEntity


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


class HubspotContactEntity(ChunkEntity):
    """Schema for HubSpot contact entities with flexible property handling."""

    # Core fields that are commonly used
    first_name: Optional[str] = AirweaveField(
        default=None, description="The contact's first name", embeddable=True
    )
    last_name: Optional[str] = AirweaveField(
        default=None, description="The contact's last name", embeddable=True
    )
    email: Optional[str] = AirweaveField(
        default=None, description="The contact's email address", embeddable=True
    )

    # All properties from HubSpot API
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from HubSpot contact object",
        embeddable=True,
    )

    created_at: Optional[datetime] = AirweaveField(
        default=None, description="Timestamp when the contact was created", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        default=None, description="Timestamp when the contact was last updated", is_updated_at=True
    )
    archived: bool = AirweaveField(default=False, description="Whether the contact is archived")

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v):
        """Parse datetime fields."""
        return parse_hubspot_datetime(v)


class HubspotCompanyEntity(ChunkEntity):
    """Schema for HubSpot company entities with flexible property handling."""

    # Core fields that are commonly used
    name: Optional[str] = AirweaveField(
        default=None, description="The company's name", embeddable=True
    )
    domain: Optional[str] = AirweaveField(
        default=None, description="The company's domain name", embeddable=True
    )

    # All properties from HubSpot API
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from HubSpot company object",
        embeddable=True,
    )

    created_at: Optional[datetime] = AirweaveField(
        default=None, description="Timestamp when the company was created", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        default=None, description="Timestamp when the company was last updated", is_updated_at=True
    )
    archived: bool = AirweaveField(default=False, description="Whether the company is archived")

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v):
        """Parse datetime fields."""
        return parse_hubspot_datetime(v)


class HubspotDealEntity(ChunkEntity):
    """Schema for HubSpot deal entities with flexible property handling."""

    # Core fields that are commonly used
    deal_name: Optional[str] = AirweaveField(
        default=None, description="The name of the deal", embeddable=True
    )
    amount: Optional[float] = AirweaveField(
        default=None, description="The monetary value of the deal", embeddable=True
    )

    # All properties from HubSpot API
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="All properties from HubSpot deal object", embeddable=True
    )

    created_at: Optional[datetime] = AirweaveField(
        default=None, description="Timestamp when the deal was created", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        default=None, description="Timestamp when the deal was last updated", is_updated_at=True
    )
    archived: bool = AirweaveField(default=False, description="Whether the deal is archived")

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v):
        """Parse datetime fields."""
        return parse_hubspot_datetime(v)


class HubspotTicketEntity(ChunkEntity):
    """Schema for HubSpot ticket entities with flexible property handling."""

    # Core fields that are commonly used
    subject: Optional[str] = AirweaveField(
        default=None, description="The subject of the support ticket", embeddable=True
    )
    content: Optional[str] = AirweaveField(
        default=None, description="The content or description of the ticket", embeddable=True
    )

    # All properties from HubSpot API
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from HubSpot ticket object",
        embeddable=True,
    )

    created_at: Optional[datetime] = AirweaveField(
        default=None, description="Timestamp when the ticket was created", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        default=None, description="Timestamp when the ticket was last updated", is_updated_at=True
    )
    archived: bool = AirweaveField(default=False, description="Whether the ticket is archived")

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, v):
        """Parse datetime fields."""
        return parse_hubspot_datetime(v)
