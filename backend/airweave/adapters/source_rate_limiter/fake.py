"""Fake source rate limiter for testing — records calls, supports error injection."""

from typing import Optional
from uuid import UUID


class FakeSourceRateLimiter:
    """In-memory fake that records calls and optionally rejects."""

    def __init__(self) -> None:
        """Initialize with empty call log."""
        self._calls: list[tuple] = []
        self._should_raise: Optional[Exception] = None

    def set_error(self, error: Exception) -> None:
        """Force subsequent calls to raise the given exception."""
        self._should_raise = error

    def clear_error(self) -> None:
        """Stop raising on subsequent calls."""
        self._should_raise = None

    async def check_and_increment(
        self,
        org_id: UUID,
        source_short_name: str,
        source_connection_id: Optional[UUID] = None,
    ) -> None:
        self._calls.append(("check_and_increment", org_id, source_short_name, source_connection_id))
        if self._should_raise:
            raise self._should_raise

    async def check_pipedream_proxy_limit(self, org_id: UUID) -> None:
        self._calls.append(("check_pipedream_proxy_limit", org_id))
        if self._should_raise:
            raise self._should_raise

    @property
    def call_count(self) -> int:
        """Total number of check calls recorded."""
        return len(self._calls)
