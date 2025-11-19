"""Admin-specific schemas for enhanced dashboard views."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from airweave.core.shared_models import FeatureFlag as FeatureFlagEnum


class OrganizationMetrics(BaseModel):
    """Comprehensive organization metrics for admin dashboard.

    Combines organization info with billing and usage metrics from the Usage model.
    """

    # Organization basic info
    id: UUID = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    description: Optional[str] = Field(None, description="Organization description")
    created_at: datetime = Field(..., description="When organization was created")
    modified_at: datetime = Field(..., description="Last modification time")
    auth0_org_id: Optional[str] = Field(None, description="Auth0 organization ID")

    # Billing information
    billing_plan: Optional[str] = Field(
        None, description="Current billing plan (trial, starter, pro, enterprise)"
    )
    billing_status: Optional[str] = Field(
        None, description="Billing status (active, cancelled, past_due, etc.)"
    )
    stripe_customer_id: Optional[str] = Field(None, description="Stripe customer ID")
    trial_ends_at: Optional[datetime] = Field(None, description="When trial ends")

    # Usage metrics - sourced from Usage model (usage.py)
    user_count: int = Field(0, description="Number of users in organization")
    source_connection_count: int = Field(
        0, description="Number of source connections (computed from source_connection table)"
    )
    entity_count: int = Field(0, description="Total number of entities (from Usage.entities)")
    query_count: int = Field(0, description="Total number of queries (from Usage.queries)")
    last_active_at: Optional[datetime] = Field(
        None, description="Last active timestamp of any user in this organization"
    )

    # Admin membership info
    is_member: bool = Field(False, description="Whether the current admin user is already a member")
    member_role: Optional[str] = Field(
        None, description="Admin's role in this organization (if member)"
    )

    # Feature flags
    enabled_features: List[FeatureFlagEnum] = Field(
        default_factory=list, description="List of enabled feature flags for this organization"
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True
