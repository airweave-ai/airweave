"""Null source rate limiter — always allows. For local dev or disabled rate limiting."""

from typing import Optional
from uuid import UUID


class NullSourceRateLimiter:
    """No-op source rate limiter. Every request is allowed."""

    async def check_and_increment(
        self,
        org_id: UUID,
        source_short_name: str,
        source_connection_id: Optional[UUID] = None,
    ) -> None:
        """Always allow."""

    async def check_pipedream_proxy_limit(self, org_id: UUID) -> None:
        """Always allow."""
