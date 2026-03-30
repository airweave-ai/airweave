"""Tests for CustomAuthProvider."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from airweave.domains.auth_provider.exceptions import (
    AuthProviderAuthError,
    AuthProviderConfigError,
    AuthProviderMissingFieldsError,
    AuthProviderRateLimitError,
    AuthProviderTemporaryError,
)
from airweave.domains.auth_provider.providers.custom import CustomAuthProvider


@pytest.fixture
async def provider():
    """Create a Custom provider."""
    return await CustomAuthProvider.create(
        credentials={
            "endpoint_url": "https://api.example.com/tokens",
            "api_key": "my-secret-key",
        }
    )


class TestCreate:
    """Tests for CustomAuthProvider.create()."""

    @pytest.mark.unit
    async def test_create(self, provider):
        assert provider.endpoint_url == "https://api.example.com/tokens"
        assert provider.api_key == "my-secret-key"

    @pytest.mark.unit
    async def test_create_strips_trailing_slash(self):
        p = await CustomAuthProvider.create(
            credentials={
                "endpoint_url": "https://api.example.com/tokens/",
                "api_key": "key",
            }
        )
        assert p.endpoint_url == "https://api.example.com/tokens"


class TestBuildHeaders:
    """Tests for _build_headers()."""

    @pytest.mark.unit
    async def test_headers(self, provider):
        headers = provider._build_headers()
        assert headers["Accept"] == "application/json"
        assert headers["X-API-Key"] == "my-secret-key"


class TestGetCredsForSource:
    """Tests for get_creds_for_source()."""

    @pytest.mark.unit
    async def test_success(self, provider):
        mock_response = httpx.Response(
            200,
            json={"access_token": "eyJ-gdrive-token", "refresh_token": "rt-123"},
            request=httpx.Request("GET", "https://api.example.com/tokens/google_drive"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            creds = await provider.get_creds_for_source(
                "google_drive",
                ["access_token"],
            )

        assert creds == {"access_token": "eyJ-gdrive-token"}

    @pytest.mark.unit
    async def test_calls_correct_url(self, provider):
        mock_response = httpx.Response(
            200,
            json={"access_token": "token"},
            request=httpx.Request("GET", "https://api.example.com/tokens/slack"),
        )

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_get:
            await provider.get_creds_for_source("slack", ["access_token"])

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args.args[0] == "https://api.example.com/tokens/slack"

    @pytest.mark.unit
    async def test_optional_fields_not_required(self, provider):
        mock_response = httpx.Response(
            200,
            json={"access_token": "token"},
            request=httpx.Request("GET", "https://api.example.com/tokens/google_drive"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            creds = await provider.get_creds_for_source(
                "google_drive",
                ["access_token", "refresh_token"],
                optional_fields={"refresh_token"},
            )

        assert creds == {"access_token": "token"}

    @pytest.mark.unit
    async def test_error_401(self, provider):
        mock_response = httpx.Response(
            401,
            json={"error": "unauthorized"},
            request=httpx.Request("GET", "https://api.example.com/tokens/slack"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(AuthProviderAuthError, match="401"):
                await provider.get_creds_for_source("slack", ["access_token"])

    @pytest.mark.unit
    async def test_error_429(self, provider):
        mock_response = httpx.Response(
            429,
            json={"error": "rate limited"},
            headers={"retry-after": "60"},
            request=httpx.Request("GET", "https://api.example.com/tokens/slack"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(AuthProviderRateLimitError) as exc_info:
                await provider.get_creds_for_source("slack", ["access_token"])
            assert exc_info.value.retry_after == 60.0

    @pytest.mark.unit
    async def test_error_500(self, provider):
        mock_response = httpx.Response(
            500,
            json={"error": "internal"},
            request=httpx.Request("GET", "https://api.example.com/tokens/slack"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(AuthProviderTemporaryError, match="500"):
                await provider.get_creds_for_source("slack", ["access_token"])

    @pytest.mark.unit
    async def test_error_timeout(self, provider):
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(AuthProviderTemporaryError, match="unreachable"):
                await provider.get_creds_for_source("slack", ["access_token"])

    @pytest.mark.unit
    async def test_error_missing_fields(self, provider):
        mock_response = httpx.Response(
            200,
            json={"some_other_field": "value"},
            request=httpx.Request("GET", "https://api.example.com/tokens/slack"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(AuthProviderMissingFieldsError) as exc_info:
                await provider.get_creds_for_source("slack", ["access_token"])
            assert "access_token" in exc_info.value.missing_fields

    @pytest.mark.unit
    async def test_ssrf_blocked(self, provider):
        provider.endpoint_url = "http://169.254.169.254/latest/meta-data"

        with pytest.raises(AuthProviderConfigError, match="SSRF"):
            await provider.get_creds_for_source("slack", ["access_token"])


class TestValidate:
    """Tests for validate()."""

    @pytest.mark.unit
    async def test_validate_success(self, provider):
        mock_response = httpx.Response(
            200,
            json={"status": "ok"},
            request=httpx.Request("GET", "https://api.example.com/tokens"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            result = await provider.validate()

        assert result is True

    @pytest.mark.unit
    async def test_validate_auth_error(self, provider):
        mock_response = httpx.Response(
            401,
            json={"error": "unauthorized"},
            request=httpx.Request("GET", "https://api.example.com/tokens"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(AuthProviderAuthError):
                await provider.validate()

    @pytest.mark.unit
    async def test_validate_server_error(self, provider):
        mock_response = httpx.Response(
            503,
            json={"error": "unavailable"},
            request=httpx.Request("GET", "https://api.example.com/tokens"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(AuthProviderTemporaryError):
                await provider.validate()

    @pytest.mark.unit
    async def test_validate_timeout(self, provider):
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(AuthProviderTemporaryError, match="unreachable"):
                await provider.validate()

    @pytest.mark.unit
    async def test_validate_ssrf_blocked(self, provider):
        provider.endpoint_url = "http://169.254.169.254/latest/meta-data"

        with pytest.raises(AuthProviderConfigError, match="SSRF"):
            await provider.validate()
