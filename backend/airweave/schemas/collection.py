"""Collection schema.

A collection is a group of different data sources that you can search using a single endpoint.
"""

import random
import re
import string
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from airweave.core.shared_models import CollectionStatus
from airweave.platform.sync.config.base import SyncConfig


def generate_readable_id(name: str) -> str:
    """Generate a readable ID from a collection name.

    Converts the name to lowercase, replaces spaces with hyphens,
    removes special characters, and adds a random 6-character suffix
    to ensure uniqueness.

    Args:
        name: The collection name to convert

    Returns:
        A URL-safe readable identifier (e.g., "finance-data-ab123")
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
    readable_id = f"{readable_id}-{suffix}"

    return readable_id


class CollectionBase(BaseModel):
    """Base schema for collections with common fields."""

    name: str = Field(
        ...,
        description=(
            "Human-readable display name for the collection. This appears in the UI and should "
            "clearly describe the data contained within (e.g., 'Finance Data')."
        ),
        min_length=4,
        max_length=64,
        examples=["Finance Data", "Customer Support", "Marketing Analytics"],
    )
    readable_id: Optional[str] = Field(
        None,
        description=(
            "URL-safe unique identifier used in API endpoints. Must contain only "
            "lowercase letters, numbers, and hyphens. If not provided, it will be automatically "
            "generated from the collection name with a random suffix for uniqueness "
            "(e.g., 'finance-data-ab123')."
        ),
        pattern="^[a-z0-9]+(-[a-z0-9]+)*$",
        examples=["finance-data-ab123", "customer-support-xy789", "marketing-analytics-cd456"],
    )

    @model_validator(mode="after")
    def generate_readable_id_if_none(self) -> "CollectionBase":
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


class CollectionCreate(CollectionBase):
    """Schema for creating a new collection.

    Collections serve as logical containers for organizing related data sources.
    Once created, you can add source connections to populate the collection with data
    from various sources like databases, APIs, and file systems.

    You can optionally set a default sync configuration that will apply to all syncs
    within this collection unless overridden at the sync or job level.
    """

    sync_config: Optional[SyncConfig] = Field(
        None,
        description=(
            "Default sync configuration for all syncs in this collection. "
            "This provides collection-level defaults that can be overridden at sync or job level."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "Finance Data", "readable_id": "finance-data-reports"},
                {
                    "name": "Customer Support"
                    # readable_id will be auto-generated as "customer-support-abc123"
                },
                {
                    "name": "ARF Test Collection",
                    "sync_config": {
                        "handlers": {
                            "enable_vector_handlers": False,
                            "enable_postgres_handler": False,
                        }
                    },
                },
            ]
        }
    }


class CollectionUpdate(BaseModel):
    """Schema for updating an existing collection.

    Allows updating the collection's display name and default sync configuration.
    The readable_id is immutable to maintain stable API endpoints and references.
    """

    name: Optional[str] = Field(
        None,
        description="Updated display name for the collection. Must be between 4 and 64 characters.",
        min_length=4,
        max_length=64,
    )
    sync_config: Optional[SyncConfig] = Field(
        None,
        description=(
            "Default sync configuration for all syncs in this collection. "
            "This provides collection-level defaults that can be overridden at sync or job level."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "Updated Finance Data"},
                {
                    "name": "Marketing Analytics - Q1 2024",
                    "sync_config": {"handlers": {"enable_vector_handlers": True}},
                },
                {"name": "Customer Support Archive"},
            ]
        }
    }


class CollectionInDBBase(CollectionBase):
    """Base schema for collections stored in the database with system fields."""

    id: UUID = Field(
        ...,
        description=(
            "Unique system identifier for the collection. This UUID is generated automatically "
            "and used for internal references."
        ),
    )
    name: str = Field(
        ...,
        description="Human-readable display name for the collection.",
    )
    readable_id: str = Field(
        ...,
        description=(
            "URL-safe unique identifier used in API endpoints. This becomes non-optional "
            "once the collection is created."
        ),
    )
    vector_size: int = Field(
        ...,
        description=(
            "Vector dimensions used by this collection. Determines which embedding model "
            "is used: 3072 (text-embedding-3-large), 1536 (text-embedding-3-small), "
            "1024 (mistral-embed), or 384 (MiniLM-L6-v2)."
        ),
    )
    embedding_model_name: str = Field(
        ...,
        description=(
            "Name of the embedding model used for this collection "
            "(e.g., 'text-embedding-3-large', 'text-embedding-3-small', 'mistral-embed'). "
            "This ensures queries use the same model as the indexed data."
        ),
    )
    sync_config: Optional[SyncConfig] = Field(
        None,
        description=(
            "Default sync configuration for all syncs in this collection. "
            "Overridable at sync and job level."
        ),
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the collection was created (ISO 8601 format).",
    )
    modified_at: datetime = Field(
        ...,
        description="Timestamp when the collection was last modified (ISO 8601 format).",
    )
    organization_id: UUID = Field(
        ...,
        description=(
            "Identifier of the organization that owns this collection. Collections are "
            "isolated per organization."
        ),
    )
    created_by_email: Optional[EmailStr] = Field(
        None,
        description="Email address of the user who created this collection.",
    )
    modified_by_email: Optional[EmailStr] = Field(
        None,
        description="Email address of the user who last modified this collection.",
    )

    model_config = ConfigDict(from_attributes=True)


class Collection(CollectionInDBBase):
    """Complete collection representation returned by the API.

    This schema includes all collection metadata plus computed status information
    based on the health and state of associated source connections.
    """

    status: CollectionStatus = Field(
        CollectionStatus.NEEDS_SOURCE,
        description=(
            "Current operational status of the collection:<br/>"
            "• **NEEDS_SOURCE**: Collection has no authenticated connections, "
            "or connections exist but haven't synced yet<br/>"
            "• **ACTIVE**: At least one connection has completed a sync "
            "or is currently syncing<br/>"
            "• **ERROR**: All connections have failed their last sync"
        ),
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Finance Data",
                "readable_id": "finance-data-ab123",
                "vector_size": 3072,
                "embedding_model_name": "text-embedding-3-large",
                "sync_config": None,
                "created_at": "2024-01-15T09:30:00Z",
                "modified_at": "2024-01-15T14:22:15Z",
                "organization_id": "org12345-6789-abcd-ef01-234567890abc",
                "created_by_email": "admin@company.com",
                "modified_by_email": "finance@company.com",
                "status": "ACTIVE",
            }
        },
    }


class CollectionSearchQuery(BaseModel):
    """Schema for search query parameters within a collection.

    This schema is used internally for search operations but not exposed
    in the main API documentation as search uses query parameters instead.
    """

    query: str = Field(
        ...,
        description="The search query text to find relevant documents and data.",
    )
    source_name: Optional[str] = Field(
        None,
        description="Optional filter to search only within a specific source connection.",
    )
    limit: int = Field(
        10,
        description="Maximum number of search results to return.",
        ge=1,
        le=100,
    )
    offset: int = Field(
        0,
        description="Number of results to skip for pagination.",
        ge=0,
    )
