"""Shared exceptions module."""

from typing import Optional

from pydantic import ValidationError


class AirweaveException(Exception):
    """Base exception for Airweave services."""

    pass


class PermissionException(AirweaveException):
    """Exception raised when a user does not have the necessary permissions to perform an action."""

    def __init__(
        self,
        message: Optional[str] = "User does not have the right to perform this action",
    ):
        """Create a new PermissionException instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


class NotFoundException(AirweaveException):
    """Exception raised when an object is not found."""

    def __init__(self, message: Optional[str] = "Object not found"):
        """Create a new NotFoundException instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


class ImmutableFieldError(AirweaveException):
    """Exception raised for attempts to modify immutable fields in a database model."""

    def __init__(self, field_name: str, message: str = "Cannot modify immutable field"):
        """Create a new ImmutableFieldError instance.

        Args:
        ----
            field_name (str): The name of the immutable field.
            message (str, optional): The error message. Has default message.

        """
        self.field_name = field_name
        self.message = message
        super().__init__(f"{message}: {field_name}")


class TokenRefreshError(AirweaveException):
    """Exception raised when a token refresh fails."""

    def __init__(self, message: Optional[str] = "Token refresh failed"):
        """Create a new TokenRefreshError instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


# New exceptions for minute-level scheduling
class SyncNotFoundException(NotFoundException):
    """Raised when a sync is not found."""

    pass


class CollectionNotFoundException(NotFoundException):
    """Raised when a collection is not found."""

    pass


class MinuteLevelScheduleException(AirweaveException):
    """Raised when minute-level schedule operations fail."""

    pass


class ScheduleNotFoundException(NotFoundException):
    """Raised when a schedule is not found."""

    pass


class ScheduleAlreadyExistsException(AirweaveException):
    """Raised when trying to create a schedule that already exists."""

    pass


class InvalidScheduleOperationException(AirweaveException):
    """Raised when an invalid schedule operation is attempted."""

    pass


class SyncJobNotFoundException(NotFoundException):
    """Raised when a sync job is not found."""

    pass


class ScheduleOperationException(AirweaveException):
    """Raised when schedule operations (pause, resume, delete) fail."""

    pass


class ScheduleNotExistsException(AirweaveException):
    """Raised when trying to perform operations on a schedule that doesn't exist."""

    pass


class ExternalServiceError(Exception):
    """Exception raised when an external service fails."""

    def __init__(self, service_name: str, message: Optional[str] = "External service failed"):
        """Create a new ExternalServiceError instance.

        Args:
        ----
            service_name (str): The name of the external service.
            message (str, optional): The error message. Has default message.

        """
        self.service_name = service_name
        self.message = message
        super().__init__(f"{service_name}: {message}")


class InvalidStateError(Exception):
    """Exception raised when an object is in an invalid state.

    Used when multiple services are involved and the state of one service is invalid,
    in relation to the other services.
    """

    def __init__(self, message: Optional[str] = "Object is in an invalid state"):
        """Create a new InvalidStateError instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


class RateLimitExceededException(AirweaveException):
    """Exception raised when API rate limit is exceeded."""

    def __init__(
        self,
        retry_after: float,
        limit: int,
        remaining: int,
        message: Optional[str] = None,
    ):
        """Create a new RateLimitExceededException instance.

        Args:
        ----
            retry_after (float): Seconds until rate limit resets.
            limit (int): Maximum requests allowed in the window.
            remaining (int): Requests remaining in current window.
            message (str, optional): Custom error message.

        """
        if message is None:
            message = (
                f"Rate limit exceeded. Please retry after {retry_after:.2f} seconds. "
                f"Limit: {limit} requests per second."
            )

        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining
        self.message = message
        super().__init__(self.message)


class SourceRateLimitExceededException(Exception):
    """Exception raised when source API rate limit is exceeded.

    This is an internal exception that gets converted to HTTP 429
    by AirweaveHttpClient so sources see identical behavior to
    actual API rate limits.
    """

    def __init__(self, retry_after: float, source_short_name: str):
        """Create a new SourceRateLimitExceededException instance.

        Args:
            retry_after: Seconds until rate limit resets
            source_short_name: Source identifier (e.g., "google_drive", "notion")
        """
        self.retry_after = retry_after
        self.source_short_name = source_short_name
        message = (
            f"Source rate limit exceeded for {source_short_name}. "
            f"Retry after {retry_after:.1f} seconds"
        )
        super().__init__(message)


def unpack_validation_error(exc: ValidationError) -> dict:
    """Unpack a Pydantic validation error into a dictionary.

    Args:
    ----
        exc (ValidationError): The Pydantic validation error.

    Returns:
    -------
        dict: The dictionary representation of the validation error.

    """
    error_messages = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_messages.append({field: message})

    return {"errors": error_messages}
