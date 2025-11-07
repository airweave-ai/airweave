"""Retry helpers for source connectors.

Provides reusable retry strategies that handle both API rate limits
and Airweave's internal rate limiting (via AirweaveHttpClient).
"""

import httpx
from tenacity import retry_if_exception, wait_exponential


def should_retry_on_rate_limit(exception: BaseException) -> bool:
    """Check if exception is a retryable rate limit (429).

    Handles both:
    - Real API 429 responses
    - Airweave internal rate limits (AirweaveHttpClient → 429)

    Args:
        exception: Exception to check

    Returns:
        True if this is a 429 that should be retried
    """
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code == 429
    return False


def should_retry_on_timeout(exception: BaseException) -> bool:
    """Check if exception is a timeout that should be retried.

    Args:
        exception: Exception to check

    Returns:
        True if this is a timeout exception
    """
    return isinstance(exception, (httpx.ConnectTimeout, httpx.ReadTimeout))


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
