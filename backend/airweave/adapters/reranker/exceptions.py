"""Reranker adapter exceptions."""


class RerankerError(Exception):
    """Base exception for reranker adapter failures.

    Wraps provider SDK errors so callers never see Cohere-specific exceptions.
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
