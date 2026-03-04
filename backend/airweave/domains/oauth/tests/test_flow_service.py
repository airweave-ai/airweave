"""Unit tests for OAuthFlowService.

Covers:
- initiate_oauth2: happy path, PKCE, missing settings
- initiate_oauth1: happy path, missing settings, non-OAuth1 settings
- complete_oauth2_callback: with/without overrides
- complete_oauth1_callback: delegates to oauth1_service
- create_init_session: platform_default vs BYOC, additional_overrides
- create_proxy_url: URL construction, returns tuple
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from airweave.api.context import ApiContext
from airweave.core.shared_models import AuthMethod
from airweave.domains.oauth.fakes.repository import (
    FakeOAuthInitSessionRepository,
    FakeOAuthRedirectSessionRepository,
)
from airweave.domains.oauth.flow_service import OAuthFlowService
from airweave.domains.oauth.types import OAuth1TokenResponse
from airweave.models.connection_init_session import ConnectionInitStatus
from airweave.platform.auth.schemas import OAuth1Settings, OAuth2TokenResponse
from airweave.schemas.organization import Organization

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx() -> ApiContext:
    org = Organization(id=str(ORG_ID), name="Test Org", created_at=NOW, modified_at=NOW)
    return ApiContext(
        request_id="test-req",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        auth_metadata={},
    )


def _settings(**overrides):
    defaults = dict(api_url="https://api.test.com", app_url="https://app.test.com")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _oauth2_settings():
    return SimpleNamespace(
        authorization_url="https://provider.com/auth",
        token_url="https://provider.com/token",
        scope="read",
    )


def _oauth1_settings():
    return OAuth1Settings(
        integration_short_name="twitter",
        request_token_url="https://provider.com/request_token",
        authorization_url="https://provider.com/authorize",
        access_token_url="https://provider.com/access_token",
        consumer_key="platform_key",
        consumer_secret="platform_secret",
        scope="read",
        expiration="never",
    )


def _service(
    *,
    integration_settings=None,
    oauth2_service=None,
    oauth1_service=None,
    init_session_repo=None,
    redirect_session_repo=None,
    settings=None,
):
    _int_settings = integration_settings or AsyncMock()
    return OAuthFlowService(
        oauth2_service=oauth2_service or AsyncMock(),
        oauth1_service=oauth1_service or MagicMock(),
        integration_settings=_int_settings,
        init_session_repo=init_session_repo or FakeOAuthInitSessionRepository(),
        redirect_session_repo=redirect_session_repo or FakeOAuthRedirectSessionRepository(),
        settings=settings or _settings(),
    )


# ---------------------------------------------------------------------------
# initiate_oauth2
# ---------------------------------------------------------------------------


class TestInitiateOAuth2:
    async def test_happy_path_returns_url_and_verifier(self):
        oauth2_svc = AsyncMock()
        oauth2_svc.generate_auth_url_with_redirect = AsyncMock(
            return_value=("https://provider.com/auth?state=abc", "verifier123")
        )
        int_settings = AsyncMock()
        int_settings.get_by_short_name = AsyncMock(return_value=_oauth2_settings())

        svc = _service(oauth2_service=oauth2_svc, integration_settings=int_settings)
        url, verifier = await svc.initiate_oauth2("github", "state-abc", ctx=_ctx())

        assert url == "https://provider.com/auth?state=abc"
        assert verifier == "verifier123"
        oauth2_svc.generate_auth_url_with_redirect.assert_awaited_once()

    async def test_no_pkce_returns_none_verifier(self):
        oauth2_svc = AsyncMock()
        oauth2_svc.generate_auth_url_with_redirect = AsyncMock(
            return_value=("https://provider.com/auth?state=abc", None)
        )
        int_settings = AsyncMock()
        int_settings.get_by_short_name = AsyncMock(return_value=_oauth2_settings())

        svc = _service(oauth2_service=oauth2_svc, integration_settings=int_settings)
        url, verifier = await svc.initiate_oauth2("github", "state-abc", ctx=_ctx())

        assert verifier is None

    async def test_missing_settings_raises_400(self):
        int_settings = AsyncMock()
        int_settings.get_by_short_name = AsyncMock(return_value=None)

        svc = _service(integration_settings=int_settings)
        with pytest.raises(HTTPException) as exc_info:
            await svc.initiate_oauth2("unknown_source", "state-abc", ctx=_ctx())
        assert exc_info.value.status_code == 400
        assert "OAuth not configured" in exc_info.value.detail

    async def test_passes_client_id_and_template_configs(self):
        oauth2_svc = AsyncMock()
        oauth2_svc.generate_auth_url_with_redirect = AsyncMock(
            return_value=("https://p.com/auth", None)
        )
        int_settings = AsyncMock()
        int_settings.get_by_short_name = AsyncMock(return_value=_oauth2_settings())

        svc = _service(oauth2_service=oauth2_svc, integration_settings=int_settings)
        await svc.initiate_oauth2(
            "github",
            "state",
            client_id="custom-id",
            template_configs={"domain": "acme"},
            ctx=_ctx(),
        )

        call_kwargs = oauth2_svc.generate_auth_url_with_redirect.call_args
        assert call_kwargs.kwargs["client_id"] == "custom-id"
        assert call_kwargs.kwargs["template_configs"] == {"domain": "acme"}

    async def test_redirect_uri_uses_api_url(self):
        oauth2_svc = AsyncMock()
        oauth2_svc.generate_auth_url_with_redirect = AsyncMock(
            return_value=("https://p.com/auth", None)
        )
        int_settings = AsyncMock()
        int_settings.get_by_short_name = AsyncMock(return_value=_oauth2_settings())

        svc = _service(
            oauth2_service=oauth2_svc,
            integration_settings=int_settings,
            settings=_settings(api_url="https://custom-api.com"),
        )
        await svc.initiate_oauth2("github", "state", ctx=_ctx())

        call_kwargs = oauth2_svc.generate_auth_url_with_redirect.call_args
        assert call_kwargs.kwargs["redirect_uri"] == "https://custom-api.com/source-connections/callback"

    async def test_value_error_from_oauth2_service_maps_to_422(self):
        oauth2_svc = AsyncMock()
        oauth2_svc.generate_auth_url_with_redirect = AsyncMock(
            side_effect=ValueError("bad template config")
        )
        int_settings = AsyncMock()
        int_settings.get_by_short_name = AsyncMock(return_value=_oauth2_settings())

        svc = _service(oauth2_service=oauth2_svc, integration_settings=int_settings)
        with pytest.raises(HTTPException) as exc:
            await svc.initiate_oauth2("github", "state", ctx=_ctx())
        assert exc.value.status_code == 422
        assert "bad template config" in exc.value.detail


# ---------------------------------------------------------------------------
# initiate_oauth1
# ---------------------------------------------------------------------------


class TestInitiateOAuth1:
    async def test_happy_path_returns_url_and_overrides(self):
        oauth1_svc = MagicMock()
        oauth1_svc.get_request_token = AsyncMock(
            return_value=OAuth1TokenResponse(oauth_token="req_tok", oauth_token_secret="req_sec")
        )
        oauth1_svc.build_authorization_url = MagicMock(return_value="https://provider.com/auth?oauth_token=req_tok")

        int_settings = AsyncMock()
        int_settings.get_by_short_name = AsyncMock(return_value=_oauth1_settings())

        svc = _service(oauth1_service=oauth1_svc, integration_settings=int_settings)
        url, overrides = await svc.initiate_oauth1(
            "twitter", consumer_key="ck", consumer_secret="cs", ctx=_ctx()
        )

        assert "oauth_token=req_tok" in url
        assert overrides["oauth_token"] == "req_tok"
        assert overrides["oauth_token_secret"] == "req_sec"
        assert overrides["consumer_key"] == "ck"
        assert overrides["consumer_secret"] == "cs"

    async def test_missing_settings_raises_400(self):
        int_settings = AsyncMock()
        int_settings.get_by_short_name = AsyncMock(return_value=None)

        svc = _service(integration_settings=int_settings)
        with pytest.raises(HTTPException) as exc_info:
            await svc.initiate_oauth1(
                "unknown", consumer_key="ck", consumer_secret="cs", ctx=_ctx()
            )
        assert exc_info.value.status_code == 400

    async def test_non_oauth1_settings_raises_400(self):
        int_settings = AsyncMock()
        int_settings.get_by_short_name = AsyncMock(return_value=_oauth2_settings())

        svc = _service(integration_settings=int_settings)
        with pytest.raises(HTTPException) as exc_info:
            await svc.initiate_oauth1(
                "github", consumer_key="ck", consumer_secret="cs", ctx=_ctx()
            )
        assert exc_info.value.status_code == 400
        assert "not configured for OAuth1" in exc_info.value.detail


# ---------------------------------------------------------------------------
# initiate_browser_flow
# ---------------------------------------------------------------------------


class TestInitiateBrowserFlow:
    async def test_oauth2_path_returns_normalized_result(self):
        svc = _service()
        svc.initiate_oauth2 = AsyncMock(return_value=("https://provider.com/auth", "verifier123"))

        result = await svc.initiate_browser_flow(
            short_name="github",
            oauth_type="access_only",
            state="state-abc",
            nested_client_id=None,
            nested_client_secret=None,
            nested_consumer_key=None,
            nested_consumer_secret=None,
            template_configs={"domain": "acme"},
            ctx=_ctx(),
        )

        assert result.provider_auth_url == "https://provider.com/auth"
        assert result.oauth_client_mode == "platform_default"
        assert result.client_id is None
        assert result.client_secret is None
        assert result.additional_overrides["code_verifier"] == "verifier123"

    async def test_oauth1_path_returns_overrides_and_byoc_mode(self):
        svc = _service()
        svc.initiate_oauth1 = AsyncMock(
            return_value=(
                "https://provider.com/oauth1",
                {
                    "oauth_token": "req_tok",
                    "oauth_token_secret": "req_sec",
                    "consumer_key": "ck",
                    "consumer_secret": "cs",
                },
            )
        )

        result = await svc.initiate_browser_flow(
            short_name="twitter",
            oauth_type="oauth1",
            state="state-abc",
            nested_client_id=None,
            nested_client_secret=None,
            nested_consumer_key="ck",
            nested_consumer_secret="cs",
            template_configs=None,
            ctx=_ctx(),
        )

        assert result.provider_auth_url == "https://provider.com/oauth1"
        assert result.oauth_client_mode == "byoc_nested"
        assert result.client_id == "ck"
        assert result.client_secret == "cs"
        assert result.additional_overrides["oauth_token"] == "req_tok"
        assert result.additional_overrides["oauth_token_secret"] == "req_sec"

    async def test_partial_custom_credentials_raises_422(self):
        svc = _service()
        with pytest.raises(HTTPException) as exc:
            await svc.initiate_browser_flow(
                short_name="github",
                oauth_type="access_only",
                state="state-abc",
                nested_client_id="only-id",
                nested_client_secret=None,
                nested_consumer_key=None,
                nested_consumer_secret=None,
                template_configs=None,
                ctx=_ctx(),
            )
        assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# complete_oauth2_callback
# ---------------------------------------------------------------------------


class TestCompleteOAuth2Callback:
    async def test_delegates_to_oauth2_service(self):
        token = OAuth2TokenResponse(access_token="at", token_type="bearer")
        oauth2_svc = AsyncMock()
        oauth2_svc.exchange_authorization_code_for_token_with_redirect = AsyncMock(
            return_value=token
        )

        svc = _service(oauth2_service=oauth2_svc)
        result = await svc.complete_oauth2_callback(
            "github", "code123", {"oauth_redirect_uri": "https://custom/cb"}, _ctx()
        )

        assert result.access_token == "at"
        call_kwargs = oauth2_svc.exchange_authorization_code_for_token_with_redirect.call_args.kwargs
        assert call_kwargs["redirect_uri"] == "https://custom/cb"
        assert call_kwargs["code"] == "code123"

    async def test_falls_back_to_api_url_when_no_override(self):
        oauth2_svc = AsyncMock()
        oauth2_svc.exchange_authorization_code_for_token_with_redirect = AsyncMock(
            return_value=OAuth2TokenResponse(access_token="at", token_type="bearer")
        )

        svc = _service(
            oauth2_service=oauth2_svc,
            settings=_settings(api_url="https://fallback-api.com"),
        )
        await svc.complete_oauth2_callback("github", "code123", {}, _ctx())

        call_kwargs = oauth2_svc.exchange_authorization_code_for_token_with_redirect.call_args.kwargs
        assert call_kwargs["redirect_uri"] == "https://fallback-api.com/source-connections/callback"

    async def test_passes_pkce_verifier_and_template_configs(self):
        oauth2_svc = AsyncMock()
        oauth2_svc.exchange_authorization_code_for_token_with_redirect = AsyncMock(
            return_value=OAuth2TokenResponse(access_token="at", token_type="bearer")
        )

        svc = _service(oauth2_service=oauth2_svc)
        overrides = {
            "code_verifier": "pkce_v",
            "template_configs": {"domain": "acme"},
            "client_id": "cid",
            "client_secret": "csec",
        }
        await svc.complete_oauth2_callback("github", "code123", overrides, _ctx())

        call_kwargs = oauth2_svc.exchange_authorization_code_for_token_with_redirect.call_args.kwargs
        assert call_kwargs["code_verifier"] == "pkce_v"
        assert call_kwargs["template_configs"] == {"domain": "acme"}
        assert call_kwargs["client_id"] == "cid"
        assert call_kwargs["client_secret"] == "csec"


# ---------------------------------------------------------------------------
# complete_oauth1_callback
# ---------------------------------------------------------------------------


class TestCompleteOAuth1Callback:
    async def test_delegates_to_oauth1_service(self):
        token = OAuth1TokenResponse(oauth_token="access_tok", oauth_token_secret="access_sec")
        oauth1_svc = MagicMock()
        oauth1_svc.exchange_token = AsyncMock(return_value=token)

        svc = _service(oauth1_service=oauth1_svc)
        settings = _oauth1_settings()
        overrides = {"oauth_token": "req_tok", "oauth_token_secret": "req_sec"}

        result = await svc.complete_oauth1_callback("twitter", "verifier", overrides, settings, _ctx())

        assert result.oauth_token == "access_tok"
        assert result.oauth_token_secret == "access_sec"
        oauth1_svc.exchange_token.assert_awaited_once()


# ---------------------------------------------------------------------------
# create_init_session
# ---------------------------------------------------------------------------


class TestCreateInitSession:
    async def test_platform_default_mode_when_no_byoc(self):
        init_repo = FakeOAuthInitSessionRepository()
        svc = _service(init_session_repo=init_repo)
        db = AsyncMock()
        uow = MagicMock()

        await svc.create_init_session(
            db,
            short_name="github",
            state="state-1",
            payload={"name": "test"},
            ctx=_ctx(),
            uow=uow,
        )

        assert len(init_repo._calls) == 1
        call_name, obj_in = init_repo._calls[0]
        assert call_name == "create"
        assert obj_in["overrides"]["oauth_client_mode"] == "platform_default"

    async def test_byoc_mode_when_client_creds_provided(self):
        init_repo = FakeOAuthInitSessionRepository()
        svc = _service(init_session_repo=init_repo)
        db = AsyncMock()
        uow = MagicMock()

        await svc.create_init_session(
            db,
            short_name="github",
            state="state-1",
            payload={},
            ctx=_ctx(),
            uow=uow,
            client_id="my-id",
            client_secret="my-secret",
        )

        _, obj_in = init_repo._calls[0]
        assert obj_in["overrides"]["oauth_client_mode"] == "byoc"
        assert obj_in["overrides"]["client_id"] == "my-id"
        assert obj_in["overrides"]["client_secret"] == "my-secret"

    async def test_additional_overrides_merged(self):
        init_repo = FakeOAuthInitSessionRepository()
        svc = _service(init_session_repo=init_repo)
        db = AsyncMock()
        uow = MagicMock()

        await svc.create_init_session(
            db,
            short_name="github",
            state="state-1",
            payload={},
            ctx=_ctx(),
            uow=uow,
            additional_overrides={"extra_key": "extra_val"},
        )

        _, obj_in = init_repo._calls[0]
        assert obj_in["overrides"]["extra_key"] == "extra_val"

    async def test_session_fields_set_correctly(self):
        init_repo = FakeOAuthInitSessionRepository()
        svc = _service(init_session_repo=init_repo)
        db = AsyncMock()
        uow = MagicMock()
        ctx = _ctx()

        await svc.create_init_session(
            db,
            short_name="github",
            state="state-1",
            payload={"name": "test"},
            ctx=ctx,
            uow=uow,
        )

        _, obj_in = init_repo._calls[0]
        assert obj_in["short_name"] == "github"
        assert obj_in["state"] == "state-1"
        assert obj_in["status"] == ConnectionInitStatus.PENDING
        assert obj_in["organization_id"] == ctx.organization.id
        assert obj_in["payload"] == {"name": "test"}

    async def test_redirect_url_defaults_to_none_when_not_provided(self):
        init_repo = FakeOAuthInitSessionRepository()
        svc = _service(init_session_repo=init_repo)
        db = AsyncMock()
        uow = MagicMock()

        await svc.create_init_session(
            db,
            short_name="github",
            state="state-1",
            payload={},
            ctx=_ctx(),
            uow=uow,
        )

        _, obj_in = init_repo._calls[0]
        assert obj_in["overrides"]["redirect_url"] is None


# ---------------------------------------------------------------------------
# create_proxy_url
# ---------------------------------------------------------------------------


class TestCreateProxyUrl:
    async def test_returns_proxy_url_with_code(self):
        redirect_repo = FakeOAuthRedirectSessionRepository()
        svc = _service(
            redirect_session_repo=redirect_repo,
            settings=_settings(api_url="https://api.test.com"),
        )
        db = AsyncMock()

        proxy_url, expires, session_id = await svc.create_proxy_url(
            db, "https://provider.com/auth?tok=1", _ctx()
        )

        assert proxy_url.startswith("https://api.test.com/source-connections/authorize/")
        assert expires > datetime.now(timezone.utc)
        assert session_id is not None
