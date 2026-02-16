"""Retry helpers for source connectors.

Provides reusable retry strategies that handle both API rate limits
and Airweave's internal rate limiting (via AirweaveHttpClient).
"""

import logging
from typing import Callable

import httpx
from tenacity import retry_if_exception, wait_exponential


def should_retry_on_rate_limit(exception: BaseException) -> bool:
    """Check if exception is a retryable rate limit (429 or Zoho's 400 rate limit).

    Handles:
    - Real API 429 responses
    - Airweave internal rate limits (AirweaveHttpClient → 429)
    - Zoho's non-standard 400 "too many requests" error

    Args:
        exception: Exception to check

    Returns:
        True if this is a rate limit that should be retried
    """
    if isinstance(exception, httpx.HTTPStatusError):
        if exception.response.status_code == 429:
            return True
        # Zoho returns 400 (not 429) for OAuth rate limits with specific format:
        # {"error_description": "You have made too many requests...", "error": "Access Denied"}
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


def should_retry_on_timeout(exception: BaseException) -> bool:
    """Check if exception is a timeout or connection error that should be retried.

    Args:
        exception: Exception to check

    Returns:
        True if this is a timeout or transient connection exception
    """
    # Include connection errors and pool timeouts in addition to regular timeouts
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
    """Combined retry condition for rate limits and timeouts.

    Use this as the retry condition for source API calls:

    Example:
        @retry(
            stop=stop_after_attempt(5),
            retry=should_retry_on_rate_limit_or_timeout,
            wait=wait_rate_limit_with_backoff,
            reraise=True,
        )
        async def _get_with_auth(self, client, url, params=None):
            ...
    """
    return should_retry_on_rate_limit(exception) or should_retry_on_timeout(exception)


def wait_rate_limit_with_backoff(retry_state) -> float:
    """Wait strategy that respects Retry-After header for 429s, exponential backoff for timeouts.

    For 429 errors:
    - Uses Retry-After header if present (set by AirweaveHttpClient)
    - Falls back to exponential backoff if no header

    For timeouts:
    - Uses exponential backoff: 2s, 4s, 8s, max 10s

    Args:
        retry_state: tenacity retry state

    Returns:
        Number of seconds to wait before retry
    """
    exception = retry_state.outcome.exception()

    # For 429 rate limits, check Retry-After header
    if isinstance(exception, httpx.HTTPStatusError) and exception.response.status_code == 429:
        retry_after = exception.response.headers.get("Retry-After")
        if retry_after:
            try:
                # Retry-After is in seconds (float)
                wait_seconds = float(retry_after)

                # CRITICAL: Add minimum wait of 1.0s to prevent rapid-fire retries
                # When Retry-After is < 1s (e.g., 0.3s), retries happen too fast and
                # burn through all attempts before the window actually expires.
                # This ensures we always wait long enough for the sliding window to clear.
                wait_seconds = max(wait_seconds, 1.0)

                # Cap at 120 seconds to avoid indefinite waits
                return min(wait_seconds, 120.0)
            except (ValueError, TypeError):
                pass

        # No Retry-After header or invalid - use exponential backoff
        # This shouldn't happen with AirweaveHttpClient (always sets header)
        # but might happen with real API 429s that don't include header
        return wait_exponential(multiplier=1, min=2, max=30)(retry_state)

    # For timeouts and other retryable errors, use exponential backoff
    return wait_exponential(multiplier=1, min=2, max=10)(retry_state)


# For sources that need simpler fixed-wait retry strategy
retry_if_rate_limit = retry_if_exception(should_retry_on_rate_limit)
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
