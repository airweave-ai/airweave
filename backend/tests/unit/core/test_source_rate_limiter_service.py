"""Tests for source rate limiter service.

Tests the Redis-backed sliding window rate limiting for external source API calls.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.domains.sources.rate_limiting.service import SourceRateLimiter

# Matches ``DatabaseRateLimitConfigProvider`` cache key prefix in
# ``airweave.domains.sources.rate_limiting.config_provider``.
_CONFIG_CACHE_PREFIX = "source_rate_limit_config"


@pytest.fixture
def org_id():
    """Create a test organization ID."""
    return uuid4()


@pytest.fixture
def connection_id():
    """Create a test source connection ID."""
    return uuid4()


@pytest.fixture
def mock_redis():
    """Async Redis double injected into ``SourceRateLimiter`` (no module-level client)."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    r.eval = AsyncMock()
    return r


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    entry = MagicMock()
    entry.rate_limit_level = "org"
    registry.get.return_value = entry
    return registry


@pytest.fixture
def mock_config_provider():
    return AsyncMock()


def _make_rate_limiter(redis, registry, config_provider):
    return SourceRateLimiter(
        redis=redis,
        source_registry=registry,
        config_provider=config_provider,
    )


@pytest.mark.asyncio
async def test_source_rate_limiter_skips_when_no_level(
    org_id, mock_redis, mock_config_provider
):
    """Test that rate limiter skips check when source has no rate_limit_level."""
    registry = MagicMock()
    entry = MagicMock()
    entry.rate_limit_level = None
    registry.get.return_value = entry

    svc = _make_rate_limiter(mock_redis, registry, mock_config_provider)
    await svc.check_and_increment(org_id=org_id, source_short_name="test_source")

    mock_config_provider.get_config.assert_not_called()
    mock_redis.eval.assert_not_called()


@pytest.mark.asyncio
async def test_source_rate_limiter_no_config_allows_request(
    org_id, mock_redis, mock_registry, mock_config_provider
):
    """Test that requests are allowed when no rate limit is configured."""
    mock_config_provider.get_config.return_value = None

    svc = _make_rate_limiter(mock_redis, mock_registry, mock_config_provider)
    await svc.check_and_increment(org_id=org_id, source_short_name="google_drive")

    mock_redis.eval.assert_not_called()


def test_source_rate_limiter_redis_key_format_org(org_id):
    """Test Redis key format for org-level rate limiting."""
    key = SourceRateLimiter._build_key(
        org_id,
        "google_drive",
        "org",
    )

    expected = f"source_rate_limit:{org_id}:google_drive:org:org"
    assert key == expected


def test_source_rate_limiter_redis_key_format_connection(org_id, connection_id):
    """Test Redis key format for connection-level rate limiting."""
    key = SourceRateLimiter._build_key(
        org_id,
        "notion",
        "connection",
        connection_id,
    )

    expected = f"source_rate_limit:{org_id}:notion:connection:{connection_id}"
    assert key == expected


def test_config_cache_key_format(org_id):
    """Test config cache key format (always org+source, no connection_id)."""
    key = f"{_CONFIG_CACHE_PREFIX}:{org_id}:google_drive"
    expected = f"source_rate_limit_config:{org_id}:google_drive"
    assert key == expected
