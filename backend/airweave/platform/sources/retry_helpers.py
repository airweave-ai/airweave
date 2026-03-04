"""Retry helpers for source connectors.

Provides reusable retry strategies that handle both API rate limits
and Airweave's internal rate limiting (via AirweaveHttpClient).
"""

import logging
import time
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

    # For 429 rate limits, try to respect provider / Airweave headers
    if isinstance(exception, httpx.HTTPStatusError) and exception.response.status_code == 429:
        headers = exception.response.headers

        # 1) Prefer standard Retry-After header (seconds to wait)
        retry_after = headers.get("Retry-After")
        if retry_after:
            try:
                wait_seconds = float(retry_after)
                # Ensure a minimum wait to avoid burning retries too quickly
                wait_seconds = max(wait_seconds, 1.0)
                # Cap at 2 minutes to avoid very long sleeps in workers
                return min(wait_seconds, 120.0)
            except (ValueError, TypeError):
                pass

        # 2) Fall back to X-RateLimit-Reset style headers if present.
        # Many providers (including Calendly-style APIs) expose either a unix
        # timestamp for reset or a relative number of seconds.
        reset_header = headers.get("X-RateLimit-Reset") or headers.get("x-ratelimit-reset")
        if reset_header:
            try:
                reset_value = float(reset_header)
                now = time.time()
                # If the reset looks like an absolute unix timestamp in the future,
                # wait until that time; otherwise treat it as a relative offset.
                if reset_value > now:
                    wait_seconds = reset_value - now
                else:
                    wait_seconds = reset_value

                wait_seconds = max(wait_seconds, 1.0)
                # Allow a bit more headroom here since some provider windows are longer.
                return min(wait_seconds, 300.0)
            except (ValueError, TypeError):
                pass

        # 3) No usable headers - use exponential backoff.
        # This shouldn't happen with AirweaveHttpClient (it always sets Retry-After),
        # but can happen with real API 429s from third-party providers.
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
