"""Unit tests for OAuthFlowService.

Table-driven tests for OAuth2 and OAuth1 completion flows using mock services.
No database, no real providers.

Note: initiate_* methods call crud.redirect_session and crud.connection_init_session
which require a real DB. Those are tested at the integration/E2E level.
Unit tests here focus on complete_* (mockable crud lookups) and exception types.
"""

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.oauth.exceptions import (
    OAuthNotConfiguredError,
    OAuthSessionAlreadyCompletedError,
    OAuthSessionNotFoundError,
    OAuthTokenExchangeError,
)
from airweave.domains.oauth.service import OAuthFlowService
from airweave.domains.oauth.types import OAuthCompletionResult
from airweave.models.connection_init_session import ConnectionInitStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(mock_oauth2_service, mock_oauth1_service, mock_integration_settings):
    return OAuthFlowService(
        oauth2_service=mock_oauth2_service,
        oauth1_service=mock_oauth1_service,
        integration_settings=mock_integration_settings,
    )


def _make_init_session(
    *,
    short_name: str = "slack",
    status: str = ConnectionInitStatus.PENDING,
    payload: Optional[dict] = None,
    overrides: Optional[dict] = None,
):
    return MagicMock(
        id=uuid4(),
        short_name=short_name,
        status=status,
        payload=payload or {},
        overrides=overrides or {},
        organization_id=uuid4(),
    )


# ---------------------------------------------------------------------------
# complete_oauth2_callback
# ---------------------------------------------------------------------------


@dataclass
class OAuth2CallbackCase:
    desc: str
    session: Any  # None = not found
    exchange_error: Optional[Exception] = None
    expect_error: Optional[type] = None


OAUTH2_CALLBACK_CASES = [
    OAuth2CallbackCase(
        desc="valid state + code returns OAuthCompletionResult",
        session=_make_init_session(),
    ),
    OAuth2CallbackCase(
        desc="session not found raises OAuthSessionNotFoundError",
        session=None,
        expect_error=OAuthSessionNotFoundError,
    ),
    OAuth2CallbackCase(
        desc="already completed session raises OAuthSessionAlreadyCompletedError",
        session=_make_init_session(status=ConnectionInitStatus.COMPLETED),
        expect_error=OAuthSessionAlreadyCompletedError,
    ),
    OAuth2CallbackCase(
        desc="token exchange failure raises OAuthTokenExchangeError",
        session=_make_init_session(),
        exchange_error=ConnectionError("provider down"),
        expect_error=OAuthTokenExchangeError,
    ),
]


@pytest.mark.parametrize("case", OAUTH2_CALLBACK_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_complete_oauth2_callback(
    case, mock_oauth2_service, mock_oauth1_service, mock_integration_settings
):
    if case.exchange_error:
        mock_oauth2_service.should_raise_on_exchange = case.exchange_error

    service = _make_service(mock_oauth2_service, mock_oauth1_service, mock_integration_settings)

    with patch(
        "airweave.domains.oauth.service.connection_init_session.get_by_state_no_auth",
        return_value=case.session,
    ):
        if case.expect_error:
            with pytest.raises(case.expect_error):
                await service.complete_oauth2_callback(
                    state="state", code="code", db=MagicMock()
                )
        else:
            result = await service.complete_oauth2_callback(
                state="state", code="code", db=MagicMock()
            )
            assert isinstance(result, OAuthCompletionResult)
            assert result.token_response.access_token == "test-access-token"
            assert result.short_name == case.session.short_name


@pytest.mark.asyncio
async def test_oauth2_preserves_payload_and_overrides(
    mock_oauth2_service, mock_oauth1_service, mock_integration_settings
):
    """Completion result carries original payload and overrides from init session."""
    service = _make_service(mock_oauth2_service, mock_oauth1_service, mock_integration_settings)
    session = _make_init_session(
        payload={"name": "My Connection", "collection": "col-123"},
        overrides={"client_id": "custom", "template_configs": {"subdomain": "acme"}},
    )

    with patch(
        "airweave.domains.oauth.service.connection_init_session.get_by_state_no_auth",
        return_value=session,
    ):
        result = await service.complete_oauth2_callback(
            state="state", code="code", db=MagicMock()
        )

    assert result.original_payload == {"name": "My Connection", "collection": "col-123"}
    assert result.overrides["client_id"] == "custom"
    assert result.overrides["template_configs"]["subdomain"] == "acme"


# ---------------------------------------------------------------------------
# complete_oauth1_callback
# ---------------------------------------------------------------------------


@dataclass
class OAuth1CallbackCase:
    desc: str
    session: Any  # None = not found
    seed_oauth1: bool = True
    exchange_error: Optional[Exception] = None
    expect_error: Optional[type] = None


OAUTH1_CALLBACK_CASES = [
    OAuth1CallbackCase(
        desc="valid token + verifier returns OAuthCompletionResult",
        session=_make_init_session(short_name="trello"),
    ),
    OAuth1CallbackCase(
        desc="session not found raises OAuthSessionNotFoundError",
        session=None,
        seed_oauth1=False,
        expect_error=OAuthSessionNotFoundError,
    ),
    OAuth1CallbackCase(
        desc="already completed raises OAuthSessionAlreadyCompletedError",
        session=_make_init_session(short_name="trello", status=ConnectionInitStatus.COMPLETED),
        expect_error=OAuthSessionAlreadyCompletedError,
    ),
    OAuth1CallbackCase(
        desc="token exchange failure raises OAuthTokenExchangeError",
        session=_make_init_session(short_name="trello"),
        exchange_error=ConnectionError("network error"),
        expect_error=OAuthTokenExchangeError,
    ),
    OAuth1CallbackCase(
        desc="source not configured for OAuth1 raises OAuthNotConfiguredError",
        session=_make_init_session(short_name="slack"),
        seed_oauth1=False,
        expect_error=OAuthNotConfiguredError,
    ),
]


@pytest.mark.parametrize("case", OAUTH1_CALLBACK_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_complete_oauth1_callback(
    case, mock_oauth2_service, mock_oauth1_service, mock_integration_settings
):
    if case.seed_oauth1 and case.session:
        mock_integration_settings.seed_oauth1(case.session.short_name)
    elif not case.seed_oauth1 and case.session:
        # Seed as OAuth2 so isinstance(OAuth1Settings) fails
        mock_integration_settings.seed_oauth2(case.session.short_name)

    if case.exchange_error:
        mock_oauth1_service.should_raise_on_exchange = case.exchange_error

    service = _make_service(mock_oauth2_service, mock_oauth1_service, mock_integration_settings)

    with patch(
        "airweave.domains.oauth.service.connection_init_session.get_by_oauth_token_no_auth",
        return_value=case.session,
    ):
        if case.expect_error:
            with pytest.raises(case.expect_error):
                await service.complete_oauth1_callback(
                    oauth_token="token", oauth_verifier="verifier", db=MagicMock()
                )
        else:
            result = await service.complete_oauth1_callback(
                oauth_token="token", oauth_verifier="verifier", db=MagicMock()
            )
            assert isinstance(result, OAuthCompletionResult)
            assert result.token_response.oauth_token == "test-access-token"
            assert result.short_name == case.session.short_name


# ---------------------------------------------------------------------------
# Exception type inheritance (middleware mapping)
# ---------------------------------------------------------------------------


@dataclass
class ExceptionInheritanceCase:
    desc: str
    exception: Exception
    expected_base: type


EXCEPTION_CASES = [
    ExceptionInheritanceCase(
        desc="OAuthSessionNotFoundError is NotFoundException (404)",
        exception=OAuthSessionNotFoundError(),
        expected_base=__import__("airweave.core.exceptions", fromlist=["NotFoundException"]).NotFoundException,
    ),
    ExceptionInheritanceCase(
        desc="OAuthSessionAlreadyCompletedError is BadRequestError (400)",
        exception=OAuthSessionAlreadyCompletedError("done"),
        expected_base=__import__("airweave.core.exceptions", fromlist=["BadRequestError"]).BadRequestError,
    ),
    ExceptionInheritanceCase(
        desc="OAuthNotConfiguredError is BadRequestError (400)",
        exception=OAuthNotConfiguredError("x"),
        expected_base=__import__("airweave.core.exceptions", fromlist=["BadRequestError"]).BadRequestError,
    ),
    ExceptionInheritanceCase(
        desc="OAuthTokenExchangeError is BadGatewayError (502)",
        exception=OAuthTokenExchangeError(),
        expected_base=__import__("airweave.core.exceptions", fromlist=["BadGatewayError"]).BadGatewayError,
    ),
]


@pytest.mark.parametrize("case", EXCEPTION_CASES, ids=lambda c: c.desc)
def test_exception_inheritance(case):
    assert isinstance(case.exception, case.expected_base)


# ---------------------------------------------------------------------------
# initiate_oauth2
# ---------------------------------------------------------------------------


class TestInitiateOAuth2:
    @pytest.mark.asyncio
    async def test_not_configured_raises(
        self, mock_oauth2_service, mock_oauth1_service, mock_integration_settings
    ):
        service = _make_service(mock_oauth2_service, mock_oauth1_service, mock_integration_settings)
        with pytest.raises(OAuthNotConfiguredError):
            await service.initiate_oauth2(
                short_name="unknown",
                payload={},
                organization_id=uuid4(),
                redirect_url=None,
                byoc_client_id=None,
                byoc_client_secret=None,
                template_configs=None,
                db=MagicMock(),
                uow=None,
            )

    @pytest.mark.asyncio
    @patch("airweave.domains.oauth.service.redirect_session")
    @patch("airweave.domains.oauth.service.connection_init_session")
    async def test_happy_path_returns_init_result(
        self,
        mock_cis,
        mock_rs,
        mock_oauth2_service,
        mock_oauth1_service,
        mock_integration_settings,
    ):
        from airweave.domains.oauth.types import OAuthInitResult

        mock_integration_settings.seed_oauth2("slack")

        redirect_sess = MagicMock()
        redirect_sess.id = uuid4()
        mock_rs.generate_unique_code = MagicMock(return_value=MagicMock())
        mock_rs.generate_unique_code.return_value = "abc12345"
        # Make generate_unique_code async
        import asyncio

        async def _gen_code(db, length=8):
            return "abc12345"

        mock_rs.generate_unique_code = _gen_code
        mock_rs.create = MagicMock(return_value=redirect_sess)

        async def _create_rs(*a, **kw):
            return redirect_sess

        mock_rs.create = _create_rs

        init_sess = MagicMock()
        init_sess.id = uuid4()

        async def _create_cis(*a, **kw):
            return init_sess

        mock_cis.create = _create_cis

        service = _make_service(mock_oauth2_service, mock_oauth1_service, mock_integration_settings)
        result = await service.initiate_oauth2(
            short_name="slack",
            payload={"name": "My Connection"},
            organization_id=uuid4(),
            redirect_url=None,
            byoc_client_id=None,
            byoc_client_secret=None,
            template_configs=None,
            db=MagicMock(),
            uow=None,
        )

        assert isinstance(result, OAuthInitResult)
        assert result.init_session_id == init_sess.id
        assert "authorize" in result.proxy_url


# ---------------------------------------------------------------------------
# initiate_oauth1
# ---------------------------------------------------------------------------


class TestInitiateOAuth1:
    @pytest.mark.asyncio
    async def test_not_configured_raises(
        self, mock_oauth2_service, mock_oauth1_service, mock_integration_settings
    ):
        service = _make_service(mock_oauth2_service, mock_oauth1_service, mock_integration_settings)
        with pytest.raises(OAuthNotConfiguredError):
            await service.initiate_oauth1(
                short_name="unknown",
                payload={},
                organization_id=uuid4(),
                redirect_url=None,
                byoc_consumer_key=None,
                byoc_consumer_secret=None,
                db=MagicMock(),
                uow=None,
            )

    @pytest.mark.asyncio
    async def test_oauth2_settings_raises_not_configured(
        self, mock_oauth2_service, mock_oauth1_service, mock_integration_settings
    ):
        """OAuth1 initiation with OAuth2 settings should raise."""
        mock_integration_settings.seed_oauth2("trello")
        service = _make_service(mock_oauth2_service, mock_oauth1_service, mock_integration_settings)
        with pytest.raises(OAuthNotConfiguredError):
            await service.initiate_oauth1(
                short_name="trello",
                payload={},
                organization_id=uuid4(),
                redirect_url=None,
                byoc_consumer_key=None,
                byoc_consumer_secret=None,
                db=MagicMock(),
                uow=None,
            )

    @pytest.mark.asyncio
    @patch("airweave.domains.oauth.service.redirect_session")
    @patch("airweave.domains.oauth.service.connection_init_session")
    async def test_happy_path_returns_init_result(
        self,
        mock_cis,
        mock_rs,
        mock_oauth2_service,
        mock_oauth1_service,
        mock_integration_settings,
    ):
        from airweave.domains.oauth.types import OAuthInitResult

        mock_integration_settings.seed_oauth1("trello")

        redirect_sess = MagicMock()
        redirect_sess.id = uuid4()

        async def _gen_code(db, length=8):
            return "xyz98765"

        mock_rs.generate_unique_code = _gen_code

        async def _create_rs(*a, **kw):
            return redirect_sess

        mock_rs.create = _create_rs

        init_sess = MagicMock()
        init_sess.id = uuid4()

        async def _create_cis(*a, **kw):
            return init_sess

        mock_cis.create = _create_cis

        service = _make_service(mock_oauth2_service, mock_oauth1_service, mock_integration_settings)
        result = await service.initiate_oauth1(
            short_name="trello",
            payload={},
            organization_id=uuid4(),
            redirect_url=None,
            byoc_consumer_key=None,
            byoc_consumer_secret=None,
            db=MagicMock(),
            uow=None,
        )

        assert isinstance(result, OAuthInitResult)
        assert result.init_session_id == init_sess.id
        assert "authorize" in result.proxy_url


# ---------------------------------------------------------------------------
# _build_overrides (pure static method)
# ---------------------------------------------------------------------------


class TestBuildOverrides:
    def test_platform_default_mode(self):
        result = OAuthFlowService._build_overrides(None, None, None, None)
        assert result["oauth_client_mode"] == "platform_default"
        assert result["client_id"] is None

    def test_byoc_mode(self):
        result = OAuthFlowService._build_overrides("cid", "csec", "http://redir", {"sub": "acme"})
        assert result["oauth_client_mode"] == "byoc"
        assert result["client_id"] == "cid"
        assert result["client_secret"] == "csec"
        assert result["redirect_url"] == "http://redir"
        assert result["template_configs"] == {"sub": "acme"}
