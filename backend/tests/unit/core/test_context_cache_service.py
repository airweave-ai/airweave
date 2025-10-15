"""Tests for context cache service.

Tests the Redis-based caching service for API context data including
organizations, users, and API key mappings.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from airweave.core.context_cache_service import ContextCacheService
from airweave.schemas import Organization, User
from airweave.schemas.billing_period import BillingPeriod, BillingPeriodStatus, BillingTransition
from airweave.schemas.organization_billing import (
    BillingPlan,
    BillingStatus,
    OrganizationBilling,
)


@pytest.fixture
def organization_id():
    """Create a test organization ID."""
    return uuid4()


@pytest.fixture
def user_email():
    """Create a test user email."""
    return "test@example.com"


@pytest.fixture
def api_key():
    """Create a test API key."""
    return "sk_test_1234567890abcdef"


@pytest.fixture
def mock_organization(organization_id):
    """Create a mock organization for testing."""
    from datetime import datetime, timezone

    billing_period = BillingPeriod(
        id=uuid4(),
        organization_id=organization_id,
        period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2024, 2, 1, tzinfo=timezone.utc),
        plan=BillingPlan.PRO,
        status=BillingPeriodStatus.ACTIVE,
        created_from=BillingTransition.INITIAL_SIGNUP,
        stripe_subscription_id="sub_test123",
        stripe_invoice_id=None,
        amount_cents=None,
        currency=None,
        paid_at=None,
        previous_period_id=None,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    billing = OrganizationBilling(
        id=uuid4(),
        organization_id=organization_id,
        billing_plan=BillingPlan.PRO,
        billing_status=BillingStatus.ACTIVE,
        billing_email="billing@test.com",
        stripe_customer_id="cus_test123",
        stripe_subscription_id="sub_test123",
        trial_ends_at=None,
        grace_period_ends_at=None,
        payment_method_added=True,
        current_period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        current_period_end=datetime(2024, 2, 1, tzinfo=timezone.utc),
        cancel_at_period_end=False,
        pending_plan_change=None,
        pending_plan_change_at=None,
        payment_method_id=None,
        last_payment_status=None,
        last_payment_at=None,
        billing_metadata={},
        has_yearly_prepay=False,
        yearly_prepay_started_at=None,
        yearly_prepay_expires_at=None,
        yearly_prepay_amount_cents=None,
        yearly_prepay_coupon_id=None,
        yearly_prepay_payment_intent_id=None,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        current_period=billing_period,
    )

    return Organization(
        id=organization_id,
        name="Test Organization",
        description="Test Description",
        auth0_org_id="auth0|test123",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        org_metadata={},
        enabled_features=[],
        billing=billing,
    )


@pytest.fixture
def mock_user(user_email):
    """Create a mock user for testing."""
    return User(
        id=uuid4(),
        email=user_email,
        full_name="Test User",
        auth0_id="auth0|user123",
        primary_organization_id=uuid4(),
        user_organizations=[],
        is_admin=False,
    )


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch("airweave.core.context_cache_service.redis_client") as mock:
        mock.client = AsyncMock()
        mock.client.get = AsyncMock(return_value=None)
        mock.client.setex = AsyncMock(return_value=True)
        mock.client.delete = AsyncMock(return_value=1)
        yield mock


@pytest.fixture
def cache_service():
    """Create a context cache service instance."""
    return ContextCacheService()


# ============================================================================
# Cache Key Generation Tests
# ============================================================================


def test_org_cache_key_generation(cache_service, organization_id):
    """Test that organization cache keys are formatted correctly."""
    key = cache_service._org_cache_key(organization_id)
    assert key == f"context:org:{organization_id}"


def test_user_cache_key_generation(cache_service, user_email):
    """Test that user cache keys are formatted correctly."""
    key = cache_service._user_cache_key(user_email)
    assert key == f"context:user:{user_email}"


def test_api_key_cache_key_generation(cache_service):
    """Test that API key cache keys are formatted correctly."""
    api_key_hash = "encrypted_key_hash"
    key = cache_service._api_key_cache_key(api_key_hash)
    assert key == f"context:apikey:{api_key_hash}"


# ============================================================================
# Organization Caching Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_organization_cache_hit(
    cache_service, mock_redis, mock_organization
):
    """Test retrieving an organization from cache when it exists."""
    # Setup cache hit
    cached_data = mock_organization.model_dump(mode="json")
    mock_redis.client.get.return_value = json.dumps(cached_data)

    result = await cache_service.get_organization(mock_organization.id)

    assert result is not None
    assert result.id == mock_organization.id
    assert result.name == mock_organization.name
    mock_redis.client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_organization_cache_miss(cache_service, mock_redis, organization_id):
    """Test retrieving an organization from cache when it doesn't exist."""
    # Setup cache miss
    mock_redis.client.get.return_value = None

    result = await cache_service.get_organization(organization_id)

    assert result is None
    mock_redis.client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_organization_redis_error(cache_service, mock_redis, organization_id):
    """Test that Redis errors are handled gracefully during org retrieval."""
    # Simulate Redis error
    mock_redis.client.get.side_effect = Exception("Redis connection error")

    result = await cache_service.get_organization(organization_id)

    # Should return None and not raise exception
    assert result is None


@pytest.mark.asyncio
async def test_get_organization_json_parse_error(
    cache_service, mock_redis, organization_id
):
    """Test that JSON parsing errors are handled gracefully."""
    # Return invalid JSON
    mock_redis.client.get.return_value = "invalid json data"

    result = await cache_service.get_organization(organization_id)

    # Should return None and not raise exception
    assert result is None


@pytest.mark.asyncio
async def test_set_organization_success(cache_service, mock_redis, mock_organization):
    """Test storing an organization in cache successfully."""
    result = await cache_service.set_organization(mock_organization)

    assert result is True
    mock_redis.client.setex.assert_called_once()

    # Verify the call arguments
    call_args = mock_redis.client.setex.call_args
    cache_key = call_args[0][0]
    ttl = call_args[0][1]
    cached_data = call_args[0][2]

    assert cache_key == f"context:org:{mock_organization.id}"
    assert ttl == ContextCacheService.ORG_TTL
    assert json.loads(cached_data)["id"] == str(mock_organization.id)


@pytest.mark.asyncio
async def test_set_organization_redis_error(cache_service, mock_redis, mock_organization):
    """Test that Redis errors during org caching are handled gracefully."""
    # Simulate Redis error
    mock_redis.client.setex.side_effect = Exception("Redis connection error")

    result = await cache_service.set_organization(mock_organization)

    # Should return False and not raise exception
    assert result is False


# ============================================================================
# User Caching Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_user_cache_hit(cache_service, mock_redis, mock_user):
    """Test retrieving a user from cache when it exists."""
    # Setup cache hit
    cached_data = mock_user.model_dump(mode="json")
    mock_redis.client.get.return_value = json.dumps(cached_data)

    result = await cache_service.get_user(mock_user.email)

    assert result is not None
    assert result.id == mock_user.id
    assert result.email == mock_user.email
    assert result.full_name == mock_user.full_name
    mock_redis.client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_cache_miss(cache_service, mock_redis, user_email):
    """Test retrieving a user from cache when it doesn't exist."""
    # Setup cache miss
    mock_redis.client.get.return_value = None

    result = await cache_service.get_user(user_email)

    assert result is None
    mock_redis.client.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_redis_error(cache_service, mock_redis, user_email):
    """Test that Redis errors are handled gracefully during user retrieval."""
    # Simulate Redis error
    mock_redis.client.get.side_effect = Exception("Redis connection error")

    result = await cache_service.get_user(user_email)

    # Should return None and not raise exception
    assert result is None


@pytest.mark.asyncio
async def test_set_user_success(cache_service, mock_redis, mock_user):
    """Test storing a user in cache successfully."""
    result = await cache_service.set_user(mock_user)

    assert result is True
    mock_redis.client.setex.assert_called_once()

    # Verify the call arguments
    call_args = mock_redis.client.setex.call_args
    cache_key = call_args[0][0]
    ttl = call_args[0][1]
    cached_data = call_args[0][2]

    assert cache_key == f"context:user:{mock_user.email}"
    assert ttl == ContextCacheService.USER_TTL
    assert json.loads(cached_data)["email"] == mock_user.email


@pytest.mark.asyncio
async def test_set_user_redis_error(cache_service, mock_redis, mock_user):
    """Test that Redis errors during user caching are handled gracefully."""
    # Simulate Redis error
    mock_redis.client.setex.side_effect = Exception("Redis connection error")

    result = await cache_service.set_user(mock_user)

    # Should return False and not raise exception
    assert result is False


# ============================================================================
# API Key Caching Tests
# ============================================================================


@pytest.mark.asyncio
@patch("airweave.core.context_cache_service.credentials")
async def test_get_api_key_org_id_cache_hit(
    mock_credentials, cache_service, mock_redis, api_key, organization_id
):
    """Test retrieving API key org mapping from cache when it exists."""
    # Setup encryption mock
    encrypted_key = "encrypted_api_key_hash"
    mock_credentials.encrypt.return_value = encrypted_key

    # Setup cache hit - Redis returns bytes
    mock_redis.client.get.return_value = str(organization_id).encode("utf-8")

    result = await cache_service.get_api_key_org_id(api_key)

    assert result == organization_id
    mock_credentials.encrypt.assert_called_once_with({"key": api_key})
    mock_redis.client.get.assert_called_once()


@pytest.mark.asyncio
@patch("airweave.core.context_cache_service.credentials")
async def test_get_api_key_org_id_cache_miss(
    mock_credentials, cache_service, mock_redis, api_key
):
    """Test retrieving API key org mapping from cache when it doesn't exist."""
    # Setup encryption mock
    encrypted_key = "encrypted_api_key_hash"
    mock_credentials.encrypt.return_value = encrypted_key

    # Setup cache miss
    mock_redis.client.get.return_value = None

    result = await cache_service.get_api_key_org_id(api_key)

    assert result is None
    mock_redis.client.get.assert_called_once()


@pytest.mark.asyncio
@patch("airweave.core.context_cache_service.credentials")
async def test_get_api_key_org_id_redis_error(
    mock_credentials, cache_service, mock_redis, api_key
):
    """Test that Redis errors are handled gracefully during API key retrieval."""
    # Setup encryption mock
    mock_credentials.encrypt.return_value = "encrypted_key"

    # Simulate Redis error
    mock_redis.client.get.side_effect = Exception("Redis connection error")

    result = await cache_service.get_api_key_org_id(api_key)

    # Should return None and not raise exception
    assert result is None


@pytest.mark.asyncio
@patch("airweave.core.context_cache_service.credentials")
async def test_set_api_key_org_id_success(
    mock_credentials, cache_service, mock_redis, api_key, organization_id
):
    """Test storing API key org mapping in cache successfully."""
    # Setup encryption mock
    encrypted_key = "encrypted_api_key_hash"
    mock_credentials.encrypt.return_value = encrypted_key

    result = await cache_service.set_api_key_org_id(api_key, organization_id)

    assert result is True
    mock_credentials.encrypt.assert_called_once_with({"key": api_key})
    mock_redis.client.setex.assert_called_once()

    # Verify the call arguments
    call_args = mock_redis.client.setex.call_args
    cache_key = call_args[0][0]
    ttl = call_args[0][1]
    cached_org_id = call_args[0][2]

    assert cache_key == f"context:apikey:{encrypted_key}"
    assert ttl == ContextCacheService.API_KEY_TTL
    assert UUID(cached_org_id) == organization_id


@pytest.mark.asyncio
@patch("airweave.core.context_cache_service.credentials")
async def test_set_api_key_org_id_redis_error(
    mock_credentials, cache_service, mock_redis, api_key, organization_id
):
    """Test that Redis errors during API key caching are handled gracefully."""
    # Setup encryption mock
    mock_credentials.encrypt.return_value = "encrypted_key"

    # Simulate Redis error
    mock_redis.client.setex.side_effect = Exception("Redis connection error")

    result = await cache_service.set_api_key_org_id(api_key, organization_id)

    # Should return False and not raise exception
    assert result is False


@pytest.mark.asyncio
@patch("airweave.core.context_cache_service.credentials")
async def test_invalidate_api_key_success(
    mock_credentials, cache_service, mock_redis, api_key
):
    """Test invalidating API key cache successfully."""
    # Setup encryption mock
    encrypted_key = "encrypted_api_key_hash"
    mock_credentials.encrypt.return_value = encrypted_key

    result = await cache_service.invalidate_api_key(api_key)

    assert result is True
    mock_credentials.encrypt.assert_called_once_with({"key": api_key})
    mock_redis.client.delete.assert_called_once_with(
        f"context:apikey:{encrypted_key}"
    )


@pytest.mark.asyncio
@patch("airweave.core.context_cache_service.credentials")
async def test_invalidate_api_key_redis_error(
    mock_credentials, cache_service, mock_redis, api_key
):
    """Test that Redis errors during API key invalidation are handled gracefully."""
    # Setup encryption mock
    mock_credentials.encrypt.return_value = "encrypted_key"

    # Simulate Redis error
    mock_redis.client.delete.side_effect = Exception("Redis connection error")

    result = await cache_service.invalidate_api_key(api_key)

    # Should return False and not raise exception
    assert result is False


# ============================================================================
# TTL Configuration Tests
# ============================================================================


def test_cache_ttl_constants():
    """Test that cache TTL constants are set correctly."""
    assert ContextCacheService.ORG_TTL == 300  # 5 minutes
    assert ContextCacheService.USER_TTL == 180  # 3 minutes
    assert ContextCacheService.API_KEY_TTL == 600  # 10 minutes


# ============================================================================
# Logger Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cache_service_with_custom_logger(mock_redis):
    """Test that cache service can be initialized with a custom logger."""
    mock_logger = MagicMock()
    cache_service = ContextCacheService(logger=mock_logger)

    assert cache_service.logger == mock_logger


@pytest.mark.asyncio
async def test_cache_service_uses_default_logger_when_none_provided(mock_redis):
    """Test that cache service uses default logger when none is provided."""
    cache_service = ContextCacheService()

    assert cache_service.logger is not None


# ============================================================================
# Global Instance Test
# ============================================================================


def test_global_context_cache_instance():
    """Test that the global context_cache instance is available."""
    from airweave.core.context_cache_service import context_cache

    assert isinstance(context_cache, ContextCacheService)
