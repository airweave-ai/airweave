"""Unit tests for DatabaseRateLimitConfigProvider.

DB access is patched; Redis is replaced with FakeRedis.
Tests verify caching, negative caching, and DB fallback.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from airweave.domains.sources.rate_limiting.config_provider import (
    DatabaseRateLimitConfigProvider,
    _CACHE_PREFIX,
)
from airweave.domains.sources.rate_limiting.types import RateLimitConfig

from .conftest import FakeRedis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(fake_redis: FakeRedis) -> DatabaseRateLimitConfigProvider:
    return DatabaseRateLimitConfigProvider(redis=fake_redis)


ORG_ID = uuid4()


# ---------------------------------------------------------------------------
# Cache read — table-driven
# ---------------------------------------------------------------------------


@dataclass
class CacheReadCase:
    id: str
    cached_value: Optional[str]
    expected_config: Optional[RateLimitConfig]
    expected_is_negative: bool = False


CACHE_READ_TABLE = [
    CacheReadCase(
        id="cache-miss",
        cached_value=None,
        expected_config=None,
    ),
    CacheReadCase(
        id="cache-hit",
        cached_value=json.dumps({"limit": 100, "window_seconds": 60}),
        expected_config=RateLimitConfig(limit=100, window_seconds=60),
    ),
    CacheReadCase(
        id="negative-cache",
        cached_value="{}",
        expected_config=None,
        expected_is_negative=True,
    ),
]


@pytest.mark.parametrize("case", CACHE_READ_TABLE, ids=lambda c: c.id)
@pytest.mark.asyncio
async def test_read_cache(case: CacheReadCase):
    redis = FakeRedis()
    provider = _make_provider(redis)
    cache_key = f"{_CACHE_PREFIX}:{ORG_ID}:slack"

    if case.cached_value is not None:
        redis.seed_string(cache_key, case.cached_value)

    result = await provider._read_cache(cache_key)

    if case.cached_value is None:
        assert result is None
    elif case.expected_is_negative:
        from airweave.domains.sources.rate_limiting.config_provider import _NEGATIVE_CACHE

        assert result is _NEGATIVE_CACHE
    else:
        assert result == case.expected_config


# ---------------------------------------------------------------------------
# Cache write
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_cache_config():
    redis = FakeRedis()
    provider = _make_provider(redis)
    key = "test:cache:key"
    config = RateLimitConfig(limit=50, window_seconds=30)

    await provider._write_cache(key, config)

    raw = await redis.get(key)
    assert raw is not None
    parsed = json.loads(raw)
    assert parsed["limit"] == 50
    assert parsed["window_seconds"] == 30


@pytest.mark.asyncio
async def test_write_cache_negative():
    redis = FakeRedis()
    provider = _make_provider(redis)
    key = "test:cache:neg"

    await provider._write_cache(key, None)

    raw = await redis.get(key)
    assert raw == "{}"


# ---------------------------------------------------------------------------
# get_config — integration of cache + DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_config_returns_cached():
    redis = FakeRedis()
    cache_key = f"{_CACHE_PREFIX}:{ORG_ID}:github"
    redis.seed_string(cache_key, json.dumps({"limit": 200, "window_seconds": 60}))

    provider = _make_provider(redis)
    config = await provider.get_config(ORG_ID, "github")

    assert config == RateLimitConfig(limit=200, window_seconds=60)


@pytest.mark.asyncio
async def test_get_config_negative_cache_returns_none():
    redis = FakeRedis()
    cache_key = f"{_CACHE_PREFIX}:{ORG_ID}:slack"
    redis.seed_string(cache_key, "{}")

    provider = _make_provider(redis)
    config = await provider.get_config(ORG_ID, "slack")

    assert config is None


@pytest.mark.asyncio
async def test_get_config_falls_through_to_db():
    redis = FakeRedis()
    provider = _make_provider(redis)

    db_config = RateLimitConfig(limit=500, window_seconds=120)

    with patch.object(
        DatabaseRateLimitConfigProvider,
        "_fetch_from_db",
        new_callable=AsyncMock,
        return_value=db_config,
    ):
        config = await provider.get_config(ORG_ID, "jira")

    assert config == db_config
    # Verify it was cached for next time
    cache_key = f"{_CACHE_PREFIX}:{ORG_ID}:jira"
    raw = await redis.get(cache_key)
    assert raw is not None
    parsed = json.loads(raw)
    assert parsed["limit"] == 500


@pytest.mark.asyncio
async def test_get_config_caches_negative_from_db():
    redis = FakeRedis()
    provider = _make_provider(redis)

    with patch.object(
        DatabaseRateLimitConfigProvider,
        "_fetch_from_db",
        new_callable=AsyncMock,
        return_value=None,
    ):
        config = await provider.get_config(ORG_ID, "notion")

    assert config is None
    cache_key = f"{_CACHE_PREFIX}:{ORG_ID}:notion"
    raw = await redis.get(cache_key)
    assert raw == "{}"
