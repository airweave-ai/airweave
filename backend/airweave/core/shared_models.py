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
    CANCELLED = "cancelled"


class IntegrationType(str, Enum):
    """Integration type enum."""

    SOURCE = "source"
    DESTINATION = "destination"
    EMBEDDING_MODEL = "embedding_model"
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
    PARTIAL_ERROR = "PARTIAL ERROR"
    NEEDS_SOURCE = "NEEDS SOURCE"
    ERROR = "ERROR"


class ActionType(str, Enum):
    """Action type enum."""

    SYNCS = "syncs"
    ENTITIES = "entities"
    QUERIES = "queries"
    COLLECTIONS = "collections"
    SOURCE_CONNECTIONS = "source_connections"
