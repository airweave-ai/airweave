"""Domain exceptions for the Temporal module."""

from airweave.core.exceptions import AirweaveException, InvalidInputError

ORPHANED_SYNC_ERROR_TYPE = "OrphanedSyncError"
"""ApplicationError.type value used for orphaned sync detection across the
activity → workflow serialization boundary."""


class OrphanedSyncError(AirweaveException):
    """Raised when a sync's source connection no longer exists.

    Domain code raises this. The activity boundary layer converts it to an
    explicit ``ApplicationError`` with ``type=ORPHANED_SYNC_ERROR_TYPE``,
    ``non_retryable=True``, and ``category=BENIGN`` so the workflow can
    detect it via the type field without importing this class.
    """

    def __init__(self, sync_id: str, reason: str = "Source connection not found"):
        """Initialize with sync ID and optional reason."""
        self.sync_id = sync_id
        self.reason = reason
        super().__init__(f"Orphaned sync {sync_id}: {reason}")


class InvalidCronExpressionError(InvalidInputError):
    """Raised when a cron expression fails validation.

    Extends InvalidInputError so the API layer's existing exception handler
    translates this to a 422 response automatically.
    """

    def __init__(self, cron_expression: str):
        """Initialize with the invalid cron expression."""
        self.cron_expression = cron_expression
        super().__init__(f"Invalid CRON expression: {cron_expression}")
