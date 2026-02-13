"""Unit tests for exception handlers in middleware.py.

Calls handlers directly to cover mappings that no endpoint currently triggers.
"""

from unittest.mock import MagicMock

import pytest

from airweave.api.middleware import airweave_exception_handler
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
