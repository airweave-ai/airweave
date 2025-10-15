"""Tests for rate limiter service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.core.exceptions import RateLimitExceededException
from airweave.core.rate_limiter_service import RateLimiterService
from airweave.schemas.organization_billing import BillingPlan


@pytest.fixture
def organization_id():
    """Create a test organization ID."""
    return uuid4()


@pytest.fixture
def mock_settings():
    """Mock settings to enable rate limiting."""
    with patch("airweave.core.rate_limiter_service.settings") as mock:
        mock.LOCAL_DEVELOPMENT = False
        mock.RATE_LIMIT_ENABLED = True
        yield mock


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch("airweave.core.rate_limiter_service.redis_client") as mock:
        # Setup mock pipeline
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[None, 0])  # zremrangebyscore, zcount
        mock.client.pipeline.return_value = mock_pipeline
        mock.client.zrange = AsyncMock(return_value=[])
        mock.client.zadd = AsyncMock(return_value=1)
        mock.client.expire = AsyncMock(return_value=True)
        yield mock


@pytest.fixture
def mock_db_context():
    """Mock database context for billing checks."""
    with patch("airweave.core.rate_limiter_service.get_db_context") as mock_ctx:
        mock_db = AsyncMock()
        mock_ctx.return_value.__aenter__.return_value = mock_db
        yield mock_db


@pytest.fixture
def mock_crud():
    """Mock CRUD operations."""
    with patch("airweave.core.rate_limiter_service.crud") as mock:
        yield mock


@pytest.mark.asyncio
async def test_rate_limiter_allows_request_under_limit(
    organization_id, mock_settings, mock_redis, mock_db_context, mock_crud
):
    """Test that requests under the limit are allowed."""
    # Setup billing with Pro plan (25 req/s)
    mock_billing = MagicMock()
    mock_crud.organization_billing.get_by_organization = AsyncMock(return_value=mock_billing)

    mock_period = MagicMock()
    mock_period.plan = BillingPlan.PRO
    mock_crud.billing_period.get_current_period = AsyncMock(return_value=mock_period)

    # Current count is 10, limit is 25
    mock_redis.client.pipeline().execute = AsyncMock(return_value=[None, 10])

    limiter = RateLimiterService(organization_id=organization_id)

    allowed, retry_after, limit, remaining = await limiter.check_rate_limit()

    assert allowed is True
    assert retry_after == 0.0
    assert limit == 25
    assert remaining == 14  # 25 - 10 - 1 = 14


@pytest.mark.asyncio
async def test_rate_limiter_blocks_request_over_limit(
    organization_id, mock_settings, mock_redis, mock_db_context, mock_crud
):
    """Test that requests over the limit are blocked."""
    # Setup billing with Developer plan (10 req/s)
    mock_billing = MagicMock()
    mock_crud.organization_billing.get_by_organization = AsyncMock(return_value=mock_billing)

    mock_period = MagicMock()
    mock_period.plan = BillingPlan.DEVELOPER
    mock_crud.billing_period.get_current_period = AsyncMock(return_value=mock_period)

    # Current count is 10, limit is 10 (at limit)
    mock_redis.client.pipeline().execute = AsyncMock(return_value=[None, 10])
    mock_redis.client.zrange = AsyncMock(return_value=[(b"1234567890.0", 1234567890.0)])

    limiter = RateLimiterService(organization_id=organization_id)

    with pytest.raises(RateLimitExceededException) as exc_info:
        await limiter.check_rate_limit()

    assert exc_info.value.limit == 10
    assert exc_info.value.remaining == 0
    assert exc_info.value.retry_after > 0


@pytest.mark.asyncio
async def test_rate_limiter_unlimited_for_enterprise(
    organization_id, mock_settings, mock_redis, mock_db_context, mock_crud
):
    """Test that Enterprise plan has unlimited rate limit."""
    # Setup billing with Enterprise plan (None = unlimited)
    mock_billing = MagicMock()
    mock_crud.organization_billing.get_by_organization = AsyncMock(return_value=mock_billing)

    mock_period = MagicMock()
    mock_period.plan = BillingPlan.ENTERPRISE
    mock_crud.billing_period.get_current_period = AsyncMock(return_value=mock_period)

    limiter = RateLimiterService(organization_id=organization_id)

    allowed, retry_after, limit, remaining = await limiter.check_rate_limit()

    assert allowed is True
    assert retry_after == 0.0
    assert limit == 0  # 0 indicates unlimited
    assert remaining == 0


@pytest.mark.asyncio
async def test_rate_limiter_legacy_org_without_billing(
    organization_id, mock_settings, mock_redis, mock_db_context, mock_crud
):
    """Test that legacy organizations without billing get Pro tier limits."""
    # No billing record
    mock_crud.organization_billing.get_by_organization = AsyncMock(return_value=None)

    # Current count is 5
    mock_redis.client.pipeline().execute = AsyncMock(return_value=[None, 5])

    limiter = RateLimiterService(organization_id=organization_id)

    allowed, retry_after, limit, remaining = await limiter.check_rate_limit()

    assert allowed is True
    assert limit == 25  # Pro tier limit


@pytest.mark.asyncio
async def test_rate_limiter_redis_failure_allows_request(
    organization_id, mock_settings, mock_redis, mock_db_context, mock_crud
):
    """Test that Redis failures allow requests through (fail-open)."""
    # Setup billing
    mock_billing = MagicMock()
    mock_crud.organization_billing.get_by_organization = AsyncMock(return_value=mock_billing)

    mock_period = MagicMock()
    mock_period.plan = BillingPlan.PRO
    mock_crud.billing_period.get_current_period = AsyncMock(return_value=mock_period)

    # Simulate Redis error
    mock_redis.client.pipeline().execute = AsyncMock(side_effect=Exception("Redis error"))

    limiter = RateLimiterService(organization_id=organization_id)

    # Should not raise exception, should allow through
    allowed, retry_after, limit, remaining = await limiter.check_rate_limit()

    assert allowed is True


@pytest.mark.asyncio
async def test_rate_limiter_concurrent_requests(
    organization_id, mock_settings, mock_redis, mock_db_context, mock_crud
):
    """Test rate limiter handles concurrent requests correctly."""
    # Setup billing with Developer plan (10 req/s)
    mock_billing = MagicMock()
    mock_crud.organization_billing.get_by_organization = AsyncMock(return_value=mock_billing)

    mock_period = MagicMock()
    mock_period.plan = BillingPlan.DEVELOPER
    mock_crud.billing_period.get_current_period = AsyncMock(return_value=mock_period)

    # Simulate increasing count for each call
    call_count = 0

    def mock_execute():
        nonlocal call_count
        call_count += 1
        return AsyncMock(return_value=[None, call_count])()

    mock_redis.client.pipeline().execute = mock_execute

    limiter = RateLimiterService(organization_id=organization_id)

    # Make 5 concurrent requests
    tasks = [limiter.check_rate_limit() for _ in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    # All should succeed since we're under the limit of 10
    assert len(results) == 5
    for result in results:
        allowed, retry_after, limit, remaining = result
        assert allowed is True
        assert limit == 10


@pytest.mark.asyncio
async def test_rate_limiter_caches_limit(
    organization_id, mock_settings, mock_redis, mock_db_context, mock_crud
):
    """Test that rate limiter caches the limit to avoid repeated DB queries."""
    # Setup billing
    mock_billing = MagicMock()
    mock_crud.organization_billing.get_by_organization = AsyncMock(return_value=mock_billing)

    mock_period = MagicMock()
    mock_period.plan = BillingPlan.TEAM
    mock_crud.billing_period.get_current_period = AsyncMock(return_value=mock_period)

    mock_redis.client.pipeline().execute = AsyncMock(return_value=[None, 0])

    limiter = RateLimiterService(organization_id=organization_id)

    # First call
    await limiter.check_rate_limit()
    assert mock_crud.billing_period.get_current_period.call_count == 1

    # Second call should use cached limit
    await limiter.check_rate_limit()
    assert mock_crud.billing_period.get_current_period.call_count == 1  # Still 1


@pytest.mark.asyncio
async def test_rate_limiter_plan_limits():
    """Test that different plans have correct rate limits."""
    assert RateLimiterService.PLAN_LIMITS[BillingPlan.DEVELOPER] == 10
    assert RateLimiterService.PLAN_LIMITS[BillingPlan.PRO] == 25
    assert RateLimiterService.PLAN_LIMITS[BillingPlan.TEAM] == 50
    assert RateLimiterService.PLAN_LIMITS[BillingPlan.ENTERPRISE] is None


@pytest.mark.asyncio
async def test_rate_limiter_redis_key_format(organization_id):
    """Test that Redis keys are formatted correctly."""
    limiter = RateLimiterService(organization_id=organization_id)
    key = limiter._get_redis_key()

    expected_key = f"rate_limit:org:{organization_id}"
    assert key == expected_key


@pytest.mark.asyncio
@patch("airweave.core.rate_limiter_service.settings")
async def test_rate_limiter_bypassed_in_local_dev(
    mock_settings, organization_id, mock_redis, mock_db_context, mock_crud
):
    """Test that rate limiting is bypassed in local development."""
    mock_settings.LOCAL_DEVELOPMENT = True
    mock_settings.RATE_LIMIT_ENABLED = True

    limiter = RateLimiterService(organization_id=organization_id)

    allowed, retry_after, limit, remaining = await limiter.check_rate_limit()

    # Should bypass all checks
    assert allowed is True
    assert limit == 9999
    assert remaining == 9999

    # Redis should not be called
    mock_redis.client.pipeline.assert_not_called()


@pytest.mark.asyncio
@patch("airweave.core.rate_limiter_service.settings")
async def test_rate_limiter_disabled_via_config(
    mock_settings, organization_id, mock_redis, mock_db_context, mock_crud
):
    """Test that rate limiting can be disabled via config."""
    mock_settings.LOCAL_DEVELOPMENT = False
    mock_settings.RATE_LIMIT_ENABLED = False

    limiter = RateLimiterService(organization_id=organization_id)

    allowed, retry_after, limit, remaining = await limiter.check_rate_limit()

    # Should bypass all checks
    assert allowed is True
    assert limit == 9999

    # Redis should not be called
    mock_redis.client.pipeline.assert_not_called()
