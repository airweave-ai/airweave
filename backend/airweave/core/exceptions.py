"""Shared exceptions module."""

from enum import Enum
from typing import Optional

from pydantic import ValidationError


class ErrorSeverity(Enum):
    """
    Error severity classification for monitoring and alerting.

    - EXPECTED: Client errors, validation failures, expected edge cases
    - OPERATIONAL: Network issues, external service failures, retryable errors
    - CRITICAL: Server bugs, data corruption, unexpected failures
    """

    EXPECTED = "expected"
    OPERATIONAL = "operational"
    CRITICAL = "critical"


class AirweaveException(Exception):
    """Base exception for Airweave services."""

    severity: ErrorSeverity = ErrorSeverity.CRITICAL


class PermissionException(AirweaveException):
    """Exception raised when a user does not have the necessary permissions to perform an action."""

    severity: ErrorSeverity = ErrorSeverity.EXPECTED

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

    severity: ErrorSeverity = ErrorSeverity.EXPECTED

    def __init__(self, message: Optional[str] = "Object not found"):
        """Create a new NotFoundException instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


class TokenRefreshError(AirweaveException):
    """Exception raised when a token refresh fails."""

    severity: ErrorSeverity = ErrorSeverity.OPERATIONAL

    def __init__(self, message: Optional[str] = "Token refresh failed"):
        """Create a new TokenRefreshError instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


class PreSyncValidationException(AirweaveException):
    """Exception raised when a pre-sync validation fails."""

    severity: ErrorSeverity = ErrorSeverity.EXPECTED

    def __init__(self, message: str, source_name: Optional[str] = None):
        """Create a new PreSyncValidationException instance.

        Args:
        ----
            message (str): The error message.
            source_name (str, optional): The name of the source.

        """
        self.message = message
        self.source_name = source_name
        super().__init__(self.message)


class UsageLimitExceededException(AirweaveException):
    """Exception raised when usage limits are exceeded."""

    severity: ErrorSeverity = ErrorSeverity.EXPECTED

    def __init__(
        self,
        action_type: Optional[str] = None,
        limit: Optional[int] = None,
        current_usage: Optional[int] = None,
        message: Optional[str] = None,
    ):
        """Create a new UsageLimitExceededException instance.

        Args:
        ----
            action_type (str, optional): The type of action that exceeded the limit.
            limit (int, optional): The limit that was exceeded.
            current_usage (int, optional): The current usage count.
            message (str, optional): Custom error message. If not provided, generates one.

        """
        if message is None:
            if action_type:
                message = f"Usage limit exceeded for {action_type}"
                if limit is not None and current_usage is not None:
                    message += f": {current_usage}/{limit}"
            else:
                message = "Usage limit exceeded"

        self.action_type = action_type
        self.limit = limit
        self.current_usage = current_usage
        self.message = message
        super().__init__(self.message)


class PaymentRequiredException(AirweaveException):
    """Exception raised when an action is blocked due to payment status."""

    severity: ErrorSeverity = ErrorSeverity.EXPECTED

    def __init__(
        self,
        action_type: Optional[str] = None,
        payment_status: Optional[str] = None,
        message: Optional[str] = None,
    ):
        """Create a new PaymentRequiredException instance.

        Args:
        ----
            action_type (str, optional): The type of action that was blocked.
            payment_status (str, optional): The current payment status.
            message (str, optional): Custom error message. If not provided, generates one.

        """
        if message is None:
            if action_type and payment_status:
                message = (
                    f"Action '{action_type}' is not allowed due to payment status: {payment_status}"
                )
            elif action_type:
                message = f"Action '{action_type}' requires an active subscription"
            else:
                message = "This action requires an active subscription"

        self.action_type = action_type
        self.payment_status = payment_status
        self.message = message
        super().__init__(self.message)


class ExternalServiceError(AirweaveException):
    """Exception raised when an external service fails."""

    severity: ErrorSeverity = ErrorSeverity.OPERATIONAL

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

    severity: ErrorSeverity = ErrorSeverity.OPERATIONAL

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


class SourceRateLimitExceededException(AirweaveException):
    """Exception raised when source API rate limit is exceeded.

    This is an internal exception that gets converted to HTTP 429
    by AirweaveHttpClient so sources see identical behavior to
    actual API rate limits.
    """

    severity: ErrorSeverity = ErrorSeverity.OPERATIONAL

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
