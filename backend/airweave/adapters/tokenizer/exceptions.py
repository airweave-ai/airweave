"""Tokenizer adapter exceptions."""


class TokenizerError(Exception):
    """Base exception for tokenizer adapter failures.

    Wraps tiktoken errors so callers never see library-specific exceptions.
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
