"""Sync-specific exceptions for error handling."""


class EntityProcessingError(Exception):
    """Raised when an individual entity cannot be processed.

    This is a recoverable error - the sync continues with other entities.
    The entity is logged and counted in the "skipped" metric.

    Examples:
    - Invalid entity data format
    - Missing required entity field
    - File download failed (404)
    - Entity transformation failed

    Usage:
        raise EntityProcessingError(f"Failed to process entity {entity_id}: {reason}")
    """

    pass


class SyncFailureError(Exception):
    """Raised when a critical error occurs that should fail the entire sync.

    This is a non-recoverable error - the sync is terminated immediately.

    Examples:
    - Database connection lost
    - Destination unreachable
    - Missing required configuration
    - Critical infrastructure failure

    Usage:
        raise SyncFailureError("Database connection lost")
    """

    pass
