"""Pipedrive entity schemas.

Based on the Pipedrive CRM API v1 reference, we define entity schemas for common
Pipedrive objects like Persons, Organizations, Deals, Activities, Products, Leads, and Notes.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field, field_validator

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


def parse_pipedrive_datetime(value: Any) -> Optional[datetime]:
    """Parse Pipedrive datetime value, handling various formats.

    Args:
        value: The datetime value from Pipedrive API (could be string, datetime, or None)

    Returns:
        Parsed datetime object or None if empty/invalid
    """
    if not value or value == "":
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        # Try common Pipedrive datetime formats
        formats = [
            "%Y-%m-%d %H:%M:%S",  # Standard Pipedrive format
            "%Y-%m-%d",  # Date only
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with microseconds
            "%Y-%m-%dT%H:%M:%SZ",  # ISO format
            "%Y-%m-%dT%H:%M:%S",  # ISO format without Z
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        # Try ISO format with timezone
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    return None


class PipedrivePersonEntity(BaseEntity):
    """Schema for Pipedrive person (contact) entities.

    Reference:
        https://developers.pipedrive.com/docs/api/v1/Persons
    """

    person_id: str = AirweaveField(..., description="The Pipedrive person ID.", is_entity_id=True)
    display_name: str = AirweaveField(
        ...,
        description="Display name of the person.",
        embeddable=True,
        is_name=True,
    )
    created_time: datetime = AirweaveField(
        ..., description="When the person was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the person was last updated.", is_updated_at=True
    )
    first_name: Optional[str] = AirweaveField(
        default=None, description="The person's first name.", embeddable=True
    )
    last_name: Optional[str] = AirweaveField(
        default=None, description="The person's last name.", embeddable=True
    )
    email: Optional[str] = AirweaveField(
        default=None, description="Primary email address.", embeddable=True
    )
    phone: Optional[str] = AirweaveField(
        default=None, description="Primary phone number.", embeddable=True
    )
    organization_id: Optional[int] = AirweaveField(
        default=None, description="ID of the linked organization.", embeddable=False
    )
    organization_name: Optional[str] = AirweaveField(
        default=None, description="Name of the linked organization.", embeddable=True
    )
    owner_id: Optional[int] = AirweaveField(
        default=None, description="ID of the user who owns the person.", embeddable=False
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from Pipedrive person object.",
        embeddable=True,
    )
    active_flag: bool = AirweaveField(
        default=True, description="Whether the person is active.", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view this person in Pipedrive.", embeddable=False, unhashable=True
    )

    @field_validator("created_time", "updated_time", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Normalize Pipedrive datetime inputs to timezone-aware datetimes."""
        return parse_pipedrive_datetime(value)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the Pipedrive person UI."""
        return self.web_url_value or ""


class PipedriveOrganizationEntity(BaseEntity):
    """Schema for Pipedrive organization (company) entities.

    Reference:
        https://developers.pipedrive.com/docs/api/v1/Organizations
    """

    organization_id: str = AirweaveField(
        ..., description="The Pipedrive organization ID.", is_entity_id=True
    )
    organization_name: str = AirweaveField(
        ..., description="Name of the organization.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the organization was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the organization was last updated.", is_updated_at=True
    )
    address: Optional[str] = AirweaveField(
        default=None, description="Organization address.", embeddable=True
    )
    owner_id: Optional[int] = AirweaveField(
        default=None, description="ID of the user who owns the organization.", embeddable=False
    )
    people_count: Optional[int] = AirweaveField(
        default=None, description="Number of people linked to the organization.", embeddable=False
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from Pipedrive organization object.",
        embeddable=True,
    )
    active_flag: bool = AirweaveField(
        default=True, description="Whether the organization is active.", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this organization in Pipedrive.",
        embeddable=False,
        unhashable=True,
    )

    @field_validator("created_time", "updated_time", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Normalize Pipedrive datetime inputs to timezone-aware datetimes."""
        return parse_pipedrive_datetime(value)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the Pipedrive organization UI."""
        return self.web_url_value or ""


class PipedriveDealEntity(BaseEntity):
    """Schema for Pipedrive deal entities.

    Reference:
        https://developers.pipedrive.com/docs/api/v1/Deals
    """

    deal_id: str = AirweaveField(..., description="The Pipedrive deal ID.", is_entity_id=True)
    deal_title: str = AirweaveField(
        ..., description="Title of the deal.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the deal was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the deal was last updated.", is_updated_at=True
    )
    value: Optional[float] = AirweaveField(
        default=None, description="Monetary value of the deal.", embeddable=True
    )
    currency: Optional[str] = AirweaveField(
        default=None, description="Currency of the deal value.", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        default=None, description="Status of the deal (open, won, lost, deleted).", embeddable=True
    )
    stage_id: Optional[int] = AirweaveField(
        default=None, description="ID of the pipeline stage.", embeddable=False
    )
    stage_name: Optional[str] = AirweaveField(
        default=None, description="Name of the pipeline stage.", embeddable=True
    )
    pipeline_id: Optional[int] = AirweaveField(
        default=None, description="ID of the pipeline.", embeddable=False
    )
    pipeline_name: Optional[str] = AirweaveField(
        default=None, description="Name of the pipeline.", embeddable=True
    )
    person_id: Optional[int] = AirweaveField(
        default=None, description="ID of the linked person.", embeddable=False
    )
    person_name: Optional[str] = AirweaveField(
        default=None, description="Name of the linked person.", embeddable=True
    )
    organization_id: Optional[int] = AirweaveField(
        default=None, description="ID of the linked organization.", embeddable=False
    )
    organization_name: Optional[str] = AirweaveField(
        default=None, description="Name of the linked organization.", embeddable=True
    )
    owner_id: Optional[int] = AirweaveField(
        default=None, description="ID of the user who owns the deal.", embeddable=False
    )
    expected_close_date: Optional[datetime] = AirweaveField(
        default=None, description="Expected close date of the deal.", embeddable=True
    )
    probability: Optional[float] = AirweaveField(
        default=None, description="Deal success probability (0-100).", embeddable=True
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from Pipedrive deal object.",
        embeddable=True,
    )
    active_flag: bool = AirweaveField(
        default=True, description="Whether the deal is active.", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view this deal in Pipedrive.", embeddable=False, unhashable=True
    )

    @field_validator("created_time", "updated_time", "expected_close_date", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Normalize Pipedrive datetime inputs to timezone-aware datetimes."""
        return parse_pipedrive_datetime(value)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the Pipedrive deal UI."""
        return self.web_url_value or ""


class PipedriveActivityEntity(BaseEntity):
    """Schema for Pipedrive activity entities (tasks, calls, meetings).

    Reference:
        https://developers.pipedrive.com/docs/api/v1/Activities
    """

    activity_id: str = AirweaveField(
        ..., description="The Pipedrive activity ID.", is_entity_id=True
    )
    activity_subject: str = AirweaveField(
        ..., description="Subject/title of the activity.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the activity was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the activity was last updated.", is_updated_at=True
    )
    activity_type: Optional[str] = AirweaveField(
        default=None, description="Type of activity (call, meeting, task, etc.).", embeddable=True
    )
    due_date: Optional[datetime] = AirweaveField(
        default=None, description="Due date of the activity.", embeddable=True
    )
    due_time: Optional[str] = AirweaveField(
        default=None, description="Due time of the activity.", embeddable=True
    )
    duration: Optional[str] = AirweaveField(
        default=None, description="Duration of the activity.", embeddable=True
    )
    done: bool = AirweaveField(
        default=False, description="Whether the activity is done.", embeddable=True
    )
    note: Optional[str] = AirweaveField(
        default=None, description="Note/description of the activity.", embeddable=True
    )
    deal_id: Optional[int] = AirweaveField(
        default=None, description="ID of the linked deal.", embeddable=False
    )
    deal_title: Optional[str] = AirweaveField(
        default=None, description="Title of the linked deal.", embeddable=True
    )
    person_id: Optional[int] = AirweaveField(
        default=None, description="ID of the linked person.", embeddable=False
    )
    person_name: Optional[str] = AirweaveField(
        default=None, description="Name of the linked person.", embeddable=True
    )
    organization_id: Optional[int] = AirweaveField(
        default=None, description="ID of the linked organization.", embeddable=False
    )
    organization_name: Optional[str] = AirweaveField(
        default=None, description="Name of the linked organization.", embeddable=True
    )
    owner_id: Optional[int] = AirweaveField(
        default=None, description="ID of the user who owns the activity.", embeddable=False
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from Pipedrive activity object.",
        embeddable=True,
    )
    active_flag: bool = AirweaveField(
        default=True, description="Whether the activity is active.", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this activity in Pipedrive.",
        embeddable=False,
        unhashable=True,
    )

    @field_validator("created_time", "updated_time", "due_date", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Normalize Pipedrive datetime inputs to timezone-aware datetimes."""
        return parse_pipedrive_datetime(value)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the Pipedrive activity UI."""
        return self.web_url_value or ""


class PipedriveProductEntity(BaseEntity):
    """Schema for Pipedrive product entities.

    Reference:
        https://developers.pipedrive.com/docs/api/v1/Products
    """

    product_id: str = AirweaveField(
        ..., description="The Pipedrive product ID.", is_entity_id=True
    )
    product_name: str = AirweaveField(
        ..., description="Name of the product.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the product was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the product was last updated.", is_updated_at=True
    )
    code: Optional[str] = AirweaveField(
        default=None, description="Product code/SKU.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        default=None, description="Product description.", embeddable=True
    )
    unit: Optional[str] = AirweaveField(
        default=None, description="Unit of the product.", embeddable=True
    )
    tax: Optional[float] = AirweaveField(
        default=None, description="Tax percentage.", embeddable=True
    )
    category: Optional[str] = AirweaveField(
        default=None, description="Product category.", embeddable=True
    )
    owner_id: Optional[int] = AirweaveField(
        default=None, description="ID of the user who owns the product.", embeddable=False
    )
    prices: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Product prices in different currencies.",
        embeddable=True,
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from Pipedrive product object.",
        embeddable=True,
    )
    active_flag: bool = AirweaveField(
        default=True, description="Whether the product is active.", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this product in Pipedrive.",
        embeddable=False,
        unhashable=True,
    )

    @field_validator("created_time", "updated_time", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Normalize Pipedrive datetime inputs to timezone-aware datetimes."""
        return parse_pipedrive_datetime(value)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the Pipedrive product UI."""
        return self.web_url_value or ""


class PipedriveLeadEntity(BaseEntity):
    """Schema for Pipedrive lead entities.

    Reference:
        https://developers.pipedrive.com/docs/api/v1/Leads
    """

    lead_id: str = AirweaveField(..., description="The Pipedrive lead ID.", is_entity_id=True)
    lead_title: str = AirweaveField(
        ..., description="Title of the lead.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the lead was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the lead was last updated.", is_updated_at=True
    )
    value: Optional[float] = AirweaveField(
        default=None, description="Potential value of the lead.", embeddable=True
    )
    currency: Optional[str] = AirweaveField(
        default=None, description="Currency of the lead value.", embeddable=True
    )
    expected_close_date: Optional[datetime] = AirweaveField(
        default=None, description="Expected close date.", embeddable=True
    )
    person_id: Optional[int] = AirweaveField(
        default=None, description="ID of the linked person.", embeddable=False
    )
    person_name: Optional[str] = AirweaveField(
        default=None, description="Name of the linked person.", embeddable=True
    )
    organization_id: Optional[int] = AirweaveField(
        default=None, description="ID of the linked organization.", embeddable=False
    )
    organization_name: Optional[str] = AirweaveField(
        default=None, description="Name of the linked organization.", embeddable=True
    )
    owner_id: Optional[int] = AirweaveField(
        default=None, description="ID of the user who owns the lead.", embeddable=False
    )
    source_name: Optional[str] = AirweaveField(
        default=None, description="Source of the lead.", embeddable=True
    )
    label_ids: Optional[List[str]] = AirweaveField(
        default=None, description="List of label IDs.", embeddable=False
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from Pipedrive lead object.",
        embeddable=True,
    )
    is_archived: bool = AirweaveField(
        default=False, description="Whether the lead is archived.", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view this lead in Pipedrive.", embeddable=False, unhashable=True
    )

    @field_validator("created_time", "updated_time", "expected_close_date", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Normalize Pipedrive datetime inputs to timezone-aware datetimes."""
        return parse_pipedrive_datetime(value)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the Pipedrive lead UI."""
        return self.web_url_value or ""


class PipedriveNoteEntity(BaseEntity):
    """Schema for Pipedrive note entities.

    Reference:
        https://developers.pipedrive.com/docs/api/v1/Notes
    """

    note_id: str = AirweaveField(..., description="The Pipedrive note ID.", is_entity_id=True)
    note_title: str = AirweaveField(
        ..., description="Title/summary of the note.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the note was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the note was last updated.", is_updated_at=True
    )
    content: Optional[str] = AirweaveField(
        default=None, description="Content of the note.", embeddable=True
    )
    deal_id: Optional[int] = AirweaveField(
        default=None, description="ID of the linked deal.", embeddable=False
    )
    deal_title: Optional[str] = AirweaveField(
        default=None, description="Title of the linked deal.", embeddable=True
    )
    person_id: Optional[int] = AirweaveField(
        default=None, description="ID of the linked person.", embeddable=False
    )
    person_name: Optional[str] = AirweaveField(
        default=None, description="Name of the linked person.", embeddable=True
    )
    organization_id: Optional[int] = AirweaveField(
        default=None, description="ID of the linked organization.", embeddable=False
    )
    organization_name: Optional[str] = AirweaveField(
        default=None, description="Name of the linked organization.", embeddable=True
    )
    lead_id: Optional[str] = AirweaveField(
        default=None, description="ID of the linked lead.", embeddable=False
    )
    user_id: Optional[int] = AirweaveField(
        default=None, description="ID of the user who created the note.", embeddable=False
    )
    pinned_to_deal_flag: bool = AirweaveField(
        default=False, description="Whether the note is pinned to a deal.", embeddable=False
    )
    pinned_to_person_flag: bool = AirweaveField(
        default=False, description="Whether the note is pinned to a person.", embeddable=False
    )
    pinned_to_organization_flag: bool = AirweaveField(
        default=False, description="Whether the note is pinned to an organization.", embeddable=False
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="All properties from Pipedrive note object.",
        embeddable=True,
    )
    active_flag: bool = AirweaveField(
        default=True, description="Whether the note is active.", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view this note in Pipedrive.", embeddable=False, unhashable=True
    )

    @field_validator("created_time", "updated_time", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Normalize Pipedrive datetime inputs to timezone-aware datetimes."""
        return parse_pipedrive_datetime(value)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the Pipedrive note UI."""
        return self.web_url_value or ""

