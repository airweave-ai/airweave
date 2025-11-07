"""Tests for source rate limiter service.

Tests the Redis-backed sliding window rate limiting for external source API calls.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.core.exceptions import SourceRateLimitExceededException
from airweave.core.source_rate_limiter_service import SourceRateLimiter


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
    """Mock Redis client."""
    with patch("airweave.core.source_rate_limiter_service.redis_client") as mock:
        # Setup mock pipeline
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[None, 0])  # zremrangebyscore, zcount
        mock.client.pipeline.return_value = mock_pipeline
        mock.client.zrange = AsyncMock(return_value=[])
        mock.client.zadd = AsyncMock(return_value=1)
        mock.client.expire = AsyncMock(return_value=True)
        mock.client.get = AsyncMock(return_value=None)  # No cached config
        mock.client.setex = AsyncMock(return_value=True)
        yield mock


@pytest.mark.asyncio
async def test_source_rate_limiter_skips_when_no_level():
    """Test that rate limiter skips check when source has no rate_limit_level."""
    # Mock source with no rate limiting
    with patch.object(
        SourceRateLimiter, "_get_source_rate_limit_level", return_value=None
    ):
        # Should return immediately without any Redis calls
        await SourceRateLimiter.check_and_increment(
            org_id=uuid4(),
            source_short_name="test_source",
        )
        # No exception means success


@pytest.mark.asyncio
async def test_source_rate_limiter_allows_request_under_limit(org_id, mock_redis):
    """Test that requests under the limit are allowed."""
    # Mock source metadata lookup (rate_limit_level from Source table)
    with patch.object(
        SourceRateLimiter, "_get_source_rate_limit_level", return_value="org"
    ), patch.object(
        SourceRateLimiter,
        "_get_limit_config",
        return_value={"limit": 100, "window_seconds": 60},
    ):
        # Current count is 50, limit is 100
        mock_redis.client.pipeline().execute = AsyncMock(return_value=[None, 50])

        # Should not raise exception
        await SourceRateLimiter.check_and_increment(
            org_id=org_id,
            source_short_name="google_drive",
        )

        # Verify Redis operations were called
        mock_redis.client.pipeline.assert_called()
        mock_redis.client.zadd.assert_called_once()
        mock_redis.client.expire.assert_called_once()


@pytest.mark.asyncio
async def test_source_rate_limiter_blocks_request_over_limit(org_id, mock_redis):
    """Test that requests over the limit are blocked."""
    # Mock source metadata and config lookup
    with patch.object(
        SourceRateLimiter, "_get_source_rate_limit_level", return_value="org"
    ), patch.object(
        SourceRateLimiter,
        "_get_limit_config",
        return_value={"limit": 10, "window_seconds": 60},
    ):
        # Current count is 10, limit is 10 (at limit)
        mock_redis.client.pipeline().execute = AsyncMock(return_value=[None, 10])
        mock_redis.client.zrange = AsyncMock(
            return_value=[(b"1234567890.0", time.time() - 30)]
        )  # Oldest entry 30s ago

        with pytest.raises(SourceRateLimitExceededException) as exc_info:
            await SourceRateLimiter.check_and_increment(
                org_id=org_id,
                source_short_name="google_drive",
            )

        # Verify exception details
        assert exc_info.value.source_short_name == "google_drive"
        assert exc_info.value.retry_after > 0

        # Verify request was NOT added to Redis
        mock_redis.client.zadd.assert_not_called()


@pytest.mark.asyncio
async def test_source_rate_limiter_connection_level(connection_id, org_id, mock_redis):
    """Test connection-level rate limiting (e.g., Notion per-user)."""
    # Mock source metadata (connection-level from Source table)
    with patch.object(
        SourceRateLimiter, "_get_source_rate_limit_level", return_value="connection"
    ), patch.object(
        SourceRateLimiter,
        "_get_limit_config",
        return_value={"limit": 2, "window_seconds": 1},
    ):
        # Current count is 1, limit is 2
        mock_redis.client.pipeline().execute = AsyncMock(return_value=[None, 1])

        # Should not raise exception
        await SourceRateLimiter.check_and_increment(
            org_id=org_id,
            source_short_name="notion",
            source_connection_id=connection_id,
        )

        # Verify Redis operations were called
        mock_redis.client.pipeline.assert_called()
        mock_redis.client.zadd.assert_called_once()


@pytest.mark.asyncio
async def test_source_rate_limiter_no_config_allows_request(org_id, mock_redis):
    """Test that requests are allowed when no rate limit is configured."""
    # Mock source has rate_limit_level but no config in DB
    with patch.object(
        SourceRateLimiter, "_get_source_rate_limit_level", return_value="org"
    ), patch.object(SourceRateLimiter, "_get_limit_config", return_value=None):
        # Should return immediately without checking Redis
        await SourceRateLimiter.check_and_increment(
            org_id=org_id,
            source_short_name="google_drive",
        )

        # Redis pipeline should not be called since we exit early
        mock_redis.client.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_source_rate_limiter_redis_key_format_org(org_id):
    """Test Redis key format for org-level rate limiting."""
    key = SourceRateLimiter._get_redis_key(
        org_id=org_id,
        source_short_name="google_drive",
        rate_limit_level="org",
        source_connection_id=None,
    )

    expected = f"source_rate_limit:{org_id}:google_drive:org:org"
    assert key == expected


@pytest.mark.asyncio
async def test_source_rate_limiter_redis_key_format_connection(org_id, connection_id):
    """Test Redis key format for connection-level rate limiting."""
    key = SourceRateLimiter._get_redis_key(
        org_id=org_id,
        source_short_name="notion",
        rate_limit_level="connection",
        source_connection_id=connection_id,
    )

    expected = f"source_rate_limit:{org_id}:notion:connection:{connection_id}"
    assert key == expected


@pytest.mark.asyncio
async def test_config_cache_key_format(org_id):
    """Test config cache key format (always org+source, no connection_id)."""
    key = SourceRateLimiter._get_config_cache_key(
        org_id=org_id,
        source_short_name="google_drive",
    )

    expected = f"source_rate_limit_config:{org_id}:google_drive"
    assert key == expected

