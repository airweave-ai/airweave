"""LLM adapter exceptions.

Exception hierarchy::

    LLMError
    ├── LLMTransientError          — retryable (rate limits, timeouts, 5xx)
    ├── LLMFatalError              — not retryable (auth, bad request, model not found)
    ├── LLMProviderExhaustedError  — single provider failed after all retries
    └── LLMAllProvidersFailedError — fallback chain exhausted
"""

from __future__ import annotations


class LLMError(Exception):
    """Base exception for all LLM adapter failures.

    Attributes:
        provider: Name of the provider that failed (e.g., "AnthropicLLM").
        cause: The original exception that triggered this error.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize with message, optional provider name and cause."""
        self.provider = provider
        self.cause = cause
        super().__init__(message)


class LLMTransientError(LLMError):
    """Retryable failure: rate limits, timeouts, 5xx, network issues.

    The BaseLLM retry loop will retry these automatically. If retries
    are exhausted, it wraps the last one in LLMProviderExhaustedError.
    """


class LLMFatalError(LLMError):
    """Non-retryable failure: auth errors, invalid model, bad request.

    Raised immediately — no retries. Indicates a configuration or
    request problem that won't resolve by retrying.
    """


class LLMProviderExhaustedError(LLMError):
    """A single provider exhausted all retry attempts.

    The fallback chain catches this to try the next provider.
    """


class LLMAllProvidersFailedError(LLMError):
    """All providers in the fallback chain failed.

    This is the terminal error that surfaces to the caller (agent loop).
    Includes per-provider error details for debugging.
    """

    def __init__(self, errors: list[tuple[str, LLMError]]) -> None:
        """Initialize with per-provider error list."""
        self.provider_errors = errors
        summary = "; ".join(f"{name}: {err}" for name, err in errors)
        super().__init__(
            f"All {len(errors)} LLM providers failed. {summary}",
            provider=None,
        )
