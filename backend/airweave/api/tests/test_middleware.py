"""Unit tests for exception handlers in middleware.py.

Calls handlers directly to cover mappings that no endpoint currently triggers.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.api.middleware import airweave_exception_handler, exception_logging_middleware
from airweave.core.exceptions import AirweaveException, TokenRefreshError


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


@pytest.mark.asyncio
async def test_exception_logging_middleware_masks_details_in_production():
    """In production, unhandled exceptions must not leak class names or messages."""

    async def _raise(_request):
        raise ValueError("badly formed hexadecimal UUID string")

    request = MagicMock()
    with (
        patch("airweave.api.middleware.settings") as mock_settings,
    ):
        mock_settings.LOCAL_CURSOR_DEVELOPMENT = False
        mock_settings.DEBUG = False

        response = await exception_logging_middleware(request, _raise)

    assert response.status_code == 500
    body = json.loads(response.body)
    assert body["detail"] == "Internal Server Error"
    assert "ValueError" not in body["detail"]
    assert "trace" not in body


@pytest.mark.asyncio
async def test_exception_logging_middleware_shows_details_in_debug():
    """In dev/debug mode, full exception details and traces should be present."""

    async def _raise(_request):
        raise ValueError("badly formed hexadecimal UUID string")

    request = MagicMock()
    with (
        patch("airweave.api.middleware.settings") as mock_settings,
    ):
        mock_settings.LOCAL_CURSOR_DEVELOPMENT = True
        mock_settings.DEBUG = False

        response = await exception_logging_middleware(request, _raise)

    assert response.status_code == 500
    body = json.loads(response.body)
    assert "ValueError" in body["detail"]
    assert "badly formed" in body["detail"]
    assert "trace" in body
