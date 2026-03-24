"""Domain exceptions for the Temporal module."""

from airweave.core.exceptions import AirweaveException, InvalidInputError


class OrphanedSyncError(AirweaveException):
    """Raised when a sync's source connection no longer exists.

    Activities raise this; workflows catch it (via Temporal's ApplicationError
    serialization) to trigger self-destruct cleanup.
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
