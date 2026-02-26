"""Auth provider schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from airweave.platform.configs._base import ConfigValues, Fields


class AuthProviderBase(BaseModel):
    """Base schema for auth providers."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable name of the auth provider (e.g., 'Google OAuth', 'GitHub')",
    )
    short_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Technical identifier used internally to reference this auth provider. "
        "Must be unique.",
    )
    class_name: str = Field(
        ...,
        description="Python class name of the auth provider implementation",
    )
    auth_config_class: str = Field(
        ...,
        description="Python class name that defines the authentication configuration fields",
    )
    config_class: str = Field(
        ...,
        description="Python class name that defines the auth provider-specific configuration",
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Detailed description explaining what this auth provider offers",
    )
    organization_id: Optional[UUID] = Field(
        None,
        description="Organization identifier for custom auth providers. System providers have "
        "this set to null.",
    )

    model_config = ConfigDict(from_attributes=True)


class AuthProviderCreate(AuthProviderBase):
    """Schema for creating an auth provider."""

    pass


class AuthProviderUpdate(BaseModel):
    """Schema for updating an auth provider."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

    model_config = ConfigDict(from_attributes=True)


class AuthProviderInDBBase(AuthProviderBase):
    """Base schema for auth provider in DB."""

    id: UUID
    created_at: datetime
    modified_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthProvider(AuthProviderInDBBase):
    """Schema for auth provider response."""

    auth_fields: Optional[Fields] = Field(
        None,
        description=(
            "Dynamically populated field definitions for authentication configuration. "
            "These describe what credentials are required to connect to this auth provider."
        ),
    )

    config_fields: Optional[Fields] = Field(
        None,
        description=(
            "Dynamically populated field definitions for auth provider-specific configuration. "
            "These describe what additional configuration is required when using this auth "
            "provider to connect to a source (e.g., auth_config_id and account_id for Composio)."
        ),
    )

    pass


# Auth Provider Connection Schemas


class AuthProviderConnectionCreate(BaseModel):
    """Schema for creating an auth provider connection with credentials."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable name for this auth provider connection",
    )
    readable_id: Optional[str] = Field(
        None,
        description=(
            "URL-safe unique identifier for the connection. Must contain only "
            "lowercase letters, numbers, and hyphens. If not provided, it will be automatically "
            "generated from the connection name with a random suffix for uniqueness "
            "(e.g., 'composio-connection-ab123')."
        ),
        pattern="^[a-z0-9]+(-[a-z0-9]+)*$",
        examples=["my-composio-connection", "oauth-github-prod"],
    )
    description: Optional[str] = Field(
        None,
        description="Optional detailed description of what this auth provider connection provides.",
    )
    short_name: str = Field(
        ...,
        description=("Technical identifier of the auth provider"),
    )
    auth_fields: Optional[ConfigValues] = Field(
        None,
        description=(
            "Authentication credentials required to access the auth provider. The required fields "
            "vary by auth provider type."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "My Composio Connection",
                "short_name": "composio",
                "description": "My Composio Connection",
                "auth_fields": {"api_key": "comp_1234567890abcdef"},
            }
        }
    )


class AuthProviderConnection(BaseModel):
    """Schema for auth provider connection response."""

    id: UUID
    name: str
    readable_id: str = Field(
        ...,
        description=(
            "URL-safe unique identifier that can be used to reference this connection "
            "when setting up source connections."
        ),
        examples=["composio-connection-ab123", "oauth-github-xy789"],
    )
    short_name: str
    description: Optional[str] = Field(None, description="Description of the connection")
    created_by_email: Optional[str] = Field(
        None, description="Email of the user who created this connection"
    )
    modified_by_email: Optional[str] = Field(
        None, description="Email of the user who last modified this connection"
    )
    created_at: datetime
    modified_at: datetime
    # Masked client_id for display purposes (e.g., "cli_abc...xyz")
    masked_client_id: Optional[str] = Field(
        None,
        description="Masked client ID for OAuth providers (first 7 and last 4 characters visible)",
    )

    model_config = ConfigDict(from_attributes=True)


class AuthProviderConnectionUpdate(BaseModel):
    """Schema for updating an auth provider connection."""

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Human-readable name for this auth provider connection",
    )
    description: Optional[str] = Field(
        None,
        description="Optional detailed description of what this auth provider connection provides.",
    )
    auth_fields: Optional[ConfigValues] = Field(
        None,
        description=(
            "Updated authentication credentials for the auth provider. The required fields "
            "vary by auth provider type. If provided, all existing credentials will be replaced."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Composio Connection",
                "description": "Updated description",
                "auth_fields": {"api_key": "comp_new_api_key_1234"},
            }
        }
    )
