"""Fake rate limiter for testing — records calls, supports limit injection."""

from uuid import UUID

from airweave import schemas
from airweave.core.exceptions import RateLimitExceededException
from airweave.core.protocols.rate_limiter import RateLimiter
from airweave.schemas.rate_limit import RateLimitResult


class FakeRateLimiter(RateLimiter):
    """In-memory fake that records calls and optionally rejects."""

    def __init__(self) -> None:
        """Initialize with empty call log and no forced limit."""
        self._calls: list[UUID] = []
        self._force_reject = False
        self._force_retry_after = 30.0

    def reject_next(self, retry_after: float = 30.0) -> None:
        """Force the next check to raise RateLimitExceededException."""
        self._force_reject = True
        self._force_retry_after = retry_after

    async def check(self, organization: schemas.Organization) -> RateLimitResult:
        """Record the call and optionally reject."""
        self._calls.append(organization.id)

        if self._force_reject:
            self._force_reject = False
            raise RateLimitExceededException(
                retry_after=self._force_retry_after,
                limit=10,
                remaining=0,
            )

        return RateLimitResult(allowed=True, retry_after=0.0, limit=9999, remaining=9999)

    @property
    def call_count(self) -> int:
        """Number of check() calls recorded."""
        return len(self._calls)
