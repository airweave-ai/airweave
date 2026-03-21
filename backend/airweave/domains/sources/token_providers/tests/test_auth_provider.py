"""Unit tests for AuthProviderTokenProvider.

The auth provider instance and source registry are faked.
Tests verify token caching, error translation, and retry behaviour.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from airweave.domains.auth_provider.exceptions import (
    AuthProviderAccountNotFoundError,
    AuthProviderAuthError,
    AuthProviderConfigError,
    AuthProviderMissingFieldsError,
    AuthProviderRateLimitError,
    AuthProviderServerError,
)
from airweave.domains.sources.token_providers.auth_provider import AuthProviderTokenProvider
from airweave.domains.sources.token_providers.exceptions import (
    TokenCredentialsInvalidError,
    TokenProviderAccountGoneError,
    TokenProviderConfigError as TPConfigError,
    TokenProviderMissingCredsError,
    TokenProviderRateLimitError,
    TokenProviderServerError,
)
from airweave.domains.sources.token_providers.protocol import AuthProviderKind

from .conftest import FakeSourceRegistryForTP, make_registry_entry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_provider_instance(
    *,
    return_creds: Optional[dict] = None,
    side_effect: Optional[Exception] = None,
) -> MagicMock:
    """Build a fake BaseAuthProvider instance."""
    provider = MagicMock()
    if side_effect:
        provider.get_creds_for_source = AsyncMock(side_effect=side_effect)
    else:
        creds = return_creds or {"access_token": "ap-tok-123"}
        provider.get_creds_for_source = AsyncMock(return_value=creds)
    return provider


def _make_provider(
    *,
    auth_provider_instance=None,
    source_short_name="github",
    source_registry=None,
) -> AuthProviderTokenProvider:
    """Build an AuthProviderTokenProvider for testing."""
    reg = source_registry or FakeSourceRegistryForTP()
    reg.seed(make_registry_entry(source_short_name))

    return AuthProviderTokenProvider(
        auth_provider_instance=auth_provider_instance or _make_auth_provider_instance(),
        source_short_name=source_short_name,
        source_registry=reg,
        logger=MagicMock(),
    )


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


def test_provider_kind():
    p = _make_provider()
    assert p.provider_kind == AuthProviderKind.AUTH_PROVIDER


def test_supports_refresh():
    p = _make_provider()
    assert p.supports_refresh is True


# ---------------------------------------------------------------------------
# get_token — caching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_token_returns_access_token():
    ap = _make_auth_provider_instance(return_creds={"access_token": "fresh-tok"})
    p = _make_provider(auth_provider_instance=ap)
    token = await p.get_token()
    assert token == "fresh-tok"


@pytest.mark.asyncio
async def test_get_token_caches_within_ttl():
    ap = _make_auth_provider_instance(return_creds={"access_token": "cached-tok"})
    p = _make_provider(auth_provider_instance=ap)

    first = await p.get_token()
    second = await p.get_token()

    assert first == second == "cached-tok"
    assert ap.get_creds_for_source.call_count == 1


@pytest.mark.asyncio
async def test_get_token_refetches_after_ttl():
    ap = _make_auth_provider_instance(return_creds={"access_token": "tok-1"})
    p = _make_provider(auth_provider_instance=ap)

    await p.get_token()

    # Simulate TTL expiry by backdating the cache timestamp
    p._cached_at = time.monotonic() - (AuthProviderTokenProvider._CACHE_TTL_SECONDS + 1)

    ap.get_creds_for_source.return_value = {"access_token": "tok-2"}
    token = await p.get_token()
    assert token == "tok-2"
    assert ap.get_creds_for_source.call_count == 2


# ---------------------------------------------------------------------------
# force_refresh — bypasses cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache():
    ap = _make_auth_provider_instance(return_creds={"access_token": "tok-1"})
    p = _make_provider(auth_provider_instance=ap)

    await p.get_token()
    ap.get_creds_for_source.return_value = {"access_token": "tok-2"}
    token = await p.force_refresh()

    assert token == "tok-2"
    assert ap.get_creds_for_source.call_count == 2


# ---------------------------------------------------------------------------
# Error translation — table-driven
# ---------------------------------------------------------------------------


@dataclass
class ErrorTranslationCase:
    id: str
    upstream_exc: Exception
    expected_type: type


ERROR_TRANSLATION_TABLE = [
    ErrorTranslationCase(
        id="auth-error-to-credentials-invalid",
        upstream_exc=AuthProviderAuthError("rejected"),
        expected_type=TokenCredentialsInvalidError,
    ),
    ErrorTranslationCase(
        id="account-not-found-to-account-gone",
        upstream_exc=AuthProviderAccountNotFoundError("gone", account_id="acc-1"),
        expected_type=TokenProviderAccountGoneError,
    ),
    ErrorTranslationCase(
        id="missing-fields-to-missing-creds",
        upstream_exc=AuthProviderMissingFieldsError("no token", missing_fields=["access_token"]),
        expected_type=TokenProviderMissingCredsError,
    ),
    ErrorTranslationCase(
        id="config-error-to-config-error",
        upstream_exc=AuthProviderConfigError("bad app"),
        expected_type=TPConfigError,
    ),
    ErrorTranslationCase(
        id="rate-limit-to-rate-limit",
        upstream_exc=AuthProviderRateLimitError(retry_after=45.0),
        expected_type=TokenProviderRateLimitError,
    ),
    ErrorTranslationCase(
        id="server-error-to-server-error",
        upstream_exc=AuthProviderServerError(status_code=502),
        expected_type=TokenProviderServerError,
    ),
    ErrorTranslationCase(
        id="unexpected-to-server-error",
        upstream_exc=RuntimeError("boom"),
        expected_type=TokenProviderServerError,
    ),
]


@pytest.mark.parametrize("case", ERROR_TRANSLATION_TABLE, ids=lambda c: c.id)
@pytest.mark.asyncio
async def test_fetch_token_error_translation(case: ErrorTranslationCase):
    ap = _make_auth_provider_instance(side_effect=case.upstream_exc)
    p = _make_provider(auth_provider_instance=ap)

    with pytest.raises(case.expected_type):
        await p._fetch_token()


# ---------------------------------------------------------------------------
# Missing access_token in response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_access_token_in_response():
    ap = _make_auth_provider_instance(return_creds={"refresh_token": "ref"})
    p = _make_provider(auth_provider_instance=ap)

    with pytest.raises(TokenProviderMissingCredsError) as exc_info:
        await p._fetch_token()
    assert "access_token" in exc_info.value.missing_fields


@pytest.mark.asyncio
async def test_non_dict_response_raises_missing_creds():
    ap = MagicMock()
    ap.get_creds_for_source = AsyncMock(return_value="just-a-string")
    p = _make_provider(auth_provider_instance=ap)

    with pytest.raises(TokenProviderMissingCredsError):
        await p._fetch_token()


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


def test_implements_token_provider_protocol():
    from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol

    p = _make_provider()
    assert isinstance(p, TokenProviderProtocol)
