"""Unit tests for IntegrationSettings.get_by_short_name with BYOC entries.

Verifies that secret enrichment is skipped when the YAML entry has no
client_secret / consumer_secret (the expected state for BYOC-only
integrations).
"""

import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from airweave.platform.auth.schemas import (
    OAuth1Settings,
    OAuth2Settings,
    OAuth2WithRefreshSettings,
)
from airweave.platform.auth.settings import IntegrationSettings


@pytest.fixture
def yaml_file(tmp_path: Path) -> Path:
    """Write a minimal integrations YAML with a mix of platform and BYOC entries."""
    content = textwrap.dedent("""\
        integrations:
          has_platform_secret:
            oauth_type: "with_refresh"
            url: "https://provider.com/authorize"
            backend_url: "https://provider.com/token"
            grant_type: "authorization_code"
            client_id: "plat-cid"
            client_secret: "plat-csec"
            content_type: "application/x-www-form-urlencoded"
            client_credential_location: "body"

          byoc_no_secret:
            oauth_type: "with_refresh"
            url: "https://provider.com/authorize"
            backend_url: "https://provider.com/token"
            grant_type: "authorization_code"
            content_type: "application/x-www-form-urlencoded"
            client_credential_location: "body"

          oauth1_with_secret:
            oauth_type: "oauth1"
            request_token_url: "https://p.com/req"
            authorization_url: "https://p.com/auth"
            access_token_url: "https://p.com/access"
            consumer_key: "plat-ck"
            consumer_secret: "plat-cs"

          oauth1_byoc:
            oauth_type: "oauth1"
            request_token_url: "https://p.com/req"
            authorization_url: "https://p.com/auth"
            access_token_url: "https://p.com/access"

          direct_auth:
            # no oauth_type → direct
    """)
    f = tmp_path / "test.integrations.yaml"
    f.write_text(content)
    return f


# ---------------------------------------------------------------------------
# get_by_short_name – secret enrichment logic
# ---------------------------------------------------------------------------


class TestGetByShortNameSecretEnrichment:
    """get_by_short_name should only call _get_client_secret when the entry has a secret."""

    @pytest.mark.asyncio
    async def test_oauth2_with_secret_enriches(self, yaml_file):
        settings = IntegrationSettings(yaml_file)
        with patch.object(
            settings, "_get_client_secret", new_callable=AsyncMock, return_value="enriched-sec"
        ) as mock_get:
            result = await settings.get_by_short_name("has_platform_secret")

        mock_get.assert_awaited_once()
        assert isinstance(result, OAuth2WithRefreshSettings)
        assert result.client_secret == "enriched-sec"
        assert result.client_id == "plat-cid"

    @pytest.mark.asyncio
    async def test_oauth2_byoc_skips_enrichment(self, yaml_file):
        settings = IntegrationSettings(yaml_file)
        with patch.object(
            settings, "_get_client_secret", new_callable=AsyncMock
        ) as mock_get:
            result = await settings.get_by_short_name("byoc_no_secret")

        mock_get.assert_not_awaited()
        assert isinstance(result, OAuth2WithRefreshSettings)
        assert result.client_id is None
        assert result.client_secret is None

    @pytest.mark.asyncio
    async def test_oauth1_with_secret_enriches(self, yaml_file):
        settings = IntegrationSettings(yaml_file)
        with patch.object(
            settings, "_get_client_secret", new_callable=AsyncMock, return_value="enriched-cs"
        ) as mock_get:
            result = await settings.get_by_short_name("oauth1_with_secret")

        mock_get.assert_awaited_once()
        assert isinstance(result, OAuth1Settings)
        assert result.consumer_secret == "enriched-cs"

    @pytest.mark.asyncio
    async def test_oauth1_byoc_skips_enrichment(self, yaml_file):
        settings = IntegrationSettings(yaml_file)
        with patch.object(
            settings, "_get_client_secret", new_callable=AsyncMock
        ) as mock_get:
            result = await settings.get_by_short_name("oauth1_byoc")

        mock_get.assert_not_awaited()
        assert isinstance(result, OAuth1Settings)
        assert result.consumer_key is None
        assert result.consumer_secret is None

    @pytest.mark.asyncio
    async def test_direct_auth_never_enriches(self, yaml_file):
        settings = IntegrationSettings(yaml_file)
        with patch.object(
            settings, "_get_client_secret", new_callable=AsyncMock
        ) as mock_get:
            result = await settings.get_by_short_name("direct_auth")

        mock_get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_raises_key_error(self, yaml_file):
        settings = IntegrationSettings(yaml_file)
        with pytest.raises(KeyError, match="not_in_yaml"):
            await settings.get_by_short_name("not_in_yaml")


# ---------------------------------------------------------------------------
# _parse_integration – BYOC entries load without credentials
# ---------------------------------------------------------------------------


class TestParseIntegrationByocEntries:
    """YAML entries without credentials should load as valid settings objects."""

    def test_oauth2_loads_without_credentials(self, yaml_file):
        settings = IntegrationSettings(yaml_file)
        raw = settings.get_settings("byoc_no_secret")
        assert isinstance(raw, OAuth2WithRefreshSettings)
        assert raw.client_id is None
        assert raw.client_secret is None
        assert raw.url == "https://provider.com/authorize"

    def test_oauth1_loads_without_credentials(self, yaml_file):
        settings = IntegrationSettings(yaml_file)
        raw = settings.get_settings("oauth1_byoc")
        assert isinstance(raw, OAuth1Settings)
        assert raw.consumer_key is None
        assert raw.consumer_secret is None
        assert raw.request_token_url == "https://p.com/req"
