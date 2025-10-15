"""Organization schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from airweave.core.shared_models import FeatureFlag as FeatureFlagEnum
from airweave.schemas.organization_billing import OrganizationBilling as OrganizationBillingSchema


class OrganizationBase(BaseModel):
    """Organization base schema."""

    name: str = Field(..., min_length=4, max_length=100, description="Organization name")
    description: Optional[str] = Field(None, max_length=500, description="Organization description")
    auth0_org_id: Optional[str] = Field(None, description="Auth0 organization ID")


class OrganizationCreate(OrganizationBase):
    """Organization creation schema."""

    org_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional organization metadata"
    )


class OrganizationUpdate(BaseModel):
    """Organization update schema."""

    name: str
    description: Optional[str] = None
    org_metadata: Optional[Dict[str, Any]] = None


class OrganizationInDBBase(OrganizationBase):
    """Organization base schema in the database."""

    model_config = {"from_attributes": True}

    id: UUID
    created_at: datetime
    modified_at: datetime
    org_metadata: Optional[Dict[str, Any]] = None


class Organization(OrganizationInDBBase):
    """Organization schema with billing and feature information.

    This is the primary organization schema used in API contexts, enriched with
    billing (including current period) and feature flags for efficient access
    without additional database queries.

    Access billing info compositionally:
    - organization.billing.plan
    - organization.billing.status
    - organization.billing.current_period
    """

    name: str
    description: Optional[str] = None
    auth0_org_id: Optional[str] = None

    # Feature flags (eager-loaded via selectinload)
    enabled_features: List[FeatureFlagEnum] = Field(
        default_factory=list,
        description="List of enabled feature flags for this organization",
    )

    # Billing information with current period (optional for OSS compatibility)
    billing: Optional[OrganizationBillingSchema] = Field(
        None,
        description="Complete billing information including current period",
    )

    @model_validator(mode="before")
    @classmethod
    def extract_enabled_features(cls, data: Any) -> Any:
        """Extract enabled_features from feature_flags relationship."""
        if isinstance(data, dict):
            return data

        # Handle SQLAlchemy model
        if hasattr(data, "__dict__"):
            # Extract feature flags
            if "feature_flags" in data.__dict__:
                enabled = [
                    FeatureFlagEnum(ff.flag) for ff in data.__dict__["feature_flags"] if ff.enabled
                ]
                data.enabled_features = enabled

            # Note: billing relationship and current_period will be loaded by CRUD layer

        return data


class OrganizationWithRole(BaseModel):
    """Organization schema with user's role information."""

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    modified_at: datetime
    role: str  # owner, admin, member
    is_primary: bool
    auth0_org_id: Optional[str] = None
    org_metadata: Optional[Dict[str, Any]] = None

    # Feature flags
    enabled_features: List[FeatureFlagEnum] = Field(
        default_factory=list,
        description="List of enabled feature flags for this organization",
    )

    # Billing information (same as Organization schema)
    billing: Optional[OrganizationBillingSchema] = Field(
        None,
        description="Complete billing information including current period",
    )

    @model_validator(mode="before")
    @classmethod
    def extract_enabled_features(cls, data: Any) -> Any:
        """Extract enabled_features from feature_flags relationship."""
        if isinstance(data, dict):
            # If it's already a dict with enabled_features, return as is
            return data

        # Handle SQLAlchemy model or other object
        if hasattr(data, "__dict__"):
            # Extract feature flags
            if "feature_flags" in data.__dict__ and not hasattr(data, "enabled_features"):
                enabled = [
                    FeatureFlagEnum(ff.flag) for ff in data.__dict__["feature_flags"] if ff.enabled
                ]
                data.enabled_features = enabled

        return data
