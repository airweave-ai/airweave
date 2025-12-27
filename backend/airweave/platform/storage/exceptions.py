"""Storage exceptions for Airweave.

All storage-related exceptions inherit from StorageException.
"""


class StorageException(Exception):
    """Base exception for storage operations."""

    pass


class StorageConnectionError(StorageException):
    """Raised when storage connection fails."""

    pass


class StorageAuthenticationError(StorageException):
    """Raised when storage authentication fails."""

    pass


class StorageNotFoundError(StorageException):
    """Raised when a requested item is not found in storage."""

    pass


class StorageQuotaExceededError(StorageException):
    """Raised when storage quota is exceeded."""

    pass
