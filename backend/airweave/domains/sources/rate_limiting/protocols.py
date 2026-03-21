"""Protocols for the rate limiting domain."""

from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from airweave.domains.sources.rate_limiting.types import RateLimitConfig


class RateLimitConfigProvider(Protocol):
    """Provides rate limit configuration per org+source.

    The SourceRateLimiter depends on this instead of importing crud/DB directly.
    Implementations handle caching, DB access, etc.
    """

    async def get_config(self, org_id: UUID, source_short_name: str) -> Optional[RateLimitConfig]:
        """Return config if a limit is set, None otherwise."""
        ...
