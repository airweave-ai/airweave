"""Unit tests for OAuthFlowService.

Covers:
- initiate_oauth2 (happy path, settings-not-found)
- initiate_oauth1 (happy path, settings-not-found, wrong settings type)
- complete_oauth2_callback (arg forwarding, redirect_uri fallback, BYOC overrides)
- complete_oauth1_callback (arg forwarding)
- create_init_session (BYOC vs platform default, overrides assembly, expiry)
- create_proxy_url (URL pattern, expiry, delegates to redirect_session_repo)

Uses table-driven tests wherever possible.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.domains.oauth.flow_service import OAuthFlowService
from airweave.domains.oauth.types import OAuth1TokenResponse
from airweave.platform.auth.schemas import OAuth1Settings, OAuth2Settings, OAuth2TokenResponse
from airweave.schemas.organization import Organization

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()

API_URL = "https://api.test.airweave.com"
APP_URL = "https://app.test.airweave.com"


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
    defaults = dict(api_url=API_URL, app_url=APP_URL)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_oauth2_settings(**overrides) -> OAuth2Settings:
    defaults = dict(
        integration_short_name="slack",
        url="https://slack.com/oauth/v2/authorize",
        backend_url="https://slack.com/api/oauth.v2.access",
        client_id="test-client-id",
        client_secret="test-client-secret",
        grant_type="authorization_code",
        content_type="application/x-www-form-urlencoded",
        client_credential_location="body",
    )
    defaults.update(overrides)
    return OAuth2Settings(**defaults)


def _make_oauth1_settings(**overrides) -> OAuth1Settings:
    defaults = dict(
        integration_short_name="twitter",
        request_token_url="https://api.twitter.com/oauth/request_token",
        authorization_url="https://api.twitter.com/oauth/authorize",
        access_token_url="https://api.twitter.com/oauth/access_token",
        consumer_key="platform-consumer-key",
        consumer_secret="platform-consumer-secret",
    )
    defaults.update(overrides)
    return OAuth1Settings(**defaults)


# ---------------------------------------------------------------------------
# Fakes (test-local, minimal)
# ---------------------------------------------------------------------------


class FakeIntegrationSettings:
    """Fake IntegrationSettings for testing."""

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    def seed(self, short_name: str, settings: Any) -> None:
        self._store[short_name] = settings

    async def get_by_short_name(self, short_name: str) -> Any:
        return self._store.get(short_name)


class FakeOAuth2Service:
    """Minimal fake that records calls and returns seeded data."""

    def __init__(self) -> None:
        self._calls: List[tuple] = []
        self._auth_url_with_redirect: Dict[str, Tuple[str, Optional[str]]] = {}
        self._exchange_responses: Dict[str, OAuth2TokenResponse] = {}

    def seed_auth_url_with_redirect(
        self, short_name: str, url: str, verifier: Optional[str] = None
    ) -> None:
        self._auth_url_with_redirect[short_name] = (url, verifier)

    def seed_exchange(self, short_name: str, token: str, **extra: str) -> None:
        self._exchange_responses[short_name] = OAuth2TokenResponse(
            access_token=token, **extra
        )

    async def generate_auth_url_with_redirect(
        self,
        oauth2_settings: OAuth2Settings,
        *,
        redirect_uri: str,
        client_id: Optional[str] = None,
        state: Optional[str] = None,
        template_configs: Optional[dict] = None,
    ) -> Tuple[str, Optional[str]]:
        self._calls.append(
            (
                "generate_auth_url_with_redirect",
                oauth2_settings.integration_short_name,
                redirect_uri,
                client_id,
                state,
                template_configs,
            )
        )
        result = self._auth_url_with_redirect.get(oauth2_settings.integration_short_name)
        if result is None:
            raise ValueError(f"No seeded auth URL for {oauth2_settings.integration_short_name}")
        return result

    async def exchange_authorization_code_for_token_with_redirect(
        self,
        ctx: ApiContext,
        *,
        source_short_name: str,
        code: str,
        redirect_uri: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        template_configs: Optional[dict] = None,
        code_verifier: Optional[str] = None,
    ) -> OAuth2TokenResponse:
        self._calls.append(
            (
                "exchange_with_redirect",
                source_short_name,
                code,
                redirect_uri,
                client_id,
                client_secret,
                template_configs,
                code_verifier,
            )
        )
        resp = self._exchange_responses.get(source_short_name)
        if not resp:
            raise ValueError(f"No seeded exchange for {source_short_name}")
        return resp


class FakeOAuth1Service:
    """Minimal fake for OAuth1ServiceProtocol."""

    def __init__(self) -> None:
        self._calls: List[tuple] = []
        self._request_token: Optional[OAuth1TokenResponse] = None
        self._auth_url: str = "https://provider.example.com/oauth/authorize?oauth_token=rt"
        self._exchange_response: Optional[OAuth1TokenResponse] = None

    def seed_request_token(self, resp: OAuth1TokenResponse) -> None:
        self._request_token = resp

    def seed_exchange(self, resp: OAuth1TokenResponse) -> None:
        self._exchange_response = resp

    async def get_request_token(self, **kwargs) -> OAuth1TokenResponse:
        self._calls.append(("get_request_token", kwargs))
        return self._request_token or OAuth1TokenResponse(
            oauth_token="req-tok", oauth_token_secret="req-sec"
        )

    def build_authorization_url(self, **kwargs) -> str:
        self._calls.append(("build_authorization_url", kwargs))
        return self._auth_url

    async def exchange_token(self, **kwargs) -> OAuth1TokenResponse:
        self._calls.append(("exchange_token", kwargs))
        return self._exchange_response or OAuth1TokenResponse(
            oauth_token="access-tok", oauth_token_secret="access-sec"
        )


class FakeInitSessionRepo:
    """Fake for OAuthInitSessionRepositoryProtocol."""

    def __init__(self) -> None:
        self._calls: List[tuple] = []
        self._created: List[Dict[str, Any]] = []

    async def create(self, db, *, obj_in, ctx, uow) -> SimpleNamespace:
        self._calls.append(("create", obj_in))
        self._created.append(obj_in)
        return SimpleNamespace(id=uuid4(), **obj_in)

    async def get_by_state_no_auth(self, db, *, state) -> None:
        return None

    async def get_by_oauth_token_no_auth(self, db, *, oauth_token) -> None:
        return None

    async def mark_completed(self, db, *, session_id, final_connection_id, ctx) -> None:
        self._calls.append(("mark_completed", session_id))


class FakeRedirectSessionRepo:
    """Fake for OAuthRedirectSessionRepositoryProtocol."""

    def __init__(self) -> None:
        self._calls: List[tuple] = []
        self._code: str = "abc12345"
        self._id: UUID = uuid4()

    async def generate_unique_code(self, db, *, length: int) -> str:
        self._calls.append(("generate_unique_code", length))
        return self._code

    async def create(self, db, *, code, final_url, expires_at, ctx, uow=None) -> SimpleNamespace:
        self._calls.append(("create", code, final_url))
        return SimpleNamespace(id=self._id)


# ---------------------------------------------------------------------------
# Deps helper
# ---------------------------------------------------------------------------


class Deps:
    """Bundles fakes for OAuthFlowService constructor."""

    def __init__(self, **settings_overrides):
        self.oauth2_svc = FakeOAuth2Service()
        self.oauth1_svc = FakeOAuth1Service()
        self.int_settings = FakeIntegrationSettings()
        self.init_session_repo = FakeInitSessionRepo()
        self.redirect_session_repo = FakeRedirectSessionRepo()
        self.settings = _make_settings(**settings_overrides)

    def build(self) -> OAuthFlowService:
        return OAuthFlowService(
            oauth2_service=self.oauth2_svc,
            oauth1_service=self.oauth1_svc,
            integration_settings=self.int_settings,
            init_session_repo=self.init_session_repo,
            redirect_session_repo=self.redirect_session_repo,
            settings=self.settings,
        )


# ===========================================================================
# initiate_oauth2 (table-driven)
# ===========================================================================


@dataclass
class InitOAuth2Case:
    desc: str
    short_name: str
    seed_settings: bool
    seed_pkce: bool = False
    client_id_override: Optional[str] = None
    template_configs: Optional[dict] = None
    expect_error: bool = False
    expect_verifier: bool = False


INIT_OAUTH2_CASES = [
    InitOAuth2Case(
        "happy path — no PKCE",
        "slack",
        seed_settings=True,
    ),
    InitOAuth2Case(
        "happy path — with PKCE verifier",
        "airtable",
        seed_settings=True,
        seed_pkce=True,
        expect_verifier=True,
    ),
    InitOAuth2Case(
        "client_id override forwarded",
        "slack",
        seed_settings=True,
        client_id_override="custom-cid",
    ),
    InitOAuth2Case(
        "template_configs forwarded",
        "salesforce",
        seed_settings=True,
        template_configs={"instance_url": "acme.my.salesforce.com"},
    ),
    InitOAuth2Case(
        "settings not found → HTTPException",
        "nonexistent",
        seed_settings=False,
        expect_error=True,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", INIT_OAUTH2_CASES, ids=lambda c: c.desc)
async def test_initiate_oauth2(case: InitOAuth2Case):
    deps = Deps()
    svc = deps.build()
    ctx = _make_ctx()

    if case.seed_settings:
        settings_obj = _make_oauth2_settings(integration_short_name=case.short_name)
        deps.int_settings.seed(case.short_name, settings_obj)
        deps.oauth2_svc.seed_auth_url_with_redirect(
            case.short_name,
            f"https://provider.example.com/auth?source={case.short_name}",
            "pkce-verifier-123" if case.seed_pkce else None,
        )

    if case.expect_error:
        with pytest.raises(HTTPException) as exc_info:
            await svc.initiate_oauth2(
                case.short_name,
                "state-abc",
                client_id=case.client_id_override,
                template_configs=case.template_configs,
                ctx=ctx,
            )
        assert exc_info.value.status_code == 400
        return

    url, verifier = await svc.initiate_oauth2(
        case.short_name,
        "state-abc",
        client_id=case.client_id_override,
        template_configs=case.template_configs,
        ctx=ctx,
    )

    assert url.startswith("https://provider.example.com/auth")
    if case.expect_verifier:
        assert verifier == "pkce-verifier-123"
    else:
        assert verifier is None

    call = deps.oauth2_svc._calls[-1]
    assert call[0] == "generate_auth_url_with_redirect"
    assert call[2] == f"{API_URL}/source-connections/callback"
    if case.client_id_override:
        assert call[3] == case.client_id_override


# ===========================================================================
# initiate_oauth1 (table-driven)
# ===========================================================================


@dataclass
class InitOAuth1Case:
    desc: str
    short_name: str
    seed_settings: bool
    seed_oauth1: bool = True
    expect_error: bool = False
    expect_status_code: int = 400


INIT_OAUTH1_CASES = [
    InitOAuth1Case(
        "happy path",
        "twitter",
        seed_settings=True,
    ),
    InitOAuth1Case(
        "settings not found → HTTPException 400",
        "nonexistent",
        seed_settings=False,
        expect_error=True,
    ),
    InitOAuth1Case(
        "settings are OAuth2 not OAuth1 → HTTPException 400",
        "slack",
        seed_settings=True,
        seed_oauth1=False,
        expect_error=True,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", INIT_OAUTH1_CASES, ids=lambda c: c.desc)
async def test_initiate_oauth1(case: InitOAuth1Case):
    deps = Deps()
    svc = deps.build()
    ctx = _make_ctx()

    if case.seed_settings:
        if case.seed_oauth1:
            settings_obj = _make_oauth1_settings(integration_short_name=case.short_name)
        else:
            settings_obj = _make_oauth2_settings(integration_short_name=case.short_name)
        deps.int_settings.seed(case.short_name, settings_obj)

    if case.expect_error:
        with pytest.raises(HTTPException) as exc_info:
            await svc.initiate_oauth1(
                case.short_name,
                "state-abc",
                consumer_key="ck",
                consumer_secret="cs",
                ctx=ctx,
            )
        assert exc_info.value.status_code == case.expect_status_code
        return

    url, overrides = await svc.initiate_oauth1(
        case.short_name,
        "state-abc",
        consumer_key="ck",
        consumer_secret="cs",
        ctx=ctx,
    )

    assert isinstance(url, str)
    assert overrides["consumer_key"] == "ck"
    assert overrides["consumer_secret"] == "cs"
    assert "oauth_token" in overrides
    assert "oauth_token_secret" in overrides


# ===========================================================================
# complete_oauth2_callback (table-driven)
# ===========================================================================


@dataclass
class CompleteOAuth2Case:
    desc: str
    overrides: Dict[str, Any]
    expect_redirect_uri: str
    expect_client_id: Optional[str] = None
    expect_client_secret: Optional[str] = None
    expect_template_configs: Optional[dict] = None
    expect_code_verifier: Optional[str] = None


COMPLETE_OAUTH2_CASES = [
    CompleteOAuth2Case(
        "fallback redirect_uri",
        overrides={},
        expect_redirect_uri=f"{API_URL}/source-connections/callback",
    ),
    CompleteOAuth2Case(
        "custom redirect_uri from overrides",
        overrides={"oauth_redirect_uri": "https://custom.app/cb"},
        expect_redirect_uri="https://custom.app/cb",
    ),
    CompleteOAuth2Case(
        "BYOC overrides forwarded",
        overrides={"client_id": "byoc-id", "client_secret": "byoc-secret"},
        expect_redirect_uri=f"{API_URL}/source-connections/callback",
        expect_client_id="byoc-id",
        expect_client_secret="byoc-secret",
    ),
    CompleteOAuth2Case(
        "template_configs forwarded",
        overrides={"template_configs": {"instance_url": "acme.sf.com"}},
        expect_redirect_uri=f"{API_URL}/source-connections/callback",
        expect_template_configs={"instance_url": "acme.sf.com"},
    ),
    CompleteOAuth2Case(
        "code_verifier forwarded",
        overrides={"code_verifier": "pkce-v"},
        expect_redirect_uri=f"{API_URL}/source-connections/callback",
        expect_code_verifier="pkce-v",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", COMPLETE_OAUTH2_CASES, ids=lambda c: c.desc)
async def test_complete_oauth2_callback(case: CompleteOAuth2Case):
    deps = Deps()
    svc = deps.build()
    ctx = _make_ctx()

    deps.oauth2_svc.seed_exchange("slack", "tok-123")

    result = await svc.complete_oauth2_callback("slack", "auth-code", case.overrides, ctx)
    assert result.access_token == "tok-123"

    call = deps.oauth2_svc._calls[-1]
    assert call[0] == "exchange_with_redirect"
    assert call[1] == "slack"
    assert call[2] == "auth-code"
    assert call[3] == case.expect_redirect_uri
    assert call[4] == case.expect_client_id
    assert call[5] == case.expect_client_secret
    assert call[6] == case.expect_template_configs
    assert call[7] == case.expect_code_verifier


# ===========================================================================
# complete_oauth1_callback
# ===========================================================================


@pytest.mark.asyncio
async def test_complete_oauth1_callback_forwards_correctly():
    deps = Deps()
    svc = deps.build()
    ctx = _make_ctx()

    oauth_settings = _make_oauth1_settings()
    overrides = {"oauth_token": "req-tok-1", "oauth_token_secret": "req-sec-1"}

    result = await svc.complete_oauth1_callback(
        "twitter", "verifier-xyz", overrides, oauth_settings, ctx
    )

    assert result.oauth_token == "access-tok"
    assert result.oauth_token_secret == "access-sec"

    call = deps.oauth1_svc._calls[-1]
    assert call[0] == "exchange_token"
    kwargs = call[1]
    assert kwargs["oauth_verifier"] == "verifier-xyz"
    assert kwargs["oauth_token"] == "req-tok-1"
    assert kwargs["oauth_token_secret"] == "req-sec-1"


# ===========================================================================
# create_init_session (table-driven)
# ===========================================================================


@dataclass
class CreateInitSessionCase:
    desc: str
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_url: Optional[str] = None
    template_configs: Optional[dict] = None
    additional_overrides: Optional[Dict[str, Any]] = None
    expect_oauth_client_mode: str = "platform_default"


CREATE_INIT_SESSION_CASES = [
    CreateInitSessionCase(
        "platform default mode",
    ),
    CreateInitSessionCase(
        "BYOC mode — both client_id and secret",
        client_id="byoc-id",
        client_secret="byoc-sec",
        expect_oauth_client_mode="byoc",
    ),
    CreateInitSessionCase(
        "client_id only — still platform default",
        client_id="byoc-id",
        expect_oauth_client_mode="platform_default",
    ),
    CreateInitSessionCase(
        "custom redirect_url",
        redirect_url="https://custom.app",
    ),
    CreateInitSessionCase(
        "template_configs passed through",
        template_configs={"instance_url": "x.y.z"},
    ),
    CreateInitSessionCase(
        "additional_overrides merged",
        additional_overrides={"code_verifier": "pkce-v"},
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CREATE_INIT_SESSION_CASES, ids=lambda c: c.desc)
async def test_create_init_session(case: CreateInitSessionCase):
    deps = Deps()
    svc = deps.build()
    ctx = _make_ctx()

    from unittest.mock import MagicMock

    db = MagicMock()
    uow = MagicMock()

    result = await svc.create_init_session(
        db,
        short_name="slack",
        state="state-123",
        payload={"name": "My Connection"},
        ctx=ctx,
        uow=uow,
        client_id=case.client_id,
        client_secret=case.client_secret,
        redirect_url=case.redirect_url,
        template_configs=case.template_configs,
        additional_overrides=case.additional_overrides,
    )

    assert len(deps.init_session_repo._created) == 1
    created = deps.init_session_repo._created[0]

    assert created["short_name"] == "slack"
    assert created["state"] == "state-123"
    assert created["payload"] == {"name": "My Connection"}
    assert created["overrides"]["oauth_client_mode"] == case.expect_oauth_client_mode
    assert created["overrides"]["client_id"] == case.client_id
    assert created["overrides"]["client_secret"] == case.client_secret

    expected_redirect = case.redirect_url or APP_URL
    assert created["overrides"]["redirect_url"] == expected_redirect
    assert created["overrides"]["oauth_redirect_uri"] == f"{API_URL}/source-connections/callback"
    assert created["overrides"]["template_configs"] == case.template_configs

    if case.additional_overrides:
        for k, v in case.additional_overrides.items():
            assert created["overrides"][k] == v

    assert created["expires_at"] is not None


# ===========================================================================
# create_proxy_url
# ===========================================================================


@pytest.mark.asyncio
async def test_create_proxy_url_returns_correct_format():
    deps = Deps()
    svc = deps.build()
    ctx = _make_ctx()

    from unittest.mock import MagicMock

    db = MagicMock()

    proxy_url, proxy_expires, session_id = await svc.create_proxy_url(
        db, "https://provider.example.com/auth?state=xyz", ctx
    )

    assert proxy_url == f"{API_URL}/source-connections/authorize/{deps.redirect_session_repo._code}"
    assert isinstance(proxy_expires, datetime)
    assert proxy_expires > NOW
    assert session_id == deps.redirect_session_repo._id

    create_call = [c for c in deps.redirect_session_repo._calls if c[0] == "create"]
    assert len(create_call) == 1
    assert create_call[0][1] == deps.redirect_session_repo._code
    assert create_call[0][2] == "https://provider.example.com/auth?state=xyz"
