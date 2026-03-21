"""Tests for the Asana source — v2 contract, pagination, exception handling."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from airweave.domains.sources.exceptions import SourceAuthError, SourceError
from airweave.platform.configs.config import AsanaConfig
from airweave.platform.sources.asana import AsanaSource, _ResultTooLarge


def _mock_auth():
    auth = AsyncMock()
    auth.get_token = AsyncMock(return_value="test-token")
    auth.force_refresh = AsyncMock(return_value="refreshed-token")
    auth.supports_refresh = True
    auth.provider_kind = "oauth"
    return auth


def _mock_http_client():
    client = AsyncMock()
    client.get = AsyncMock()
    client.head = AsyncMock()
    return client


def _mock_logger():
    return MagicMock()


def _ok_response(data: dict) -> httpx.Response:
    import json

    return httpx.Response(
        status_code=200,
        content=json.dumps(data).encode(),
        request=httpx.Request("GET", "https://app.asana.com/api/1.0/test"),
    )


class TestCreateContract:
    """Tests for AsanaSource.create() — the v2 contract."""

    @pytest.mark.asyncio
    async def test_create_returns_instance(self):
        source = await AsanaSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=_mock_http_client(),
            config=AsanaConfig(),
        )
        assert isinstance(source, AsanaSource)

    @pytest.mark.asyncio
    async def test_create_requires_auth(self):
        with pytest.raises(TypeError):
            await AsanaSource.create(
                logger=_mock_logger(),
                http_client=_mock_http_client(),
                config=AsanaConfig(),
            )

    @pytest.mark.asyncio
    async def test_create_requires_logger(self):
        with pytest.raises(TypeError):
            await AsanaSource.create(
                auth=_mock_auth(),
                http_client=_mock_http_client(),
                config=AsanaConfig(),
            )

    @pytest.mark.asyncio
    async def test_create_requires_http_client(self):
        with pytest.raises(TypeError):
            await AsanaSource.create(
                auth=_mock_auth(),
                logger=_mock_logger(),
                config=AsanaConfig(),
            )

    @pytest.mark.asyncio
    async def test_auth_accessible_via_property(self):
        auth = _mock_auth()
        source = await AsanaSource.create(
            auth=auth,
            logger=_mock_logger(),
            http_client=_mock_http_client(),
            config=AsanaConfig(),
        )
        assert source.auth is auth

    @pytest.mark.asyncio
    async def test_http_client_accessible_via_property(self):
        client = _mock_http_client()
        source = await AsanaSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=AsanaConfig(),
        )
        assert source.http_client is client


class TestGet:
    """Tests for AsanaSource._get() — auth, retry, 401 refresh."""

    @pytest.mark.asyncio
    async def test_get_adds_bearer_header(self):
        client = _mock_http_client()
        client.get.return_value = _ok_response({"data": []})

        source = await AsanaSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=AsanaConfig(),
        )
        await source._get("https://app.asana.com/api/1.0/workspaces")

        call_kwargs = client.get.call_args
        assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer test-token"

    @pytest.mark.asyncio
    async def test_get_refreshes_on_401(self):
        client = _mock_http_client()
        client.get.side_effect = [
            httpx.Response(
                status_code=401,
                request=httpx.Request("GET", "https://app.asana.com/api/1.0/test"),
            ),
            _ok_response({"data": []}),
        ]
        auth = _mock_auth()

        source = await AsanaSource.create(
            auth=auth,
            logger=_mock_logger(),
            http_client=client,
            config=AsanaConfig(),
        )
        result = await source._get("https://app.asana.com/api/1.0/test")

        auth.force_refresh.assert_called_once()
        assert result == {"data": []}

    @pytest.mark.asyncio
    async def test_get_detects_result_too_large(self):
        client = _mock_http_client()
        client.get.return_value = httpx.Response(
            status_code=400,
            text="The result is too large",
            request=httpx.Request("GET", "https://app.asana.com/api/1.0/tasks"),
        )

        source = await AsanaSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=AsanaConfig(),
        )
        with pytest.raises(_ResultTooLarge):
            await source._get("https://app.asana.com/api/1.0/tasks")

    @pytest.mark.asyncio
    async def test_get_raises_source_auth_on_persistent_401(self):
        client = _mock_http_client()
        resp_401 = httpx.Response(
            status_code=401,
            request=httpx.Request("GET", "https://app.asana.com/api/1.0/test"),
        )
        client.get.return_value = resp_401

        source = await AsanaSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=AsanaConfig(),
        )
        with pytest.raises(SourceAuthError):
            await source._get("https://app.asana.com/api/1.0/test")


class TestPaginate:
    """Tests for AsanaSource._paginate() — recursive limit reduction."""

    @pytest.mark.asyncio
    async def test_paginate_yields_all_items(self):
        client = _mock_http_client()
        client.get.side_effect = [
            _ok_response({
                "data": [{"gid": "1"}, {"gid": "2"}],
                "next_page": {"offset": "abc"},
            }),
            _ok_response({
                "data": [{"gid": "3"}],
                "next_page": None,
            }),
        ]

        source = await AsanaSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=AsanaConfig(),
        )
        items = [item async for item in source._paginate("https://url", "gid,name")]
        assert [i["gid"] for i in items] == ["1", "2", "3"]

    @pytest.mark.asyncio
    async def test_paginate_retries_with_smaller_limit_on_too_large(self):
        client = _mock_http_client()
        client.get.side_effect = [
            httpx.Response(
                status_code=400,
                text="The result is too large",
                request=httpx.Request("GET", "https://url"),
            ),
            _ok_response({"data": [{"gid": "1"}], "next_page": None}),
        ]

        source = await AsanaSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=AsanaConfig(),
        )
        items = [item async for item in source._paginate("https://url", "gid,name", limit=100)]
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_paginate_raises_at_min_limit(self):
        client = _mock_http_client()
        client.get.return_value = httpx.Response(
            status_code=400,
            text="The result is too large",
            request=httpx.Request("GET", "https://url"),
        )

        source = await AsanaSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=client,
            config=AsanaConfig(),
        )
        with pytest.raises(_ResultTooLarge):
            async for _ in source._paginate("https://url", "gid", limit=10, _min_limit=10):
                pass
