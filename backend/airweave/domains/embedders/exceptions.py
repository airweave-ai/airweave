"""Embedder domain exceptions.

All embedder implementations should raise these instead of letting provider-specific
exceptions (openai.*, httpx.*, mistralai.*) bubble up.  Callers can catch at the
granularity they need — e.g. ``except EmbedderProviderError`` for all transient
provider issues, or ``except EmbedderRateLimitError`` for just rate limits.
"""

from airweave.core.exceptions import AirweaveException

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class EmbedderError(AirweaveException):
    """Base exception for all embedder errors."""

    def __init__(self, message: str = "Embedder error"):
        """Initialize with message."""
        self.message = message
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# Configuration / initialisation
# ---------------------------------------------------------------------------


class EmbedderConfigError(EmbedderError):
    """Missing API key, inference URL, uninstalled package, or model load failure."""

    def __init__(self, message: str = "Embedder configuration error"):
        """Initialize with message."""
        super().__init__(message)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class EmbedderInputError(EmbedderError):
    """Empty text, text exceeding max tokens, or other input problems."""

    def __init__(self, message: str = "Invalid embedder input"):
        """Initialize with message."""
        super().__init__(message)


# ---------------------------------------------------------------------------
# Provider communication
# ---------------------------------------------------------------------------


class EmbedderProviderError(EmbedderError):
    """Wraps errors from the underlying provider SDK or HTTP call."""

    def __init__(
        self,
        message: str = "Embedder provider error",
        *,
        provider: str = "unknown",
        retryable: bool = True,
    ):
        """Initialize with message, provider name, and retryability flag."""
        self.provider = provider
        self.retryable = retryable
        super().__init__(message)


class EmbedderAuthError(EmbedderProviderError):
    """Authentication failure (invalid or expired API key)."""

    def __init__(
        self,
        message: str = "Embedder authentication failed",
        *,
        provider: str = "unknown",
    ):
        """Initialize with message and provider name."""
        super().__init__(message, provider=provider, retryable=False)


class EmbedderRateLimitError(EmbedderProviderError):
    """Provider rate limit hit (HTTP 429) or local rate-limiter timeout."""

    def __init__(
        self,
        message: str = "Embedder rate limit exceeded",
        *,
        provider: str = "unknown",
        retry_after: float | None = None,
    ):
        """Initialize with message, provider name, and optional retry-after hint."""
        self.retry_after = retry_after
        super().__init__(message, provider=provider, retryable=True)


class EmbedderTimeoutError(EmbedderProviderError):
    """Connection or request timeout."""

    def __init__(
        self,
        message: str = "Embedder request timed out",
        *,
        provider: str = "unknown",
    ):
        """Initialize with message and provider name."""
        super().__init__(message, provider=provider, retryable=True)


class EmbedderConnectionError(EmbedderProviderError):
    """Connection refused, DNS failure, or network unreachable."""

    def __init__(
        self,
        message: str = "Embedder connection failed",
        *,
        provider: str = "unknown",
    ):
        """Initialize with message and provider name."""
        super().__init__(message, provider=provider, retryable=True)


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------


class EmbedderResponseError(EmbedderError):
    """Unexpected response from the provider (missing fields, wrong count, etc.)."""

    def __init__(self, message: str = "Invalid embedder response"):
        """Initialize with message."""
        super().__init__(message)


class EmbedderDimensionError(EmbedderResponseError):
    """Returned vector dimensions don't match the expected size."""

    def __init__(
        self,
        message: str = "Embedding dimension mismatch",
        *,
        expected: int = 0,
        actual: int = 0,
    ):
        """Initialize with message and the expected/actual dimensions."""
        self.expected = expected
        self.actual = actual
        if expected and actual and message == "Embedding dimension mismatch":
            message = f"Embedding dimension mismatch: expected {expected}, got {actual}"
        super().__init__(message)
