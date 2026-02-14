"""Unit tests for exception handlers in middleware.py.

Calls handlers directly to cover mappings that no endpoint currently triggers.
"""

from unittest.mock import MagicMock

import pytest

from airweave.api.middleware import airweave_exception_handler
from airweave.core.exceptions import (
    AirweaveException,
    BadGatewayError,
    BadRequestError,
    TokenRefreshError,
)


@pytest.mark.asyncio
async def test_bad_request_error_returns_400():
    response = await airweave_exception_handler(MagicMock(), BadRequestError("invalid input"))
    assert response.status_code == 400
    assert b"invalid input" in response.body


@pytest.mark.asyncio
async def test_bad_request_subclass_returns_400():
    """Subclasses of BadRequestError also map to 400."""
    from airweave.domains.credentials.exceptions import InvalidCredentialsError

    response = await airweave_exception_handler(MagicMock(), InvalidCredentialsError("bad creds"))
    assert response.status_code == 400
    assert b"bad creds" in response.body


@pytest.mark.asyncio
async def test_token_refresh_error_returns_401():
    response = await airweave_exception_handler(MagicMock(), TokenRefreshError("token expired"))
    assert response.status_code == 401
    assert b"token expired" in response.body


@pytest.mark.asyncio
async def test_bad_gateway_error_returns_502():
    response = await airweave_exception_handler(MagicMock(), BadGatewayError("upstream failed"))
    assert response.status_code == 502
    assert b"upstream failed" in response.body


@pytest.mark.asyncio
async def test_bad_gateway_subclass_returns_502():
    """Subclasses of BadGatewayError also map to 502."""
    from airweave.domains.oauth.exceptions import OAuthTokenExchangeError

    response = await airweave_exception_handler(MagicMock(), OAuthTokenExchangeError("provider down"))
    assert response.status_code == 502
    assert b"provider down" in response.body


@pytest.mark.asyncio
async def test_unmapped_airweave_exception_returns_500():
    response = await airweave_exception_handler(MagicMock(), AirweaveException("unexpected"))
    assert response.status_code == 500
    assert b"unexpected" in response.body
