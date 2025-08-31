"""Organization billing schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from airweave.core.config import settings


class BillingPlan(str, Enum):
    """Billing plan tiers."""

    TRIAL = "trial"
    DEVELOPER = "developer"
    STARTUP = "startup"
    ENTERPRISE = "enterprise"


class BillingStatus(str, Enum):
    """Billing subscription status."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    PAUSED = "paused"
    TRIALING = "trialing"
    TRIAL_EXPIRED = "trial_expired"
    GRACE_PERIOD = "grace_period"


class PaymentStatus(str, Enum):
    """Payment status."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PENDING = "pending"


class OrganizationBillingBase(BaseModel):
    """Organization billing base schema."""

    billing_plan: BillingPlan = Field(
        default_factory=lambda: BillingPlan(settings.DEFAULT_BILLING_PLAN), 
        description="Current billing plan"
    )
    billing_status: BillingStatus = Field(
        default=BillingStatus.ACTIVE, description="Current billing status"
    )
    billing_email: str = Field(..., description="Billing contact email")


class OrganizationBillingCreate(OrganizationBillingBase):
    """Organization billing creation schema."""

    stripe_customer_id: str = Field(..., description="Stripe customer ID")
    trial_ends_at: Optional[datetime] = Field(None, description="Trial end date")
    grace_period_ends_at: Optional[datetime] = Field(None, description="Grace period end date")


class OrganizationBillingUpdate(BaseModel):
    """Organization billing update schema."""

    billing_plan: Optional[BillingPlan] = None
    billing_status: Optional[BillingStatus] = None
    billing_email: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    payment_method_id: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    grace_period_ends_at: Optional[datetime] = None
    payment_method_added: Optional[bool] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: Optional[bool] = None
    pending_plan_change: Optional[BillingPlan] = None
    pending_plan_change_at: Optional[datetime] = None
    last_payment_status: Optional[PaymentStatus] = None
    last_payment_at: Optional[datetime] = None
    billing_metadata: Optional[Dict[str, Any]] = None


class OrganizationBillingInDBBase(OrganizationBillingBase):
    """Organization billing base schema in the database."""

    model_config = {"from_attributes": True}

    id: UUID
    organization_id: UUID
    stripe_customer_id: str
    stripe_subscription_id: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    grace_period_ends_at: Optional[datetime] = None
    payment_method_added: bool = False
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    payment_method_id: Optional[str] = None
    last_payment_status: Optional[str] = None
    last_payment_at: Optional[datetime] = None
    billing_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    modified_at: datetime


class OrganizationBilling(OrganizationBillingInDBBase):
    """Organization billing schema."""

    pass


class PlanLimits(BaseModel):
    """Plan limits configuration."""

    source_connections: int = Field(..., description="Number of allowed source connections")
    entities_per_month: int = Field(..., description="Number of entities allowed per month")
    sync_frequency_minutes: int = Field(..., description="Minimum sync frequency in minutes")
    team_members: int = Field(..., description="Number of allowed team members")


class SubscriptionInfo(BaseModel):
    """Subscription information response."""

    plan: str = Field(..., description="Current billing plan")
    status: str = Field(..., description="Subscription status")
    trial_ends_at: Optional[datetime] = Field(None, description="Trial end date")
    grace_period_ends_at: Optional[datetime] = Field(None, description="Grace period end date")
    current_period_start: Optional[datetime] = Field(
        None, description="Current billing period start"
    )
    current_period_end: Optional[datetime] = Field(None, description="Current billing period end")
    cancel_at_period_end: bool = Field(
        False, description="Whether subscription will cancel at period end"
    )
    limits: Dict[str, Any] = Field(..., description="Plan limits")
    is_oss: bool = Field(False, description="Whether using OSS version")
    has_active_subscription: bool = Field(
        False, description="Whether has active Stripe subscription"
    )
    in_trial: bool = Field(False, description="Whether currently in trial period")
    in_grace_period: bool = Field(False, description="Whether currently in grace period")
    payment_method_added: bool = Field(False, description="Whether payment method is added")
    requires_payment_method: bool = Field(
        False, description="Whether payment method is required now"
    )
    # Add pending plan change info
    pending_plan_change: Optional[str] = Field(
        None, description="Plan that will take effect at period end"
    )
    pending_plan_change_at: Optional[datetime] = Field(
        None, description="When the pending plan change takes effect"
    )


# Request/Response schemas for API endpoints
class CheckoutSessionRequest(BaseModel):
    """Request to create a checkout session."""

    plan: str = Field(..., description="Plan to subscribe to (developer, startup)")
    success_url: str = Field(..., description="URL to redirect on successful payment")
    cancel_url: str = Field(..., description="URL to redirect on cancellation")


class CheckoutSessionResponse(BaseModel):
    """Response with checkout session URL."""

    checkout_url: str = Field(..., description="Stripe checkout URL")


class CustomerPortalRequest(BaseModel):
    """Request to create customer portal session."""

    return_url: str = Field(..., description="URL to return to after portal session")


class CustomerPortalResponse(BaseModel):
    """Response with customer portal URL."""

    portal_url: str = Field(..., description="Stripe customer portal URL")


class CancelSubscriptionRequest(BaseModel):
    """Request to cancel subscription.

    Subscription will be canceled at the end of the current billing period.
    For immediate cancellation, delete the organization instead.
    """

    # No fields needed - always cancels at period end


class UpdatePlanRequest(BaseModel):
    """Request to update subscription plan."""

    plan: str = Field(..., description="New plan (developer, startup)")


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str = Field(..., description="Response message")
