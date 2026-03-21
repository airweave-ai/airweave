"""Types for the rate limiting domain."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    """Rate limit configuration for one org+source pair."""

    limit: int
    window_seconds: int
