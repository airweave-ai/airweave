"""Connection schemas.

This is a system table that contains the connection information for all integrations.
Not to be confused with the source connection model, which is a user-facing model that
encompasses the connection and sync information for a specific source.

"""

import random
import re
import string
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from airweave.core.shared_models import ConnectionStatus, IntegrationType


def generate_readable_id(name: str) -> str:
    """Generate a readable ID from a connection name.

    Converts the name to lowercase, replaces spaces with hyphens,
    removes special characters, and adds a random 6-character suffix
    to ensure uniqueness.

    Args:
        name: The connection name to convert

    Returns:
        A URL-safe readable identifier (e.g., "stripe-connection-ab123")
    """
    # Convert to lowercase and replace spaces with hyphens
    readable_id = name.lower().strip()

    # Replace any character that's not a letter, number, or space with nothing
    readable_id = re.sub(r"[^a-z0-9\s]", "", readable_id)
    # Replace spaces with hyphens
    readable_id = re.sub(r"\s+", "-", readable_id)
    # Ensure no consecutive hyphens
    readable_id = re.sub(r"-+", "-", readable_id)
    # Trim hyphens from start and end
    readable_id = readable_id.strip("-")

    # Add random alphanumeric suffix
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    readable_id = f"{(readable_id + '-') if readable_id else ''}{suffix}"

    return readable_id


class ConnectionBase(BaseModel):
    """Base schema for connections."""

    name: str = Field(
        ...,
        description="Human-readable display name for the connection.",
        min_length=1,
        max_length=64,
    )
    readable_id: Optional[str] = Field(
        None,
        description=(
            "URL-safe unique identifier used in API endpoints. Must contain only "
            "lowercase letters, numbers, and hyphens. If not provided, it will be automatically "
            "generated from the connection name with a random suffix for uniqueness "
            "(e.g., 'stripe-connection-ab123')."
        ),
        pattern="^[a-z0-9]+(-[a-z0-9]+)*$",
        examples=["stripe-connection-ab123", "github-connection-xy789"],
    )
    description: Optional[str] = None
    integration_type: IntegrationType
    integration_credential_id: Optional[UUID] = None
    status: ConnectionStatus
    short_name: str

    @model_validator(mode="after")
    def generate_readable_id_if_none(self) -> "ConnectionBase":
        """Generate a readable_id automatically if none is provided."""
        if self.readable_id is None and self.name:
            self.readable_id = generate_readable_id(self.name)
        return self

    @field_validator("readable_id")
    def validate_readable_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate that readable_id follows the required format."""
        if v is None:
            return None
        if not all(c.islower() or c.isdigit() or c == "-" for c in v):
            raise ValueError(
                "readable_id must contain only lowercase letters, numbers, and hyphens"
            )
        # Check that readable_id doesn't start or end with a hyphen
        if v and (v.startswith("-") or v.endswith("-")):
            raise ValueError("readable_id must not start or end with a hyphen")
        return v

    model_config = ConfigDict(from_attributes=True)


class ConnectionCreate(ConnectionBase):
    """Schema for creating a connection."""


class ConnectionUpdate(BaseModel):
    """Schema for updating a connection."""

    name: Optional[str] = Field(
        None,
        description="Updated name for the connection.",
        min_length=1,
        max_length=64,
    )
    readable_id: Optional[str] = Field(
        None,
        description=(
            "Updated readable ID for the connection. Must contain only "
            "lowercase letters, numbers, and hyphens."
        ),
        pattern="^[a-z0-9]+(-[a-z0-9]+)*$",
    )
    description: Optional[str] = None
    status: Optional[ConnectionStatus] = None


class ConnectionInDBBase(ConnectionBase):
    """Base schema for connection in DB."""

    id: UUID = Field(
        ...,
        description="Unique system identifier for the connection.",
    )
    readable_id: str = Field(
        ...,
        description=(
            "URL-safe unique identifier used in API endpoints. This becomes non-optional "
            "once the connection is created."
        ),
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the connection was created (ISO 8601 format).",
    )
    modified_at: datetime = Field(
        ...,
        description="Timestamp when the connection was last modified (ISO 8601 format).",
    )
    organization_id: Optional[UUID] = None
    created_by_email: Optional[EmailStr] = None
    modified_by_email: Optional[EmailStr] = None

    model_config = ConfigDict(from_attributes=True)


class Connection(ConnectionInDBBase):
    """Schema for connection with config fields."""
