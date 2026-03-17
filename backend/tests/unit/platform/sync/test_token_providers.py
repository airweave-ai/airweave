"""Unit tests for TokenProvider implementations.

Tests:
- OAuthTokenProvider: timer/cache behavior, get_token, force_refresh
- StaticTokenProvider: get_token, force_refresh raises
- AuthProviderTokenProvider: delegates to auth provider
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from airweave.core.logging import ContextualLogger
from airweave.domains.oauth.types import RefreshResult
from airweave.domains.sources.token_providers.auth_provider import AuthProviderTokenProvider
from airweave.domains.sources.token_providers.exceptions import (
    TokenProviderError,
    TokenRefreshNotSupportedError,
)
from airweave.domains.sources.token_providers.oauth import OAuthTokenProvider
from airweave.domains.sources.token_providers.static import StaticTokenProvider


def _mock_logger() -> ContextualLogger:
    """Create a mock ContextualLogger."""
    return MagicMock(spec=ContextualLogger)


def _oauth_provider(
    credentials="test_token",
    oauth_type=None,
    **overrides,
):
    """Create an OAuthTokenProvider with sensible defaults.

    Args:
        credentials: Raw credentials (str, dict, or object).
        oauth_type: OAuth type string — use "with_refresh" to enable refresh.
    """
    return OAuthTokenProvider(
        credentials=credentials,
        oauth_type=oauth_type,
        oauth2_service=overrides.get("oauth2_service", MagicMock()),
        source_short_name=overrides.get("source_short_name", "test_source"),
        connection_id=overrides.get("connection_id", uuid4()),
        ctx=overrides.get("ctx", MagicMock()),
        logger=overrides.get("logger", _mock_logger()),
        config_fields=overrides.get("config_fields", None),
    )


# ---------------------------------------------------------------------------
# OAuthTokenProvider
# ---------------------------------------------------------------------------


class TestOAuthGetToken:
    """Tests for OAuthTokenProvider.get_token."""

    @pytest.mark.asyncio
    async def test_returns_token_when_no_refresh(self):
        """When oauth_type doesn't support refresh, returns the initial token."""
        p = _oauth_provider("my_token", oauth_type="access_only")
        assert await p.get_token() == "my_token"

    @pytest.mark.asyncio
    async def test_returns_token_when_recently_refreshed(self):
        """When last refresh was recent, returns cached token without calling service."""
        mock_service = MagicMock()
        mock_service.refresh_and_persist = AsyncMock(
            return_value=RefreshResult(access_token="refreshed", expires_in=3600)
        )

        creds = {"access_token": "initial", "refresh_token": "rt"}
        p = _oauth_provider(creds, oauth_type="with_refresh", oauth2_service=mock_service)

        token = await p.get_token()
        assert token == "refreshed"
        assert mock_service.refresh_and_persist.call_count == 1

        token2 = await p.get_token()
        assert token2 == "refreshed"
        assert mock_service.refresh_and_persist.call_count == 1

    @pytest.mark.asyncio
    async def test_raises_on_refresh_failure(self):
        """When refresh fails, raises TokenProviderError."""
        from airweave.core.exceptions import TokenRefreshError

        mock_service = MagicMock()
        mock_service.refresh_and_persist = AsyncMock(
            side_effect=TokenRefreshError("network error")
        )

        creds = {"access_token": "tok", "refresh_token": "rt"}
        p = _oauth_provider(creds, oauth_type="with_refresh", oauth2_service=mock_service)

        with pytest.raises(TokenProviderError):
            await p.get_token()


class TestOAuthForceRefresh:
    """Tests for OAuthTokenProvider.force_refresh."""

    @pytest.mark.asyncio
    async def test_raises_when_no_refresh(self):
        """force_refresh raises TokenRefreshNotSupportedError when refresh not possible."""
        p = _oauth_provider("tok", oauth_type="access_only")
        with pytest.raises(TokenRefreshNotSupportedError):
            await p.force_refresh()

    @pytest.mark.asyncio
    async def test_returns_fresh_token(self):
        """force_refresh calls service and returns new token."""
        mock_service = MagicMock()
        mock_service.refresh_and_persist = AsyncMock(
            return_value=RefreshResult(access_token="forced_token", expires_in=3600)
        )

        creds = {"access_token": "old", "refresh_token": "rt"}
        p = _oauth_provider(creds, oauth_type="with_refresh", oauth2_service=mock_service)
        token = await p.force_refresh()
        assert token == "forced_token"

    @pytest.mark.asyncio
    async def test_raises_on_failure(self):
        """force_refresh raises TokenProviderError when service fails."""
        from airweave.core.exceptions import TokenRefreshError

        mock_service = MagicMock()
        mock_service.refresh_and_persist = AsyncMock(
            side_effect=TokenRefreshError("fail")
        )

        creds = {"access_token": "old", "refresh_token": "rt"}
        p = _oauth_provider(creds, oauth_type="with_refresh", oauth2_service=mock_service)
        with pytest.raises(TokenProviderError):
            await p.force_refresh()


class TestOAuthConstructor:
    """Tests for OAuthTokenProvider credential handling."""

    def test_extracts_token_from_string(self):
        p = _oauth_provider("raw_token")
        assert p._token == "raw_token"

    def test_extracts_token_from_dict(self):
        p = _oauth_provider({"access_token": "dict_tok"})
        assert p._token == "dict_tok"

    def test_extracts_token_from_object(self):
        class C:
            access_token = "obj_tok"
        p = _oauth_provider(C())
        assert p._token == "obj_tok"

    def test_raises_on_missing_token(self):
        with pytest.raises(ValueError, match="No access token"):
            _oauth_provider({"not_a_token": "x"})

    def test_can_refresh_when_type_and_token_present(self):
        creds = {"access_token": "at", "refresh_token": "rt"}
        p = _oauth_provider(creds, oauth_type="with_refresh")
        assert p._can_refresh is True

    def test_no_refresh_when_type_is_access_only(self):
        creds = {"access_token": "at", "refresh_token": "rt"}
        p = _oauth_provider(creds, oauth_type="access_only")
        assert p._can_refresh is False

    def test_no_refresh_when_no_refresh_token(self):
        creds = {"access_token": "at"}
        p = _oauth_provider(creds, oauth_type="with_refresh")
        assert p._can_refresh is False

    def test_no_refresh_when_refresh_token_empty(self):
        creds = {"access_token": "at", "refresh_token": "  "}
        p = _oauth_provider(creds, oauth_type="with_refresh")
        assert p._can_refresh is False


# ---------------------------------------------------------------------------
# StaticTokenProvider
# ---------------------------------------------------------------------------


class TestStaticTokenProvider:
    """Tests for StaticTokenProvider."""

    @pytest.mark.asyncio
    async def test_get_token_returns_value(self):
        p = StaticTokenProvider("api_key_123")
        assert await p.get_token() == "api_key_123"

    @pytest.mark.asyncio
    async def test_force_refresh_raises(self):
        p = StaticTokenProvider("api_key_123", source_short_name="attio")
        with pytest.raises(TokenRefreshNotSupportedError):
            await p.force_refresh()

    def test_empty_token_raises(self):
        with pytest.raises(ValueError):
            StaticTokenProvider("")


# ---------------------------------------------------------------------------
# AuthProviderTokenProvider
# ---------------------------------------------------------------------------


class TestAuthProviderTokenProvider:
    """Tests for AuthProviderTokenProvider."""

    def _make_provider(self, access_token: str = "fresh_token"):
        mock_auth_provider = MagicMock()
        mock_auth_provider.get_creds_for_source = AsyncMock(
            return_value={"access_token": access_token}
        )

        mock_registry = MagicMock()
        entry = MagicMock()
        entry.runtime_auth_all_fields = ["access_token"]
        entry.runtime_auth_optional_fields = []
        mock_registry.get.return_value = entry

        return AuthProviderTokenProvider(
            auth_provider_instance=mock_auth_provider,
            source_short_name="test_source",
            source_registry=mock_registry,
            logger=_mock_logger(),
        )

    @pytest.mark.asyncio
    async def test_get_token_delegates_to_provider(self):
        p = self._make_provider("fresh_at")
        assert await p.get_token() == "fresh_at"

    @pytest.mark.asyncio
    async def test_force_refresh_same_as_get_token(self):
        p = self._make_provider("refreshed_at")
        assert await p.force_refresh() == "refreshed_at"
