"""Unit tests for OAuth2Service.

Covers:
- _encode_client_credentials (base64 encoding)
- _generate_pkce_challenge_pair (RFC 7636 compliance)
- _normalize_token_response (standard + non-standard formats)
- _is_oauth_rate_limit_error (429, Zoho-style 400, normal errors)
- _prepare_token_request (scope rules, credential location)
- _get_client_credentials (priority ordering)
- _supports_oauth2 (trivial)
- generate_auth_url (URL construction, templates, scopes, state)
- generate_auth_url_with_redirect (PKCE toggle, redirect_uri)
- exchange_authorization_code_for_token (happy path, missing settings, template URLs)
- exchange_authorization_code_for_token_with_redirect (same + PKCE)
- refresh_access_token (full flow, rotating refresh, missing token, missing config)
- _exchange_code (HTTP errors, PKCE, credential location)
- _make_token_request (rate limit retries)
- _handle_token_response (rotating vs non-rotating credential update)

Uses table-driven tests wherever possible.
"""

import base64
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import httpx
import pytest

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException, TokenRefreshError
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.domains.oauth.fakes.repository import (
    FakeCredentialEncryptor,
    FakeOAuthConnectionRepository,
    FakeOAuthCredentialRepository,
    FakeOAuthSourceRepository,
)
from airweave.domains.oauth.oauth2_service import OAuth2Service
from airweave.platform.auth.schemas import OAuth2Settings, OAuth2TokenResponse
from airweave.schemas.organization import Organization

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> ApiContext:
    org = Organization(
        id=str(ORG_ID),
        name="Test Org",
        created_at=NOW,
        modified_at=NOW,
        enabled_features=[],
    )
    return ApiContext(
        request_id="test-req-001",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        auth_metadata={},
        logger=logger.with_context(request_id="test-req-001"),
    )


def _make_settings(**overrides) -> SimpleNamespace:
    defaults = dict(app_url="https://app.airweave.ai")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_oauth2_settings(
    *,
    short_name: str = "slack",
    url: str = "https://slack.com/oauth/v2/authorize",
    backend_url: str = "https://slack.com/api/oauth.v2.access",
    client_id: str = "test-client-id",
    client_secret: str = "test-client-secret",
    grant_type: str = "authorization_code",
    content_type: str = "application/x-www-form-urlencoded",
    client_credential_location: str = "body",
    scope: Optional[str] = None,
    user_scope: Optional[str] = None,
    additional_frontend_params: Optional[dict] = None,
    url_template: bool = False,
    backend_url_template: bool = False,
    requires_pkce: bool = False,
    oauth_type: Optional[str] = None,
) -> OAuth2Settings:
    return OAuth2Settings(
        integration_short_name=short_name,
        url=url,
        backend_url=backend_url,
        client_id=client_id,
        client_secret=client_secret,
        grant_type=grant_type,
        content_type=content_type,
        client_credential_location=client_credential_location,
        scope=scope,
        user_scope=user_scope,
        additional_frontend_params=additional_frontend_params,
        url_template=url_template,
        backend_url_template=backend_url_template,
        requires_pkce=requires_pkce,
        oauth_type=oauth_type,
    )


def _make_integration_config(**overrides) -> OAuth2Settings:
    """Build an OAuth2Settings for use as integration config in tests."""
    if "integration_short_name" in overrides:
        overrides["short_name"] = overrides.pop("integration_short_name")
    defaults = dict(
        short_name="google_drive",
        url="https://accounts.google.com/o/oauth2/v2/auth",
        backend_url="https://oauth2.googleapis.com/token",
        backend_url_template=False,
        content_type="application/x-www-form-urlencoded",
        grant_type="authorization_code",
        client_id="cfg-client-id",
        client_secret="cfg-client-secret",
        client_credential_location="body",
        scope="https://www.googleapis.com/auth/drive.readonly",
        oauth_type="with_refresh",
    )
    defaults.update(overrides)
    return _make_oauth2_settings(**defaults)


def _make_httpx_response(
    status_code: int = 200,
    json_body: Optional[dict] = None,
    text: str = "",
) -> httpx.Response:
    """Build an httpx.Response with controllable body."""
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(json_body).encode() if json_body else text.encode(),
        headers={"content-type": "application/json"} if json_body else {},
        request=httpx.Request("POST", "https://example.com/token"),
    )


class Deps:
    """Bundles fakes for OAuth2Service constructor."""

    def __init__(self, **settings_overrides):
        self.settings = _make_settings(**settings_overrides)
        self.conn_repo = FakeOAuthConnectionRepository()
        self.cred_repo = FakeOAuthCredentialRepository()
        self.encryptor = FakeCredentialEncryptor()
        self.source_repo = FakeOAuthSourceRepository()

    def build(self) -> OAuth2Service:
        return OAuth2Service(
            settings=self.settings,
            conn_repo=self.conn_repo,
            cred_repo=self.cred_repo,
            encryptor=self.encryptor,
            source_repo=self.source_repo,
        )


def _svc(**settings_overrides) -> OAuth2Service:
    return Deps(**settings_overrides).build()


# ===========================================================================
# _encode_client_credentials (table-driven)
# ===========================================================================


@dataclass
class EncodeCredCase:
    desc: str
    client_id: str
    client_secret: str
    expected: str


ENCODE_CRED_CASES = [
    EncodeCredCase(
        "standard credentials",
        "my-id",
        "my-secret",
        base64.b64encode(b"my-id:my-secret").decode("ascii"),
    ),
    EncodeCredCase(
        "empty secret",
        "my-id",
        "",
        base64.b64encode(b"my-id:").decode("ascii"),
    ),
    EncodeCredCase(
        "special characters in secret",
        "id",
        "s3cr3t+/=!@#",
        base64.b64encode(b"id:s3cr3t+/=!@#").decode("ascii"),
    ),
    EncodeCredCase(
        "both empty",
        "",
        "",
        base64.b64encode(b":").decode("ascii"),
    ),
]


@pytest.mark.parametrize("case", ENCODE_CRED_CASES, ids=lambda c: c.desc)
def test_encode_client_credentials(case: EncodeCredCase):
    result = _svc()._encode_client_credentials(case.client_id, case.client_secret)
    assert result == case.expected


# ===========================================================================
# _generate_pkce_challenge_pair
# ===========================================================================


def test_pkce_pair_format_and_length():
    verifier, challenge = _svc()._generate_pkce_challenge_pair()
    assert 43 <= len(verifier) <= 128
    assert len(challenge) > 0
    assert "=" not in challenge  # no padding per spec


def test_pkce_pair_verifier_matches_challenge():
    """SHA256(verifier) base64url-encoded == challenge (RFC 7636)."""
    verifier, challenge = _svc()._generate_pkce_challenge_pair()
    sha = hashlib.sha256(verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(sha).decode("ascii").rstrip("=")
    assert challenge == expected


def test_pkce_pair_uniqueness():
    pairs = [_svc()._generate_pkce_challenge_pair() for _ in range(10)]
    verifiers = [v for v, _ in pairs]
    assert len(set(verifiers)) == 10


# ===========================================================================
# _normalize_token_response (table-driven)
# ===========================================================================


@dataclass
class NormalizeCase:
    desc: str
    response_data: dict
    expected_access_token: str
    expected_token_type: Optional[str] = None


NORMALIZE_CASES = [
    NormalizeCase(
        "standard format — passthrough",
        {"access_token": "tok-123", "token_type": "Bearer", "scope": "read"},
        "tok-123",
        "Bearer",
    ),
    NormalizeCase(
        "slack nested authed_user",
        {
            "ok": True,
            "authed_user": {
                "access_token": "xoxp-slack-user",
                "token_type": "user",
                "scope": "channels:read",
            },
        },
        "xoxp-slack-user",
        "user",
    ),
    NormalizeCase(
        "authed_user present but access_token also at top level — no normalization",
        {
            "access_token": "top-level-tok",
            "authed_user": {"access_token": "nested-tok"},
        },
        "top-level-tok",
        None,
    ),
    NormalizeCase(
        "authed_user is not a dict — ignored",
        {"access_token": "tok-abc", "authed_user": "not-a-dict"},
        "tok-abc",
        None,
    ),
    NormalizeCase(
        "empty authed_user dict without access_token — passthrough",
        {"access_token": "tok-xyz", "authed_user": {}},
        "tok-xyz",
        None,
    ),
]


@pytest.mark.parametrize("case", NORMALIZE_CASES, ids=lambda c: c.desc)
def test_normalize_token_response(case: NormalizeCase):
    svc = _svc()
    log = logger.with_context(test="normalize")
    result = svc._normalize_token_response(case.response_data, "test_source", log)
    assert result["access_token"] == case.expected_access_token
    if case.expected_token_type:
        assert result.get("token_type") == case.expected_token_type


# ===========================================================================
# _is_oauth_rate_limit_error (table-driven)
# ===========================================================================


@dataclass
class RateLimitCase:
    desc: str
    status_code: int
    json_body: Optional[dict]
    expected: bool


RATE_LIMIT_CASES = [
    RateLimitCase("429 → True", 429, None, True),
    RateLimitCase("200 → False", 200, None, False),
    RateLimitCase("500 → False", 500, None, False),
    RateLimitCase(
        "400 Zoho-style rate limit → True",
        400,
        {"error_description": "You have made too many requests recently", "error": "Access Denied"},
        True,
    ),
    RateLimitCase(
        "400 but different error → False",
        400,
        {"error_description": "Invalid grant", "error": "invalid_grant"},
        False,
    ),
    RateLimitCase(
        "400 with non-JSON body → False",
        400,
        None,
        False,
    ),
    RateLimitCase(
        "400 error_description without 'too many requests' → False",
        400,
        {"error_description": "Something went wrong", "error": "Access Denied"},
        False,
    ),
]


@pytest.mark.parametrize("case", RATE_LIMIT_CASES, ids=lambda c: c.desc)
def test_is_oauth_rate_limit_error(case: RateLimitCase):
    resp = _make_httpx_response(status_code=case.status_code, json_body=case.json_body)
    result = _svc()._is_oauth_rate_limit_error(resp)
    assert result is case.expected


# ===========================================================================
# _get_client_credentials (table-driven)
# ===========================================================================


@dataclass
class ClientCredCase:
    desc: str
    config_id: str
    config_secret: str
    auth_fields: Optional[dict]
    decrypted_credential: Optional[dict]
    expect_id: str
    expect_secret: str


CLIENT_CRED_CASES = [
    ClientCredCase(
        "config only — fallback to integration_config",
        "cfg-id", "cfg-secret", None, None, "cfg-id", "cfg-secret",
    ),
    ClientCredCase(
        "decrypted_credential overrides config",
        "cfg-id", "cfg-secret", None,
        {"client_id": "cred-id", "client_secret": "cred-secret"},
        "cred-id", "cred-secret",
    ),
    ClientCredCase(
        "auth_fields overrides decrypted_credential",
        "cfg-id", "cfg-secret",
        {"client_id": "auth-id", "client_secret": "auth-secret"},
        {"client_id": "cred-id", "client_secret": "cred-secret"},
        "auth-id", "auth-secret",
    ),
    ClientCredCase(
        "partial override — decrypted_credential overrides only id",
        "cfg-id", "cfg-secret", None,
        {"client_id": "new-id"},
        "new-id", "cfg-secret",
    ),
    ClientCredCase(
        "partial override — auth_fields overrides only secret",
        "cfg-id", "cfg-secret",
        {"client_secret": "new-secret"}, None,
        "cfg-id", "new-secret",
    ),
    ClientCredCase(
        "all three — auth_fields wins",
        "cfg-id", "cfg-secret",
        {"client_id": "auth-id"},
        {"client_id": "cred-id"},
        "auth-id", "cfg-secret",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CLIENT_CRED_CASES, ids=lambda c: c.desc)
async def test_get_client_credentials(case: ClientCredCase):
    config = _make_integration_config(client_id=case.config_id, client_secret=case.config_secret)
    cid, csecret = await _svc()._get_client_credentials(
        config, case.auth_fields, case.decrypted_credential
    )
    assert cid == case.expect_id
    assert csecret == case.expect_secret


# ===========================================================================
# _prepare_token_request — scope rules (table-driven)
# ===========================================================================


@dataclass
class PrepareRequestCase:
    desc: str
    oauth_type: Optional[str]
    integration_short_name: str
    scope: Optional[str]
    cred_location: str  # "header" or "body"
    expect_scope_in_payload: bool
    expect_auth_header: bool


PREPARE_REQUEST_CASES = [
    PrepareRequestCase(
        "with_refresh + scope → scope included",
        "with_refresh", "google_drive", "drive.readonly", "body",
        True, False,
    ),
    PrepareRequestCase(
        "with_rotating_refresh → scope excluded",
        "with_rotating_refresh", "jira", "read:jira-work", "body",
        False, False,
    ),
    PrepareRequestCase(
        "salesforce → scope excluded (special case)",
        "with_refresh", "salesforce", "full", "body",
        False, False,
    ),
    PrepareRequestCase(
        "no oauth_type → scope excluded",
        None, "generic", "some-scope", "body",
        False, False,
    ),
    PrepareRequestCase(
        "with_refresh but no scope → no scope key",
        "with_refresh", "hubspot", None, "body",
        False, False,
    ),
    PrepareRequestCase(
        "header location → Basic auth in header, no client_id/secret in body",
        "with_refresh", "zoom", "meeting:read", "header",
        True, True,
    ),
    PrepareRequestCase(
        "body location → client_id/secret in payload",
        "with_refresh", "google_drive", "drive", "body",
        True, False,
    ),
]


@pytest.mark.parametrize("case", PREPARE_REQUEST_CASES, ids=lambda c: c.desc)
def test_prepare_token_request(case: PrepareRequestCase):
    config = _make_integration_config(
        oauth_type=case.oauth_type,
        integration_short_name=case.integration_short_name,
        scope=case.scope,
        client_credential_location=case.cred_location,
    )
    log = logger.with_context(test="prepare")
    headers, payload = _svc()._prepare_token_request(
        log, config, "refresh-tok-xyz", "cid", "csecret"
    )

    assert payload["grant_type"] == "refresh_token"
    assert payload["refresh_token"] == "refresh-tok-xyz"

    if case.expect_scope_in_payload:
        assert "scope" in payload
    else:
        assert "scope" not in payload

    if case.expect_auth_header:
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert "client_id" not in payload
        assert "client_secret" not in payload
    else:
        if case.cred_location == "body":
            assert payload["client_id"] == "cid"
            assert payload["client_secret"] == "csecret"


# ===========================================================================
# _supports_oauth2
# ===========================================================================


@pytest.mark.parametrize(
    "oauth_type,expected",
    [("with_refresh", True), ("access_only", True), (None, False)],
    ids=["with_refresh", "access_only", "none"],
)
def test_supports_oauth2(oauth_type, expected):
    assert _svc()._supports_oauth2(oauth_type) is expected


# ===========================================================================
# generate_auth_url (table-driven)
# ===========================================================================


@dataclass
class AuthUrlCase:
    desc: str
    scope: Optional[str]
    user_scope: Optional[str]
    state: Optional[str]
    client_id_override: Optional[str]
    additional_frontend_params: Optional[dict]
    url_template: bool
    template_configs: Optional[dict]
    url: str
    expect_in_url: list[str] = field(default_factory=list)
    expect_not_in_url: list[str] = field(default_factory=list)
    expect_error: bool = False


AUTH_URL_CASES = [
    AuthUrlCase(
        "basic — no scope, no state",
        None, None, None, None, None, False, None,
        "https://provider.com/auth",
        ["response_type=code", "client_id=test-client-id", "redirect_uri="],
        ["scope=", "state=", "user_scope="],
    ),
    AuthUrlCase(
        "with scope and user_scope",
        "read write", "channels:read", None, None, None, False, None,
        "https://provider.com/auth",
        ["scope=read+write", "user_scope=channels"],
    ),
    AuthUrlCase(
        "with state",
        None, None, "csrf-tok-abc", None, None, False, None,
        "https://provider.com/auth",
        ["state=csrf-tok-abc"],
    ),
    AuthUrlCase(
        "client_id override",
        None, None, None, "override-id", None, False, None,
        "https://provider.com/auth",
        ["client_id=override-id"],
        ["client_id=test-client-id"],
    ),
    AuthUrlCase(
        "additional_frontend_params",
        None, None, None, None, {"prompt": "consent"}, False, None,
        "https://provider.com/auth",
        ["prompt=consent"],
    ),
    AuthUrlCase(
        "template URL — rendered",
        None, None, None, None, None, True,
        {"instance_url": "mycompany.example.com"},
        "https://{instance_url}/oauth/authorize",
        ["mycompany.example.com"],
    ),
    AuthUrlCase(
        "template URL — missing configs → error",
        None, None, None, None, None, True, None,
        "https://{instance_url}/oauth/authorize",
        expect_error=True,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", AUTH_URL_CASES, ids=lambda c: c.desc)
async def test_generate_auth_url(case: AuthUrlCase):
    settings_obj = _make_oauth2_settings(
        url=case.url,
        scope=case.scope,
        user_scope=case.user_scope,
        additional_frontend_params=case.additional_frontend_params,
        url_template=case.url_template,
    )
    svc = _svc()

    if case.expect_error:
        with pytest.raises(ValueError):
            await svc.generate_auth_url(
                settings_obj,
                client_id=case.client_id_override,
                state=case.state,
                template_configs=case.template_configs,
            )
        return

    url = await svc.generate_auth_url(
        settings_obj,
        client_id=case.client_id_override,
        state=case.state,
        template_configs=case.template_configs,
    )

    for expected in case.expect_in_url:
        assert expected in url, f"expected '{expected}' in URL: {url}"
    for unexpected in case.expect_not_in_url:
        assert unexpected not in url, f"did not expect '{unexpected}' in URL: {url}"


# ===========================================================================
# generate_auth_url_with_redirect — PKCE (table-driven)
# ===========================================================================


@dataclass
class AuthUrlRedirectCase:
    desc: str
    requires_pkce: bool
    state: Optional[str]
    expect_code_verifier: bool
    expect_in_url: list[str] = field(default_factory=list)


AUTH_URL_REDIRECT_CASES = [
    AuthUrlRedirectCase(
        "no PKCE → verifier is None",
        False, None, False,
        ["redirect_uri=https%3A%2F%2Fcustom.app%2Fcallback"],
    ),
    AuthUrlRedirectCase(
        "PKCE required → verifier returned, challenge in URL",
        True, None, True,
        ["code_challenge=", "code_challenge_method=S256"],
    ),
    AuthUrlRedirectCase(
        "with state → state in URL",
        False, "my-state", False,
        ["state=my-state"],
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", AUTH_URL_REDIRECT_CASES, ids=lambda c: c.desc)
async def test_generate_auth_url_with_redirect(case: AuthUrlRedirectCase):
    settings_obj = _make_oauth2_settings(requires_pkce=case.requires_pkce)
    svc = _svc()

    url, verifier = await svc.generate_auth_url_with_redirect(
        settings_obj,
        redirect_uri="https://custom.app/callback",
        state=case.state,
    )

    if case.expect_code_verifier:
        assert verifier is not None
        assert len(verifier) >= 43
    else:
        assert verifier is None

    for expected in case.expect_in_url:
        assert expected in url, f"expected '{expected}' in URL: {url}"


# ===========================================================================
# _exchange_code (table-driven)
# ===========================================================================


@dataclass
class ExchangeCodeCase:
    desc: str
    cred_location: str
    code_verifier: Optional[str]
    http_status: int
    response_body: dict
    expect_error: bool
    expect_pkce_in_payload: bool


EXCHANGE_CODE_CASES = [
    ExchangeCodeCase(
        "happy path — body credentials",
        "body", None, 200,
        {"access_token": "new-tok", "token_type": "Bearer"},
        False, False,
    ),
    ExchangeCodeCase(
        "happy path — header credentials",
        "header", None, 200,
        {"access_token": "new-tok"},
        False, False,
    ),
    ExchangeCodeCase(
        "with PKCE verifier",
        "body", "verifier-abc", 200,
        {"access_token": "pkce-tok"},
        False, True,
    ),
    ExchangeCodeCase(
        "HTTP 401 error → HTTPException",
        "body", None, 401,
        {"error": "invalid_client"},
        True, False,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", EXCHANGE_CODE_CASES, ids=lambda c: c.desc)
async def test_exchange_code(case: ExchangeCodeCase):
    config = _make_integration_config(client_credential_location=case.cred_location)
    log = logger.with_context(test="exchange_code")
    svc = _svc()

    mock_response = _make_httpx_response(case.http_status, case.response_body)

    async def fake_post(url, headers=None, data=None):
        if case.expect_pkce_in_payload:
            assert "code_verifier" in data
        if case.http_status >= 400:
            raise httpx.HTTPStatusError(
                "error", request=mock_response.request, response=mock_response
            )
        return mock_response

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("airweave.domains.oauth.oauth2_service.httpx.AsyncClient", return_value=mock_client):
        if case.expect_error:
            with pytest.raises(Exception):
                await svc._exchange_code(
                    logger=log,
                    code="auth-code-xyz",
                    redirect_uri="https://app.test/callback",
                    client_id="cid",
                    client_secret="csecret",
                    backend_url="https://provider.com/token",
                    integration_config=config,
                    code_verifier=case.code_verifier,
                )
        else:
            result = await svc._exchange_code(
                logger=log,
                code="auth-code-xyz",
                redirect_uri="https://app.test/callback",
                client_id="cid",
                client_secret="csecret",
                backend_url="https://provider.com/token",
                integration_config=config,
                code_verifier=case.code_verifier,
            )
            assert result.access_token == case.response_body["access_token"]


@pytest.mark.asyncio
async def test_exchange_code_normalizes_slack_response():
    """Slack-style nested authed_user response is normalized."""
    config = _make_integration_config()
    log = logger.with_context(test="exchange_slack")
    svc = _svc()

    slack_body = {
        "ok": True,
        "authed_user": {
            "access_token": "xoxp-user-tok",
            "token_type": "user",
            "scope": "channels:read",
        },
    }
    mock_response = _make_httpx_response(200, slack_body)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("airweave.domains.oauth.oauth2_service.httpx.AsyncClient", return_value=mock_client):
        result = await svc._exchange_code(
            logger=log,
            code="slack-code",
            redirect_uri="https://app.test/callback",
            client_id="cid",
            client_secret="csecret",
            backend_url="https://slack.com/api/oauth.v2.access",
            integration_config=config,
        )
    assert result.access_token == "xoxp-user-tok"


# ===========================================================================
# exchange_authorization_code_for_token (table-driven)
# ===========================================================================


@dataclass
class ExchangeTokenCase:
    desc: str
    settings_found: bool
    backend_url_template: bool
    template_configs: Optional[dict]
    client_id_override: Optional[str]
    client_secret_override: Optional[str]
    expect_error: bool
    expect_error_type: type = Exception


EXCHANGE_TOKEN_CASES = [
    ExchangeTokenCase("happy path", True, False, None, None, None, False),
    ExchangeTokenCase("settings not found → HTTPException", False, False, None, None, None, True),
    ExchangeTokenCase(
        "template URL without configs → ValueError",
        True, True, None, None, None, True, ValueError,
    ),
    ExchangeTokenCase(
        "template URL with configs → rendered",
        True, True, {"instance_url": "acme.example.com"}, None, None, False,
    ),
    ExchangeTokenCase("client_id + secret override", True, False, None, "custom-id", "custom-secret", False),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", EXCHANGE_TOKEN_CASES, ids=lambda c: c.desc)
async def test_exchange_authorization_code_for_token(case: ExchangeTokenCase):
    svc = _svc()
    ctx = _make_ctx()

    oauth_settings = _make_oauth2_settings(
        backend_url=(
            "https://{instance_url}/oauth/token" if case.backend_url_template
            else "https://provider.com/token"
        ),
        backend_url_template=case.backend_url_template,
    )

    async def fake_get_by_short_name(name):
        if not case.settings_found:
            raise KeyError(f"Integration settings not found for {name}")
        return oauth_settings

    token_response = OAuth2TokenResponse(access_token="exchanged-tok")

    with (
        patch(
            "airweave.domains.oauth.oauth2_service.integration_settings"
        ) as mock_int_settings,
        patch.object(svc, "_exchange_code", new_callable=AsyncMock, return_value=token_response),
    ):
        mock_int_settings.get_by_short_name = AsyncMock(side_effect=fake_get_by_short_name)

        if case.expect_error:
            with pytest.raises(Exception):
                await svc.exchange_authorization_code_for_token(
                    ctx, "test_source", "auth-code",
                    client_id=case.client_id_override,
                    client_secret=case.client_secret_override,
                    template_configs=case.template_configs,
                )
        else:
            result = await svc.exchange_authorization_code_for_token(
                ctx, "test_source", "auth-code",
                client_id=case.client_id_override,
                client_secret=case.client_secret_override,
                template_configs=case.template_configs,
            )
            assert result.access_token == "exchanged-tok"


# ===========================================================================
# exchange_authorization_code_for_token_with_redirect (table-driven)
# ===========================================================================


@dataclass
class ExchangeWithRedirectCase:
    desc: str
    settings_raises: bool
    backend_url_template: bool
    template_configs: Optional[dict]
    code_verifier: Optional[str]
    expect_error: bool


EXCHANGE_WITH_REDIRECT_CASES = [
    ExchangeWithRedirectCase("happy path", False, False, None, None, False),
    ExchangeWithRedirectCase("settings KeyError → HTTPException", True, False, None, None, True),
    ExchangeWithRedirectCase(
        "template URL with configs", False, True,
        {"instance_url": "acme.example.com"}, None, False,
    ),
    ExchangeWithRedirectCase("with PKCE verifier", False, False, None, "pkce-verifier", False),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", EXCHANGE_WITH_REDIRECT_CASES, ids=lambda c: c.desc)
async def test_exchange_token_with_redirect(case: ExchangeWithRedirectCase):
    svc = _svc()
    ctx = _make_ctx()

    oauth_settings = _make_oauth2_settings(
        backend_url=(
            "https://{instance_url}/oauth/token" if case.backend_url_template
            else "https://provider.com/token"
        ),
        backend_url_template=case.backend_url_template,
    )

    async def fake_get_by_short_name(name):
        if case.settings_raises:
            raise KeyError(f"No settings for {name}")
        return oauth_settings

    token_response = OAuth2TokenResponse(access_token="redirect-tok")

    with (
        patch(
            "airweave.domains.oauth.oauth2_service.integration_settings"
        ) as mock_int_settings,
        patch.object(svc, "_exchange_code", new_callable=AsyncMock, return_value=token_response),
    ):
        mock_int_settings.get_by_short_name = AsyncMock(side_effect=fake_get_by_short_name)

        if case.expect_error:
            with pytest.raises(Exception):
                await svc.exchange_authorization_code_for_token_with_redirect(
                    ctx,
                    source_short_name="test_source",
                    code="auth-code",
                    redirect_uri="https://custom.app/cb",
                    template_configs=case.template_configs,
                    code_verifier=case.code_verifier,
                )
        else:
            result = await svc.exchange_authorization_code_for_token_with_redirect(
                ctx,
                source_short_name="test_source",
                code="auth-code",
                redirect_uri="https://custom.app/cb",
                template_configs=case.template_configs,
                code_verifier=case.code_verifier,
            )
            assert result.access_token == "redirect-tok"


# ===========================================================================
# refresh_access_token (table-driven)
# ===========================================================================


@dataclass
class RefreshCase:
    desc: str
    decrypted_credential: dict
    config_found: bool
    oauth_type: str
    http_status: int
    http_body: dict
    expect_error: bool
    expect_error_type: type = Exception
    expect_access_token: Optional[str] = None


REFRESH_CASES = [
    RefreshCase(
        "happy path — with_refresh",
        {"refresh_token": "rt-123", "access_token": "old-at"},
        True, "with_refresh", 200,
        {"access_token": "new-at", "token_type": "Bearer"},
        False,
        expect_access_token="new-at",
    ),
    RefreshCase(
        "no refresh token → TokenRefreshError",
        {"access_token": "only-at"},
        True, "with_refresh", 200, {},
        True, TokenRefreshError,
    ),
    RefreshCase(
        "integration config not found → NotFoundException",
        {"refresh_token": "rt-123"},
        False, "with_refresh", 200, {},
        True, NotFoundException,
    ),
    RefreshCase(
        "rotating refresh — new refresh_token stored",
        {"refresh_token": "old-rt", "access_token": "old-at"},
        True, "with_rotating_refresh", 200,
        {"access_token": "fresh-at", "refresh_token": "fresh-rt"},
        False,
        expect_access_token="fresh-at",
    ),
    RefreshCase(
        "HTTP 401 from provider → error bubbles",
        {"refresh_token": "rt-expired"},
        True, "with_refresh", 401,
        {"error": "invalid_grant"},
        True,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", REFRESH_CASES, ids=lambda c: c.desc)
async def test_refresh_access_token(case: RefreshCase):
    deps = Deps()
    svc = deps.build()
    ctx = _make_ctx()
    connection_id = uuid4()
    cred_id = uuid4()

    integration_config = _make_integration_config(oauth_type=case.oauth_type)

    async def fake_get_by_short_name(name):
        if not case.config_found:
            raise KeyError(f"Integration settings not found for {name}")
        return integration_config

    # Seed repos for rotating refresh path
    deps.conn_repo.seed(
        connection_id, SimpleNamespace(id=connection_id, integration_credential_id=cred_id)
    )
    deps.cred_repo.seed(
        cred_id, SimpleNamespace(id=cred_id, encrypted_credentials="enc-blob")
    )
    deps.encryptor.seed_decrypt(dict(case.decrypted_credential))

    mock_http_response = _make_httpx_response(case.http_status, case.http_body)

    async def fake_post(url, headers=None, data=None):
        if case.http_status >= 400:
            raise httpx.HTTPStatusError(
                "err", request=mock_http_response.request, response=mock_http_response
            )
        return mock_http_response

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "airweave.domains.oauth.oauth2_service.integration_settings"
        ) as mock_int_settings,
        patch(
            "airweave.domains.oauth.oauth2_service.httpx.AsyncClient",
            return_value=mock_client,
        ),
    ):
        mock_int_settings.get_by_short_name = AsyncMock(side_effect=fake_get_by_short_name)

        if case.expect_error:
            with pytest.raises(case.expect_error_type):
                await svc.refresh_access_token(
                    MagicMock(), "google_drive", ctx, connection_id,
                    case.decrypted_credential,
                )
        else:
            result = await svc.refresh_access_token(
                MagicMock(), "google_drive", ctx, connection_id,
                case.decrypted_credential,
            )
            assert result.access_token == case.expect_access_token


# ===========================================================================
# _handle_token_response — rotating vs non-rotating (table-driven)
# ===========================================================================


@dataclass
class HandleResponseCase:
    desc: str
    oauth_type: Optional[str]
    response_body: dict
    expect_credential_update: bool


HANDLE_RESPONSE_CASES = [
    HandleResponseCase(
        "with_refresh — no credential update",
        "with_refresh",
        {"access_token": "at-1", "refresh_token": "rt-1"},
        False,
    ),
    HandleResponseCase(
        "with_rotating_refresh — credential updated with new refresh_token",
        "with_rotating_refresh",
        {"access_token": "at-2", "refresh_token": "rt-new"},
        True,
    ),
    HandleResponseCase(
        "no oauth_type — no credential update",
        None,
        {"access_token": "at-3"},
        False,
    ),
    HandleResponseCase(
        "access_only — no credential update",
        "access_only",
        {"access_token": "at-4"},
        False,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", HANDLE_RESPONSE_CASES, ids=lambda c: c.desc)
async def test_handle_token_response(case: HandleResponseCase):
    deps = Deps()
    svc = deps.build()
    ctx = _make_ctx()
    connection_id = uuid4()
    cred_id = uuid4()
    config = _make_integration_config(oauth_type=case.oauth_type)

    http_response = _make_httpx_response(200, case.response_body)

    deps.conn_repo.seed(
        connection_id, SimpleNamespace(id=connection_id, integration_credential_id=cred_id)
    )
    deps.cred_repo.seed(
        cred_id, SimpleNamespace(id=cred_id, encrypted_credentials="enc-blob")
    )
    deps.encryptor.seed_decrypt({"refresh_token": "old-rt", "access_token": "old-at"})

    result = await svc._handle_token_response(
        MagicMock(), http_response, config, ctx, connection_id
    )

    assert result.access_token == case.response_body["access_token"]

    if case.expect_credential_update:
        assert len(deps.cred_repo._updated) == 1
        assert len(deps.encryptor._encrypt_calls) == 1
        encrypted_input = deps.encryptor._encrypt_calls[0]
        assert encrypted_input["refresh_token"] == case.response_body["refresh_token"]
    else:
        assert len(deps.cred_repo._updated) == 0
        assert len(deps.encryptor._encrypt_calls) == 0


# ===========================================================================
# _make_token_request — rate limit retry (integration-ish)
# ===========================================================================


@pytest.mark.asyncio
async def test_make_token_request_retries_on_429():
    """First call 429, second call 200 → succeeds after retry."""
    svc = _svc()
    log = logger.with_context(test="retry")

    call_count = 0

    async def fake_post(url, headers=None, data=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_httpx_response(429)
        return _make_httpx_response(200, {"access_token": "retry-tok"})

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "airweave.domains.oauth.oauth2_service.httpx.AsyncClient",
            return_value=mock_client,
        ),
        patch("airweave.domains.oauth.oauth2_service.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await svc._make_token_request(log, "https://p.com/token", {}, {})

    assert result.status_code == 200
    assert call_count == 2


@pytest.mark.asyncio
async def test_make_token_request_zoho_style_rate_limit():
    """Zoho returns 400 with 'too many requests' — detected as rate limit."""
    svc = _svc()
    log = logger.with_context(test="zoho")

    call_count = 0
    zoho_body = {
        "error_description": "You have made too many requests recently",
        "error": "Access Denied",
    }

    async def fake_post(url, headers=None, data=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_httpx_response(400, zoho_body)
        return _make_httpx_response(200, {"access_token": "zoho-tok"})

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "airweave.domains.oauth.oauth2_service.httpx.AsyncClient",
            return_value=mock_client,
        ),
        patch("airweave.domains.oauth.oauth2_service.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await svc._make_token_request(log, "https://p.com/token", {}, {})

    assert result.status_code == 200
    assert call_count == 2


@pytest.mark.asyncio
async def test_make_token_request_non_retryable_error_raises():
    """500 error (not rate limit) → raises immediately."""
    svc = _svc()
    log = logger.with_context(test="non_retry")

    async def fake_post(url, headers=None, data=None):
        resp = _make_httpx_response(500, {"error": "server_error"})
        raise httpx.HTTPStatusError("err", request=resp.request, response=resp)

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "airweave.domains.oauth.oauth2_service.httpx.AsyncClient",
        return_value=mock_client,
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await svc._make_token_request(log, "https://p.com/token", {}, {})


# ===========================================================================
# _get_redirect_url — uses injected settings
# ===========================================================================


def test_get_redirect_url_uses_injected_settings():
    svc = _svc(app_url="https://myapp.com")
    assert svc._get_redirect_url("slack") == "https://myapp.com/auth/callback"


def test_get_redirect_url_different_env():
    svc = _svc(app_url="http://localhost:3000")
    assert svc._get_redirect_url("jira") == "http://localhost:3000/auth/callback"


# ===========================================================================
# FakeOAuth2Service (verify fake contract matches real service)
# ===========================================================================


class TestFakeOAuth2Service:
    """Verify the fake records calls and returns seeded data."""

    def _make_fake(self):
        from airweave.domains.oauth.fakes.oauth2_service import FakeOAuth2Service
        return FakeOAuth2Service()

    @pytest.mark.asyncio
    async def test_refresh_happy_path(self):
        fake = self._make_fake()
        fake.seed_refresh("slack", "fresh-tok")
        ctx = _make_ctx()
        result = await fake.refresh_access_token(
            MagicMock(), "slack", ctx, uuid4(), {"refresh_token": "rt"},
        )
        assert result.access_token == "fresh-tok"
        assert len(fake.calls_for("refresh_access_token")) == 1

    @pytest.mark.asyncio
    async def test_refresh_unseeded_raises(self):
        fake = self._make_fake()
        with pytest.raises(ValueError, match="No seeded"):
            await fake.refresh_access_token(
                MagicMock(), "unknown", _make_ctx(), uuid4(), {},
            )

    @pytest.mark.asyncio
    async def test_set_error_propagates(self):
        fake = self._make_fake()
        fake.seed_refresh("slack", "tok")
        fake.set_error(TokenRefreshError("forced"))
        with pytest.raises(TokenRefreshError):
            await fake.refresh_access_token(
                MagicMock(), "slack", _make_ctx(), uuid4(), {},
            )

    @pytest.mark.asyncio
    async def test_exchange_happy_path(self):
        fake = self._make_fake()
        fake.seed_exchange("github", "gh-tok")
        result = await fake.exchange_authorization_code_for_token(
            _make_ctx(), "github", "code-abc",
        )
        assert result.access_token == "gh-tok"
        assert len(fake.calls_for("exchange_authorization_code_for_token")) == 1

    @pytest.mark.asyncio
    async def test_generate_auth_url_happy_path(self):
        fake = self._make_fake()
        fake.seed_auth_url("slack", "https://slack.com/oauth?client_id=x")
        settings_obj = _make_oauth2_settings()
        url = await fake.generate_auth_url(settings_obj)
        assert url == "https://slack.com/oauth?client_id=x"

    @pytest.mark.asyncio
    async def test_exchange_with_redirect_happy_path(self):
        fake = self._make_fake()
        fake.seed_exchange("jira", "jira-tok")
        result = await fake.exchange_authorization_code_for_token_with_redirect(
            _make_ctx(),
            source_short_name="jira",
            code="code-xyz",
            redirect_uri="https://app.test/cb",
        )
        assert result.access_token == "jira-tok"

    @pytest.mark.asyncio
    async def test_auth_url_with_redirect_happy_path(self):
        fake = self._make_fake()
        fake.seed_auth_url_with_redirect("airtable", "https://airtable.com/oauth", "v123")
        settings_obj = _make_oauth2_settings(short_name="airtable")
        url, verifier = await fake.generate_auth_url_with_redirect(
            settings_obj, redirect_uri="https://app.test/cb",
        )
        assert url == "https://airtable.com/oauth"
        assert verifier == "v123"

    @pytest.mark.asyncio
    async def test_clear_error(self):
        fake = self._make_fake()
        fake.seed_refresh("slack", "tok")
        fake.set_error(RuntimeError("boom"))
        fake.clear_error()
        result = await fake.refresh_access_token(
            MagicMock(), "slack", _make_ctx(), uuid4(), {},
        )
        assert result.access_token == "tok"
