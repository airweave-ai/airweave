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


class FileSkippedException(Exception):
    """Exception raised when a file is intentionally skipped (not an error).

    This is raised when files are skipped for valid reasons like:
    - Unsupported file extension
    - File too large
    - No download URL available

    This is NOT an error condition - it's expected behavior during normal sync operations.
    """

    def __init__(self, reason: str, filename: str):
        """Initialize file skipped exception.

        Args:
            reason: Human-readable reason why file was skipped
            filename: Name of the file that was skipped
        """
        self.reason = reason
        self.filename = filename
        super().__init__(f"File '{filename}' skipped: {reason}")
