"""Source rate limit schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SourceRateLimitBase(BaseModel):
    """Base schema for source rate limits.

    Stores ONE limit per (organization, source). The limit applies to all
    users/connections of that source in the organization.
    """

    source_short_name: str = Field(
        ..., description="Source identifier (e.g., 'google_drive', 'notion')"
    )
    limit: int = Field(..., gt=0, description="Maximum requests allowed per window")
    window_seconds: int = Field(
        default=60, gt=0, description="Time window in seconds (60=per minute, 86400=per day, etc.)"
    )


class SourceRateLimitCreate(SourceRateLimitBase):
    """Schema for creating a new source rate limit."""

    pass


class SourceRateLimitUpdate(BaseModel):
    """Schema for updating source rate limit."""

    limit: Optional[int] = Field(None, gt=0, description="Updated request limit")
    window_seconds: Optional[int] = Field(None, gt=0, description="Updated time window in seconds")


class SourceRateLimit(SourceRateLimitBase):
    """Complete source rate limit schema."""

    id: UUID
    organization_id: UUID
    created_at: datetime
    modified_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceRateLimitUpdateRequest(BaseModel):
    """Request schema for updating rate limits via API."""

    limit: int = Field(gt=0, description="Maximum requests allowed per window")
    window_seconds: int = Field(gt=0, description="Time window in seconds")


class SourceRateLimitResponse(BaseModel):
    """Response schema with source metadata merged for UI display."""

    source_short_name: str
    rate_limit_level: Optional[str] = Field(
        None,
        description=("'org' (organization-wide), 'connection' (per-user), or None (not supported)"),
    )
    limit: Optional[int] = Field(None, description="Configured limit, None if not set")
    window_seconds: Optional[int] = Field(None, description="Configured window, None if not set")
    id: Optional[UUID] = Field(None, description="DB record ID, None if not configured")
