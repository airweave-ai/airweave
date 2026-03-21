"""Rate limiting domain exceptions.

``RateLimitExceeded`` is an internal signal between the rate limiter and
``AirweaveHttpClient``. Sources never see it — the client converts it to
a synthetic HTTP 429 so the source's retry logic handles it transparently.
"""

from __future__ import annotations


class InternalRateLimitExceeded(Exception):
    """Internal rate limit exceeded — converted to 429 by AirweaveHttpClient."""

    def __init__(self, retry_after: float, source_short_name: str) -> None:
        """Initialize with retry timing and source identifier."""
        self.retry_after = retry_after
        self.source_short_name = source_short_name
        super().__init__(
            f"Rate limit exceeded for {source_short_name}, retry after {retry_after:.1f}s"
        )
