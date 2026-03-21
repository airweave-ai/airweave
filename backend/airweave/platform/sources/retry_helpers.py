"""Retry helpers for source connectors.

Provides reusable retry strategies that handle both API rate limits
and Airweave's internal rate limiting (via AirweaveHttpClient), as well
as the typed domain exceptions from ``domains.sources.exceptions``.
"""

import logging
from typing import Callable

import httpx
from tenacity import retry_if_exception, wait_exponential

from airweave.domains.sources.exceptions import (
    SourceRateLimitError,
    SourceServerError,
)


def should_retry_on_rate_limit(exception: BaseException) -> bool:
    """Check if exception is a retryable rate limit.

    Handles:
    - ``SourceRateLimitError`` (raised by ``http_helpers.raise_for_status``)
    - Real API 429 responses (raw ``httpx.HTTPStatusError``)
    - Airweave internal rate limits (AirweaveHttpClient → 429)
    - Zoho's non-standard 400 "too many requests" error
    """
    if isinstance(exception, SourceRateLimitError):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        if exception.response.status_code == 429:
            return True
        if exception.response.status_code == 400:
            try:
                data = exception.response.json()
                error_desc = data.get("error_description", "").lower()
                error_type = data.get("error", "").lower()
                if "too many requests" in error_desc and error_type == "access denied":
                    return True
            except Exception:
                pass
    return False


def should_retry_on_server_error(exception: BaseException) -> bool:
    """Check if exception is a retryable upstream server error (5xx).

    Handles ``SourceServerError`` and raw ``httpx.HTTPStatusError`` with 5xx.
    """
    if isinstance(exception, SourceServerError):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code >= 500
    return False


def should_retry_on_timeout(exception: BaseException) -> bool:
    """Check if exception is a timeout or connection error that should be retried."""
    return isinstance(
        exception,
        (
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.ConnectError,
        ),
    )


def should_retry_on_ntlm_auth(exception: BaseException) -> bool:
    """Check if exception is an NTLM authentication failure that should be retried.

    SharePoint 2019 with NTLM can return 401 when the connection pool
    reuses a connection whose NTLM context has expired. Retrying
    establishes a fresh NTLM handshake.

    Args:
        exception: Exception to check

    Returns:
        True if this is a 401 that should be retried with fresh NTLM auth
    """
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code == 401
    return False


def should_retry_on_ntlm_auth_or_rate_limit_or_timeout(exception: BaseException) -> bool:
    """Combined retry condition for NTLM auth failures, rate limits, and timeouts.

    Use this for SharePoint 2019 NTLM-authenticated endpoints where
    connection pool reuse can cause stale auth contexts.
    """
    return (
        should_retry_on_ntlm_auth(exception)
        or should_retry_on_rate_limit(exception)
        or should_retry_on_timeout(exception)
    )


def should_retry_on_rate_limit_or_timeout(exception: BaseException) -> bool:
    """Combined retry condition for rate limits, server errors, and timeouts.

    Use this as the default retry condition for source API calls::

        @retry(
            stop=stop_after_attempt(5),
            retry=retry_if_rate_limit_or_timeout,
            wait=wait_rate_limit_with_backoff,
            reraise=True,
        )
        async def _get_with_auth(self, url, params=None): ...
    """
    return (
        should_retry_on_rate_limit(exception)
        or should_retry_on_server_error(exception)
        or should_retry_on_timeout(exception)
    )


def wait_rate_limit_with_backoff(retry_state) -> float:
    """Wait strategy: Retry-After for rate limits, exponential backoff for transients.

    Handles both raw ``httpx.HTTPStatusError`` (429) and domain
    ``SourceRateLimitError`` / ``SourceServerError``.
    """
    exception = retry_state.outcome.exception()

    if isinstance(exception, SourceRateLimitError):
        return min(max(exception.retry_after, 1.0), 120.0)

    if isinstance(exception, SourceServerError):
        return wait_exponential(multiplier=1, min=2, max=30)(retry_state)

    if isinstance(exception, httpx.HTTPStatusError) and exception.response.status_code == 429:
        retry_after = exception.response.headers.get("Retry-After")
        if retry_after:
            try:
                wait_seconds = float(retry_after)
                wait_seconds = max(wait_seconds, 1.0)
                return min(wait_seconds, 120.0)
            except (ValueError, TypeError):
                pass
        return wait_exponential(multiplier=1, min=2, max=30)(retry_state)

    return wait_exponential(multiplier=1, min=2, max=10)(retry_state)


# Pre-built tenacity retry conditions
retry_if_rate_limit = retry_if_exception(should_retry_on_rate_limit)
retry_if_server_error = retry_if_exception(should_retry_on_server_error)
retry_if_timeout = retry_if_exception(should_retry_on_timeout)
retry_if_rate_limit_or_timeout = retry_if_exception(should_retry_on_rate_limit_or_timeout)
retry_if_ntlm_auth_or_rate_limit_or_timeout = retry_if_exception(
    should_retry_on_ntlm_auth_or_rate_limit_or_timeout
)


def log_retry_attempt(logger: logging.Logger, service_name: str = "API") -> Callable[..., None]:
    """Create a before_sleep callback that logs retry attempts.

    Args:
        logger: Logger instance to use
        service_name: Name of the service being called (for log messages)

    Returns:
        Callable that can be used as before_sleep in @retry decorator
    """

    def before_sleep(retry_state) -> None:
        exception = retry_state.outcome.exception()
        attempt = retry_state.attempt_number
        wait_time = retry_state.next_action.sleep if retry_state.next_action else 0

        # Build a descriptive error message
        if isinstance(exception, httpx.HTTPStatusError):
            error_desc = f"HTTP {exception.response.status_code}"
        elif isinstance(exception, httpx.TimeoutException):
            error_desc = f"timeout ({type(exception).__name__})"
        elif isinstance(exception, httpx.RequestError):
            error_desc = f"connection error ({type(exception).__name__})"
        else:
            error_desc = f"{type(exception).__name__}: {exception}"

        logger.warning(
            f"🔄 {service_name} request failed ({error_desc}), "
            f"retrying in {wait_time:.1f}s (attempt {attempt}/5)"
        )

    return before_sleep
