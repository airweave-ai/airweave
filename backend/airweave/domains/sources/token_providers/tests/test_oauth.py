"""Unit tests for OAuthTokenProvider.

External dependencies (oauth2_service, DB session) are faked.
Only ``get_db_context`` is patched to avoid real DB access in _refresh_with_retry.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.oauth.exceptions import (
    OAuthRefreshBadRequestError,
    OAuthRefreshCredentialMissingError,
    OAuthRefreshRateLimitError,
    OAuthRefreshServerError,
    OAuthRefreshTokenRevokedError,
)
from airweave.domains.oauth.types import RefreshResult
from airweave.domains.sources.token_providers.exceptions import (
    TokenCredentialsInvalidError,
    TokenProviderConfigError,
    TokenProviderError,
    TokenProviderRateLimitError,
    TokenProviderServerError,
    TokenRefreshNotSupportedError,
)
from airweave.domains.sources.token_providers.oauth import (
    OAuthTokenProvider,
    _extract_access_token,
    _has_refresh_token,
)
from airweave.domains.sources.token_providers.protocol import AuthProviderKind

from .conftest import make_ctx, make_oauth2_service


# ---------------------------------------------------------------------------
# Module-level helpers: _extract_access_token, _has_refresh_token
# ---------------------------------------------------------------------------


@dataclass
class ExtractTokenCase:
    id: str
    creds: object
    expected: Optional[str]


EXTRACT_TOKEN_TABLE = [
    ExtractTokenCase(id="string", creds="tok-123", expected="tok-123"),
    ExtractTokenCase(id="dict-with-key", creds={"access_token": "tok"}, expected="tok"),
    ExtractTokenCase(id="dict-without-key", creds={"refresh_token": "r"}, expected=None),
    ExtractTokenCase(id="object-with-attr", creds=MagicMock(access_token="obj-tok"), expected="obj-tok"),
    ExtractTokenCase(id="none-type", creds=42, expected=None),
]


@pytest.mark.parametrize("case", EXTRACT_TOKEN_TABLE, ids=lambda c: c.id)
def test_extract_access_token(case: ExtractTokenCase):
    assert _extract_access_token(case.creds) == case.expected


@dataclass
class HasRefreshCase:
    id: str
    creds: object
    expected: bool


HAS_REFRESH_TABLE = [
    HasRefreshCase(id="dict-yes", creds={"refresh_token": "ref"}, expected=True),
    HasRefreshCase(id="dict-empty", creds={"refresh_token": ""}, expected=False),
    HasRefreshCase(id="dict-missing", creds={"access_token": "t"}, expected=False),
    HasRefreshCase(id="object-yes", creds=MagicMock(refresh_token="ref"), expected=True),
    HasRefreshCase(id="object-empty", creds=MagicMock(refresh_token=""), expected=False),
    HasRefreshCase(id="string", creds="plain-token", expected=False),
]


@pytest.mark.parametrize("case", HAS_REFRESH_TABLE, ids=lambda c: c.id)
def test_has_refresh_token(case: HasRefreshCase):
    assert _has_refresh_token(case.creds) == case.expected


# ---------------------------------------------------------------------------
# Construction — table-driven
# ---------------------------------------------------------------------------


@dataclass
class ConstructCase:
    id: str
    creds: object
    oauth_type: Optional[str]
    expect_error: bool = False
    expect_refresh: bool = False


CONSTRUCT_TABLE = [
    ConstructCase(
        id="dict-with-refresh",
        creds={"access_token": "tok", "refresh_token": "ref"},
        oauth_type="with_refresh",
        expect_refresh=True,
    ),
    ConstructCase(
        id="dict-no-refresh-token",
        creds={"access_token": "tok"},
        oauth_type="with_refresh",
        expect_refresh=False,
    ),
    ConstructCase(
        id="access-only-type",
        creds={"access_token": "tok"},
        oauth_type="access_only",
        expect_refresh=False,
    ),
    ConstructCase(
        id="string-creds",
        creds="direct-string-token",
        oauth_type=None,
        expect_refresh=False,
    ),
    ConstructCase(
        id="no-access-token-raises",
        creds={"refresh_token": "ref"},
        oauth_type="with_refresh",
        expect_error=True,
    ),
]


def _make_provider(creds, oauth_type, oauth2_service=None, ctx=None):
    return OAuthTokenProvider(
        credentials=creds,
        oauth_type=oauth_type,
        oauth2_service=oauth2_service or make_oauth2_service(),
        source_short_name="github",
        connection_id=uuid4(),
        ctx=ctx or make_ctx(),
        logger=MagicMock(),
    )


@pytest.mark.parametrize("case", CONSTRUCT_TABLE, ids=lambda c: c.id)
def test_construction(case: ConstructCase):
    if case.expect_error:
        with pytest.raises(ValueError, match="No access token"):
            _make_provider(case.creds, case.oauth_type)
    else:
        p = _make_provider(case.creds, case.oauth_type)
        assert p.provider_kind == AuthProviderKind.OAUTH
        assert p.supports_refresh == case.expect_refresh


# ---------------------------------------------------------------------------
# get_token — no refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_token_no_refresh_returns_initial():
    p = _make_provider("my-token", oauth_type="access_only")
    assert await p.get_token() == "my-token"


# ---------------------------------------------------------------------------
# get_token — with refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_token_refreshes_on_first_call():
    svc = make_oauth2_service(refresh_result=RefreshResult(access_token="new-tok", expires_in=3600))
    p = _make_provider(
        {"access_token": "old", "refresh_token": "ref"},
        oauth_type="with_refresh",
        oauth2_service=svc,
    )

    with patch("airweave.domains.sources.token_providers.oauth.get_db_context") as mock_db:
        mock_db.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)
        token = await p.get_token()

    assert token == "new-tok"


@pytest.mark.asyncio
async def test_get_token_returns_cached_within_window():
    svc = make_oauth2_service(refresh_result=RefreshResult(access_token="new-tok", expires_in=3600))
    p = _make_provider(
        {"access_token": "old", "refresh_token": "ref"},
        oauth_type="with_refresh",
        oauth2_service=svc,
    )

    with patch("airweave.domains.sources.token_providers.oauth.get_db_context") as mock_db:
        mock_db.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)
        first = await p.get_token()
        second = await p.get_token()

    assert first == second == "new-tok"
    assert svc.refresh_and_persist.call_count == 1


# ---------------------------------------------------------------------------
# force_refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_refresh_no_refresh_support_raises():
    p = _make_provider("tok", oauth_type="access_only")
    with pytest.raises(TokenRefreshNotSupportedError):
        await p.force_refresh()


@pytest.mark.asyncio
async def test_force_refresh_updates_token():
    svc = make_oauth2_service(refresh_result=RefreshResult(access_token="forced-tok", expires_in=3600))
    p = _make_provider(
        {"access_token": "old", "refresh_token": "ref"},
        oauth_type="with_refresh",
        oauth2_service=svc,
    )

    with patch("airweave.domains.sources.token_providers.oauth.get_db_context") as mock_db:
        mock_db.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)
        token = await p.force_refresh()

    assert token == "forced-tok"


# ---------------------------------------------------------------------------
# _compute_refresh_interval — table-driven
# ---------------------------------------------------------------------------


@dataclass
class RefreshIntervalCase:
    id: str
    expires_in: Optional[int]
    expected_min: float
    expected_max: float


REFRESH_INTERVAL_TABLE = [
    RefreshIntervalCase(id="none-uses-default", expires_in=None, expected_min=1500, expected_max=1500),
    RefreshIntervalCase(id="zero-uses-default", expires_in=0, expected_min=1500, expected_max=1500),
    RefreshIntervalCase(id="negative-uses-default", expires_in=-1, expected_min=1500, expected_max=1500),
    RefreshIntervalCase(id="3600s-80pct", expires_in=3600, expected_min=2880, expected_max=2880),
    RefreshIntervalCase(id="short-clamps-to-60", expires_in=30, expected_min=60, expected_max=60),
    RefreshIntervalCase(id="very-long-clamps-to-50min", expires_in=100_000, expected_min=3000, expected_max=3000),
]


@pytest.mark.parametrize("case", REFRESH_INTERVAL_TABLE, ids=lambda c: c.id)
def test_compute_refresh_interval(case: RefreshIntervalCase):
    result = OAuthTokenProvider._compute_refresh_interval(case.expires_in)
    assert case.expected_min <= result <= case.expected_max


# ---------------------------------------------------------------------------
# _translate_refresh_error — table-driven
# ---------------------------------------------------------------------------


@dataclass
class TranslateErrorCase:
    id: str
    upstream_exc: Exception
    expected_type: type


TRANSLATE_ERROR_TABLE = [
    TranslateErrorCase(
        id="revoked-to-credentials-invalid",
        upstream_exc=OAuthRefreshTokenRevokedError(),
        expected_type=TokenCredentialsInvalidError,
    ),
    TranslateErrorCase(
        id="bad-request-to-credentials-invalid",
        upstream_exc=OAuthRefreshBadRequestError(),
        expected_type=TokenCredentialsInvalidError,
    ),
    TranslateErrorCase(
        id="cred-missing-to-config-error",
        upstream_exc=OAuthRefreshCredentialMissingError("gone"),
        expected_type=TokenProviderConfigError,
    ),
    TranslateErrorCase(
        id="rate-limit-to-rate-limit",
        upstream_exc=OAuthRefreshRateLimitError(retry_after=45.0),
        expected_type=TokenProviderRateLimitError,
    ),
    TranslateErrorCase(
        id="server-error-to-server-error",
        upstream_exc=OAuthRefreshServerError(status_code=502),
        expected_type=TokenProviderServerError,
    ),
    TranslateErrorCase(
        id="unknown-to-server-error",
        upstream_exc=RuntimeError("unexpected"),
        expected_type=TokenProviderServerError,
    ),
]


@pytest.mark.parametrize("case", TRANSLATE_ERROR_TABLE, ids=lambda c: c.id)
def test_translate_refresh_error(case: TranslateErrorCase):
    p = _make_provider(
        {"access_token": "tok", "refresh_token": "ref"},
        oauth_type="with_refresh",
    )
    result = p._translate_refresh_error(case.upstream_exc)
    assert isinstance(result, case.expected_type)
    assert result.source_short_name == "github"


def test_translate_rate_limit_preserves_retry_after():
    p = _make_provider(
        {"access_token": "tok", "refresh_token": "ref"},
        oauth_type="with_refresh",
    )
    upstream = OAuthRefreshRateLimitError(retry_after=90.0)
    result = p._translate_refresh_error(upstream)
    assert isinstance(result, TokenProviderRateLimitError)
    assert result.retry_after == 90.0


def test_translate_server_error_preserves_status_code():
    p = _make_provider(
        {"access_token": "tok", "refresh_token": "ref"},
        oauth_type="with_refresh",
    )
    upstream = OAuthRefreshServerError(status_code=503)
    result = p._translate_refresh_error(upstream)
    assert isinstance(result, TokenProviderServerError)
    assert result.status_code == 503
