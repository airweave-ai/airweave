"""Source rate limiter protocol for external API quota enforcement.

Adapters: Redis (production), Null (local dev / disabled), Fake (testing).
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class SourceRateLimiter(Protocol):
    """Distributed rate limiting for external source API calls.

    Enforces per-org (or per-connection) sliding-window limits to prevent
    Airweave from exhausting customer API quotas.
    """

    async def check_and_increment(
        self,
        org_id: UUID,
        source_short_name: str,
        source_connection_id: Optional[UUID] = None,
    ) -> None:
        """Check rate limit and increment counter if allowed.

        Raises:
            SourceRateLimitExceededException: If rate limit is exceeded.
        """
        ...

    async def check_pipedream_proxy_limit(self, org_id: UUID) -> None:
        """Check Pipedream proxy rate limit (org-wide infrastructure limit).

        Raises:
            SourceRateLimitExceededException: If Pipedream proxy limit exceeded.
        """
        ...
