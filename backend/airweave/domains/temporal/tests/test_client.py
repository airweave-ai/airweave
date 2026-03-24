"""Tests for the temporal client module-level singleton."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import airweave.domains.temporal.client as temporal_client_mod


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the cached client between tests."""
    temporal_client_mod._client = None
    yield
    temporal_client_mod._client = None


@patch("airweave.domains.temporal.client.Client.connect", new_callable=AsyncMock)
async def test_get_client_without_runtime(mock_connect):
    """get_client() without runtime passes runtime=None."""
    mock_connect.return_value = MagicMock()

    await temporal_client_mod.get_client()

    mock_connect.assert_awaited_once()
    _, kwargs = mock_connect.call_args
    assert kwargs.get("runtime") is None


@patch("airweave.domains.temporal.client.Client.connect", new_callable=AsyncMock)
async def test_get_client_with_runtime(mock_connect):
    """get_client(runtime=r) forwards runtime to Client.connect()."""
    mock_connect.return_value = MagicMock()
    sentinel = MagicMock(name="runtime")

    await temporal_client_mod.get_client(runtime=sentinel)

    mock_connect.assert_awaited_once()
    _, kwargs = mock_connect.call_args
    assert kwargs["runtime"] is sentinel


@patch("airweave.domains.temporal.client.Client.connect", new_callable=AsyncMock)
async def test_get_client_caches_singleton(mock_connect):
    """Repeated calls return the cached client without reconnecting."""
    mock_connect.return_value = MagicMock()

    first = await temporal_client_mod.get_client()
    second = await temporal_client_mod.get_client()

    assert first is second
    assert mock_connect.await_count == 1


async def test_close_resets_cached_client():
    """close() clears the singleton so the next get_client() reconnects."""
    temporal_client_mod._client = MagicMock()

    await temporal_client_mod.close()

    assert temporal_client_mod._client is None


async def test_close_noop_when_no_client():
    """close() is safe to call when no client has been created."""
    assert temporal_client_mod._client is None
    await temporal_client_mod.close()
    assert temporal_client_mod._client is None


def test_get_cached_client_returns_none_initially():
    """get_cached_client() returns None before any connection."""
    assert temporal_client_mod.get_cached_client() is None


def test_get_cached_client_returns_client():
    """get_cached_client() returns the cached client."""
    sentinel = MagicMock()
    temporal_client_mod._client = sentinel
    assert temporal_client_mod.get_cached_client() is sentinel
