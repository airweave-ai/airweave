"""Tests for PipedreamAuthProvider."""

import json
from unittest.mock import AsyncMock, patch

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
from airweave.domains.auth_provider.providers.pipedream import (
    PipedreamAuthProvider,
    PipedreamDefaultOAuthException,
)

PIPEDREAM_MODULE = "airweave.domains.auth_provider.providers.pipedream"


def _make_response(status_code: int = 200, json_body=None, text: str = "", headers=None):
    """Build httpx.Response with controllable body and headers."""
    content = json.dumps(json_body).encode() if json_body is not None else text.encode()
    hdrs = dict(headers or {})
    if json_body is not None and "content-type" not in (k.lower() for k in hdrs):
        hdrs["content-type"] = "application/json"
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers=hdrs,
        request=httpx.Request("POST", "https://api.pipedream.com/v1/oauth/token"),
    )


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_success():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj-1", "account_id": "acc-1", "environment": "production"},
    )
    assert provider.client_id == "cid"
    assert provider.client_secret == "csec"
    assert provider.project_id == "proj-1"
    assert provider.account_id == "acc-1"
    assert provider.environment == "production"
    assert provider._access_token is None
    assert provider._token_expires_at == 0


@pytest.mark.asyncio
async def test_create_credentials_none_raises():
    with pytest.raises(ValueError, match="credentials parameter is required"):
        await PipedreamAuthProvider.create(credentials=None)


@pytest.mark.asyncio
async def test_create_config_none_uses_defaults():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config=None,
    )
    assert provider.project_id is None
    assert provider.account_id is None
    assert provider.environment == "production"


# ---------------------------------------------------------------------------
# PipedreamDefaultOAuthException
# ---------------------------------------------------------------------------


def test_pipedream_default_oauth_exception_default_message():
    exc = PipedreamDefaultOAuthException("slack")
    assert exc.source_short_name == "slack"
    assert "slack" in str(exc)
    assert "default OAuth" in str(exc)


def test_pipedream_default_oauth_exception_custom_message():
    exc = PipedreamDefaultOAuthException("slack", message="custom")
    assert str(exc) == "custom"


# ---------------------------------------------------------------------------
# _ensure_valid_token() error branches (lines 222, 226-227, 231-233, 238)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_valid_token_401_raises_auth_error():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    resp = _make_response(401, {"error": "invalid_client"})

    mock_post = AsyncMock(side_effect=httpx.HTTPStatusError("401", request=resp.request, response=resp))

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderAuthError, match="rejected client credentials"):
            await provider._ensure_valid_token()


@pytest.mark.asyncio
async def test_ensure_valid_token_429_raises_rate_limit_with_retry_after():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    resp = _make_response(429, {"error": "rate_limited"}, headers={"retry-after": "120"})

    mock_post = AsyncMock(side_effect=httpx.HTTPStatusError("429", request=resp.request, response=resp))

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderRateLimitError) as exc_info:
            await provider._ensure_valid_token()
        assert exc_info.value.retry_after == 120.0


@pytest.mark.asyncio
async def test_ensure_valid_token_429_default_retry_after():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    resp = _make_response(429, {"error": "rate_limited"})

    mock_post = AsyncMock(side_effect=httpx.HTTPStatusError("429", request=resp.request, response=resp))

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderRateLimitError) as exc_info:
            await provider._ensure_valid_token()
        assert exc_info.value.retry_after == 30.0


@pytest.mark.asyncio
async def test_ensure_valid_token_500_raises_temporary_error():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    resp = _make_response(500, {"error": "internal"})

    mock_post = AsyncMock(side_effect=httpx.HTTPStatusError("500", request=resp.request, response=resp))

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderTemporaryError, match="returned 500"):
            await provider._ensure_valid_token()


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    mock_response = _make_response(200, {"access_token": "tok", "expires_in": 3600})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        result = await provider.validate()
    assert result is True


@pytest.mark.asyncio
async def test_validate_missing_access_token_raises_config_error():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    mock_response = _make_response(200, {"token_type": "bearer"})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderConfigError, match="without access_token"):
            await provider.validate()


@pytest.mark.asyncio
async def test_validate_401_raises_auth_error():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    resp = _make_response(401, {"error": "invalid_client"})

    mock_post = AsyncMock(side_effect=httpx.HTTPStatusError("401", request=resp.request, response=resp))

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderAuthError, match="Invalid client credentials"):
            await provider.validate()


@pytest.mark.asyncio
async def test_validate_5xx_raises_temporary_error():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    resp = _make_response(502, {"error": "bad_gateway", "error_description": "upstream down"})

    mock_post = AsyncMock(side_effect=httpx.HTTPStatusError("502", request=resp.request, response=resp))

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderTemporaryError, match="502"):
            await provider.validate()


@pytest.mark.asyncio
async def test_validate_4xx_other_raises_config_error():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    resp = _make_response(400, {"error": "invalid_request", "error_description": "bad params"})

    mock_post = AsyncMock(side_effect=httpx.HTTPStatusError("400", request=resp.request, response=resp))

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderConfigError, match="400"):
            await provider.validate()


@pytest.mark.asyncio
async def test_validate_detail_extraction_error_fallback():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    resp = _make_response(400, text="not json at all")

    mock_post = AsyncMock(side_effect=httpx.HTTPStatusError("400", request=resp.request, response=resp))

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderConfigError, match="not json at all"):
            await provider.validate()


@pytest.mark.asyncio
async def test_validate_connect_error_raises_temporary():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )

    mock_post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderTemporaryError, match="unreachable"):
            await provider.validate()


@pytest.mark.asyncio
async def test_validate_timeout_raises_temporary():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )

    mock_post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderTemporaryError, match="unreachable"):
            await provider.validate()


@pytest.mark.asyncio
async def test_validate_reraises_config_error():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    mock_response = _make_response(200, {"token_type": "bearer"})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(f"{PIPEDREAM_MODULE}.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AuthProviderConfigError) as exc_info:
            await provider.validate()
        assert "provider_name" in str(exc_info.value) or "access_token" in str(exc_info.value)


# ---------------------------------------------------------------------------
# _get_account_with_credentials()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_account_with_credentials_app_mismatch():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )
    account_data = {"app": {"name_slug": "wrong_app"}, "name": "acc"}

    mock_get_with_auth = AsyncMock(return_value=account_data)

    with patch.object(provider, "_get_with_auth", mock_get_with_auth):
        with pytest.raises(AuthProviderConfigError, match="expected 'slack_v2'"):
            await provider._get_account_with_credentials(
                AsyncMock(), "slack_v2", "slack"
            )


@pytest.mark.asyncio
async def test_get_account_with_credentials_no_credentials_raises_default_oauth():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )
    account_data = {"app": {"name_slug": "slack_v2"}, "name": "acc"}

    mock_get_with_auth = AsyncMock(return_value=account_data)

    with patch.object(provider, "_get_with_auth", mock_get_with_auth):
        with pytest.raises(PipedreamDefaultOAuthException) as exc_info:
            await provider._get_account_with_credentials(
                AsyncMock(), "slack_v2", "slack"
            )
        assert exc_info.value.source_short_name == "slack"


@pytest.mark.asyncio
async def test_get_account_with_credentials_reraises_config_error():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )
    err = AuthProviderConfigError("bad config", provider_name="pipedream")
    mock_get_with_auth = AsyncMock(side_effect=err)

    with patch.object(provider, "_get_with_auth", mock_get_with_auth):
        with pytest.raises(AuthProviderConfigError, match="bad config"):
            await provider._get_account_with_credentials(
                AsyncMock(), "slack_v2", "slack"
            )


@pytest.mark.asyncio
async def test_get_account_with_credentials_reraises_default_oauth():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )
    err = PipedreamDefaultOAuthException("slack")
    mock_get_with_auth = AsyncMock(side_effect=err)

    with patch.object(provider, "_get_with_auth", mock_get_with_auth):
        with pytest.raises(PipedreamDefaultOAuthException):
            await provider._get_account_with_credentials(
                AsyncMock(), "slack_v2", "slack"
            )


@pytest.mark.asyncio
async def test_get_account_with_credentials_404_raises_account_not_found():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )
    resp = _make_response(404, {"error": "not_found"})
    err = httpx.HTTPStatusError("404", request=resp.request, response=resp)
    mock_get_with_auth = AsyncMock(side_effect=err)

    with patch.object(provider, "_get_with_auth", mock_get_with_auth):
        with pytest.raises(AuthProviderAccountNotFoundError) as exc_info:
            await provider._get_account_with_credentials(
                AsyncMock(), "slack_v2", "slack"
            )
        assert exc_info.value.account_id == "acc"


@pytest.mark.asyncio
async def test_get_account_with_credentials_429_raises_rate_limit():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )
    resp = _make_response(429, {"error": "rate_limited"}, headers={"retry-after": "60"})
    err = httpx.HTTPStatusError("429", request=resp.request, response=resp)
    mock_get_with_auth = AsyncMock(side_effect=err)

    with patch.object(provider, "_get_with_auth", mock_get_with_auth):
        with pytest.raises(AuthProviderRateLimitError) as exc_info:
            await provider._get_account_with_credentials(
                AsyncMock(), "slack_v2", "slack"
            )
        assert exc_info.value.retry_after == 60.0


@pytest.mark.asyncio
async def test_get_account_with_credentials_5xx_raises_temporary():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )
    resp = _make_response(503, {"error": "unavailable"})
    err = httpx.HTTPStatusError("503", request=resp.request, response=resp)
    mock_get_with_auth = AsyncMock(side_effect=err)

    with patch.object(provider, "_get_with_auth", mock_get_with_auth):
        with pytest.raises(AuthProviderTemporaryError, match="503"):
            await provider._get_account_with_credentials(
                AsyncMock(), "slack_v2", "slack"
            )


@pytest.mark.asyncio
async def test_get_account_with_credentials_other_status_raises_temporary():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )
    resp = _make_response(418, text="I'm a teapot")
    err = httpx.HTTPStatusError("418", request=resp.request, response=resp)
    mock_get_with_auth = AsyncMock(side_effect=err)

    with patch.object(provider, "_get_with_auth", mock_get_with_auth):
        with pytest.raises(AuthProviderTemporaryError, match="418"):
            await provider._get_account_with_credentials(
                AsyncMock(), "slack_v2", "slack"
            )


# ---------------------------------------------------------------------------
# _extract_and_map_credentials() missing fields (line 554)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_and_map_credentials_missing_required_raises():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    account_data = {"credentials": {"oauth_client_id": "cid"}}
    with pytest.raises(AuthProviderMissingFieldsError) as exc_info:
        provider._extract_and_map_credentials(
            account_data,
            source_auth_config_fields=["access_token", "client_id"],
            source_short_name="slack",
        )
    assert "access_token" in exc_info.value.missing_fields
    assert exc_info.value.available_fields == ["oauth_client_id"]


@pytest.mark.asyncio
async def test_extract_and_map_credentials_optional_skipped():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    account_data = {"credentials": {"oauth_access_token": "tok"}}
    result = provider._extract_and_map_credentials(
        account_data,
        source_auth_config_fields=["access_token", "refresh_token"],
        source_short_name="slack",
        optional_fields={"refresh_token"},
    )
    assert result == {"access_token": "tok"}


@pytest.mark.asyncio
async def test_extract_and_map_credentials_success():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    account_data = {
        "credentials": {
            "oauth_access_token": "tok",
            "oauth_refresh_token": "ref",
        },
    }
    result = provider._extract_and_map_credentials(
        account_data,
        source_auth_config_fields=["access_token", "refresh_token"],
        source_short_name="slack",
    )
    assert result == {"access_token": "tok", "refresh_token": "ref"}


@pytest.mark.asyncio
async def test_extract_and_map_credentials_source_field_mapping_coda():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    account_data = {"credentials": {"api_token": "coda-key"}}
    result = provider._extract_and_map_credentials(
        account_data,
        source_auth_config_fields=["api_key"],
        source_short_name="coda",
    )
    assert result == {"api_key": "coda-key"}


# ---------------------------------------------------------------------------
# get_creds_for_source()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_creds_for_source_success():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )
    account_data = {
        "app": {"name_slug": "slack_v2"},
        "name": "My Slack",
        "credentials": {"oauth_access_token": "xoxb-tok"},
    }

    async def fake_get_account(client, slug, source):
        return account_data

    with patch.object(provider, "_get_account_with_credentials", fake_get_account):
        creds = await provider.get_creds_for_source(
            "slack", ["access_token"]
        )
    assert creds == {"access_token": "xoxb-tok"}


# ---------------------------------------------------------------------------
# get_auth_result()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_auth_result_blocked_source_raises_config_error():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )
    with pytest.raises(AuthProviderConfigError, match="not supported via Pipedream"):
        await provider.get_auth_result("github", ["access_token"])


@pytest.mark.asyncio
async def test_get_auth_result_direct_success():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )
    account_data = {
        "app": {"name_slug": "slack_v2"},
        "name": "My Slack",
        "credentials": {"oauth_access_token": "xoxb-tok"},
    }

    async def fake_get_account(client, slug, source):
        return account_data

    with patch.object(provider, "_get_account_with_credentials", fake_get_account):
        result = await provider.get_auth_result("slack", ["access_token"])
    assert result.credentials == {"access_token": "xoxb-tok"}


@pytest.mark.asyncio
async def test_get_auth_result_default_oauth_raises_config_error():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )

    async def fake_get_account(client, slug, source):
        raise PipedreamDefaultOAuthException("slack")

    with patch.object(provider, "_get_account_with_credentials", fake_get_account):
        with pytest.raises(AuthProviderConfigError, match="default OAuth client"):
            await provider.get_auth_result("slack", ["access_token"])


@pytest.mark.asyncio
async def test_get_auth_result_with_source_config_mappings():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "proj", "account_id": "acc"},
    )
    account_data = {
        "app": {"name_slug": "slack_v2"},
        "name": "My Slack",
        "credentials": {"oauth_access_token": "xoxb-tok"},
    }

    async def fake_get_account(client, slug, source):
        return account_data

    async def fake_get_config(source, mappings):
        return {"instance_url": "https://example.slack.com"}

    with patch.object(provider, "_get_account_with_credentials", fake_get_account):
        with patch.object(provider, "get_config_for_source", fake_get_config):
            result = await provider.get_auth_result(
                "slack",
                ["access_token"],
                source_config_field_mappings={"instance_url": "instance_url"},
            )
    assert result.source_config == {"instance_url": "https://example.slack.com"}


# ---------------------------------------------------------------------------
# _get_pipedream_app_slug, _map_field_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pipedream_app_slug_mapped():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    assert provider._get_pipedream_app_slug("slack") == "slack_v2"
    assert provider._get_pipedream_app_slug("apollo") == "apollo_io"


@pytest.mark.asyncio
async def test_get_pipedream_app_slug_unmapped():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    assert provider._get_pipedream_app_slug("gmail") == "gmail"


@pytest.mark.asyncio
async def test_map_field_name_default():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    assert provider._map_field_name("access_token") == "oauth_access_token"


@pytest.mark.asyncio
async def test_map_field_name_source_override():
    provider = await PipedreamAuthProvider.create(
        credentials={"client_id": "cid", "client_secret": "csec"},
        config={"project_id": "p", "account_id": "a"},
    )
    assert provider._map_field_name("api_key", "coda") == "api_token"
