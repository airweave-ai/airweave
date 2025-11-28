"""Pydantic schemas for Pipedrive test data generation."""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class PipedrivePerson(BaseModel):
    """Structured person (contact) content for Pipedrive."""

    token: str = Field(
        description="Verification token that MUST appear in the name or organization."
    )
    name: str = Field(description="Full name of the person")
    email: EmailStr = Field(description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    org_name: Optional[str] = Field(default=None, description="Organization name")


class PipedriveOrganization(BaseModel):
    """Structured organization (company) content for Pipedrive."""

    token: str = Field(
        description="Verification token that MUST appear in the organization name."
    )
    name: str = Field(description="Organization name")
    address: Optional[str] = Field(default=None, description="Business address")


class PipedriveDeal(BaseModel):
    """Structured deal content for Pipedrive."""

    token: str = Field(description="Verification token that MUST appear in the title.")
    title: str = Field(description="Deal title")
    value: Optional[float] = Field(default=None, description="Deal value")
    currency: str = Field(default="USD", description="Currency code")

