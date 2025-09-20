"""Clean source connection schemas with automatic auth method inference.

This module provides a clean schema hierarchy for source connections:
- Input schemas for create/update operations
- Response schemas optimized for API endpoints with computed fields
- Builder classes with type-safe construction and validation
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, computed_field, model_validator

from airweave.core.shared_models import SourceConnectionStatus, SyncJobStatus


class AuthenticationMethod(str, Enum):
    """Authentication methods for source connections."""

    DIRECT = "direct"
    OAUTH_BROWSER = "oauth_browser"
    OAUTH_TOKEN = "oauth_token"
    OAUTH_BYOC = "oauth_byoc"
    AUTH_PROVIDER = "auth_provider"


class OAuthType(str, Enum):
    """OAuth token types for sources."""

    ACCESS_ONLY = "access_only"  # Just access token, no refresh
    WITH_REFRESH = "with_refresh"  # Access + refresh token
    WITH_ROTATING_REFRESH = "with_rotating_refresh"  # Refresh token rotates on use


# ===========================
# Schedule Configuration
# ===========================


class ScheduleConfig(BaseModel):
    """Schedule configuration for syncs."""

    cron: Optional[str] = Field(None, description="Cron expression for scheduled syncs")
    continuous: bool = Field(False, description="Enable continuous sync mode")
    cursor_field: Optional[str] = Field(None, description="Field for incremental sync")


# ===========================
# Authentication Schemas - Nested structure without explicit type fields
# ===========================


class DirectAuthentication(BaseModel):
    """Direct authentication with API keys or passwords."""

    credentials: Dict[str, Any] = Field(..., description="Authentication credentials")

    @model_validator(mode="after")
    def validate_credentials(self):
        """Ensure credentials are not empty."""
        if not self.credentials:
            raise ValueError("Credentials cannot be empty")
        return self


class OAuthTokenAuthentication(BaseModel):
    """OAuth authentication with pre-obtained token."""

    access_token: str = Field(..., description="OAuth access token")
    refresh_token: Optional[str] = Field(None, description="OAuth refresh token")
    expires_at: Optional[datetime] = Field(None, description="Token expiry time")

    @model_validator(mode="after")
    def validate_token(self):
        """Validate token is not expired."""
        if self.expires_at and self.expires_at < datetime.utcnow():
            raise ValueError("Token has already expired")
        return self


class OAuthBrowserAuthentication(BaseModel):
    """OAuth authentication via browser flow."""

    redirect_uri: Optional[str] = Field(None, description="OAuth redirect URI")
    # Optional BYOC fields
    client_id: Optional[str] = Field(None, description="OAuth client ID (for custom apps)")
    client_secret: Optional[str] = Field(None, description="OAuth client secret (for custom apps)")

    @model_validator(mode="after")
    def validate_byoc_credentials(self):
        """Validate BYOC credentials are both provided or neither."""
        if bool(self.client_id) != bool(self.client_secret):
            raise ValueError("Custom OAuth requires both client_id and client_secret or neither")
        return self


class AuthProviderAuthentication(BaseModel):
    """Authentication via external provider."""

    provider_name: str = Field(..., description="Auth provider identifier")
    provider_config: Optional[Dict[str, Any]] = Field(
        None, description="Provider-specific configuration"
    )


# Authentication configuration without explicit type field
AuthenticationConfig = Union[
    DirectAuthentication,
    OAuthTokenAuthentication,
    OAuthBrowserAuthentication,
    AuthProviderAuthentication,
]


# ===========================
# Input Schema - Nested structure


class SourceConnectionCreate(BaseModel):
    """Create source connection with nested authentication."""

    name: Optional[str] = Field(
        None,
        min_length=4,
        max_length=42,
        description="Connection name (defaults to '{Source Name} Connection')",
    )
    short_name: str = Field(..., description="Source identifier (e.g., 'slack', 'github')")
    readable_collection_id: str = Field(..., description="Collection readable ID")
    description: Optional[str] = Field(None, max_length=255, description="Connection description")
    config: Optional[Dict[str, Any]] = Field(None, description="Source-specific configuration")
    schedule: Optional[ScheduleConfig] = None
    sync_immediately: bool = Field(True, description="Run initial sync after creation")
    authentication: Optional[AuthenticationConfig] = Field(
        None,
        description="Authentication config (defaults to OAuth browser flow for OAuth sources)",
    )


class SourceConnectionUpdate(BaseModel):
    """Update schema for source connections."""

    name: Optional[str] = Field(None, min_length=4, max_length=42)
    description: Optional[str] = Field(None, max_length=255)
    config: Optional[Dict[str, Any]] = Field(None, description="Source-specific configuration")
    schedule: Optional[ScheduleConfig] = None

    # Re-authentication only for direct auth
    credentials: Optional[Dict[str, Any]] = Field(
        None, description="Update credentials (direct auth only)"
    )

    @model_validator(mode="after")
    def validate_minimal_change(self):
        """Ensure at least one field is being updated."""
        if not any([self.name, self.description, self.config, self.schedule, self.credentials]):
            raise ValueError("At least one field must be provided for update")
        return self


# ===========================
# Output Schemas
# ===========================


class SyncSummary(BaseModel):
    """Sync summary for list views."""

    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    success_rate: Optional[float] = None


class SourceConnectionListItem(BaseModel):
    """Minimal source connection for list views with computed fields."""

    # Direct database fields
    id: UUID
    name: str
    short_name: str
    readable_collection_id: str
    created_at: datetime
    modified_at: datetime

    # Fields needed for computing auth_method and status
    is_authenticated: bool
    readable_auth_provider_id: Optional[str] = None
    connection_init_session_id: Optional[UUID] = None
    is_active: bool = True  # Default to active if not provided

    # Summary fields
    last_sync: Optional[SyncSummary] = None
    entity_count: int = 0
    last_job_status: Optional[SyncJobStatus] = None  # For computing status

    @computed_field  # type: ignore[misc]
    @property
    def auth_method(self) -> AuthenticationMethod:
        """Compute authentication method from database fields."""
        # Auth provider takes precedence
        if self.readable_auth_provider_id:
            return AuthenticationMethod.AUTH_PROVIDER

        # Check for pending OAuth
        if self.connection_init_session_id and not self.is_authenticated:
            return AuthenticationMethod.OAUTH_BROWSER

        # TODO: Distinguish between DIRECT, OAUTH_TOKEN, and OAUTH_BYOC
        # This would require additional fields from the database
        # For now, default to direct if authenticated
        if self.is_authenticated:
            return AuthenticationMethod.DIRECT

        # Default to OAuth browser for unauthenticated
        return AuthenticationMethod.OAUTH_BROWSER

    @computed_field  # type: ignore[misc]
    @property
    def status(self) -> SourceConnectionStatus:
        """Compute connection status from current state."""
        if not self.is_authenticated:
            return SourceConnectionStatus.PENDING_AUTH

        # Check if manually disabled
        if not self.is_active:
            return SourceConnectionStatus.INACTIVE

        # Check last job status if provided
        if self.last_job_status:
            if self.last_job_status == SyncJobStatus.RUNNING:
                return SourceConnectionStatus.SYNCING
            elif self.last_job_status == SyncJobStatus.FAILED:
                return SourceConnectionStatus.ERROR

        return SourceConnectionStatus.ACTIVE


class AuthenticationDetails(BaseModel):
    """Authentication information."""

    method: AuthenticationMethod
    authenticated: bool
    authenticated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # OAuth-specific
    auth_url: Optional[str] = Field(None, description="For pending OAuth flows")
    auth_url_expires: Optional[datetime] = None
    redirect_url: Optional[str] = None

    # Provider-specific
    provider_name: Optional[str] = None
    provider_id: Optional[str] = None


class ScheduleDetails(BaseModel):
    """Schedule information."""

    cron: Optional[str] = None
    next_run: Optional[datetime] = None
    continuous: bool = False
    cursor_field: Optional[str] = None
    cursor_value: Optional[Any] = None


class SyncJobDetails(BaseModel):
    """Sync job details."""

    id: UUID
    status: SyncJobStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    entities_processed: int = 0
    entities_inserted: int = 0
    entities_updated: int = 0
    entities_deleted: int = 0
    entities_failed: int = 0
    error: Optional[str] = None


class SyncDetails(BaseModel):
    """Sync execution details."""

    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    last_job: Optional[SyncJobDetails] = None


class EntityTypeStats(BaseModel):
    """Statistics for a specific entity type."""

    count: int
    last_updated: Optional[datetime] = None


class EntitySummary(BaseModel):
    """Entity state summary."""

    total_entities: int = 0
    by_type: Dict[str, EntityTypeStats] = Field(default_factory=dict)
    last_updated: Optional[datetime] = None


class SourceConnectionSimple(BaseModel):
    """Simple source connection details."""

    id: UUID
    name: str
    description: Optional[str]
    short_name: str
    sync_id: Optional[UUID] = None
    readable_collection_id: str
    status: SourceConnectionStatus
    created_at: datetime
    modified_at: datetime


class SourceConnection(BaseModel):
    """Complete source connection details."""

    id: UUID
    name: str
    description: Optional[str]
    short_name: str
    readable_collection_id: str
    status: SourceConnectionStatus
    created_at: datetime
    modified_at: datetime

    # Authentication
    auth: AuthenticationDetails

    # Configuration
    config: Optional[Dict[str, Any]] = None
    schedule: Optional[ScheduleDetails] = None

    # Sync information
    sync: Optional[SyncDetails] = None

    # Entity information
    entities: Optional[EntitySummary] = None


class SourceConnectionJob(BaseModel):
    """Individual sync job for a source connection."""

    id: UUID
    source_connection_id: UUID
    status: SyncJobStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Metrics
    entities_processed: int = 0
    entities_inserted: int = 0
    entities_updated: int = 0
    entities_deleted: int = 0
    entities_failed: int = 0

    # Error info
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


# ===========================
# Helper Functions (Deprecated - use computed fields in schemas instead)
# ===========================


def determine_auth_method(source_conn: Any) -> AuthenticationMethod:
    """DEPRECATED: Use SourceConnectionListItem computed field instead.

    Determine authentication method from database fields.
    """
    # Auth provider takes precedence
    if hasattr(source_conn, "readable_auth_provider_id") and source_conn.readable_auth_provider_id:
        return AuthenticationMethod.AUTH_PROVIDER

    # Check for pending OAuth
    if (
        hasattr(source_conn, "connection_init_session_id")
        and source_conn.connection_init_session_id
        and not source_conn.is_authenticated
    ):
        return AuthenticationMethod.OAUTH_BROWSER

    # Default to direct if authenticated
    if source_conn.is_authenticated:
        return AuthenticationMethod.DIRECT

    # Default to OAuth browser for unauthenticated
    return AuthenticationMethod.OAUTH_BROWSER


def compute_status(
    source_conn: Any,
    last_job_status: Optional[SyncJobStatus] = None,
) -> SourceConnectionStatus:
    """DEPRECATED: Use SourceConnectionListItem computed field instead.

    Compute connection status from current state.
    """
    if not source_conn.is_authenticated:
        return SourceConnectionStatus.PENDING_AUTH

    # Check if manually disabled
    if hasattr(source_conn, "is_active") and not source_conn.is_active:
        return SourceConnectionStatus.INACTIVE

    # Check last job status if provided
    if last_job_status:
        if last_job_status == SyncJobStatus.RUNNING:
            return SourceConnectionStatus.SYNCING
        elif last_job_status == SyncJobStatus.FAILED:
            return SourceConnectionStatus.ERROR

    return SourceConnectionStatus.ACTIVE
