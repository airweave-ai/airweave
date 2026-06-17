"""Creatio-specific generation schemas.

Pydantic schemas for generating test content for all Creatio entity types.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class CreatioAccountArtifact(BaseModel):
    """Schema for Creatio account generation."""

    name: str = Field(description="Company/account name")
    phone: str = Field(description="Account phone number")
    web: str = Field(description="Account website URL")
    address: str = Field(description="Account address")
    created_at: datetime = Field(default_factory=datetime.now)


class CreatioContactArtifact(BaseModel):
    """Schema for Creatio contact generation."""

    name: str = Field(description="Full name of the contact")
    email: str = Field(description="Contact email address")
    phone: str = Field(description="Contact phone number")
    job_title: str = Field(description="Contact job title (token embedded here)")
    created_at: datetime = Field(default_factory=datetime.now)


class CreatioCampaignArtifact(BaseModel):
    """Schema for Creatio campaign generation."""

    name: str = Field(description="Campaign name (token embedded here)")
    target_description: str = Field(description="Description of the campaign target")
    created_at: datetime = Field(default_factory=datetime.now)


class CreatioOpportunityArtifact(BaseModel):
    """Schema for Creatio opportunity generation."""

    title: str = Field(description="Opportunity title (token embedded here)")
    description: str = Field(description="Opportunity description")
    budget: float = Field(description="Opportunity budget amount")
    amount: float = Field(description="Opportunity deal amount")
    created_at: datetime = Field(default_factory=datetime.now)


class CreatioOrderArtifact(BaseModel):
    """Schema for Creatio order generation."""

    notes: str = Field(description="Order notes (token embedded here)")
    comment: str = Field(description="Order comment")
    receiver_name: str = Field(description="Receiver name for delivery")
    delivery_address: str = Field(description="Delivery address")
    created_at: datetime = Field(default_factory=datetime.now)
