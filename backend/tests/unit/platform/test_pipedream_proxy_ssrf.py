"""Tests for SSRF protection in PipedreamProxyClient."""

from unittest.mock import AsyncMock

import pytest

from airweave.platform.http_client.pipedream_proxy import PipedreamProxyClient
from airweave.platform.utils.ssrf import SSRFViolation


def _make_client() -> PipedreamProxyClient:
    """Create a PipedreamProxyClient with dummy config."""
    return PipedreamProxyClient(
        project_id="proj_test",
        account_id="acct_test",
        external_user_id="user_test",
        environment="development",
        pipedream_token="tok_test",
    )


class TestPipedreamProxySsrf:
    """Verify the proxy client blocks SSRF-dangerous URLs."""

    @pytest.mark.asyncio
    async def test_pipedream_request_blocks_loopback(self):
        client = _make_client()
        client._client = AsyncMock()
        client._get_proxy_headers = AsyncMock(return_value={})

        with pytest.raises(SSRFViolation):
            await client.request("GET", "http://127.0.0.1/")

        client._client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipedream_stream_blocks_loopback(self):
        client = _make_client()
        client._client = AsyncMock()
        client._get_proxy_headers = AsyncMock(return_value={})

        with pytest.raises(SSRFViolation):
            async with client.stream("GET", "http://127.0.0.1/"):
                pass  # pragma: no cover

        client._client.stream.assert_not_called()
