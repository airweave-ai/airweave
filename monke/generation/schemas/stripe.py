"""Stripe-specific generation schema."""

from datetime import datetime
from pydantic import BaseModel, Field


class StripeArtifact(BaseModel):
    """Schema for Stripe customer generation."""

    name: str = Field(description="Customer name")
    email: str = Field(description="Customer email address")
    description: str = Field(description="Customer description or notes")
    created_at: datetime = Field(default_factory=datetime.now)
