"""Unit tests for middleware.py.

Covers exception handlers and the cache-control middleware.
"""

from unittest.mock import MagicMock

import pytest
from starlette.responses import Response

from airweave.api.middleware import (
    airweave_exception_handler,
    cache_control_middleware,
)
from airweave.core.exceptions import AirweaveException, TokenRefreshError

# ---------------------------------------------------------------------------
# Exception handler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_refresh_error_returns_401():
    response = await airweave_exception_handler(MagicMock(), TokenRefreshError("token expired"))
    assert response.status_code == 401
    assert b"token expired" in response.body


@pytest.mark.asyncio
async def test_unmapped_airweave_exception_returns_500():
    response = await airweave_exception_handler(MagicMock(), AirweaveException("unexpected"))
    assert response.status_code == 500
    assert b"unexpected" in response.body


# ---------------------------------------------------------------------------
# Cache-control middleware tests
# ---------------------------------------------------------------------------


def _make_request(path: str) -> MagicMock:
    """Build a mock request with the given URL path."""
    request = MagicMock()
    request.url.path = path
    return request


def _make_response(headers: dict[str, str] | None = None) -> Response:
    """Build a real Starlette Response so MutableHeaders behaves correctly."""
    resp = Response(content="ok")
    if headers:
        for key, value in headers.items():
            resp.headers[key] = value
    return resp


@pytest.mark.asyncio
async def test_cache_control_set_on_normal_response():
    resp = _make_response()

    async def call_next(_request):
        return resp

    result = await cache_control_middleware(_make_request("/users"), call_next)
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["pragma"] == "no-cache"


@pytest.mark.asyncio
async def test_cache_control_preserves_no_transform():
    resp = _make_response({"Cache-Control": "no-cache, no-transform"})

    async def call_next(_request):
        return resp

    result = await cache_control_middleware(_make_request("/sync/subscribe"), call_next)
    assert result.headers["cache-control"] == "no-store, no-transform"
    assert result.headers["pragma"] == "no-cache"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/favicon.ico",
        "/redoc",
        "/",
    ],
)
async def test_cache_control_exempt_paths(path: str):
    sentinel = _make_response()

    async def call_next(_request):
        return sentinel

    result = await cache_control_middleware(_make_request(path), call_next)
    assert result is sentinel
    assert "cache-control" not in result.headers


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/health/ready", "/docs/oauth2-redirect"])
async def test_cache_control_exempt_subpaths(path: str):
    sentinel = _make_response()

    async def call_next(_request):
        return sentinel

    result = await cache_control_middleware(_make_request(path), call_next)
    assert result is sentinel
    assert "cache-control" not in result.headers


@pytest.mark.asyncio
async def test_cache_control_overwrites_weaker_policy():
    resp = _make_response({"Cache-Control": "no-cache"})

    async def call_next(_request):
        return resp

    result = await cache_control_middleware(_make_request("/api-keys"), call_next)
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["pragma"] == "no-cache"
