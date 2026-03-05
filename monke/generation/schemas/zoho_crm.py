"""Pydantic schemas for LLM-generated Zoho CRM test content."""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class ZohoCRMContact(BaseModel):
    """Structured contact content for Zoho CRM."""

    token: str = Field(
        description="Verification token that MUST appear in at least one property (e.g., email)."
    )
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str] = None
    mobile: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    description: Optional[str] = None
    mailing_street: Optional[str] = None
    mailing_city: Optional[str] = None
    mailing_state: Optional[str] = None
    mailing_zip: Optional[str] = None
    mailing_country: Optional[str] = None


class ZohoCRMAccount(BaseModel):
    """Structured account content for Zoho CRM."""

    token: str = Field(
        description="Verification token that MUST appear in account_name or description."
    )
    account_name: str = Field(description="Company/organization name with token embedded")
    website: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    billing_street: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_code: Optional[str] = None
    billing_country: Optional[str] = None


class ZohoCRMDeal(BaseModel):
    """Structured deal content for Zoho CRM."""

    token: str = Field(
        description="Verification token that MUST appear in deal_name or description."
    )
    deal_name: str = Field(description="Deal name with token embedded")
    stage: Optional[str] = Field(
        default="Qualification",
        description="Sales stage (Qualification, Needs Analysis, Proposal, etc.)"
    )
    amount: Optional[float] = None
    description: Optional[str] = None
    next_step: Optional[str] = None
    lead_source: Optional[str] = None


class ZohoCRMLead(BaseModel):
    """Structured lead content for Zoho CRM."""

    token: str = Field(
        description="Verification token that MUST appear in email or description."
    )
    email: EmailStr
    first_name: str
    last_name: str
    company: str = Field(description="Company name for the lead")
    phone: Optional[str] = None
    mobile: Optional[str] = None
    title: Optional[str] = None
    industry: Optional[str] = None
    lead_source: Optional[str] = None
    lead_status: Optional[str] = Field(
        default="Not Contacted",
        description="Lead status (Not Contacted, Contacted, etc.)"
    )
    description: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
