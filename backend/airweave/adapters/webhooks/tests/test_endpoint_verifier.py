"""Unit tests for HttpEndpointVerifier.

Uses unittest.mock to patch httpx.AsyncClient so we can simulate
success, timeout, connection error, and general HTTP error scenarios
without making real network calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from airweave.adapters.webhooks.endpoint_verifier import HttpEndpointVerifier
from airweave.domains.webhooks.types import WebhooksError


@pytest.fixture
def verifier() -> HttpEndpointVerifier:
    return HttpEndpointVerifier()


class TestHttpEndpointVerifier:
    """Tests for HttpEndpointVerifier.verify()."""

    @pytest.mark.asyncio
    async def test_successful_verification(self, verifier):
        """Any HTTP response (even 4xx/5xx) counts as reachable."""
        mock_response = MagicMock()
        mock_response.status_code = 403  # Server rejects but is reachable

        with patch("airweave.adapters.webhooks.endpoint_verifier.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(return_value=mock_response)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # Should not raise
            await verifier.verify("https://example.com/webhook")
            mock_client.head.assert_called_once_with("https://example.com/webhook")

    @pytest.mark.asyncio
    async def test_timeout_raises_webhooks_error(self, verifier):
        with patch("airweave.adapters.webhooks.endpoint_verifier.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(WebhooksError) as exc_info:
                await verifier.verify("https://slow.example.com/webhook")

            assert exc_info.value.status_code == 400
            assert "5 seconds" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_connection_error_raises_webhooks_error(self, verifier):
        with patch("airweave.adapters.webhooks.endpoint_verifier.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(side_effect=httpx.ConnectError("DNS failure"))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(WebhooksError) as exc_info:
                await verifier.verify("https://nonexistent.example.com/webhook")

            assert exc_info.value.status_code == 400
            assert "Could not connect" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_generic_http_error_raises_webhooks_error(self, verifier):
        with patch("airweave.adapters.webhooks.endpoint_verifier.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(side_effect=httpx.HTTPError("something broke"))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(WebhooksError) as exc_info:
                await verifier.verify("https://broken.example.com/webhook")

            assert exc_info.value.status_code == 400
            assert "Failed to reach endpoint" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_custom_timeout_passed_to_client(self, verifier):
        """Verify the timeout parameter is forwarded to httpx.AsyncClient."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("airweave.adapters.webhooks.endpoint_verifier.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.head = AsyncMock(return_value=mock_response)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await verifier.verify("https://example.com/webhook", timeout=10.0)
            mock_cls.assert_called_once_with(timeout=10.0)
