"""Source connection schemas.

A source connection is an authenticated and configured link to a data source that
automatically syncs data into your collection, enabling unified search across multiple systems.
"""

import re
from datetime import datetime
from typing import Any, Dict, Literal, Optional, Tuple, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from airweave.core.shared_models import SourceConnectionStatus, SyncJobStatus
from airweave.platform.configs._base import ConfigValues


class SourceConnectionBase(BaseModel):
    """Base schema for source connections with common fields."""

    name: str = Field(
        ...,
        description=(
            "Human-readable display name for the source connection. This helps you identify "
            "the connection in the UI and should clearly describe what data it connects to "
            "(e.g., 'Production Stripe Account', 'Customer Support Database')."
        ),
        min_length=1,
        max_length=64,
    )
    description: Optional[str] = Field(
        None,
        description=(
            "Optional additional context about the data this connection provides. Use this to "
            "document the purpose, data types, or any special considerations for this connection."
        ),
        max_length=255,
    )
    config_fields: Optional[ConfigValues] = Field(
        None,
        description=(
            "Source-specific configuration options that control data retrieval behavior. "
            "These vary by source type and control how data is retrieved (e.g., database "
            "queries, API filters, file paths). Check the documentation of a specific source "
            "(for example [Github](https://docs.airweave.ai/docs/connectors/github)) to see "
            "what is required."
        ),
        examples=[],
    )
    short_name: str = Field(
        ...,
        description=(
            "Technical identifier of the source type (e.g., 'github', 'stripe', "
            "'postgresql', 'slack'). This determines which connector Airweave uses to sync data."
        ),
        examples=["stripe", "postgresql", "slack"],
    )
    white_label_id: Optional[UUID] = Field(
        None,
        description=(
            "Optional identifier for white label OAuth integrations that use your own "
            "branding and credentials. Only applicable for sources that support OAuth "
            "authentication."
        ),
    )
    auth_provider: Optional[str] = Field(
        None,
        description=(
            "Readable ID of the auth provider used to create this connection. "
            "Present only if the connection was created through an auth provider."
        ),
    )
    auth_provider_config: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Configuration used with the auth provider to create this connection. "
            "Present only if the connection was created through an auth provider."
        ),
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class SourceConnectionCreateBase(BaseModel):
    """Base schema for creating source connections without white label fields."""

    name: str = Field(
        ...,
        description=(
            "Human-readable name for the source connection. This helps you identify the "
            "connection in the UI and should clearly describe what data it connects to."
        ),
        min_length=4,
        max_length=42,
        examples=["Production Stripe Account", "Main PostgreSQL DB", "Support Tickets API"],
    )
    description: Optional[str] = Field(
        None,
        description=(
            "Optional detailed description of what this source connection provides. Use this to "
            "document the purpose, data types, or any special considerations for this connection."
        ),
        examples=[
            "Production Stripe account for payment and subscription data",
            "Customer support tickets from Zendesk",
        ],
    )
    config_fields: Optional[ConfigValues] = Field(
        None,
        description=(
            "Source-specific configuration parameters required for data extraction. "
            "These vary by source type and control how data is retrieved (e.g., database "
            "queries, API filters, file paths). Check the documentation of a specific source "
            "(for example [Github](https://docs.airweave.ai/docs/connectors/github)) to see "
            "what is required."
        ),
    )
    short_name: str = Field(
        ...,
        description=(
            "Technical identifier of the source type that determines which connector to use for "
            "data synchronization."
        ),
        examples=["stripe", "postgresql", "slack", "notion"],
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True

    def map_to_core_and_auxiliary_attributes(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Map the source connection create schema to core and auxiliary attributes.

        This separates the attributes in the schema into two groups:
        1. Core attributes: These are used to create the SourceConnection model directly
        2. Auxiliary attributes: These are used in the creation process but aren't part of the model

        Returns:
            A tuple containing (core_attributes, auxiliary_attributes)
        """
        data = self.model_dump(exclude_unset=True)

        # Handle auth provider config conversion (but keep auth_provider as-is for service logic)
        if "auth_provider_config" in data:
            # Convert ConfigValues to dict if needed
            config = data["auth_provider_config"]
            if hasattr(config, "model_dump"):
                data["auth_provider_config"] = config.model_dump()

        # Auxiliary attributes used in the creation process but not directly in the model
        auxiliary_attrs = {
            "auth_fields": data.pop("auth_fields", None),
            "credential_id": data.pop("credential_id", None),
            "cron_schedule": data.pop("cron_schedule", None),
            "sync_immediately": data.pop("sync_immediately", True),
        }

        # Everything else is a core attribute for the SourceConnection model
        core_attrs = data

        return core_attrs, auxiliary_attrs


class SourceConnectionCreate(SourceConnectionCreateBase):
    """Schema for creating a source connection through the public API."""

    collection: Optional[str] = Field(
        None,
        description=(
            "Readable ID of the collection where synced data will be stored. If not provided, "
            "a new collection will be automatically created."
        ),
    )
    cron_schedule: Optional[str] = Field(
        None,
        description=(
            "Cron expression for automatic data synchronization schedule. If not provided, "
            "data will only sync when manually triggered. Use standard cron format: "
            "minute hour day month weekday."
        ),
    )
    auth_fields: Optional[ConfigValues] = Field(
        None,
        description=(
            "Authentication credentials required to access the data source. The required fields "
            "vary by source type. Check the documentation of a specific source (for example "
            "[Github](https://docs.airweave.ai/docs/connectors/github)) to see what is required."
        ),
    )
    auth_provider: Optional[str] = Field(
        None,
        description=(
            "Unique readable ID of a connected auth provider to use for authentication instead of "
            "providing auth_fields directly. When specified, credentials for the source will be "
            "obtained and refreshed automatically by Airweave interaction with the auth provider. "
            "To see which auth providers are supported and learn more about how to use them, "
            "check [this page](https://docs.airweave.ai/docs/auth-providers)."
        ),
        examples=["composio"],
    )
    auth_provider_config: Optional[ConfigValues] = Field(
        None,
        description=(
            "Configuration for the auth provider when using auth_provider field. "
            "Required fields vary by auth provider. For Composio, use auth_config_id and "
            " account_id to specify which integration and account from Composio you want "
            "to use to connect to the source."
        ),
    )
    sync_immediately: bool = Field(
        True,
        description=(
            "Whether to start an initial data synchronization immediately after "
            "creating the connection."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "GitHub - Airweave Repository",
                    "description": "Sync code and documentation from our main repository",
                    "short_name": "github",
                    "collection": "engineering-docs",
                    "auth_fields": {
                        "personal_access_token": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        "repo_name": "airweave-ai/airweave",
                    },
                    "config_fields": {"branch": "main"},
                    "cron_schedule": "0 */6 * * *",
                    "sync_immediately": True,
                },
            ]
        }
    )

    @field_validator("cron_schedule")
    def validate_cron_schedule(cls, v: str) -> str:
        """Validate cron schedule format using standard cron syntax."""
        if v is None:
            return None
        cron_pattern = r"^(\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-6]|SUN|MON|TUE|WED|THU|FRI|SAT|[0-6]-[0-6]|[0-6]/[0-6]|[0-6],[0-6]|\*\/[0-6])$"  # noqa: E501
        if not re.match(cron_pattern, v):
            raise ValueError(
                "Invalid cron schedule format. Use standard cron syntax: "
                "minute hour day month weekday"
            )
        return v


class SourceConnectionCreateWithWhiteLabel(SourceConnectionCreateBase):
    """Schema for creating a source connection through white label OAuth integrations."""

    collection: Optional[str] = Field(
        None,
        description=(
            "Readable ID of the collection where synced data will be stored. If not provided, "
            "a new collection will be automatically created."
        ),
        examples=["finance-data-ab123", "customer-support-xy789"],
    )
    cron_schedule: Optional[str] = Field(
        None,
        description=(
            "Cron expression for automatic data synchronization schedule. Uses standard cron "
            "format: minute hour day month weekday."
        ),
        examples=["0 */6 * * *", "0 9 * * 1-5"],
    )
    auth_fields: Optional[ConfigValues] = Field(
        None,
        description=(
            "Authentication credentials for the data source. For white label OAuth flows, these "
            "are typically obtained automatically during the OAuth consent process."
        ),
    )
    credential_id: Optional[UUID] = Field(
        None,
        description=(
            "ID of an existing integration credential to use instead of creating a new one. "
            "Useful when credentials have already been established through OAuth flows."
        ),
    )
    sync_immediately: bool = Field(
        True,
        description=(
            "Whether to start an initial data synchronization immediately after creating the "
            "connection."
        ),
    )
    white_label_id: Optional[UUID] = Field(
        None,
        description=(
            "ID of the white label integration configuration. This is automatically set by the "
            "white label OAuth endpoint and links the connection to your custom OAuth application."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Company Slack Workspace",
                    "description": "Main Slack workspace for team communications",
                    "short_name": "slack",
                    "collection": "team-communications",
                    "cron_schedule": "0 */2 * * *",
                    "sync_immediately": True,
                    "white_label_id": "123e4567-e89b-12d3-a456-426614174000",
                }
            ]
        }
    )

    @field_validator("cron_schedule")
    def validate_cron_schedule(cls, v: str) -> str:
        """Validate cron schedule format using standard cron syntax."""
        if v is None:
            return None
        cron_pattern = r"^(\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-6]|SUN|MON|TUE|WED|THU|FRI|SAT|[0-6]-[0-6]|[0-6]/[0-6]|[0-6],[0-6]|\*\/[0-6])$"  # noqa: E501
        if not re.match(cron_pattern, v):
            raise ValueError(
                "Invalid cron schedule format. Use standard cron syntax: "
                "minute hour day month weekday"
            )
        return v


class SourceConnectionCreateWithCredential(SourceConnectionCreateBase):
    """Schema for creating a source connection with pre-existing credentials (internal use)."""

    collection: Optional[str] = Field(
        None,
        description="Readable ID of the collection where synced data will be stored.",
    )
    cron_schedule: Optional[str] = Field(
        None,
        description="Cron expression for automatic data synchronization schedule.",
    )
    credential_id: UUID = Field(
        ...,
        description=(
            "ID of the existing integration credential to use for authentication. "
            "This credential must already exist and be associated with the same source type."
        ),
    )
    config_fields: Optional[ConfigValues] = Field(
        None,
        description=(
            "Source-specific configuration parameters required for data extraction. "
            "These vary by source type and control how data is retrieved (e.g., database "
            "queries, API filters, file paths). Check the documentation of a specific source "
            "(for example [Github](https://docs.airweave.ai/docs/connectors/github)) to see "
            "what is required."
        ),
    )
    sync_immediately: bool = Field(
        True,
        description=(
            "Whether to start an initial data synchronization immediately after creating "
            "the connection."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "OAuth Stripe Connection",
                    "description": "Stripe connection created through OAuth flow",
                    "short_name": "stripe",
                    "collection": "finance-data",
                    "credential_id": "123e4567-e89b-12d3-a456-426614174000",
                    "config_fields": {"webhook_url": "https://my-app.com/webhooks"},
                    "cron_schedule": "0 0,6,12,18 * * *",
                    "sync_immediately": True,
                }
            ]
        }
    )

    @field_validator("cron_schedule")
    def validate_cron_schedule(cls, v: str) -> str:
        """Validate cron schedule format using standard cron syntax."""
        if v is None:
            return None
        cron_pattern = r"^(\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-6]|SUN|MON|TUE|WED|THU|FRI|SAT|[0-6]-[0-6]|[0-6]/[0-6]|[0-6],[0-6]|\*\/[0-6])$"  # noqa: E501
        if not re.match(cron_pattern, v):
            raise ValueError(
                "Invalid cron schedule format. Use standard cron syntax: "
                "minute hour day month weekday"
            )
        return v

    def map_to_core_and_auxiliary_attributes(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Map the source connection create schema to core and auxiliary attributes.

        For credential-based creation, the credential_id is an auxiliary attribute.
        """
        data = self.model_dump(exclude_unset=True)

        # Auxiliary attributes used in the creation process but not directly in the model
        auxiliary_attrs = {
            "auth_fields": None,  # No auth_fields for credential-based creation
            "credential_id": data.pop("credential_id"),
            "cron_schedule": data.pop("cron_schedule", None),
            "sync_immediately": data.pop("sync_immediately", True),
        }

        # Everything else is a core attribute for the SourceConnection model
        core_attrs = data

        return core_attrs, auxiliary_attrs


class SourceConnectionUpdate(BaseModel):
    """Schema for updating an existing source connection."""

    name: Optional[str] = Field(
        None,
        description="Updated name for the source connection. Must be between 4 and 42 characters.",
        min_length=4,
        max_length=42,
        examples=["Updated Stripe Connection", "Main DB - Updated"],
    )
    description: Optional[str] = Field(
        None,
        description="Updated description of what this source connection provides.",
        examples=["Updated: Now includes subscription events and customer data"],
    )
    auth_fields: Optional[Union[ConfigValues, str]] = Field(
        None,
        description=(
            "Updated authentication credentials for the data source. "
            "Provide new credentials to refresh or update authentication."
        ),
    )
    config_fields: Optional[ConfigValues] = Field(
        None,
        description=(
            "Source-specific configuration parameters required for data extraction. "
            "These vary by source type and control how data is retrieved (e.g., database "
            "queries, API filters, file paths). Check the documentation of a specific source "
            "(for example [Github](https://docs.airweave.ai/docs/connectors/github)) to see "
            "what is required."
        ),
    )
    cron_schedule: Optional[str] = Field(
        None,
        description=(
            "Updated cron expression for automatic synchronization schedule. "
            "Set to null to disable automatic syncing."
        ),
        examples=["0 */4 * * *", "0 9,17 * * 1-5"],
    )
    connection_id: Optional[UUID] = Field(
        None,
        description=(
            "Internal connection identifier. This is typically managed automatically "
            "and should not be modified manually."
        ),
    )
    white_label_id: Optional[UUID] = Field(
        None,
        description=(
            "ID of the white label integration. Used for custom OAuth integrations "
            "with your own branding."
        ),
    )
    auth_provider: Optional[str] = Field(
        None,
        description=(
            "Updated auth provider readable ID. "
            "Only relevant if the connection uses an auth provider."
        ),
    )
    auth_provider_config: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Updated configuration for the auth provider. "
            "Only relevant if the connection uses an auth provider."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "GitHub - Updated Engineering Documentation",
                    "description": (
                        "Updated: Now includes API documentation and code examples "
                        "from multiple repositories"
                    ),
                    "auth_fields": {
                        "personal_access_token": "ghp_yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
                        "repo_name": "airweave-ai/engineering-docs",
                    },
                    "config_fields": {"branch": "develop"},
                    "cron_schedule": "0 */4 * * *",
                }
            ]
        }
    )


class SourceConnectionInDBBase(SourceConnectionBase):
    """Base schema for source connections stored in the database with system fields."""

    id: UUID = Field(
        ...,
        description=(
            "Unique system identifier for this source connection. This UUID is generated "
            "automatically and used for API operations."
        ),
    )
    sync_id: Optional[UUID] = Field(
        None,
        description=(
            "Internal identifier for the sync configuration associated with this source "
            "connection. Managed automatically by the system."
        ),
    )
    organization_id: UUID = Field(
        ...,
        description=(
            "Identifier of the organization that owns this source connection. "
            "Source connections are isolated per organization."
        ),
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the source connection was created (ISO 8601 format).",
    )
    modified_at: datetime = Field(
        ...,
        description="Timestamp when the source connection was last modified (ISO 8601 format).",
    )
    connection_id: Optional[UUID] = Field(
        None,
        description=(
            "Internal identifier for the underlying connection object that manages "
            "authentication and configuration."
        ),
    )
    collection: str = Field(
        ...,
        description=(
            "Readable ID of the collection where this source connection syncs its data. "
            "This creates the link between your data source and searchable content."
        ),
        examples=["finance-data-ab123", "customer-support-xy789"],
    )
    white_label_id: Optional[UUID] = Field(
        None,
        description=(
            "Identifier for custom OAuth integrations. Only present for connections "
            "created through white label OAuth flows."
        ),
    )
    created_by_email: Optional[EmailStr] = Field(
        None,
        description="Email address of the user who created this source connection.",
    )
    modified_by_email: Optional[EmailStr] = Field(
        None,
        description="Email address of the user who last modified this source connection.",
    )

    @model_validator(mode="before")
    @classmethod
    def map_collection_field(cls, data: Any) -> Any:
        """Map readable_collection_id to collection before validation."""
        if isinstance(data, dict):
            # If readable_collection_id exists and collection doesn't, map it
            if "readable_collection_id" in data and "collection" not in data:
                data["collection"] = data["readable_collection_id"]
        elif hasattr(data, "readable_collection_id"):
            # If it's an ORM object, we need to convert to dict first
            # Extract all attributes we need
            data_dict = {}
            for field in cls.model_fields:
                if hasattr(data, field):
                    data_dict[field] = getattr(data, field)

            data_dict["collection"] = data.readable_collection_id

            return data_dict
        return data

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class SourceConnection(SourceConnectionInDBBase):
    """Complete source connection representation returned by the API."""

    auth_fields: Optional[Union[ConfigValues, str]] = Field(
        None,
        description=(
            "Authentication credentials for the data source. "
            "Returns '********' by default for security."
        ),
    )
    status: Optional[SourceConnectionStatus] = Field(
        None,
        description="Current operational status of the source connection:<br/>"
        "• **active**: Connection is healthy and ready for data synchronization<br/>"
        "• **in_progress**: Currently syncing data from the source<br/>"
        "• **failing**: Recent sync attempts have failed and require attention",
    )
    latest_sync_job_status: Optional[SyncJobStatus] = Field(
        None,
        description="Status of the most recent data synchronization job:<br/>"
        "• **completed**: Last sync finished successfully<br/>"
        "• **failed**: Last sync encountered errors<br/>"
        "• **in_progress**: Currently running a sync job<br/>"
        "• **pending**: Sync job is queued and waiting to start",
    )
    latest_sync_job_id: Optional[UUID] = Field(
        None,
        description=(
            "Unique identifier of the most recent sync job. Use this to track sync progress "
            "or retrieve detailed job information."
        ),
    )
    latest_sync_job_started_at: Optional[datetime] = Field(
        None,
        description="Timestamp when the most recent sync job started (ISO 8601 format).",
    )
    latest_sync_job_completed_at: Optional[datetime] = Field(
        None,
        description=(
            "Timestamp when the most recent sync job completed (ISO 8601 format). "
            "Null if the job is still running or failed."
        ),
    )
    latest_sync_job_error: Optional[str] = Field(
        None,
        description=(
            "Error message from the most recent sync job if it failed. "
            "Use this to diagnose and resolve sync issues."
        ),
    )
    cron_schedule: Optional[str] = Field(
        None,
        description=(
            "Cron expression defining when automatic data synchronization occurs. "
            "Null if automatic syncing is disabled and syncs must be triggered manually."
        ),
        examples=["0 */6 * * *", "0 9,17 * * 1-5"],
    )
    next_scheduled_run: Optional[datetime] = Field(
        None,
        description=(
            "Timestamp when the next automatic sync is scheduled to run (ISO 8601 format). "
            "Null if no automatic schedule is configured."
        ),
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "GitHub - Engineering Documentation",
                    "description": (
                        "Sync technical documentation and code from our engineering repos"
                    ),
                    "short_name": "github",
                    "collection": "engineering-docs-ab123",
                    "status": "active",
                    "sync_id": "123e4567-e89b-12d3-a456-426614174000",
                    "organization_id": "org12345-6789-abcd-ef01-234567890abc",
                    "connection_id": "conn9876-5432-10fe-dcba-098765432100",
                    "white_label_id": None,
                    "created_at": "2024-01-15T09:30:00Z",
                    "modified_at": "2024-01-15T14:22:15Z",
                    "created_by_email": "engineering@company.com",
                    "modified_by_email": "engineering@company.com",
                    "auth_fields": {
                        "personal_access_token": "********",
                        "repo_name": "airweave-ai/docs",
                    },
                    "config_fields": {"branch": "main"},
                    "latest_sync_job_status": "completed",
                    "latest_sync_job_id": "987fcdeb-51a2-43d7-8f3e-1234567890ab",
                    "latest_sync_job_started_at": "2024-01-15T14:00:00Z",
                    "latest_sync_job_completed_at": "2024-01-15T14:05:22Z",
                    "latest_sync_job_error": None,
                    "cron_schedule": "0 */6 * * *",
                    "next_scheduled_run": "2024-01-16T02:00:00Z",
                }
            ]
        },
    )

    @classmethod
    def from_orm_with_collection_mapping(cls, obj):
        """Create a SourceConnection from a source_connection ORM model."""
        # Convert to dict and filter out SQLAlchemy internal attributes
        obj_dict = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}

        # Map the readable_collection_id to collection if needed
        if hasattr(obj, "readable_collection_id"):
            obj_dict["collection"] = obj.readable_collection_id

        # Map the readable_auth_provider_id to auth_provider if needed
        if hasattr(obj, "readable_auth_provider_id"):
            obj_dict["auth_provider"] = obj.readable_auth_provider_id

        return cls.model_validate(obj_dict)


class SourceConnectionCreateContinuous(SourceConnectionCreateBase):
    """Schema for creating a continuously syncing source connection (BETA).

    This endpoint creates a source connection that stays continuously in sync with your
    data source. Your data will be automatically synchronized every minute, ensuring it's
    always up-to-date without any manual intervention or sync management.
    """

    collection: Optional[str] = Field(
        None,
        description=(
            "Readable ID of the collection where synced data will be stored. If not provided, "
            "a new collection will be automatically created."
        ),
    )
    auth_fields: Optional[ConfigValues] = Field(
        None,
        description=(
            "Authentication credentials required to access the data source. The required fields "
            "vary by source type. Check the documentation of a specific source (for example "
            "[Github](https://docs.airweave.ai/docs/connectors/github)) to see what is required."
        ),
    )
    auth_provider: Optional[str] = Field(
        None,
        description=(
            "Unique readable ID of a connected auth provider to use for authentication instead of "
            "providing auth_fields directly."
        ),
        examples=["composio"],
    )
    auth_provider_config: Optional[ConfigValues] = Field(
        None,
        description=("Configuration for the auth provider when using auth_provider field."),
    )
    cursor_field: Optional[str] = Field(
        None,
        description=(
            "Specify which field in the entity should be used as the cursor for incremental syncs. "
            "This field must contain a timestamp or incrementing value that indicates when records "
            "were last modified. Required for sources without predefined entities "
            "(e.g., databases). "
            "If not specified, the source's default cursor field will be used if available."
        ),
        examples=["updated_at", "modified_timestamp", "last_modified", "created_at"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "GitHub - Live Repository Mirror",
                    "description": "Continuously sync our GitHub repository",
                    "short_name": "github",
                    "collection": "engineering-docs",
                    "auth_fields": {
                        "personal_access_token": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        "repo_name": "airweave-ai/airweave",
                    },
                    "config_fields": {"branch": "main"},
                },
                {
                    "name": "Database - Live Sync",
                    "description": "Keep database records continuously synchronized",
                    "short_name": "postgresql",
                    "collection": "customer-data",
                    "auth_fields": {
                        "host": "localhost",
                        "port": 5432,
                        "database": "myapp",
                        "user": "postgres",
                        "password": "secret",
                        "schema": "public",
                        "tables": "users,orders",
                    },
                    "cursor_field": "updated_at",
                },
            ]
        }
    )

    def map_to_core_and_auxiliary_attributes(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Map the source connection create schema to core and auxiliary attributes."""
        data = self.model_dump(exclude_unset=True)

        # Handle auth provider config conversion
        if "auth_provider_config" in data:
            config = data["auth_provider_config"]
            if hasattr(config, "model_dump"):
                data["auth_provider_config"] = config.model_dump()

        # Extract cursor_field - DON'T store in config_fields
        cursor_field = data.pop("cursor_field", None)

        # Auxiliary attributes for the creation process
        auxiliary_attrs = {
            "auth_fields": data.pop("auth_fields", None),
            "credential_id": data.pop("credential_id", None),
            "cron_schedule": None,  # No regular cron schedule
            "sync_immediately": True,  # Always sync immediately
            "minute_level_cron": "*/1 * * * *",  # Default to every minute
            "auto_start_schedule": True,  # Always auto-start
            "cursor_field": cursor_field,  # Pass cursor field separately
        }

        # Core attributes for the SourceConnection model
        core_attrs = data

        return core_attrs, auxiliary_attrs


class SourceConnectionContinuousResponse(SourceConnection):
    """Response schema for continuous source connection creation."""

    minute_level_schedule: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Information about the created minute-level schedule including schedule ID, "
            "cron expression, and current status."
        ),
        examples=[
            {
                "schedule_id": "sync_550e8400-e29b-41d4_schedule",
                "cron_expression": "*/5 * * * *",
                "status": "active",
                "next_run": "2024-01-15T14:05:00Z",
            }
        ],
    )


class SourceConnectionListItem(BaseModel):
    """Simplified source connection representation for list operations."""

    id: UUID = Field(
        ...,
        description="Unique identifier for the source connection.",
    )
    name: str = Field(
        ...,
        description="Human-readable name of the source connection.",
    )
    description: Optional[str] = Field(
        None,
        description="Brief description of what data this connection provides.",
    )
    short_name: str = Field(
        ...,
        description="Technical identifier of the source type (e.g., 'stripe', 'postgresql').",
    )
    status: SourceConnectionStatus = Field(
        ...,
        description="Current operational status: active, in_progress, or failing.",
    )
    created_at: datetime = Field(
        ...,
        description="When the source connection was created (ISO 8601 format).",
    )
    modified_at: datetime = Field(
        ...,
        description="When the source connection was last modified (ISO 8601 format).",
    )
    sync_id: UUID = Field(
        ...,
        description="Internal identifier for the sync configuration.",
    )
    collection: str = Field(
        ...,
        description="Readable ID of the collection where this connection syncs data.",
        examples=["finance-data-ab123", "customer-support-xy789"],
    )
    white_label_id: Optional[UUID] = Field(
        None,
        description="Identifier for custom OAuth integrations, if applicable.",
    )

    @model_validator(mode="after")
    def map_collection_readable_id(self) -> "SourceConnectionListItem":
        """Map collection_readable_id to collection if present."""
        # This is handled in the before mode validator below
        return self

    @model_validator(mode="before")
    @classmethod
    def map_collection_field(cls, data: Any) -> Any:
        """Map collection_readable_id to collection before validation."""
        if isinstance(data, dict):
            # If collection_readable_id exists and collection doesn't, map it
            if "collection_readable_id" in data and "collection" not in data:
                data["collection"] = data["collection_readable_id"]
        elif hasattr(data, "readable_collection_id"):
            # If it's an ORM object, we need to convert to dict first
            # Extract all attributes we need
            data_dict = {}
            for field in cls.model_fields:
                if hasattr(data, field):
                    data_dict[field] = getattr(data, field)

            data_dict["collection"] = data.readable_collection_id

            return data_dict
        return data

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "GitHub - Engineering Documentation",
                    "description": (
                        "Sync technical documentation and code from our engineering repos"
                    ),
                    "short_name": "github",
                    "status": "active",
                    "created_at": "2024-01-15T09:30:00Z",
                    "modified_at": "2024-01-15T14:22:15Z",
                    "sync_id": "123e4567-e89b-12d3-a456-426614174000",
                    "collection": "engineering-docs-ab123",
                    "white_label_id": None,
                }
            ]
        },
    )


class SourceConnectionInitiate(SourceConnectionCreate):
    """Unified initiation schema.

    Accepts all fields of SourceConnectionCreate, plus optional overrides that define
    the auth mode.
      - No overrides => platform-managed OAuth (if source is OAuth)
      - client_id + client_secret => BYOC
      - access_token (+ refresh_token) => token injection (immediate)
      - redirect_url => where to redirect the user AFTER completion (final landing)
    """

    client_id: Optional[str] = Field(None, description="Override OAuth client ID (BYOC).")
    client_secret: Optional[str] = Field(None, description="Override OAuth client secret (BYOC).")
    access_token: Optional[str] = Field(
        None,
        description=(
            "Token injection: supply an access token to create immediately without OAuth redirect."
        ),
    )
    refresh_token: Optional[str] = Field(
        None, description="Optional refresh token for token injection."
    )
    redirect_url: Optional[str] = Field(
        None, description="Final landing URL after the server completes the OAuth exchange."
    )


class SourceConnectionInitiateResponse(BaseModel):
    """Response for initiate endpoint.

    - If 'created': source_connection is present and authentication_url is null.
    - If 'pending': authentication_url is present (visit to authorize).
    """

    connection_init_id: Optional[UUID] = None
    authentication_url: Optional[str] = None
    status: Literal["created", "pending"]
    source_connection: Optional[SourceConnection] = None
