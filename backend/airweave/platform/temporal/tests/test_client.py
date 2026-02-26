"""Tests for TemporalClient.get_client() runtime forwarding and singleton."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.temporal.client import TemporalClient


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the cached client between tests."""
    TemporalClient._client = None
    yield
    TemporalClient._client = None


@patch("airweave.platform.temporal.client.Client.connect", new_callable=AsyncMock)
async def test_get_client_without_runtime(mock_connect):
    """get_client() without runtime does not pass runtime kwarg."""
    mock_connect.return_value = MagicMock()

    await TemporalClient.get_client()

    mock_connect.assert_awaited_once()
    _, kwargs = mock_connect.call_args
    assert "runtime" not in kwargs


@patch("airweave.platform.temporal.client.Client.connect", new_callable=AsyncMock)
async def test_get_client_with_runtime(mock_connect):
    """get_client(runtime=r) forwards runtime to Client.connect()."""
    mock_connect.return_value = MagicMock()
    sentinel = MagicMock(name="runtime")

    await TemporalClient.get_client(runtime=sentinel)

    mock_connect.assert_awaited_once()
    _, kwargs = mock_connect.call_args
    assert kwargs["runtime"] is sentinel


@patch("airweave.platform.temporal.client.Client.connect", new_callable=AsyncMock)
async def test_get_client_caches_singleton(mock_connect):
    """Repeated calls return the cached client without reconnecting."""
    mock_connect.return_value = MagicMock()

    first = await TemporalClient.get_client()
    second = await TemporalClient.get_client()

    assert first is second
    assert mock_connect.await_count == 1


async def test_close_resets_cached_client():
    """close() clears the singleton so the next get_client() reconnects."""
    TemporalClient._client = MagicMock()

    await TemporalClient.close()

    assert TemporalClient._client is None


async def test_close_noop_when_no_client():
    """close() is safe to call when no client has been created."""
    assert TemporalClient._client is None

    await TemporalClient.close()  # should not raise

    assert TemporalClient._client is None
