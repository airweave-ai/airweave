"""Unit tests for SourceRateLimiter.

Redis is replaced with FakeRedis. Config provider and source registry are
fakes. Tests verify the sliding-window logic, key building, and error paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

import pytest

from airweave.core.shared_models import RateLimitLevel
from airweave.domains.sources.rate_limiting.exceptions import InternalRateLimitExceeded
from airweave.domains.sources.rate_limiting.service import SourceRateLimiter
from airweave.domains.sources.rate_limiting.types import RateLimitConfig

from .conftest import FakeRateLimitConfigProvider, FakeRedis, FakeSourceRegistryForRL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


ORG_ID = uuid4()
SC_ID = uuid4()


def _make_limiter(
    *,
    fake_redis: Optional[FakeRedis] = None,
    source_registry: Optional[FakeSourceRegistryForRL] = None,
    config_provider: Optional[FakeRateLimitConfigProvider] = None,
) -> SourceRateLimiter:
    return SourceRateLimiter(
        redis=fake_redis or FakeRedis(),
        source_registry=source_registry or FakeSourceRegistryForRL(),
        config_provider=config_provider or FakeRateLimitConfigProvider(),
    )


# ---------------------------------------------------------------------------
# _build_key — table-driven
# ---------------------------------------------------------------------------


@dataclass
class BuildKeyCase:
    id: str
    level: str
    source_connection_id: Optional[UUID] = None
    expect_contains: str = ""


BUILD_KEY_TABLE = [
    BuildKeyCase(
        id="org-level",
        level=RateLimitLevel.ORG.value,
        expect_contains=":org:org",
    ),
    BuildKeyCase(
        id="connection-level",
        level=RateLimitLevel.CONNECTION.value,
        source_connection_id=SC_ID,
        expect_contains=f":connection:{SC_ID}",
    ),
]


@pytest.mark.parametrize("case", BUILD_KEY_TABLE, ids=lambda c: c.id)
def test_build_key(case: BuildKeyCase):
    key = SourceRateLimiter._build_key(
        ORG_ID, "github", case.level, case.source_connection_id
    )
    assert case.expect_contains in key
    assert "source_rate_limit" in key
    assert str(ORG_ID) in key
    assert "github" in key


# ---------------------------------------------------------------------------
# check_and_increment — no limit configured → no-op
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_rate_limit_level_is_noop():
    """Source without rate_limit_level in registry → skip entirely."""
    registry = FakeSourceRegistryForRL()
    registry.seed("github", None)

    limiter = _make_limiter(source_registry=registry)
    # Should not raise
    await limiter.check_and_increment(ORG_ID, "github")


@pytest.mark.asyncio
async def test_no_config_is_noop():
    """Source has rate_limit_level but no config in DB → skip."""
    registry = FakeSourceRegistryForRL()
    registry.seed("github", RateLimitLevel.ORG.value)

    config_provider = FakeRateLimitConfigProvider()
    # No config seeded

    limiter = _make_limiter(source_registry=registry, config_provider=config_provider)
    await limiter.check_and_increment(ORG_ID, "github")


@pytest.mark.asyncio
async def test_unknown_source_is_noop():
    """Source not in registry → skip (KeyError caught internally)."""
    registry = FakeSourceRegistryForRL()
    # Not seeded
    limiter = _make_limiter(source_registry=registry)
    await limiter.check_and_increment(ORG_ID, "unknown_source")


# ---------------------------------------------------------------------------
# check_and_increment — within limits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_within_limit_succeeds():
    redis = FakeRedis()
    registry = FakeSourceRegistryForRL()
    registry.seed("notion", RateLimitLevel.CONNECTION.value)

    config_provider = FakeRateLimitConfigProvider()
    config_provider.seed(ORG_ID, "notion", RateLimitConfig(limit=10, window_seconds=60))

    limiter = _make_limiter(
        fake_redis=redis, source_registry=registry, config_provider=config_provider
    )

    for _ in range(10):
        await limiter.check_and_increment(ORG_ID, "notion", source_connection_id=SC_ID)


# ---------------------------------------------------------------------------
# check_and_increment — exceeds limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exceeds_limit_raises():
    redis = FakeRedis()
    registry = FakeSourceRegistryForRL()
    registry.seed("notion", RateLimitLevel.CONNECTION.value)

    config_provider = FakeRateLimitConfigProvider()
    config_provider.seed(ORG_ID, "notion", RateLimitConfig(limit=3, window_seconds=60))

    limiter = _make_limiter(
        fake_redis=redis, source_registry=registry, config_provider=config_provider
    )

    for _ in range(3):
        await limiter.check_and_increment(ORG_ID, "notion", source_connection_id=SC_ID)

    with pytest.raises(InternalRateLimitExceeded) as exc_info:
        await limiter.check_and_increment(ORG_ID, "notion", source_connection_id=SC_ID)

    assert exc_info.value.source_short_name == "notion"
    assert exc_info.value.retry_after > 0


# ---------------------------------------------------------------------------
# check_and_increment — org-level
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_org_level_rate_limit():
    redis = FakeRedis()
    registry = FakeSourceRegistryForRL()
    registry.seed("google_drive", RateLimitLevel.ORG.value)

    config_provider = FakeRateLimitConfigProvider()
    config_provider.seed(ORG_ID, "google_drive", RateLimitConfig(limit=2, window_seconds=60))

    limiter = _make_limiter(
        fake_redis=redis, source_registry=registry, config_provider=config_provider
    )

    # Different connection IDs still share the org-level limit
    await limiter.check_and_increment(ORG_ID, "google_drive", source_connection_id=uuid4())
    await limiter.check_and_increment(ORG_ID, "google_drive", source_connection_id=uuid4())

    with pytest.raises(InternalRateLimitExceeded):
        await limiter.check_and_increment(ORG_ID, "google_drive", source_connection_id=uuid4())


# ---------------------------------------------------------------------------
# _get_rate_limit_level — caching in Redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_level_is_cached():
    redis = FakeRedis()
    registry = FakeSourceRegistryForRL()
    registry.seed("slack", RateLimitLevel.ORG.value)

    limiter = _make_limiter(fake_redis=redis, source_registry=registry)

    level = await limiter._get_rate_limit_level("slack")
    assert level == RateLimitLevel.ORG.value

    # Second call should use cache, not registry
    registry._levels.pop("slack")
    level2 = await limiter._get_rate_limit_level("slack")
    assert level2 == RateLimitLevel.ORG.value


@pytest.mark.asyncio
async def test_rate_limit_level_none_cached_as_none():
    redis = FakeRedis()
    registry = FakeSourceRegistryForRL()
    registry.seed("trello", None)

    limiter = _make_limiter(fake_redis=redis, source_registry=registry)

    level = await limiter._get_rate_limit_level("trello")
    assert level is None

    # Cached "None" string → returns None
    cached = await redis.get("source_metadata:trello:rate_limit_level")
    assert cached == "None"
