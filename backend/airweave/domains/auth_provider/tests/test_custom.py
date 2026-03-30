"""Tests for CustomAuthProvider."""

from unittest.mock import AsyncMock, patch
from uuid import UUID

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

TEST_SC_ID = UUID("d035439c-dc7d-4813-a207-c68e548cfe51")


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
    async def test_requires_source_connection_id(self, provider):
        with pytest.raises(AuthProviderConfigError, match="source_connection_id"):
            await provider.get_creds_for_source("slack", ["access_token"])

    @pytest.mark.unit
    async def test_success(self, provider):
        mock_response = httpx.Response(
            200,
            json={"access_token": "eyJ-gdrive-token", "refresh_token": "rt-123"},
            request=httpx.Request("GET", f"https://api.example.com/tokens/{TEST_SC_ID}"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            creds = await provider.get_creds_for_source(
                "google_drive",
                ["access_token"],
                source_connection_id=TEST_SC_ID,
            )

        assert creds == {"access_token": "eyJ-gdrive-token"}

    @pytest.mark.unit
    async def test_maps_access_token_to_personal_access_token(self, provider):
        """Customer returns access_token, provider maps to personal_access_token for GitHub."""
        mock_response = httpx.Response(
            200,
            json={"access_token": "ghp_test123"},
            request=httpx.Request("GET", f"https://api.example.com/tokens/{TEST_SC_ID}"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            creds = await provider.get_creds_for_source(
                "github",
                ["personal_access_token"],
                source_connection_id=TEST_SC_ID,
            )

        assert creds == {"personal_access_token": "ghp_test123"}

    @pytest.mark.unit
    async def test_maps_access_token_to_api_token(self, provider):
        """Customer returns access_token, provider maps to api_token for Document360."""
        mock_response = httpx.Response(
            200,
            json={"access_token": "doc360_token"},
            request=httpx.Request("GET", f"https://api.example.com/tokens/{TEST_SC_ID}"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            creds = await provider.get_creds_for_source(
                "document360",
                ["api_token"],
                source_connection_id=TEST_SC_ID,
            )

        assert creds == {"api_token": "doc360_token"}

    @pytest.mark.unit
    async def test_calls_correct_url(self, provider):
        mock_response = httpx.Response(
            200,
            json={"access_token": "token"},
            request=httpx.Request("GET", f"https://api.example.com/tokens/{TEST_SC_ID}"),
        )

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_get:
            await provider.get_creds_for_source(
                "slack", ["access_token"], source_connection_id=TEST_SC_ID,
            )

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args.args[0] == f"https://api.example.com/tokens/{TEST_SC_ID}"

    @pytest.mark.unit
    async def test_optional_fields_not_required(self, provider):
        mock_response = httpx.Response(
            200,
            json={"access_token": "token"},
            request=httpx.Request("GET", f"https://api.example.com/tokens/{TEST_SC_ID}"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            creds = await provider.get_creds_for_source(
                "google_drive",
                ["access_token", "refresh_token"],
                optional_fields={"refresh_token"},
                source_connection_id=TEST_SC_ID,
            )

        assert creds == {"access_token": "token"}

    @pytest.mark.unit
    async def test_error_401(self, provider):
        mock_response = httpx.Response(
            401,
            json={"error": "unauthorized"},
            request=httpx.Request("GET", f"https://api.example.com/tokens/{TEST_SC_ID}"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(AuthProviderAuthError, match="401"):
                await provider.get_creds_for_source(
                    "slack", ["access_token"], source_connection_id=TEST_SC_ID,
                )

    @pytest.mark.unit
    async def test_error_429(self, provider):
        mock_response = httpx.Response(
            429,
            json={"error": "rate limited"},
            headers={"retry-after": "60"},
            request=httpx.Request("GET", f"https://api.example.com/tokens/{TEST_SC_ID}"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(AuthProviderRateLimitError) as exc_info:
                await provider.get_creds_for_source(
                    "slack", ["access_token"], source_connection_id=TEST_SC_ID,
                )
            assert exc_info.value.retry_after == 60.0

    @pytest.mark.unit
    async def test_error_500(self, provider):
        mock_response = httpx.Response(
            500,
            json={"error": "internal"},
            request=httpx.Request("GET", f"https://api.example.com/tokens/{TEST_SC_ID}"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(AuthProviderTemporaryError, match="500"):
                await provider.get_creds_for_source(
                    "slack", ["access_token"], source_connection_id=TEST_SC_ID,
                )

    @pytest.mark.unit
    async def test_error_timeout(self, provider):
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(AuthProviderTemporaryError, match="unreachable"):
                await provider.get_creds_for_source(
                    "slack", ["access_token"], source_connection_id=TEST_SC_ID,
                )

    @pytest.mark.unit
    async def test_error_missing_fields(self, provider):
        mock_response = httpx.Response(
            200,
            json={"some_other_field": "value"},
            request=httpx.Request("GET", f"https://api.example.com/tokens/{TEST_SC_ID}"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(AuthProviderMissingFieldsError) as exc_info:
                await provider.get_creds_for_source(
                    "slack", ["access_token"], source_connection_id=TEST_SC_ID,
                )
            assert "access_token" in exc_info.value.missing_fields

    @pytest.mark.unit
    async def test_error_404(self, provider):
        mock_response = httpx.Response(
            404,
            json={"error": "not found"},
            request=httpx.Request("GET", f"https://api.example.com/tokens/{TEST_SC_ID}"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(AuthProviderMissingFieldsError, match="404"):
                await provider.get_creds_for_source(
                    "slack", ["access_token"], source_connection_id=TEST_SC_ID,
                )

    @pytest.mark.unit
    async def test_ssrf_blocked(self, provider):
        provider.endpoint_url = "http://169.254.169.254/latest/meta-data"

        with pytest.raises(AuthProviderConfigError, match="SSRF"):
            await provider.get_creds_for_source(
                "slack", ["access_token"], source_connection_id=TEST_SC_ID,
            )


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
