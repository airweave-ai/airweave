"""Sync-specific exceptions for error handling."""

from typing import Optional

from airweave.core.exceptions import AirweaveException


class SyncError(AirweaveException):
    """Base class for all sync-related errors with classification attributes.
    
    Attributes:
        is_retryable: Whether the sync can be retried
        requires_user_action: Whether user intervention is needed
        should_deschedule: Whether this error should count toward schedule pause threshold
        error_category: Category for tracking and UI display
        original_error: The underlying exception that caused this error
    """
    
    def __init__(
        self,
        message: str,
        is_retryable: bool = True,
        requires_user_action: bool = False,
        should_deschedule: bool = False,
        error_category: str = "UNKNOWN",
        original_error: Optional[Exception] = None,
    ):
        """Initialize a sync error with classification attributes."""
        super().__init__(message)
        self.is_retryable = is_retryable
        self.requires_user_action = requires_user_action
        self.should_deschedule = should_deschedule
        self.error_category = error_category
        self.original_error = original_error
        
    def get_user_message(self) -> str:
        """Get sanitized user-friendly error message.
        
        Returns sanitized message that hides technical details like:
        - SQL queries and database internals
        - IP addresses and internal URLs
        - Stack traces and file paths
        - Connection strings and credentials
        """
        category_messages = {
            "AUTH": "Authentication failed. Please re-authenticate your connection.",
            "VALIDATION": "Connection validation failed. Please check your configuration.",
            "TRANSIENT": "Temporary error occurred. Sync will retry automatically.",
            "CONFIG": "Configuration issue detected. Please verify your settings.",
            "PERMANENT": "Sync encountered an error. Please review your connection settings.",
        }
        return category_messages.get(self.error_category, "An error occurred during sync.")


class AuthenticationSyncError(SyncError):
    """Authentication failure requiring user to re-authenticate.
    
    Examples:
    - Expired OAuth token
    - Invalid API key
    - Revoked credentials
    - HTTP 401/403 responses
    
    Behavior:
    - Pauses schedules after 1 failure (immediate)
    - Requires user action to fix
    - Shows re-authentication prompt in UI
    """
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """Initialize authentication error."""
        super().__init__(
            message=message,
            is_retryable=False,
            requires_user_action=True,
            should_deschedule=True,
            error_category="AUTH",
            original_error=original_error,
        )


class ValidationSyncError(SyncError):
    """Connection validation failure requiring user to check config.
    
    Examples:
    - Invalid connection parameters
    - Unreachable host
    - Invalid schema or database
    - Permission denied on resource
    
    Behavior:
    - Pauses schedules after 3 consecutive failures
    - Requires user action to fix
    - Shows configuration prompt in UI
    """
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """Initialize validation error."""
        super().__init__(
            message=message,
            is_retryable=False,
            requires_user_action=True,
            should_deschedule=True,
            error_category="VALIDATION",
            original_error=original_error,
        )


class ConfigurationSyncError(SyncError):
    """Configuration error indicating engineering issue in code.
    
    Examples:
    - Deleted table that code references
    - Changed API schema
    - Missing required transformer
    - Bug in source implementation
    
    Behavior:
    - Never pauses schedules (engineering must fix code)
    - Keeps retrying on schedule
    - Logged for engineering investigation
    - Not shown to users (internal issue)
    """
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """Initialize configuration error."""
        super().__init__(
            message=message,
            is_retryable=True,
            requires_user_action=False,
            should_deschedule=False,
            error_category="CONFIG",
            original_error=original_error,
        )


class TransientSyncError(SyncError):
    """Temporary infrastructure error that should auto-retry.
    
    Examples:
    - Network timeouts
    - Rate limiting
    - Database deadlocks
    - Service temporarily unavailable (503)
    - Qdrant connection failures
    - Connection pool exhausted
    
    Behavior:
    - Never counts toward pause threshold
    - Sync fails for this run
    - Automatically retries on next schedule
    - No user action needed
    """
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """Initialize transient error."""
        super().__init__(
            message=message,
            is_retryable=True,
            requires_user_action=False,
            should_deschedule=False,
            error_category="TRANSIENT",
            original_error=original_error,
        )


class PermanentSyncError(SyncError):
    """Permanent failure requiring user intervention.
    
    Examples:
    - Quota exceeded
    - Resource not found (deleted by user)
    - Unsupported operation
    - Data format incompatibility
    
    Behavior:
    - Pauses schedules after 3 consecutive failures
    - Requires user action to resolve
    - Shows error details in UI
    """
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """Initialize permanent error."""
        super().__init__(
            message=message,
            is_retryable=False,
            requires_user_action=True,
            should_deschedule=True,
            error_category="PERMANENT",
            original_error=original_error,
        )


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
