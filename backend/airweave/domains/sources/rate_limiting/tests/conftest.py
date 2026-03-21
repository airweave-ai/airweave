"""Rate limiting test fixtures.

Provides a FakeRedis, fake config provider, and fake source registry
so rate limiting tests run without real Redis or DB.
"""

from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

import pytest

from airweave.domains.sources.rate_limiting.types import RateLimitConfig


# ---------------------------------------------------------------------------
# Fake Redis
# ---------------------------------------------------------------------------


class FakeRedis:
    """In-memory Redis fake supporting the operations used by rate limiting.

    Supports: get, setex, eval (Lua), and ZREMRANGEBYSCORE/ZCOUNT/ZADD/EXPIRE
    via a simplified eval implementation.
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._sorted_sets: dict[str, list[tuple[float, str]]] = {}
        self._ttls: dict[str, float] = {}

    async def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value
        self._ttls[key] = ttl

    async def eval(
        self,
        script: str,
        num_keys: int,
        key: str,
        limit: int,
        window_start: float,
        current_time: float,
        window_seconds: int,
        expire_seconds: int,
        unique_id: str,
    ) -> list:
        """Simplified Lua script emulation for the sliding window algorithm."""
        ss = self._sorted_sets.setdefault(key, [])

        # ZREMRANGEBYSCORE: remove entries before window_start
        ss[:] = [(score, member) for score, member in ss if score > window_start]

        # ZCOUNT: count entries in window
        current_count = sum(1 for score, _ in ss if window_start <= score <= current_time)

        if current_count >= int(limit):
            retry_after = float(window_seconds)
            if ss:
                oldest_score = ss[0][0]
                retry_after = max(0.1, oldest_score + float(window_seconds) - current_time)
            return [-1, retry_after]

        # ZADD
        ss.append((current_time, unique_id))
        self._ttls[key] = expire_seconds
        return [current_count + 1, 0]

    def seed_string(self, key: str, value: str) -> None:
        """Seed a string value for testing cache reads."""
        self._store[key] = value

    def clear(self) -> None:
        self._store.clear()
        self._sorted_sets.clear()
        self._ttls.clear()


# ---------------------------------------------------------------------------
# Fake config provider
# ---------------------------------------------------------------------------


class FakeRateLimitConfigProvider:
    """In-memory config provider for testing."""

    def __init__(self) -> None:
        self._configs: dict[tuple[UUID, str], RateLimitConfig] = {}

    def seed(self, org_id: UUID, source_short_name: str, config: RateLimitConfig) -> None:
        self._configs[(org_id, source_short_name)] = config

    async def get_config(self, org_id: UUID, source_short_name: str) -> Optional[RateLimitConfig]:
        return self._configs.get((org_id, source_short_name))


# ---------------------------------------------------------------------------
# Fake source registry
# ---------------------------------------------------------------------------


class FakeSourceRegistryForRL:
    """Minimal source registry for rate limiting tests."""

    def __init__(self) -> None:
        self._levels: dict[str, Optional[str]] = {}

    def seed(self, short_name: str, rate_limit_level: Optional[str]) -> None:
        self._levels[short_name] = rate_limit_level

    def get(self, short_name: str):
        if short_name not in self._levels:
            raise KeyError(short_name)

        class _Entry:
            pass

        entry = _Entry()
        entry.rate_limit_level = self._levels[short_name]
        return entry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def fake_config_provider():
    return FakeRateLimitConfigProvider()


@pytest.fixture
def fake_source_registry():
    return FakeSourceRegistryForRL()
