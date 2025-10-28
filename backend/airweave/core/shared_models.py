"""Shared models for the backend."""

from enum import Enum


class ConnectionStatus(str, Enum):
    """Connection status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class SyncJobStatus(str, Enum):
    """Sync job status enum."""

    CREATED = "created"
    PENDING = "pending"
    RUNNING = "running"  # Changed from IN_PROGRESS for consistency
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"


class IntegrationType(str, Enum):
    """Integration type enum."""

    SOURCE = "source"
    DESTINATION = "destination"
    AUTH_PROVIDER = "auth_provider"


class SyncStatus(str, Enum):
    """Sync status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class SourceConnectionStatus(str, Enum):
    """Source connection status enum - represents overall connection state."""

    ACTIVE = "active"  # Authenticated and ready to sync
    PENDING_AUTH = "pending_auth"  # Awaiting authentication (OAuth flow, etc.)
    SYNCING = "syncing"  # Currently running a sync job
    ERROR = "error"  # Last sync failed or auth error
    INACTIVE = "inactive"  # Manually disabled
    PENDING_SYNC = "pending_sync"  # Awaiting a sync job to start


class CollectionStatus(str, Enum):
    """Collection status enum."""

    ACTIVE = "ACTIVE"
    NEEDS_SOURCE = "NEEDS SOURCE"
    ERROR = "ERROR"


class ActionType(str, Enum):
    """Action type enum."""

    ENTITIES = "entities"
    QUERIES = "queries"
    SOURCE_CONNECTIONS = "source_connections"
    TEAM_MEMBERS = "team_members"


class FeatureFlag(str, Enum):
    """Available feature flags in Airweave.

    Add new flags here to enable feature gating at the organization level.
    """

    S3_DESTINATION = "s3_destination"
    PRIORITY_SUPPORT = "priority_support"


class AuthMethod(str, Enum):
    """Authentication methods used in API requests.

    Defines the valid authentication methods for API context.
    """

    AUTH0 = "auth0"  # User authentication via Auth0 JWT tokens
    API_KEY = "api_key"  # Programmatic access via API keys
    SYSTEM = "system"  # Internal system operations (local dev, migrations)
    INTERNAL_SYSTEM = "internal_system"  # Internal service-to-service calls
    STRIPE_WEBHOOK = "stripe_webhook"  # Stripe webhook handlers
    OAUTH_CALLBACK = "oauth_callback"  # OAuth callback handlers
