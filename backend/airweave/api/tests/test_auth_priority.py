"""Test authentication priority: system > API key > Auth0."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from airweave.api.context_resolver import AuthResult, ContextResolver
from airweave.core.shared_models import AuthMethod


def _make_resolver() -> ContextResolver:
    return ContextResolver(
        cache=AsyncMock(),
        rate_limiter=AsyncMock(),
        user_repo=AsyncMock(),
        api_key_repo=AsyncMock(),
        org_repo=AsyncMock(),
    )


def _fake_request() -> MagicMock:
    request = MagicMock(spec=Request)
    request.url.path = "/test"
    request.headers = {}
    request.client = MagicMock(host="127.0.0.1")
    return request


@pytest.mark.asyncio
async def test_system_auth_beats_api_key_when_auth_disabled():
    """When AUTH_ENABLED=False, system auth wins even if an API key is present."""
    resolver = _make_resolver()
    db = AsyncMock()
    request = _fake_request()

    system_result = AuthResult(method=AuthMethod.SYSTEM, metadata={"disabled_auth": True})

    with (
        patch("airweave.api.context_resolver.settings") as mock_settings,
        patch.object(
            resolver, "_authenticate_system", new_callable=AsyncMock, return_value=system_result
        ) as mock_system,
        patch.object(
            resolver, "_authenticate_api_key", new_callable=AsyncMock
        ) as mock_api_key,
    ):
        mock_settings.AUTH_ENABLED = False
        result = await resolver._authenticate(db, None, "ak_test_secret", request)

    mock_system.assert_awaited_once_with(db)
    mock_api_key.assert_not_awaited()
    assert result.method == AuthMethod.SYSTEM


@pytest.mark.asyncio
async def test_api_key_takes_priority_over_auth0():
    """When both x_api_key and auth0_user are provided, API key wins."""
    resolver = _make_resolver()
    db = AsyncMock()
    auth0_user = MagicMock(email="user@example.com", id="auth0|123")
    request = _fake_request()

    api_key_result = AuthResult(method=AuthMethod.API_KEY, api_key_org_id="org-1")

    with (
        patch("airweave.api.context_resolver.settings") as mock_settings,
        patch.object(
            resolver, "_authenticate_api_key", new_callable=AsyncMock, return_value=api_key_result
        ) as mock_api_key_auth,
        patch.object(
            resolver, "_authenticate_auth0", new_callable=AsyncMock
        ) as mock_auth0_auth,
    ):
        mock_settings.AUTH_ENABLED = True
        result = await resolver._authenticate(db, auth0_user, "ak_test_secret", request)

    mock_api_key_auth.assert_awaited_once_with(db, "ak_test_secret", request)
    mock_auth0_auth.assert_not_awaited()
    assert result.method == AuthMethod.API_KEY
