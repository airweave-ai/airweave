"""Tests for AirweaveHttpClient wrapper.

Tests the HTTP client wrapper that adds rate limiting to source API calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from airweave.core.exceptions import SourceRateLimitExceededException
from airweave.core.logging import logger
from airweave.platform.http_client.airweave_client import AirweaveHttpClient


@pytest.fixture
def org_id():
    """Create a test organization ID."""
    return uuid4()


@pytest.fixture
def connection_id():
    """Create a test source connection ID."""
    return uuid4()


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx.AsyncClient."""
    mock = MagicMock()
    mock.request = AsyncMock(return_value=MagicMock(status_code=200))
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock()
    mock.is_closed = False
    mock.aclose = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_airweave_client_allows_request_under_limit(org_id, mock_httpx_client):
    """Test that requests under limit are allowed and delegated to wrapped client."""
    with patch(
        "airweave.platform.http_client.airweave_client.source_rate_limiter"
    ) as mock_limiter:
        mock_limiter.check_and_increment = AsyncMock()  # No exception

        client = AirweaveHttpClient(
            wrapped_client=mock_httpx_client,
            org_id=org_id,
            source_short_name="google_drive",
            feature_flag_enabled=True,
            logger=logger,
        )

        response = await client.request("GET", "https://api.example.com/data")

        # Verify rate limiter was called
        mock_limiter.check_and_increment.assert_called_once_with(
            org_id=org_id,
            source_short_name="google_drive",
            source_connection_id=None,
        )

        # Verify wrapped client was called
        mock_httpx_client.request.assert_called_once_with(
            "GET", "https://api.example.com/data"
        )


@pytest.mark.asyncio
async def test_airweave_client_converts_exception_to_429(org_id, mock_httpx_client):
    """Test that SourceRateLimitExceededException is converted to HTTP 429."""
    with patch(
        "airweave.platform.http_client.airweave_client.source_rate_limiter"
    ) as mock_limiter:
        # Simulate rate limit exceeded
        mock_limiter.check_and_increment = AsyncMock(
            side_effect=SourceRateLimitExceededException(
                retry_after=30.0, source_short_name="google_drive"
            )
        )

        client = AirweaveHttpClient(
            wrapped_client=mock_httpx_client,
            org_id=org_id,
            source_short_name="google_drive",
            feature_flag_enabled=True,
            logger=logger,
        )

        # Should raise httpx.HTTPStatusError with 429 status
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.request("GET", "https://api.example.com/data")

        # Verify it's a 429 error
        assert exc_info.value.response.status_code == 429
        assert "Retry-After" in exc_info.value.response.headers
        assert exc_info.value.response.headers["Retry-After"] == "30"

        # Verify wrapped client was NOT called
        mock_httpx_client.request.assert_not_called()


@pytest.mark.asyncio
async def test_airweave_client_delegates_http_methods(org_id, mock_httpx_client):
    """Test that all HTTP methods are delegated to wrapped client."""
    with patch(
        "airweave.platform.http_client.airweave_client.source_rate_limiter"
    ) as mock_limiter:
        mock_limiter.check_and_increment = AsyncMock()

        client = AirweaveHttpClient(
            wrapped_client=mock_httpx_client,
            org_id=org_id,
            source_short_name="google_drive",
            feature_flag_enabled=True,
            logger=logger,
        )

        # Test all HTTP methods
        await client.get("https://api.example.com/data")
        await client.post("https://api.example.com/data", json={"key": "value"})
        await client.put("https://api.example.com/data")
        await client.delete("https://api.example.com/data")
        await client.patch("https://api.example.com/data")
        await client.head("https://api.example.com/data")
        await client.options("https://api.example.com/data")

        # Verify all methods were delegated
        assert mock_httpx_client.request.call_count == 7


@pytest.mark.asyncio
async def test_airweave_client_context_manager(org_id, mock_httpx_client):
    """Test that context manager is properly delegated."""
    with patch(
        "airweave.platform.http_client.airweave_client.source_rate_limiter"
    ) as mock_limiter:
        mock_limiter.check_and_increment = AsyncMock()

        client = AirweaveHttpClient(
            wrapped_client=mock_httpx_client,
            org_id=org_id,
            source_short_name="google_drive",
            feature_flag_enabled=True,
            logger=logger,
        )

        async with client as c:
            await c.get("https://api.example.com/data")

        # Verify context manager methods were called
        mock_httpx_client.__aenter__.assert_called_once()
        mock_httpx_client.__aexit__.assert_called_once()


@pytest.mark.asyncio
async def test_airweave_client_connection_level_limiting(org_id, connection_id, mock_httpx_client):
    """Test connection-level rate limiting (e.g., Notion per-user)."""
    with patch(
        "airweave.platform.http_client.airweave_client.source_rate_limiter"
    ) as mock_limiter:
        mock_limiter.check_and_increment = AsyncMock()

        client = AirweaveHttpClient(
            wrapped_client=mock_httpx_client,
            org_id=org_id,
            source_short_name="notion",
            source_connection_id=connection_id,
            feature_flag_enabled=True,
            logger=logger,
        )

        await client.get("https://api.notion.com/v1/users/me")

        # Verify rate limiter was called with connection ID
        # Limiter reads rate_limit_level from Source table internally
        mock_limiter.check_and_increment.assert_called_once_with(
            org_id=org_id,
            source_short_name="notion",
            source_connection_id=connection_id,
        )


@pytest.mark.asyncio
async def test_airweave_client_skips_check_when_feature_disabled(org_id, mock_httpx_client):
    """Test that rate limit check is skipped when feature flag is disabled."""
    with patch(
        "airweave.platform.http_client.airweave_client.source_rate_limiter"
    ) as mock_limiter:
        mock_limiter.check_and_increment = AsyncMock()

        client = AirweaveHttpClient(
            wrapped_client=mock_httpx_client,
            org_id=org_id,
            source_short_name="google_drive",
            feature_flag_enabled=False,  # Feature disabled
            logger=logger,
        )

        await client.get("https://api.example.com/data")

        # Verify rate limiter was NOT called
        mock_limiter.check_and_increment.assert_not_called()

        # Verify wrapped client WAS called
        mock_httpx_client.request.assert_called_once()


@pytest.mark.asyncio
async def test_airweave_client_checks_pipedream_proxy_limit(org_id):
    """Test Pipedream proxy limit checked when using PipedreamProxyClient."""
    from airweave.platform.http_client.pipedream_proxy import PipedreamProxyClient

    # Mock PipedreamProxyClient
    mock_pipedream = MagicMock(spec=PipedreamProxyClient)
    mock_pipedream.request = AsyncMock(return_value=MagicMock(status_code=200))

    with patch(
        "airweave.platform.http_client.airweave_client.source_rate_limiter"
    ) as mock_limiter:
        mock_limiter.check_pipedream_proxy_limit = AsyncMock()
        mock_limiter.check_and_increment = AsyncMock()

        client = AirweaveHttpClient(
            wrapped_client=mock_pipedream,
            org_id=org_id,
            source_short_name="google_drive",
            feature_flag_enabled=True,
            logger=logger,
        )

        await client.get("https://api.example.com/data")

        # Verify BOTH checks called in order
        mock_limiter.check_pipedream_proxy_limit.assert_called_once_with(org_id)
        mock_limiter.check_and_increment.assert_called_once()


@pytest.mark.asyncio
async def test_airweave_client_skips_pipedream_check_for_regular_httpx(org_id, mock_httpx_client):
    """Test Pipedream check skipped for regular httpx.AsyncClient."""
    with patch(
        "airweave.platform.http_client.airweave_client.source_rate_limiter"
    ) as mock_limiter:
        mock_limiter.check_pipedream_proxy_limit = AsyncMock()
        mock_limiter.check_and_increment = AsyncMock()

        client = AirweaveHttpClient(
            wrapped_client=mock_httpx_client,  # NOT PipedreamProxyClient
            org_id=org_id,
            source_short_name="google_drive",
            feature_flag_enabled=True,
            logger=logger,
        )

        await client.get("https://api.example.com/data")

        # Pipedream check NOT called
        mock_limiter.check_pipedream_proxy_limit.assert_not_called()
        # Source check WAS called
        mock_limiter.check_and_increment.assert_called_once()


@pytest.mark.asyncio
async def test_pipedream_proxy_limit_exceeded(org_id):
    """Test Pipedream proxy limit raises 429 with correct message."""
    from airweave.platform.http_client.pipedream_proxy import PipedreamProxyClient

    mock_pipedream = MagicMock(spec=PipedreamProxyClient)

    with patch(
        "airweave.platform.http_client.airweave_client.source_rate_limiter"
    ) as mock_limiter:
        mock_limiter.check_pipedream_proxy_limit = AsyncMock(
            side_effect=SourceRateLimitExceededException(
                retry_after=180.0, source_short_name="pipedream_proxy"
            )
        )

        client = AirweaveHttpClient(
            wrapped_client=mock_pipedream,
            org_id=org_id,
            source_short_name="google_drive",
            feature_flag_enabled=True,
            logger=logger,
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.get("https://api.example.com/data")

        assert exc_info.value.response.status_code == 429
        assert "Pipedream proxy rate limit exceeded" in str(exc_info.value)
        assert "1000 req/5min org-wide" in str(exc_info.value)

