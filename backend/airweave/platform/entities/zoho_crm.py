"""Zoho CRM entity schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse Zoho CRM ISO8601 timestamps into timezone-aware datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_ref(data: Dict[str, Any], key: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract (id, name) from a nested Zoho reference field that may be a dict or None."""
    ref = data.get(key)
    if isinstance(ref, dict):
        return ref.get("id"), ref.get("name")
    return None, None


def _build_record_url(org_id: Optional[str], module: str, record_id: str) -> Optional[str]:
    """Construct a Zoho CRM record URL."""
    if not record_id:
        return None
    return f"https://crm.zoho.com/crm/org{org_id or ''}/tab/{module}/{record_id}"


def _account_breadcrumb(account_id: Optional[str], account_name: Optional[str]) -> List[Breadcrumb]:
    if not account_id:
        return []
    return [
        Breadcrumb(
            entity_id=account_id,
            name=account_name or f"Account {account_id}",
            entity_type="ZohoCRMAccountEntity",
        )
    ]


class ZohoCRMAccountEntity(BaseEntity):
    """Schema for Zoho CRM Account entities."""

    account_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the account.", is_entity_id=True
    )
    account_name: str = AirweaveField(
        ..., description="Display name of the account.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the account was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the account was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to open the account in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    website: Optional[str] = AirweaveField(
        None, description="Account website URL", embeddable=False
    )
    phone: Optional[str] = AirweaveField(None, description="Account phone number", embeddable=True)
    fax: Optional[str] = AirweaveField(None, description="Account fax number", embeddable=False)
    industry: Optional[str] = AirweaveField(None, description="Account industry", embeddable=True)
    annual_revenue: Optional[float] = AirweaveField(
        None, description="Annual revenue", embeddable=False
    )
    employees: Optional[int] = AirweaveField(
        None, description="Number of employees", embeddable=False
    )
    ownership: Optional[str] = AirweaveField(
        None, description="Account ownership type", embeddable=True
    )
    ticker_symbol: Optional[str] = AirweaveField(
        None, description="Stock ticker symbol", embeddable=False
    )
    description: Optional[str] = AirweaveField(
        None, description="Account description", embeddable=True
    )
    rating: Optional[str] = AirweaveField(None, description="Account rating", embeddable=True)
    parent_account_id: Optional[str] = AirweaveField(
        None, description="ID of parent account", embeddable=False
    )
    account_type: Optional[str] = AirweaveField(None, description="Account type", embeddable=True)
    billing_street: Optional[str] = AirweaveField(
        None, description="Billing street address", embeddable=True
    )
    billing_city: Optional[str] = AirweaveField(None, description="Billing city", embeddable=True)
    billing_state: Optional[str] = AirweaveField(
        None, description="Billing state/province", embeddable=True
    )
    billing_code: Optional[str] = AirweaveField(
        None, description="Billing postal code", embeddable=False
    )
    billing_country: Optional[str] = AirweaveField(
        None, description="Billing country", embeddable=True
    )
    shipping_street: Optional[str] = AirweaveField(
        None, description="Shipping street address", embeddable=True
    )
    shipping_city: Optional[str] = AirweaveField(None, description="Shipping city", embeddable=True)
    shipping_state: Optional[str] = AirweaveField(
        None, description="Shipping state/province", embeddable=True
    )
    shipping_code: Optional[str] = AirweaveField(
        None, description="Shipping postal code", embeddable=False
    )
    shipping_country: Optional[str] = AirweaveField(
        None, description="Shipping country", embeddable=True
    )
    account_number: Optional[str] = AirweaveField(
        None, description="Account number", embeddable=True
    )
    sic_code: Optional[str] = AirweaveField(None, description="SIC code", embeddable=False)
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the account", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the account owner", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the account",
        embeddable=False,
    )

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, org_id: Optional[str] = None
    ) -> ZohoCRMAccountEntity:
        """Construct from a Zoho CRM Accounts API record."""
        account_id = str(data.get("id", ""))
        account_name = data.get("Account_Name") or f"Account {account_id}"
        created = _parse_dt(data.get("Created_Time")) or datetime.utcnow()
        updated = _parse_dt(data.get("Modified_Time")) or created
        owner_id, owner_name = _extract_ref(data, "Owner")
        parent_account_id, _ = _extract_ref(data, "Parent_Account")

        return cls(
            entity_id=account_id,
            breadcrumbs=[],
            name=account_name,
            created_at=created,
            updated_at=updated,
            account_id=account_id,
            account_name=account_name,
            created_time=created,
            updated_time=updated,
            web_url_value=_build_record_url(org_id, "Accounts", account_id),
            website=data.get("Website"),
            phone=data.get("Phone"),
            fax=data.get("Fax"),
            industry=data.get("Industry"),
            annual_revenue=data.get("Annual_Revenue"),
            employees=data.get("Employees"),
            ownership=data.get("Ownership"),
            ticker_symbol=data.get("Ticker_Symbol"),
            description=data.get("Description"),
            rating=data.get("Rating"),
            parent_account_id=parent_account_id,
            account_type=data.get("Account_Type"),
            billing_street=data.get("Billing_Street"),
            billing_city=data.get("Billing_City"),
            billing_state=data.get("Billing_State"),
            billing_code=data.get("Billing_Code"),
            billing_country=data.get("Billing_Country"),
            shipping_street=data.get("Shipping_Street"),
            shipping_city=data.get("Shipping_City"),
            shipping_state=data.get("Shipping_State"),
            shipping_code=data.get("Shipping_Code"),
            shipping_country=data.get("Shipping_Country"),
            account_number=data.get("Account_Number"),
            sic_code=data.get("SIC_Code"),
            owner_id=owner_id,
            owner_name=owner_name,
            metadata=data,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the account."""
        return self.web_url_value or ""


class ZohoCRMContactEntity(BaseEntity):
    """Schema for Zoho CRM Contact entities."""

    contact_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the contact.", is_entity_id=True
    )
    contact_name: str = AirweaveField(
        ..., description="Display name of the contact.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the contact was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the contact was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the contact in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    first_name: Optional[str] = AirweaveField(
        None, description="Contact's first name", embeddable=True
    )
    last_name: Optional[str] = AirweaveField(
        None, description="Contact's last name", embeddable=True
    )
    email: Optional[str] = AirweaveField(
        None, description="Contact's email address", embeddable=True
    )
    secondary_email: Optional[str] = AirweaveField(
        None, description="Contact's secondary email address", embeddable=True
    )
    phone: Optional[str] = AirweaveField(
        None, description="Contact's phone number", embeddable=True
    )
    mobile: Optional[str] = AirweaveField(
        None, description="Contact's mobile phone number", embeddable=True
    )
    fax: Optional[str] = AirweaveField(None, description="Contact's fax number", embeddable=False)
    title: Optional[str] = AirweaveField(None, description="Contact's job title", embeddable=True)
    department: Optional[str] = AirweaveField(
        None, description="Contact's department", embeddable=True
    )
    account_id: Optional[str] = AirweaveField(
        None, description="ID of the associated account", embeddable=False
    )
    account_name: Optional[str] = AirweaveField(
        None, description="Name of the associated account", embeddable=True
    )
    lead_source: Optional[str] = AirweaveField(
        None, description="Source of the lead", embeddable=True
    )
    date_of_birth: Optional[str] = AirweaveField(
        None, description="Contact's date of birth", embeddable=False
    )
    description: Optional[str] = AirweaveField(
        None, description="Contact description", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the contact", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the contact owner", embeddable=True
    )
    mailing_street: Optional[str] = AirweaveField(
        None, description="Mailing street address", embeddable=True
    )
    mailing_city: Optional[str] = AirweaveField(None, description="Mailing city", embeddable=True)
    mailing_state: Optional[str] = AirweaveField(
        None, description="Mailing state/province", embeddable=True
    )
    mailing_zip: Optional[str] = AirweaveField(
        None, description="Mailing postal code", embeddable=False
    )
    mailing_country: Optional[str] = AirweaveField(
        None, description="Mailing country", embeddable=True
    )
    other_street: Optional[str] = AirweaveField(
        None, description="Other street address", embeddable=True
    )
    other_city: Optional[str] = AirweaveField(None, description="Other city", embeddable=True)
    other_state: Optional[str] = AirweaveField(
        None, description="Other state/province", embeddable=True
    )
    other_zip: Optional[str] = AirweaveField(
        None, description="Other postal code", embeddable=False
    )
    other_country: Optional[str] = AirweaveField(None, description="Other country", embeddable=True)
    assistant: Optional[str] = AirweaveField(None, description="Assistant's name", embeddable=True)
    asst_phone: Optional[str] = AirweaveField(
        None, description="Assistant's phone number", embeddable=False
    )
    reports_to_id: Optional[str] = AirweaveField(
        None, description="ID of the contact this contact reports to", embeddable=False
    )
    email_opt_out: bool = AirweaveField(
        False,
        description="Indicates whether the contact has opted out of email",
        embeddable=False,
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Additional metadata about the contact", embeddable=False
    )

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, org_id: Optional[str] = None
    ) -> ZohoCRMContactEntity:
        """Construct from a Zoho CRM Contacts API record."""
        contact_id = str(data.get("id", ""))
        first_name = data.get("First_Name") or ""
        last_name = data.get("Last_Name") or ""
        contact_name = f"{first_name} {last_name}".strip() or f"Contact {contact_id}"
        created = _parse_dt(data.get("Created_Time")) or datetime.utcnow()
        updated = _parse_dt(data.get("Modified_Time")) or created
        owner_id, owner_name = _extract_ref(data, "Owner")
        account_id, account_name_val = _extract_ref(data, "Account_Name")
        reports_to_id, _ = _extract_ref(data, "Reporting_To")

        return cls(
            entity_id=contact_id,
            breadcrumbs=_account_breadcrumb(account_id, account_name_val),
            name=contact_name,
            created_at=created,
            updated_at=updated,
            contact_id=contact_id,
            contact_name=contact_name,
            created_time=created,
            updated_time=updated,
            web_url_value=_build_record_url(org_id, "Contacts", contact_id),
            first_name=first_name or None,
            last_name=last_name or None,
            email=data.get("Email"),
            secondary_email=data.get("Secondary_Email"),
            phone=data.get("Phone"),
            mobile=data.get("Mobile"),
            fax=data.get("Fax"),
            title=data.get("Title"),
            department=data.get("Department"),
            account_id=account_id,
            account_name=account_name_val,
            lead_source=data.get("Lead_Source"),
            date_of_birth=data.get("Date_of_Birth"),
            description=data.get("Description"),
            owner_id=owner_id,
            owner_name=owner_name,
            mailing_street=data.get("Mailing_Street"),
            mailing_city=data.get("Mailing_City"),
            mailing_state=data.get("Mailing_State"),
            mailing_zip=data.get("Mailing_Zip"),
            mailing_country=data.get("Mailing_Country"),
            other_street=data.get("Other_Street"),
            other_city=data.get("Other_City"),
            other_state=data.get("Other_State"),
            other_zip=data.get("Other_Zip"),
            other_country=data.get("Other_Country"),
            assistant=data.get("Assistant"),
            asst_phone=data.get("Asst_Phone"),
            reports_to_id=reports_to_id,
            email_opt_out=data.get("Email_Opt_Out", False),
            metadata=data,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the contact."""
        return self.web_url_value or ""


class ZohoCRMDealEntity(BaseEntity):
    """Schema for Zoho CRM Deal entities (pipelines)."""

    deal_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the deal.", is_entity_id=True
    )
    deal_name: str = AirweaveField(
        ..., description="Display name of the deal.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the deal was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the deal was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the deal in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    account_id: Optional[str] = AirweaveField(
        None, description="ID of the associated account", embeddable=False
    )
    account_name: Optional[str] = AirweaveField(
        None, description="Name of the associated account", embeddable=True
    )
    contact_id: Optional[str] = AirweaveField(
        None, description="ID of the associated contact", embeddable=False
    )
    contact_name: Optional[str] = AirweaveField(
        None, description="Name of the associated contact", embeddable=True
    )
    amount: Optional[float] = AirweaveField(None, description="Deal amount", embeddable=True)
    closing_date: Optional[str] = AirweaveField(
        None, description="Expected closing date", embeddable=True
    )
    stage: Optional[str] = AirweaveField(None, description="Sales stage", embeddable=True)
    probability: Optional[float] = AirweaveField(
        None, description="Probability percentage", embeddable=True
    )
    expected_revenue: Optional[float] = AirweaveField(
        None, description="Expected revenue", embeddable=False
    )
    pipeline: Optional[str] = AirweaveField(None, description="Pipeline name", embeddable=True)
    campaign_source: Optional[str] = AirweaveField(
        None, description="Campaign source", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the deal", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the deal owner", embeddable=True
    )
    lead_source: Optional[str] = AirweaveField(
        None, description="Source of the lead", embeddable=True
    )
    deal_type: Optional[str] = AirweaveField(None, description="Deal type", embeddable=True)
    next_step: Optional[str] = AirweaveField(
        None, description="Next step in the sales process", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Deal description", embeddable=True
    )
    reason_for_loss: Optional[str] = AirweaveField(
        None, description="Reason for loss if deal was lost", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the deal",
        embeddable=False,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, org_id: Optional[str] = None) -> ZohoCRMDealEntity:
        """Construct from a Zoho CRM Deals API record."""
        deal_id = str(data.get("id", ""))
        deal_name = data.get("Deal_Name") or f"Deal {deal_id}"
        created = _parse_dt(data.get("Created_Time")) or datetime.utcnow()
        updated = _parse_dt(data.get("Modified_Time")) or created
        owner_id, owner_name = _extract_ref(data, "Owner")
        account_id, account_name_val = _extract_ref(data, "Account_Name")
        contact_id, contact_name_val = _extract_ref(data, "Contact_Name")
        _, campaign_source = _extract_ref(data, "Campaign_Source")

        return cls(
            entity_id=deal_id,
            breadcrumbs=_account_breadcrumb(account_id, account_name_val),
            name=deal_name,
            created_at=created,
            updated_at=updated,
            deal_id=deal_id,
            deal_name=deal_name,
            created_time=created,
            updated_time=updated,
            web_url_value=_build_record_url(org_id, "Deals", deal_id),
            account_id=account_id,
            account_name=account_name_val,
            contact_id=contact_id,
            contact_name=contact_name_val,
            amount=data.get("Amount"),
            closing_date=data.get("Closing_Date"),
            stage=data.get("Stage"),
            probability=data.get("Probability"),
            expected_revenue=data.get("Expected_Revenue"),
            pipeline=data.get("Pipeline"),
            campaign_source=campaign_source,
            owner_id=owner_id,
            owner_name=owner_name,
            lead_source=data.get("Lead_Source"),
            deal_type=data.get("Type"),
            next_step=data.get("Next_Step"),
            description=data.get("Description"),
            reason_for_loss=data.get("Reason_For_Loss__s"),
            metadata=data,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the deal."""
        return self.web_url_value or ""


class ZohoCRMLeadEntity(BaseEntity):
    """Schema for Zoho CRM Lead entities.

    Leads are pre-qualified prospects that haven't been converted to contacts yet.
    """

    lead_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the lead.", is_entity_id=True
    )
    lead_name: str = AirweaveField(
        ..., description="Display name of the lead.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the lead was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the lead was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the lead in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    first_name: Optional[str] = AirweaveField(
        None, description="Lead's first name", embeddable=True
    )
    last_name: Optional[str] = AirweaveField(None, description="Lead's last name", embeddable=True)
    company: Optional[str] = AirweaveField(None, description="Lead's company name", embeddable=True)
    email: Optional[str] = AirweaveField(None, description="Lead's email address", embeddable=True)
    phone: Optional[str] = AirweaveField(None, description="Lead's phone number", embeddable=True)
    mobile: Optional[str] = AirweaveField(
        None, description="Lead's mobile phone number", embeddable=True
    )
    fax: Optional[str] = AirweaveField(None, description="Lead's fax number", embeddable=False)
    title: Optional[str] = AirweaveField(None, description="Lead's job title", embeddable=True)
    website: Optional[str] = AirweaveField(None, description="Lead's website", embeddable=False)
    lead_source: Optional[str] = AirweaveField(
        None, description="Source of the lead", embeddable=True
    )
    lead_status: Optional[str] = AirweaveField(
        None, description="Current status of the lead", embeddable=True
    )
    industry: Optional[str] = AirweaveField(None, description="Lead's industry", embeddable=True)
    annual_revenue: Optional[float] = AirweaveField(
        None, description="Annual revenue", embeddable=False
    )
    no_of_employees: Optional[int] = AirweaveField(
        None, description="Number of employees", embeddable=False
    )
    rating: Optional[str] = AirweaveField(None, description="Lead rating", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Lead description", embeddable=True
    )
    street: Optional[str] = AirweaveField(None, description="Street address", embeddable=True)
    city: Optional[str] = AirweaveField(None, description="City", embeddable=True)
    state: Optional[str] = AirweaveField(None, description="State/province", embeddable=True)
    zip_code: Optional[str] = AirweaveField(None, description="Postal code", embeddable=False)
    country: Optional[str] = AirweaveField(None, description="Country", embeddable=True)
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the lead", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the lead owner", embeddable=True
    )
    converted: bool = AirweaveField(
        False, description="Whether the lead has been converted", embeddable=False
    )
    email_opt_out: bool = AirweaveField(
        False,
        description="Indicates whether the lead has opted out of email",
        embeddable=False,
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the lead",
        embeddable=False,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, org_id: Optional[str] = None) -> ZohoCRMLeadEntity:
        """Construct from a Zoho CRM Leads API record."""
        lead_id = str(data.get("id", ""))
        first_name = data.get("First_Name") or ""
        last_name = data.get("Last_Name") or ""
        lead_name = f"{first_name} {last_name}".strip() or f"Lead {lead_id}"
        created = _parse_dt(data.get("Created_Time")) or datetime.utcnow()
        updated = _parse_dt(data.get("Modified_Time")) or created
        owner_id, owner_name = _extract_ref(data, "Owner")

        return cls(
            entity_id=lead_id,
            breadcrumbs=[],
            name=lead_name,
            created_at=created,
            updated_at=updated,
            lead_id=lead_id,
            lead_name=lead_name,
            created_time=created,
            updated_time=updated,
            web_url_value=_build_record_url(org_id, "Leads", lead_id),
            first_name=first_name or None,
            last_name=last_name or None,
            company=data.get("Company"),
            email=data.get("Email"),
            phone=data.get("Phone"),
            mobile=data.get("Mobile"),
            fax=data.get("Fax"),
            title=data.get("Title"),
            website=data.get("Website"),
            lead_source=data.get("Lead_Source"),
            lead_status=data.get("Lead_Status"),
            industry=data.get("Industry"),
            annual_revenue=data.get("Annual_Revenue"),
            no_of_employees=data.get("No_of_Employees"),
            rating=data.get("Rating"),
            description=data.get("Description"),
            street=data.get("Street"),
            city=data.get("City"),
            state=data.get("State"),
            zip_code=data.get("Zip_Code"),
            country=data.get("Country"),
            owner_id=owner_id,
            owner_name=owner_name,
            converted=data.get("$converted", False),
            email_opt_out=data.get("Email_Opt_Out", False),
            metadata=data,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the lead."""
        return self.web_url_value or ""


class ZohoCRMProductEntity(BaseEntity):
    """Schema for Zoho CRM Product entities.

    Products represent items in the product catalog.
    """

    product_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the product.", is_entity_id=True
    )
    product_name: str = AirweaveField(
        ..., description="Display name of the product.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the product was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the product was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the product in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    product_code: Optional[str] = AirweaveField(
        None, description="Product code/SKU", embeddable=True
    )
    product_category: Optional[str] = AirweaveField(
        None, description="Product category", embeddable=True
    )
    manufacturer: Optional[str] = AirweaveField(
        None, description="Product manufacturer", embeddable=True
    )
    vendor_name: Optional[str] = AirweaveField(None, description="Vendor name", embeddable=True)
    unit_price: Optional[float] = AirweaveField(None, description="Unit price", embeddable=True)
    sales_start_date: Optional[str] = AirweaveField(
        None, description="Sales start date", embeddable=False
    )
    sales_end_date: Optional[str] = AirweaveField(
        None, description="Sales end date", embeddable=False
    )
    support_start_date: Optional[str] = AirweaveField(
        None, description="Support start date", embeddable=False
    )
    support_expiry_date: Optional[str] = AirweaveField(
        None, description="Support expiry date", embeddable=False
    )
    qty_in_stock: Optional[float] = AirweaveField(
        None, description="Quantity in stock", embeddable=False
    )
    qty_in_demand: Optional[float] = AirweaveField(
        None, description="Quantity in demand", embeddable=False
    )
    qty_ordered: Optional[float] = AirweaveField(
        None, description="Quantity ordered", embeddable=False
    )
    reorder_level: Optional[float] = AirweaveField(
        None, description="Reorder level", embeddable=False
    )
    commission_rate: Optional[float] = AirweaveField(
        None, description="Commission rate", embeddable=False
    )
    tax: Optional[str] = AirweaveField(None, description="Tax information", embeddable=False)
    taxable: bool = AirweaveField(
        False, description="Whether the product is taxable", embeddable=False
    )
    product_active: bool = AirweaveField(
        True, description="Whether the product is active", embeddable=False
    )
    description: Optional[str] = AirweaveField(
        None, description="Product description", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the product", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the product owner", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the product",
        embeddable=False,
    )

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, org_id: Optional[str] = None
    ) -> ZohoCRMProductEntity:
        """Construct from a Zoho CRM Products API record."""
        product_id = str(data.get("id", ""))
        product_name = data.get("Product_Name") or f"Product {product_id}"
        created = _parse_dt(data.get("Created_Time")) or datetime.utcnow()
        updated = _parse_dt(data.get("Modified_Time")) or created
        owner_id, owner_name = _extract_ref(data, "Owner")
        _, vendor_name = _extract_ref(data, "Vendor_Name")

        return cls(
            entity_id=product_id,
            breadcrumbs=[],
            name=product_name,
            created_at=created,
            updated_at=updated,
            product_id=product_id,
            product_name=product_name,
            created_time=created,
            updated_time=updated,
            web_url_value=_build_record_url(org_id, "Products", product_id),
            product_code=data.get("Product_Code"),
            product_category=data.get("Product_Category"),
            manufacturer=data.get("Manufacturer"),
            vendor_name=vendor_name,
            unit_price=data.get("Unit_Price"),
            sales_start_date=data.get("Sales_Start_Date"),
            sales_end_date=data.get("Sales_End_Date"),
            support_start_date=data.get("Support_Start_Date"),
            support_expiry_date=data.get("Support_Expiry_Date"),
            qty_in_stock=data.get("Qty_in_Stock"),
            qty_in_demand=data.get("Qty_in_Demand"),
            qty_ordered=data.get("Qty_Ordered"),
            reorder_level=data.get("Reorder_Level"),
            commission_rate=data.get("Commission_Rate"),
            tax=data.get("Tax"),
            taxable=data.get("Taxable", False),
            product_active=data.get("Product_Active", True),
            description=data.get("Description"),
            owner_id=owner_id,
            owner_name=owner_name,
            metadata=data,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the product."""
        return self.web_url_value or ""


class ZohoCRMQuoteEntity(BaseEntity):
    """Schema for Zoho CRM Quote entities.

    Quotes are sales proposals sent to potential customers.
    """

    quote_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the quote.", is_entity_id=True
    )
    quote_name: str = AirweaveField(
        ..., description="Display name/subject of the quote.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the quote was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the quote was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the quote in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    quote_number: Optional[str] = AirweaveField(None, description="Quote number", embeddable=True)
    quote_stage: Optional[str] = AirweaveField(None, description="Quote stage", embeddable=True)
    account_id: Optional[str] = AirweaveField(
        None, description="ID of the associated account", embeddable=False
    )
    account_name: Optional[str] = AirweaveField(
        None, description="Name of the associated account", embeddable=True
    )
    contact_id: Optional[str] = AirweaveField(
        None, description="ID of the associated contact", embeddable=False
    )
    contact_name: Optional[str] = AirweaveField(
        None, description="Name of the associated contact", embeddable=True
    )
    deal_id: Optional[str] = AirweaveField(
        None, description="ID of the associated deal", embeddable=False
    )
    deal_name: Optional[str] = AirweaveField(
        None, description="Name of the associated deal", embeddable=True
    )
    valid_till: Optional[str] = AirweaveField(
        None, description="Quote validity date", embeddable=False
    )
    sub_total: Optional[float] = AirweaveField(None, description="Subtotal amount", embeddable=True)
    discount: Optional[float] = AirweaveField(None, description="Discount amount", embeddable=False)
    tax: Optional[float] = AirweaveField(None, description="Tax amount", embeddable=False)
    adjustment: Optional[float] = AirweaveField(
        None, description="Adjustment amount", embeddable=False
    )
    grand_total: Optional[float] = AirweaveField(
        None, description="Grand total amount", embeddable=True
    )
    carrier: Optional[str] = AirweaveField(None, description="Carrier/shipper", embeddable=True)
    shipping_charge: Optional[float] = AirweaveField(
        None, description="Shipping charge", embeddable=False
    )
    terms_and_conditions: Optional[str] = AirweaveField(
        None, description="Terms and conditions", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Quote description", embeddable=True
    )
    billing_street: Optional[str] = AirweaveField(
        None, description="Billing street", embeddable=True
    )
    billing_city: Optional[str] = AirweaveField(None, description="Billing city", embeddable=True)
    billing_state: Optional[str] = AirweaveField(None, description="Billing state", embeddable=True)
    billing_code: Optional[str] = AirweaveField(
        None, description="Billing postal code", embeddable=False
    )
    billing_country: Optional[str] = AirweaveField(
        None, description="Billing country", embeddable=True
    )
    shipping_street: Optional[str] = AirweaveField(
        None, description="Shipping street", embeddable=True
    )
    shipping_city: Optional[str] = AirweaveField(None, description="Shipping city", embeddable=True)
    shipping_state: Optional[str] = AirweaveField(
        None, description="Shipping state", embeddable=True
    )
    shipping_code: Optional[str] = AirweaveField(
        None, description="Shipping postal code", embeddable=False
    )
    shipping_country: Optional[str] = AirweaveField(
        None, description="Shipping country", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the quote", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the quote owner", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the quote",
        embeddable=False,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, org_id: Optional[str] = None) -> ZohoCRMQuoteEntity:
        """Construct from a Zoho CRM Quotes API record."""
        quote_id = str(data.get("id", ""))
        quote_name = data.get("Subject") or f"Quote {quote_id}"
        created = _parse_dt(data.get("Created_Time")) or datetime.utcnow()
        updated = _parse_dt(data.get("Modified_Time")) or created
        owner_id, owner_name = _extract_ref(data, "Owner")
        account_id, account_name_val = _extract_ref(data, "Account_Name")
        contact_id, contact_name_val = _extract_ref(data, "Contact_Name")
        deal_id, deal_name_val = _extract_ref(data, "Deal_Name")

        return cls(
            entity_id=quote_id,
            breadcrumbs=_account_breadcrumb(account_id, account_name_val),
            name=quote_name,
            created_at=created,
            updated_at=updated,
            quote_id=quote_id,
            quote_name=quote_name,
            created_time=created,
            updated_time=updated,
            web_url_value=_build_record_url(org_id, "Quotes", quote_id),
            quote_number=data.get("Quote_Number"),
            quote_stage=data.get("Quote_Stage"),
            account_id=account_id,
            account_name=account_name_val,
            contact_id=contact_id,
            contact_name=contact_name_val,
            deal_id=deal_id,
            deal_name=deal_name_val,
            valid_till=data.get("Valid_Till"),
            sub_total=data.get("Sub_Total"),
            discount=data.get("Discount"),
            tax=data.get("Tax"),
            adjustment=data.get("Adjustment"),
            grand_total=data.get("Grand_Total"),
            carrier=data.get("Carrier"),
            shipping_charge=data.get("Shipping_Charge"),
            terms_and_conditions=data.get("Terms_and_Conditions"),
            description=data.get("Description"),
            billing_street=data.get("Billing_Street"),
            billing_city=data.get("Billing_City"),
            billing_state=data.get("Billing_State"),
            billing_code=data.get("Billing_Code"),
            billing_country=data.get("Billing_Country"),
            shipping_street=data.get("Shipping_Street"),
            shipping_city=data.get("Shipping_City"),
            shipping_state=data.get("Shipping_State"),
            shipping_code=data.get("Shipping_Code"),
            shipping_country=data.get("Shipping_Country"),
            owner_id=owner_id,
            owner_name=owner_name,
            metadata=data,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the quote."""
        return self.web_url_value or ""


class ZohoCRMSalesOrderEntity(BaseEntity):
    """Schema for Zoho CRM Sales Order entities.

    Sales Orders are confirmed orders from customers.
    """

    sales_order_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the sales order.", is_entity_id=True
    )
    sales_order_name: str = AirweaveField(
        ..., description="Display name/subject of the sales order.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the sales order was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the sales order was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the sales order in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    so_number: Optional[str] = AirweaveField(
        None, description="Sales order number", embeddable=True
    )
    status: Optional[str] = AirweaveField(None, description="Sales order status", embeddable=True)
    account_id: Optional[str] = AirweaveField(
        None, description="ID of the associated account", embeddable=False
    )
    account_name: Optional[str] = AirweaveField(
        None, description="Name of the associated account", embeddable=True
    )
    contact_id: Optional[str] = AirweaveField(
        None, description="ID of the associated contact", embeddable=False
    )
    contact_name: Optional[str] = AirweaveField(
        None, description="Name of the associated contact", embeddable=True
    )
    deal_id: Optional[str] = AirweaveField(
        None, description="ID of the associated deal", embeddable=False
    )
    deal_name: Optional[str] = AirweaveField(
        None, description="Name of the associated deal", embeddable=True
    )
    quote_id: Optional[str] = AirweaveField(
        None, description="ID of the associated quote", embeddable=False
    )
    quote_name: Optional[str] = AirweaveField(
        None, description="Name of the associated quote", embeddable=True
    )
    due_date: Optional[str] = AirweaveField(None, description="Due date", embeddable=False)
    sub_total: Optional[float] = AirweaveField(None, description="Subtotal amount", embeddable=True)
    discount: Optional[float] = AirweaveField(None, description="Discount amount", embeddable=False)
    tax: Optional[float] = AirweaveField(None, description="Tax amount", embeddable=False)
    adjustment: Optional[float] = AirweaveField(
        None, description="Adjustment amount", embeddable=False
    )
    grand_total: Optional[float] = AirweaveField(
        None, description="Grand total amount", embeddable=True
    )
    carrier: Optional[str] = AirweaveField(None, description="Carrier/shipper", embeddable=True)
    shipping_charge: Optional[float] = AirweaveField(
        None, description="Shipping charge", embeddable=False
    )
    excise_duty: Optional[float] = AirweaveField(None, description="Excise duty", embeddable=False)
    terms_and_conditions: Optional[str] = AirweaveField(
        None, description="Terms and conditions", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Sales order description", embeddable=True
    )
    billing_street: Optional[str] = AirweaveField(
        None, description="Billing street", embeddable=True
    )
    billing_city: Optional[str] = AirweaveField(None, description="Billing city", embeddable=True)
    billing_state: Optional[str] = AirweaveField(None, description="Billing state", embeddable=True)
    billing_code: Optional[str] = AirweaveField(
        None, description="Billing postal code", embeddable=False
    )
    billing_country: Optional[str] = AirweaveField(
        None, description="Billing country", embeddable=True
    )
    shipping_street: Optional[str] = AirweaveField(
        None, description="Shipping street", embeddable=True
    )
    shipping_city: Optional[str] = AirweaveField(None, description="Shipping city", embeddable=True)
    shipping_state: Optional[str] = AirweaveField(
        None, description="Shipping state", embeddable=True
    )
    shipping_code: Optional[str] = AirweaveField(
        None, description="Shipping postal code", embeddable=False
    )
    shipping_country: Optional[str] = AirweaveField(
        None, description="Shipping country", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the sales order", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the sales order owner", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the sales order",
        embeddable=False,
    )

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, org_id: Optional[str] = None
    ) -> ZohoCRMSalesOrderEntity:
        """Construct from a Zoho CRM Sales_Orders API record."""
        so_id = str(data.get("id", ""))
        so_name = data.get("Subject") or f"Sales Order {so_id}"
        created = _parse_dt(data.get("Created_Time")) or datetime.utcnow()
        updated = _parse_dt(data.get("Modified_Time")) or created
        owner_id, owner_name = _extract_ref(data, "Owner")
        account_id, account_name_val = _extract_ref(data, "Account_Name")
        contact_id, contact_name_val = _extract_ref(data, "Contact_Name")
        deal_id, deal_name_val = _extract_ref(data, "Deal_Name")
        quote_id, quote_name_val = _extract_ref(data, "Quote_Name")

        return cls(
            entity_id=so_id,
            breadcrumbs=_account_breadcrumb(account_id, account_name_val),
            name=so_name,
            created_at=created,
            updated_at=updated,
            sales_order_id=so_id,
            sales_order_name=so_name,
            created_time=created,
            updated_time=updated,
            web_url_value=_build_record_url(org_id, "Sales_Orders", so_id),
            so_number=data.get("SO_Number"),
            status=data.get("Status"),
            account_id=account_id,
            account_name=account_name_val,
            contact_id=contact_id,
            contact_name=contact_name_val,
            deal_id=deal_id,
            deal_name=deal_name_val,
            quote_id=quote_id,
            quote_name=quote_name_val,
            due_date=data.get("Due_Date"),
            sub_total=data.get("Sub_Total"),
            discount=data.get("Discount"),
            tax=data.get("Tax"),
            adjustment=data.get("Adjustment"),
            grand_total=data.get("Grand_Total"),
            carrier=data.get("Carrier"),
            shipping_charge=data.get("Shipping_Charge"),
            excise_duty=data.get("Excise_Duty"),
            terms_and_conditions=data.get("Terms_and_Conditions"),
            description=data.get("Description"),
            billing_street=data.get("Billing_Street"),
            billing_city=data.get("Billing_City"),
            billing_state=data.get("Billing_State"),
            billing_code=data.get("Billing_Code"),
            billing_country=data.get("Billing_Country"),
            shipping_street=data.get("Shipping_Street"),
            shipping_city=data.get("Shipping_City"),
            shipping_state=data.get("Shipping_State"),
            shipping_code=data.get("Shipping_Code"),
            shipping_country=data.get("Shipping_Country"),
            owner_id=owner_id,
            owner_name=owner_name,
            metadata=data,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the sales order."""
        return self.web_url_value or ""


class ZohoCRMInvoiceEntity(BaseEntity):
    """Schema for Zoho CRM Invoice entities.

    Invoices are billing documents sent to customers.
    """

    invoice_id: str = AirweaveField(
        ..., description="Unique Zoho CRM ID for the invoice.", is_entity_id=True
    )
    invoice_name: str = AirweaveField(
        ..., description="Display name/subject of the invoice.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the invoice was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the invoice was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the invoice in Zoho CRM.",
        embeddable=False,
        unhashable=True,
    )

    invoice_number: Optional[str] = AirweaveField(
        None, description="Invoice number", embeddable=True
    )
    invoice_date: Optional[str] = AirweaveField(None, description="Invoice date", embeddable=False)
    status: Optional[str] = AirweaveField(None, description="Invoice status", embeddable=True)
    account_id: Optional[str] = AirweaveField(
        None, description="ID of the associated account", embeddable=False
    )
    account_name: Optional[str] = AirweaveField(
        None, description="Name of the associated account", embeddable=True
    )
    contact_id: Optional[str] = AirweaveField(
        None, description="ID of the associated contact", embeddable=False
    )
    contact_name: Optional[str] = AirweaveField(
        None, description="Name of the associated contact", embeddable=True
    )
    deal_id: Optional[str] = AirweaveField(
        None, description="ID of the associated deal", embeddable=False
    )
    deal_name: Optional[str] = AirweaveField(
        None, description="Name of the associated deal", embeddable=True
    )
    sales_order_id: Optional[str] = AirweaveField(
        None, description="ID of the associated sales order", embeddable=False
    )
    sales_order_name: Optional[str] = AirweaveField(
        None, description="Name of the associated sales order", embeddable=True
    )
    due_date: Optional[str] = AirweaveField(None, description="Payment due date", embeddable=False)
    purchase_order: Optional[str] = AirweaveField(
        None, description="Purchase order number", embeddable=True
    )
    sub_total: Optional[float] = AirweaveField(None, description="Subtotal amount", embeddable=True)
    discount: Optional[float] = AirweaveField(None, description="Discount amount", embeddable=False)
    tax: Optional[float] = AirweaveField(None, description="Tax amount", embeddable=False)
    adjustment: Optional[float] = AirweaveField(
        None, description="Adjustment amount", embeddable=False
    )
    grand_total: Optional[float] = AirweaveField(
        None, description="Grand total amount", embeddable=True
    )
    shipping_charge: Optional[float] = AirweaveField(
        None, description="Shipping charge", embeddable=False
    )
    excise_duty: Optional[float] = AirweaveField(None, description="Excise duty", embeddable=False)
    terms_and_conditions: Optional[str] = AirweaveField(
        None, description="Terms and conditions", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Invoice description", embeddable=True
    )
    billing_street: Optional[str] = AirweaveField(
        None, description="Billing street", embeddable=True
    )
    billing_city: Optional[str] = AirweaveField(None, description="Billing city", embeddable=True)
    billing_state: Optional[str] = AirweaveField(None, description="Billing state", embeddable=True)
    billing_code: Optional[str] = AirweaveField(
        None, description="Billing postal code", embeddable=False
    )
    billing_country: Optional[str] = AirweaveField(
        None, description="Billing country", embeddable=True
    )
    shipping_street: Optional[str] = AirweaveField(
        None, description="Shipping street", embeddable=True
    )
    shipping_city: Optional[str] = AirweaveField(None, description="Shipping city", embeddable=True)
    shipping_state: Optional[str] = AirweaveField(
        None, description="Shipping state", embeddable=True
    )
    shipping_code: Optional[str] = AirweaveField(
        None, description="Shipping postal code", embeddable=False
    )
    shipping_country: Optional[str] = AirweaveField(
        None, description="Shipping country", embeddable=True
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who owns the invoice", embeddable=False
    )
    owner_name: Optional[str] = AirweaveField(
        None, description="Name of the invoice owner", embeddable=True
    )
    metadata: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Additional metadata about the invoice",
        embeddable=False,
    )

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, org_id: Optional[str] = None
    ) -> ZohoCRMInvoiceEntity:
        """Construct from a Zoho CRM Invoices API record."""
        invoice_id = str(data.get("id", ""))
        invoice_name = data.get("Subject") or f"Invoice {invoice_id}"
        created = _parse_dt(data.get("Created_Time")) or datetime.utcnow()
        updated = _parse_dt(data.get("Modified_Time")) or created
        owner_id, owner_name = _extract_ref(data, "Owner")
        account_id, account_name_val = _extract_ref(data, "Account_Name")
        contact_id, contact_name_val = _extract_ref(data, "Contact_Name")
        deal_id, deal_name_val = _extract_ref(data, "Deal_Name")
        sales_order_id, sales_order_name_val = _extract_ref(data, "Sales_Order")

        return cls(
            entity_id=invoice_id,
            breadcrumbs=_account_breadcrumb(account_id, account_name_val),
            name=invoice_name,
            created_at=created,
            updated_at=updated,
            invoice_id=invoice_id,
            invoice_name=invoice_name,
            created_time=created,
            updated_time=updated,
            web_url_value=_build_record_url(org_id, "Invoices", invoice_id),
            invoice_number=data.get("Invoice_Number"),
            invoice_date=data.get("Invoice_Date"),
            status=data.get("Status"),
            account_id=account_id,
            account_name=account_name_val,
            contact_id=contact_id,
            contact_name=contact_name_val,
            deal_id=deal_id,
            deal_name=deal_name_val,
            sales_order_id=sales_order_id,
            sales_order_name=sales_order_name_val,
            due_date=data.get("Due_Date"),
            purchase_order=data.get("Purchase_Order"),
            sub_total=data.get("Sub_Total"),
            discount=data.get("Discount"),
            tax=data.get("Tax"),
            adjustment=data.get("Adjustment"),
            grand_total=data.get("Grand_Total"),
            shipping_charge=data.get("Shipping_Charge"),
            excise_duty=data.get("Excise_Duty"),
            terms_and_conditions=data.get("Terms_and_Conditions"),
            description=data.get("Description"),
            billing_street=data.get("Billing_Street"),
            billing_city=data.get("Billing_City"),
            billing_state=data.get("Billing_State"),
            billing_code=data.get("Billing_Code"),
            billing_country=data.get("Billing_Country"),
            shipping_street=data.get("Shipping_Street"),
            shipping_city=data.get("Shipping_City"),
            shipping_state=data.get("Shipping_State"),
            shipping_code=data.get("Shipping_Code"),
            shipping_country=data.get("Shipping_Country"),
            owner_id=owner_id,
            owner_name=owner_name,
            metadata=data,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the invoice."""
        return self.web_url_value or ""
