"""Usage schemas for tracking organization subscription limits."""

from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UsageBase(BaseModel):
    """Base schema for usage tracking."""

    organization_id: UUID = Field(
        ...,
        description="Organization this usage belongs to.",
    )
    billing_period_id: Optional[UUID] = Field(
        None,
        description="Billing period this usage belongs to.",
    )
    syncs: int = Field(
        0,
        ge=0,
        description="Number of syncs created by the organization.",
    )
    entities: int = Field(
        0,
        ge=0,
        description="Total number of entities processed across all syncs.",
    )
    queries: int = Field(
        0,
        ge=0,
        description="Number of search queries executed.",
    )
    collections: int = Field(
        0,
        ge=0,
        description="Number of collections created.",
    )
    source_connections: int = Field(
        0,
        ge=0,
        description="Number of source connections configured.",
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class UsageCreate(BaseModel):
    """Schema for creating usage records.

    Usage records track resource consumption per billing period.
    """

    organization_id: UUID = Field(..., description="Organization ID")
    billing_period_id: UUID = Field(..., description="Billing period ID")
    # All counters default to 0 in the base schema


class UsageUpdate(BaseModel):
    """Schema for updating usage counters.

    All fields are optional, allowing partial updates of specific counters.
    """

    syncs: Optional[int] = Field(
        None,
        ge=0,
        description="Updated sync count.",
    )
    entities: Optional[int] = Field(
        None,
        ge=0,
        description="Updated entity count.",
    )
    queries: Optional[int] = Field(
        None,
        ge=0,
        description="Updated query count.",
    )
    collections: Optional[int] = Field(
        None,
        ge=0,
        description="Updated collection count.",
    )
    source_connections: Optional[int] = Field(
        None,
        ge=0,
        description="Updated source connection count.",
    )


class UsageInDBBase(UsageBase):
    """Base schema for usage records stored in the database."""

    id: UUID = Field(
        ...,
        description="Unique identifier for the usage record.",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the usage record was created.",
    )
    modified_at: datetime = Field(
        ...,
        description="Timestamp when the usage record was last updated.",
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class Usage(UsageInDBBase):
    """Complete usage representation for a billing period."""

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "organization_id": "org12345-6789-abcd-ef01-234567890abc",
                    "billing_period_id": "period123-4567-89ab-cdef-0123456789ab",
                    "syncs": 5,
                    "entities": 10000,
                    "queries": 250,
                    "collections": 3,
                    "source_connections": 8,
                    "created_at": "2024-01-01T00:00:00Z",
                    "modified_at": "2024-01-15T14:22:15Z",
                }
            ]
        },
    }


class UsageLimit(BaseModel):
    """Schema for defining usage limits per subscription tier."""

    max_syncs: Optional[int] = Field(
        None,
        ge=0,
        description="Maximum number of syncs allowed. None means unlimited.",
    )
    max_entities: Optional[int] = Field(
        None,
        ge=0,
        description="Maximum number of entities allowed. None means unlimited.",
    )
    max_queries: Optional[int] = Field(
        None,
        ge=0,
        description="Maximum number of queries allowed. None means unlimited.",
    )
    max_collections: Optional[int] = Field(
        None,
        ge=0,
        description="Maximum number of collections allowed. None means unlimited.",
    )
    max_source_connections: Optional[int] = Field(
        None,
        ge=0,
        description="Maximum number of source connections allowed. None means unlimited.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "max_syncs": 10,
                    "max_entities": 50000,
                    "max_queries": 1000,
                    "max_collections": 5,
                    "max_source_connections": 20,
                },
            ]
        }
    }


class SingleActionCheckResponse(BaseModel):
    """Response schema for single action permission check."""

    allowed: bool = Field(
        ...,
        description="Whether the action is allowed for the organization",
    )

    action: str = Field(
        ...,
        description="The action type that was checked",
    )

    reason: Optional[Literal["payment_required", "usage_limit_exceeded"]] = Field(
        None,
        description="Reason why the action is not allowed (if applicable)",
    )

    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional details about why the action is not allowed",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "allowed": True,
                    "action": "queries",
                    "reason": None,
                    "details": None,
                },
            ]
        }
    }
