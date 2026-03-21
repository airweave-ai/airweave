"""Pipedrive entity schemas.

Based on the Pipedrive CRM API v1 reference, we define entity schemas for common
Pipedrive objects like Persons, Organizations, Deals, Activities, Products, Leads, and Notes.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field, field_validator

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb


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
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    return None


def _clean_properties(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove null, empty string, and internal fields from properties."""
    cleaned = {}
    skip_keys = {"id", "company_id", "creator_user_id", "owner_id", "user_id"}
    for key, value in data.items():
        if key in skip_keys:
            continue
        if value is None or value == "":
            continue
        if isinstance(value, dict) and set(value.keys()) <= {"id", "name", "value"}:
            continue
        cleaned[key] = value
    return cleaned


def _build_record_url(
    company_domain: Optional[str], record_type: str, record_id: str
) -> Optional[str]:
    """Build a Pipedrive UI URL for the given record."""
    if not company_domain:
        return None
    base = f"https://{company_domain}.pipedrive.com"
    url_patterns = {
        "person": f"{base}/person/{record_id}",
        "organization": f"{base}/organization/{record_id}",
        "deal": f"{base}/deal/{record_id}",
        "activity": f"{base}/activities/list/user/everyone/filter/all/activity/{record_id}",
        "product": f"{base}/settings/products",
        "lead": f"{base}/leads/inbox/{record_id}",
    }
    return url_patterns.get(record_type, f"{base}/{record_type}/{record_id}")


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

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, company_domain: Optional[str] = None
    ) -> "PipedrivePersonEntity":
        """Construct from a Pipedrive API persons response."""
        person_id = str(data.get("id"))
        name = data.get("name") or f"Person {person_id}"

        emails = data.get("email") or []
        primary_email = None
        if isinstance(emails, list) and emails:
            primary_email = emails[0].get("value") if isinstance(emails[0], dict) else emails[0]
        elif isinstance(emails, str):
            primary_email = emails

        phones = data.get("phone") or []
        primary_phone = None
        if isinstance(phones, list) and phones:
            primary_phone = phones[0].get("value") if isinstance(phones[0], dict) else phones[0]
        elif isinstance(phones, str):
            primary_phone = phones

        org_id = data.get("org_id")
        org_name = None
        if isinstance(org_id, dict):
            org_name = org_id.get("name")
            org_id = org_id.get("value")

        created_time = parse_pipedrive_datetime(data.get("add_time")) or datetime.utcnow()
        updated_time = parse_pipedrive_datetime(data.get("update_time")) or created_time

        breadcrumbs: List[Breadcrumb] = []
        if org_id and org_name:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=str(org_id),
                    name=org_name,
                    entity_type="PipedriveOrganizationEntity",
                )
            )

        owner_id_raw = data.get("owner_id")
        owner_id = owner_id_raw.get("id") if isinstance(owner_id_raw, dict) else owner_id_raw

        return cls(
            entity_id=f"person_{person_id}",
            breadcrumbs=breadcrumbs,
            name=name,
            created_at=created_time,
            updated_at=updated_time,
            person_id=person_id,
            display_name=name,
            created_time=created_time,
            updated_time=updated_time,
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            email=primary_email,
            phone=primary_phone,
            organization_id=org_id,
            organization_name=org_name,
            owner_id=owner_id,
            properties=_clean_properties(data),
            active_flag=data.get("active_flag", True),
            web_url_value=_build_record_url(company_domain, "person", person_id),
        )

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

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, company_domain: Optional[str] = None
    ) -> "PipedriveOrganizationEntity":
        """Construct from a Pipedrive API organizations response."""
        org_id = str(data.get("id"))
        name = data.get("name") or f"Organization {org_id}"

        created_time = parse_pipedrive_datetime(data.get("add_time")) or datetime.utcnow()
        updated_time = parse_pipedrive_datetime(data.get("update_time")) or created_time

        owner_id_raw = data.get("owner_id")
        owner_id = owner_id_raw.get("id") if isinstance(owner_id_raw, dict) else owner_id_raw

        return cls(
            entity_id=f"organization_{org_id}",
            breadcrumbs=[],
            name=name,
            created_at=created_time,
            updated_at=updated_time,
            organization_id=org_id,
            organization_name=name,
            created_time=created_time,
            updated_time=updated_time,
            address=data.get("address"),
            owner_id=owner_id,
            people_count=data.get("people_count"),
            properties=_clean_properties(data),
            active_flag=data.get("active_flag", True),
            web_url_value=_build_record_url(company_domain, "organization", org_id),
        )

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

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, company_domain: Optional[str] = None
    ) -> "PipedriveDealEntity":
        """Construct from a Pipedrive API deals response."""
        deal_id = str(data.get("id"))
        title = data.get("title") or f"Deal {deal_id}"

        person_id = data.get("person_id")
        person_name = None
        if isinstance(person_id, dict):
            person_name = person_id.get("name")
            person_id = person_id.get("value")

        org_id = data.get("org_id")
        org_name = None
        if isinstance(org_id, dict):
            org_name = org_id.get("name")
            org_id = org_id.get("value")

        created_time = parse_pipedrive_datetime(data.get("add_time")) or datetime.utcnow()
        updated_time = parse_pipedrive_datetime(data.get("update_time")) or created_time
        expected_close = parse_pipedrive_datetime(data.get("expected_close_date"))

        breadcrumbs: List[Breadcrumb] = []
        if org_id and org_name:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=str(org_id),
                    name=org_name,
                    entity_type="PipedriveOrganizationEntity",
                )
            )
        if person_id and person_name:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=str(person_id),
                    name=person_name,
                    entity_type="PipedrivePersonEntity",
                )
            )

        owner_id_raw = data.get("user_id")
        owner_id = owner_id_raw.get("id") if isinstance(owner_id_raw, dict) else owner_id_raw

        return cls(
            entity_id=f"deal_{deal_id}",
            breadcrumbs=breadcrumbs,
            name=title,
            created_at=created_time,
            updated_at=updated_time,
            deal_id=deal_id,
            deal_title=title,
            created_time=created_time,
            updated_time=updated_time,
            value=data.get("value"),
            currency=data.get("currency"),
            status=data.get("status"),
            stage_id=data.get("stage_id"),
            stage_name=None,
            pipeline_id=data.get("pipeline_id"),
            pipeline_name=None,
            person_id=person_id,
            person_name=person_name,
            organization_id=org_id,
            organization_name=org_name,
            owner_id=owner_id,
            expected_close_date=expected_close,
            probability=data.get("probability"),
            properties=_clean_properties(data),
            active_flag=data.get("active", True),
            web_url_value=_build_record_url(company_domain, "deal", deal_id),
        )

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

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, company_domain: Optional[str] = None
    ) -> "PipedriveActivityEntity":
        """Construct from a Pipedrive API activities response."""
        activity_id = str(data.get("id"))
        subject = data.get("subject") or f"Activity {activity_id}"

        deal_id = data.get("deal_id")
        deal_title = data.get("deal_title")
        person_id = data.get("person_id")
        person_name = data.get("person_name")
        org_id = data.get("org_id")
        org_name = data.get("org_name")

        created_time = parse_pipedrive_datetime(data.get("add_time")) or datetime.utcnow()
        updated_time = parse_pipedrive_datetime(data.get("update_time")) or created_time
        due_date = parse_pipedrive_datetime(data.get("due_date"))

        breadcrumbs: List[Breadcrumb] = []
        if org_id and org_name:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=str(org_id),
                    name=org_name,
                    entity_type="PipedriveOrganizationEntity",
                )
            )
        if person_id and person_name:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=str(person_id),
                    name=person_name,
                    entity_type="PipedrivePersonEntity",
                )
            )
        if deal_id and deal_title:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=str(deal_id),
                    name=deal_title,
                    entity_type="PipedriveDealEntity",
                )
            )

        return cls(
            entity_id=f"activity_{activity_id}",
            breadcrumbs=breadcrumbs,
            name=subject,
            created_at=created_time,
            updated_at=updated_time,
            activity_id=activity_id,
            activity_subject=subject,
            created_time=created_time,
            updated_time=updated_time,
            activity_type=data.get("type"),
            due_date=due_date,
            due_time=data.get("due_time"),
            duration=data.get("duration"),
            done=data.get("done", False),
            note=data.get("note"),
            deal_id=deal_id,
            deal_title=deal_title,
            person_id=person_id,
            person_name=person_name,
            organization_id=org_id,
            organization_name=org_name,
            owner_id=data.get("user_id"),
            properties=_clean_properties(data),
            active_flag=data.get("active_flag", True),
            web_url_value=_build_record_url(company_domain, "activity", activity_id),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the Pipedrive activity UI."""
        return self.web_url_value or ""


class PipedriveProductEntity(BaseEntity):
    """Schema for Pipedrive product entities.

    Reference:
        https://developers.pipedrive.com/docs/api/v1/Products
    """

    product_id: str = AirweaveField(..., description="The Pipedrive product ID.", is_entity_id=True)
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

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, company_domain: Optional[str] = None
    ) -> "PipedriveProductEntity":
        """Construct from a Pipedrive API products response."""
        product_id = str(data.get("id"))
        name = data.get("name") or f"Product {product_id}"

        created_time = parse_pipedrive_datetime(data.get("add_time")) or datetime.utcnow()
        updated_time = parse_pipedrive_datetime(data.get("update_time")) or created_time

        prices: Dict[str, Any] = {}
        if data.get("prices"):
            for price in data.get("prices", []):
                if isinstance(price, dict):
                    currency = price.get("currency")
                    if currency:
                        prices[currency] = {
                            "price": price.get("price"),
                            "cost": price.get("cost"),
                            "overhead_cost": price.get("overhead_cost"),
                        }

        owner_id_raw = data.get("owner_id")
        owner_id = owner_id_raw.get("id") if isinstance(owner_id_raw, dict) else owner_id_raw

        return cls(
            entity_id=f"product_{product_id}",
            breadcrumbs=[],
            name=name,
            created_at=created_time,
            updated_at=updated_time,
            product_id=product_id,
            product_name=name,
            created_time=created_time,
            updated_time=updated_time,
            code=data.get("code"),
            description=data.get("description"),
            unit=data.get("unit"),
            tax=data.get("tax"),
            category=data.get("category"),
            owner_id=owner_id,
            prices=prices,
            properties=_clean_properties(data),
            active_flag=data.get("active_flag", True),
            web_url_value=_build_record_url(company_domain, "product", product_id),
        )

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

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, company_domain: Optional[str] = None
    ) -> "PipedriveLeadEntity":
        """Construct from a Pipedrive API leads response."""
        lead_id = str(data.get("id"))
        title = data.get("title") or f"Lead {lead_id}"

        person_id = data.get("person_id")
        person_name = None
        if isinstance(person_id, dict):
            person_name = person_id.get("name")
            person_id = person_id.get("value")

        org_id = data.get("organization_id")
        org_name = None
        if isinstance(org_id, dict):
            org_name = org_id.get("name")
            org_id = org_id.get("value")

        value_obj = data.get("value") or {}
        value = value_obj.get("amount") if isinstance(value_obj, dict) else None
        currency = value_obj.get("currency") if isinstance(value_obj, dict) else None

        created_time = parse_pipedrive_datetime(data.get("add_time")) or datetime.utcnow()
        updated_time = parse_pipedrive_datetime(data.get("update_time")) or created_time
        expected_close = parse_pipedrive_datetime(data.get("expected_close_date"))

        breadcrumbs: List[Breadcrumb] = []
        if org_id and org_name:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=str(org_id),
                    name=org_name,
                    entity_type="PipedriveOrganizationEntity",
                )
            )
        if person_id and person_name:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=str(person_id),
                    name=person_name,
                    entity_type="PipedrivePersonEntity",
                )
            )

        return cls(
            entity_id=f"lead_{lead_id}",
            breadcrumbs=breadcrumbs,
            name=title,
            created_at=created_time,
            updated_at=updated_time,
            lead_id=lead_id,
            lead_title=title,
            created_time=created_time,
            updated_time=updated_time,
            value=value,
            currency=currency,
            expected_close_date=expected_close,
            person_id=person_id,
            person_name=person_name,
            organization_id=org_id,
            organization_name=org_name,
            owner_id=data.get("owner_id"),
            source_name=data.get("source_name"),
            label_ids=data.get("label_ids"),
            properties=_clean_properties(data),
            is_archived=data.get("is_archived", False),
            web_url_value=_build_record_url(company_domain, "lead", lead_id),
        )

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
        default=False,
        description="Whether the note is pinned to an organization.",
        embeddable=False,
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

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, company_domain: Optional[str] = None
    ) -> "PipedriveNoteEntity":
        """Construct from a Pipedrive API notes response."""
        note_id = str(data.get("id"))
        content = data.get("content") or ""

        title = content[:50].strip() if content else f"Note {note_id}"
        if len(content) > 50:
            title += "..."

        deal_id = data.get("deal_id")
        deal_title = None
        if isinstance(data.get("deal"), dict):
            deal_title = data["deal"].get("title")

        person_id = data.get("person_id")
        person_name = (
            data.get("person", {}).get("name") if isinstance(data.get("person"), dict) else None
        )

        org_id = data.get("org_id")
        org_name = (
            data.get("organization", {}).get("name")
            if isinstance(data.get("organization"), dict)
            else None
        )

        created_time = parse_pipedrive_datetime(data.get("add_time")) or datetime.utcnow()
        updated_time = parse_pipedrive_datetime(data.get("update_time")) or created_time

        breadcrumbs: List[Breadcrumb] = []
        if org_id and org_name:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=str(org_id),
                    name=org_name,
                    entity_type="PipedriveOrganizationEntity",
                )
            )
        if person_id and person_name:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=str(person_id),
                    name=person_name,
                    entity_type="PipedrivePersonEntity",
                )
            )
        if deal_id and deal_title:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=str(deal_id),
                    name=deal_title,
                    entity_type="PipedriveDealEntity",
                )
            )

        return cls(
            entity_id=f"note_{note_id}",
            breadcrumbs=breadcrumbs,
            name=title,
            created_at=created_time,
            updated_at=updated_time,
            note_id=note_id,
            note_title=title,
            created_time=created_time,
            updated_time=updated_time,
            content=content,
            deal_id=deal_id,
            deal_title=deal_title,
            person_id=person_id,
            person_name=person_name,
            organization_id=org_id,
            organization_name=org_name,
            lead_id=data.get("lead_id"),
            user_id=data.get("user_id"),
            pinned_to_deal_flag=data.get("pinned_to_deal_flag", False),
            pinned_to_person_flag=data.get("pinned_to_person_flag", False),
            pinned_to_organization_flag=data.get("pinned_to_organization_flag", False),
            properties=_clean_properties(data),
            active_flag=data.get("active_flag", True),
            web_url_value=None,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the Pipedrive note UI."""
        return self.web_url_value or ""
