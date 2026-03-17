"""Unit tests for ComposioAuthProvider."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from airweave.domains.auth_provider.exceptions import (
    AuthProviderAccountNotFoundError,
    AuthProviderAuthError,
    AuthProviderConfigError,
    AuthProviderMissingFieldsError,
    AuthProviderRateLimitError,
    AuthProviderTemporaryError,
)
from airweave.domains.auth_provider.providers.composio import ComposioAuthProvider


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_sets_instance_attrs():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "test-key"},
        config={"auth_config_id": "cfg-1", "account_id": "acc-1"},
    )
    assert provider.api_key == "test-key"
    assert provider.auth_config_id == "cfg-1"
    assert provider.account_id == "acc-1"
    assert provider._last_credential_blob is None


@pytest.mark.asyncio
async def test_create_handles_partial_config():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={},
    )
    assert provider.api_key == "k"
    assert provider.auth_config_id is None
    assert provider.account_id is None


# ---------------------------------------------------------------------------
# _get_with_auth() — error branches (401, 429, 5xx, ConnectError, TimeoutException)
# ---------------------------------------------------------------------------


def _make_http_status_error(status_code: int, headers: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    return httpx.HTTPStatusError("err", request=MagicMock(), response=resp)


@pytest.mark.asyncio
async def test_get_with_auth_401_raises_auth_error():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=_make_http_status_error(401),
    )

    with pytest.raises(AuthProviderAuthError) as exc_info:
        await provider._get_with_auth(mock_client, "https://example.com/api")

    assert "invalid or revoked" in str(exc_info.value).lower()
    assert exc_info.value.provider_name == "composio"


@pytest.mark.asyncio
async def test_get_with_auth_429_raises_rate_limit_with_retry_after():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )
    mock_client = AsyncMock()
    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {"retry-after": "120"}
    mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError("err", request=MagicMock(), response=resp))

    with pytest.raises(AuthProviderRateLimitError) as exc_info:
        await provider._get_with_auth(mock_client, "https://example.com/api")

    assert exc_info.value.retry_after == 120.0
    assert exc_info.value.provider_name == "composio"


@pytest.mark.asyncio
async def test_get_with_auth_429_default_retry_after():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )
    mock_client = AsyncMock()
    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {}
    mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError("err", request=MagicMock(), response=resp))

    with pytest.raises(AuthProviderRateLimitError) as exc_info:
        await provider._get_with_auth(mock_client, "https://example.com/api")

    assert exc_info.value.retry_after == 30.0


@pytest.mark.asyncio
async def test_get_with_auth_5xx_raises_temporary_error():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=_make_http_status_error(502))

    with pytest.raises(AuthProviderTemporaryError) as exc_info:
        await provider._get_with_auth(mock_client, "https://example.com/api")

    assert "502" in str(exc_info.value)
    assert exc_info.value.status_code == 502
    assert exc_info.value.provider_name == "composio"


@pytest.mark.asyncio
async def test_get_with_auth_connect_error_raises_temporary():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    with pytest.raises(AuthProviderTemporaryError) as exc_info:
        await provider._get_with_auth(mock_client, "https://example.com/api")

    assert "unreachable" in str(exc_info.value).lower() or "connection" in str(exc_info.value).lower()
    assert exc_info.value.provider_name == "composio"


@pytest.mark.asyncio
async def test_get_with_auth_timeout_raises_temporary():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    with pytest.raises(AuthProviderTemporaryError) as exc_info:
        await provider._get_with_auth(mock_client, "https://example.com/api")

    assert exc_info.value.provider_name == "composio"


@pytest.mark.asyncio
async def test_get_with_auth_success_returns_json():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"items": [], "total": 0}
    mock_resp.raise_for_status = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    result = await provider._get_with_auth(mock_client, "https://example.com/api")
    assert result == {"items": [], "total": 0}


# ---------------------------------------------------------------------------
# _get_source_connected_accounts() — no match -> AuthProviderAccountNotFoundError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_source_connected_accounts_no_match_raises():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "cfg-1", "account_id": "acc-1"},
    )
    # All accounts have different slug
    provider._get_all_connected_accounts = AsyncMock(
        return_value=[
            {"id": "a1", "toolkit": {"slug": "slack"}, "auth_config": {"id": "x"}},
        ]
    )

    with pytest.raises(AuthProviderAccountNotFoundError) as exc_info:
        await provider._get_source_connected_accounts(
            MagicMock(), composio_slug="googledrive", source_short_name="google_drive"
        )

    assert "No connected accounts" in str(exc_info.value)
    assert exc_info.value.provider_name == "composio"


@pytest.mark.asyncio
async def test_get_source_connected_accounts_empty_list_raises():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "cfg-1", "account_id": "acc-1"},
    )
    provider._get_all_connected_accounts = AsyncMock(return_value=[])

    with pytest.raises(AuthProviderAccountNotFoundError):
        await provider._get_source_connected_accounts(
            MagicMock(), composio_slug="slack", source_short_name="slack"
        )


# ---------------------------------------------------------------------------
# _find_matching_connection() — match caches blob; no match raises
# ---------------------------------------------------------------------------


def test_find_matching_connection_match_caches_blob():
    provider = ComposioAuthProvider()
    provider.auth_config_id = "cfg-1"
    provider.account_id = "acc-1"
    provider._last_credential_blob = None

    creds = {"generic_api_key": "secret", "instance_url": "https://x.com"}
    accounts = [
        {
            "id": "acc-1",
            "auth_config": {"id": "cfg-1"},
            "state": {"val": creds},
        }
    ]

    result = provider._find_matching_connection(accounts, "salesforce")
    assert result == creds
    assert provider._last_credential_blob == creds


def test_find_matching_connection_no_match_raises():
    provider = ComposioAuthProvider()
    provider.auth_config_id = "cfg-1"
    provider.account_id = "acc-1"

    accounts = [
        {"id": "other", "auth_config": {"id": "other-cfg"}, "state": {"val": {}}},
    ]

    with pytest.raises(AuthProviderAccountNotFoundError) as exc_info:
        provider._find_matching_connection(accounts, "slack")

    assert "No matching Composio connection" in str(exc_info.value)
    assert exc_info.value.account_id == "acc-1"
    assert exc_info.value.provider_name == "composio"


# ---------------------------------------------------------------------------
# _map_and_validate_fields() — missing required raises
# ---------------------------------------------------------------------------


def test_map_and_validate_fields_missing_required_raises():
    provider = ComposioAuthProvider()
    # No api_key, generic_api_key, or access_token — all required fields missing
    source_creds = {"other_field": "x"}

    with pytest.raises(AuthProviderMissingFieldsError) as exc_info:
        provider._map_and_validate_fields(
            source_creds,
            source_auth_config_fields=["api_key", "refresh_token"],
            source_short_name="slack",
        )

    assert "api_key" in exc_info.value.missing_fields
    assert "refresh_token" in exc_info.value.missing_fields
    assert exc_info.value.available_fields == ["other_field"]
    assert exc_info.value.provider_name == "composio"


def test_map_and_validate_fields_optional_skipped():
    provider = ComposioAuthProvider()
    source_creds = {"generic_api_key": "key"}

    result = provider._map_and_validate_fields(
        source_creds,
        source_auth_config_fields=["api_key", "optional_field"],
        source_short_name="stripe",
        optional_fields={"optional_field"},
    )
    assert result == {"api_key": "key"}


def test_map_and_validate_fields_api_key_tries_multiple():
    provider = ComposioAuthProvider()
    # api_key maps to generic_api_key, but we also try access_token
    source_creds = {"access_token": "oauth-tok"}

    result = provider._map_and_validate_fields(
        source_creds,
        source_auth_config_fields=["api_key"],
        source_short_name="stripe",
    )
    assert result == {"api_key": "oauth-tok"}


# ---------------------------------------------------------------------------
# get_config_for_source()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_config_for_source_extracts_from_cached_blob():
    provider = ComposioAuthProvider()
    provider._last_credential_blob = {"instance_url": "https://my.salesforce.com", "org_id": "00D123"}

    result = await provider.get_config_for_source(
        source_short_name="salesforce",
        source_config_field_mappings={"instance_url": "instance_url", "org_id": "org_id"},
    )
    assert result == {"instance_url": "https://my.salesforce.com", "org_id": "00D123"}


@pytest.mark.asyncio
async def test_get_config_for_source_empty_blob_returns_empty():
    provider = ComposioAuthProvider()
    provider._last_credential_blob = None

    result = await provider.get_config_for_source(
        source_short_name="slack",
        source_config_field_mappings={"team_id": "team_id"},
    )
    assert result == {}


# ---------------------------------------------------------------------------
# validate() — 401, 403, 5xx, other status, ConnectError, non-JSON fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_401_raises_auth_error():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "401", request=MagicMock(), response=mock_resp
    )

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("airweave.domains.auth_provider.providers.composio.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderAuthError) as exc_info:
            await provider.validate()

    assert "Invalid API key" in str(exc_info.value)
    assert exc_info.value.provider_name == "composio"


@pytest.mark.asyncio
async def test_validate_403_raises_auth_error():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=MagicMock(), response=mock_resp
    )

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("airweave.domains.auth_provider.providers.composio.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderAuthError) as exc_info:
            await provider.validate()

    assert "Access denied" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_5xx_raises_temporary_error():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.json.return_value = {"message": "Service unavailable"}
    mock_resp.text = "Service unavailable"
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503", request=MagicMock(), response=mock_resp
    )

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("airweave.domains.auth_provider.providers.composio.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderTemporaryError) as exc_info:
            await provider.validate()

    assert "503" in str(exc_info.value)
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_validate_other_status_raises_config_error():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"message": "Bad request"}
    mock_resp.text = "Bad request"
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400", request=MagicMock(), response=mock_resp
    )

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("airweave.domains.auth_provider.providers.composio.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderConfigError) as exc_info:
            await provider.validate()

    assert "400" in str(exc_info.value)
    assert exc_info.value.provider_name == "composio"


@pytest.mark.asyncio
async def test_validate_non_json_fallback_uses_text():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.side_effect = ValueError("not json")
    mock_resp.text = "plain text error"
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400", request=MagicMock(), response=mock_resp
    )

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("airweave.domains.auth_provider.providers.composio.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderConfigError) as exc_info:
            await provider.validate()

    assert "plain text error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_connect_error_raises_temporary():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("airweave.domains.auth_provider.providers.composio.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderTemporaryError) as exc_info:
            await provider.validate()

    assert "unreachable" in str(exc_info.value).lower() or "connection" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_validate_timeout_raises_temporary():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("airweave.domains.auth_provider.providers.composio.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderTemporaryError):
            await provider.validate()


@pytest.mark.asyncio
async def test_validate_success_returns_true():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "c", "account_id": "a"},
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("airweave.domains.auth_provider.providers.composio.httpx.AsyncClient", return_value=mock_client):
        result = await provider.validate()

    assert result is True


# ---------------------------------------------------------------------------
# get_creds_for_source() — integration via mocked HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_creds_for_source_happy_path():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "test-key"},
        config={"auth_config_id": "cfg-1", "account_id": "acc-1"},
    )

    def mock_get(url, headers=None, params=None):
        resp = MagicMock()
        resp.json.return_value = {
            "items": [
                {
                    "id": "acc-1",
                    "auth_config": {"id": "cfg-1"},
                    "toolkit": {"slug": "slack"},
                    "state": {"val": {"access_token": "tok123", "oauth_access_token": "tok123"}},
                }
            ]
        }
        resp.raise_for_status = MagicMock()
        return resp

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=mock_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("airweave.domains.auth_provider.providers.composio.httpx.AsyncClient", return_value=mock_client):
        creds = await provider.get_creds_for_source(
            source_short_name="slack",
            source_auth_config_fields=["access_token"],
        )

    assert creds == {"access_token": "tok123"}


@pytest.mark.asyncio
async def test_get_creds_for_source_slug_mapping():
    provider = await ComposioAuthProvider.create(
        credentials={"api_key": "k"},
        config={"auth_config_id": "cfg-1", "account_id": "acc-1"},
    )

    def mock_get(url, headers=None, params=None):
        resp = MagicMock()
        resp.json.return_value = {
            "items": [
                {
                    "id": "acc-1",
                    "auth_config": {"id": "cfg-1"},
                    "toolkit": {"slug": "googledrive"},
                    "state": {"val": {"access_token": "tok"}},
                }
            ]
        }
        resp.raise_for_status = MagicMock()
        return resp

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=mock_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("airweave.domains.auth_provider.providers.composio.httpx.AsyncClient", return_value=mock_client):
        creds = await provider.get_creds_for_source(
            source_short_name="google_drive",
            source_auth_config_fields=["access_token"],
        )

    assert creds == {"access_token": "tok"}
