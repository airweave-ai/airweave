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


class SyncDagNotFoundException(NotFoundException):
    """Raised when a sync DAG is not found."""

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
