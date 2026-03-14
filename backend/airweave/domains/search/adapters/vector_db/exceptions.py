"""Vector DB adapter exceptions."""


class VectorDBError(Exception):
    """Base exception for vector DB adapter failures.

    Wraps Vespa SDK errors so callers never see pyvespa-specific exceptions.
    """

    def __init__(
        self,
        message: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        """Initialize with message and optional cause."""
        self.cause = cause
        super().__init__(message)


class FilterTranslationError(Exception):
    """Raised when filter translation to the DB query language fails."""

    pass
