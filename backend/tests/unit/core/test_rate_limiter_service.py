"""Tests for rate limiter service.

Tests the minute-based rate limiting system with Redis-backed sliding window.

Rate limits:
- Developer: 10 requests/minute
- Pro: 100 requests/minute
- Team: 250 requests/minute
- Enterprise: Unlimited
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.core.exceptions import RateLimitExceededException
from airweave.core.rate_limiter_service import RateLimiter
from airweave.schemas.organization_billing import BillingPlan
from airweave.schemas.rate_limit import RateLimitResult


@pytest.fixture
def organization_id():
    """Create a test organization ID."""
    return uuid4()


@pytest.fixture
def mock_ctx(organization_id):
    """Create a mock API context with organization and billing."""
    mock = MagicMock()
    mock.organization.id = organization_id
    mock.organization.billing = None  # Default to no billing
    mock.logger = MagicMock()
    return mock


@pytest.fixture
def mock_settings():
    """Mock settings to enable rate limiting."""
    with patch("airweave.core.rate_limiter_service.settings") as mock:
        mock.DISABLE_RATE_LIMIT = False
        yield mock


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch("airweave.core.rate_limiter_service.redis_client") as mock:
        # Setup mock pipeline — pipeline methods (zremrangebyscore, zadd, zcount)
        # are synchronous queue operations; only execute() is async.
        mock_pipeline = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[None, 0])  # zremrangebyscore, zcount
        mock.client.pipeline.return_value = mock_pipeline
        mock.client.zrange = AsyncMock(return_value=[])
        mock.client.zadd = AsyncMock(return_value=1)
        mock.client.expire = AsyncMock(return_value=True)
        yield mock


@pytest.mark.asyncio
async def test_rate_limiter_allows_request_under_limit(
    mock_ctx, mock_settings, mock_redis
):
    """Test that requests under the limit are allowed."""
    # Setup billing with Pro plan (100 req/min)
    mock_billing = MagicMock()
    mock_period = MagicMock()
    mock_period.plan = BillingPlan.PRO
    mock_billing.current_period = mock_period
    mock_ctx.organization.billing = mock_billing

    # Current count is 50, limit is 100
    mock_redis.client.pipeline().execute = AsyncMock(return_value=[None, 50])

    result = await RateLimiter.check_rate_limit(ctx=mock_ctx)

    assert result.allowed is True
    assert result.retry_after == 0.0
    assert result.limit == 100
    assert result.remaining == 49  # 100 - 50 - 1 = 49


@pytest.mark.asyncio
async def test_rate_limiter_blocks_request_over_limit(
    mock_ctx, mock_settings, mock_redis
):
    """Test that requests over the limit are blocked."""
    # Setup billing with Developer plan (10 req/min)
    mock_billing = MagicMock()
    mock_period = MagicMock()
    mock_period.plan = BillingPlan.DEVELOPER
    mock_billing.current_period = mock_period
    mock_ctx.organization.billing = mock_billing

    # Current count is 10, limit is 10 (at limit)
    mock_redis.client.pipeline().execute = AsyncMock(return_value=[None, 10])
    mock_redis.client.zrange = AsyncMock(return_value=[(b"1234567890.0", 1234567890.0)])

    with pytest.raises(RateLimitExceededException) as exc_info:
        await RateLimiter.check_rate_limit(ctx=mock_ctx)

    assert exc_info.value.limit == 10
    assert exc_info.value.remaining == 0
    assert exc_info.value.retry_after > 0


@pytest.mark.asyncio
async def test_rate_limiter_unlimited_for_enterprise(
    mock_ctx, mock_settings, mock_redis
):
    """Test that Enterprise plan has unlimited rate limit."""
    # Setup billing with Enterprise plan (None = unlimited)
    mock_billing = MagicMock()
    mock_period = MagicMock()
    mock_period.plan = BillingPlan.ENTERPRISE
    mock_billing.current_period = mock_period
    mock_ctx.organization.billing = mock_billing

    result = await RateLimiter.check_rate_limit(ctx=mock_ctx)

    assert result.allowed is True
    assert result.retry_after == 0.0
    assert result.limit == 9999  # 9999 indicates unlimited
    assert result.remaining == 9999


@pytest.mark.asyncio
async def test_rate_limiter_legacy_org_without_billing(
    mock_ctx, mock_settings, mock_redis
):
    """Test that legacy organizations without billing get Pro tier limits."""
    # No billing record - ctx.organization.billing is None (set in fixture)
    # Current count is 5
    mock_redis.client.pipeline().execute = AsyncMock(return_value=[None, 5])

    result = await RateLimiter.check_rate_limit(ctx=mock_ctx)

    assert result.allowed is True
    assert result.limit == 100  # Pro tier limit (100 req/min)


@pytest.mark.asyncio
async def test_rate_limiter_concurrent_requests(
    mock_ctx, mock_settings, mock_redis
):
    """Test rate limiter handles concurrent requests correctly."""
    # Setup billing with Developer plan (10 req/min)
    mock_billing = MagicMock()
    mock_period = MagicMock()
    mock_period.plan = BillingPlan.DEVELOPER
    mock_billing.current_period = mock_period
    mock_ctx.organization.billing = mock_billing

    # Simulate increasing count for each call
    call_count = 0

    def mock_execute():
        nonlocal call_count
        call_count += 1
        return AsyncMock(return_value=[None, call_count])()

    mock_redis.client.pipeline().execute = mock_execute

    # Make 5 concurrent requests
    tasks = [RateLimiter.check_rate_limit(ctx=mock_ctx) for _ in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    # All should succeed since we're under the limit of 10 req/min
    assert len(results) == 5
    for result in results:
        assert result.allowed is True
        assert result.limit == 10


@pytest.mark.asyncio
async def test_rate_limiter_plan_limits():
    """Test that different plans have correct rate limits (requests per minute)."""
    assert RateLimiter.PLAN_LIMITS[BillingPlan.DEVELOPER] == 10  # 10 req/min
    assert RateLimiter.PLAN_LIMITS[BillingPlan.PRO] == 100  # 100 req/min
    assert RateLimiter.PLAN_LIMITS[BillingPlan.TEAM] == 250  # 250 req/min
    assert RateLimiter.PLAN_LIMITS[BillingPlan.ENTERPRISE] is None  # Unlimited


@pytest.mark.asyncio
async def test_rate_limiter_redis_key_format(organization_id):
    """Test that Redis keys are formatted correctly."""
    key = RateLimiter._get_redis_key(organization_id)

    expected_key = f"rate_limit:org:{organization_id}"
    assert key == expected_key
