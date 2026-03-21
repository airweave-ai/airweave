"""Unit tests for token provider exception hierarchy.

Verifies inheritance, default values, and custom attributes.
"""

from dataclasses import dataclass
from typing import Optional

import pytest

from airweave.domains.sources.exceptions import SourceError
from airweave.domains.sources.token_providers.exceptions import (
    TokenCredentialsInvalidError,
    TokenExpiredError,
    TokenProviderAccountGoneError,
    TokenProviderConfigError,
    TokenProviderError,
    TokenProviderMissingCredsError,
    TokenProviderRateLimitError,
    TokenProviderServerError,
    TokenRefreshNotSupportedError,
)


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


@dataclass
class InheritanceCase:
    id: str
    exc_class: type
    expected_bases: tuple[type, ...]


INHERITANCE_TABLE = [
    InheritanceCase("base-is-source-error", TokenProviderError, (SourceError,)),
    InheritanceCase("expired", TokenExpiredError, (TokenProviderError,)),
    InheritanceCase("credentials-invalid", TokenCredentialsInvalidError, (TokenProviderError,)),
    InheritanceCase("account-gone", TokenProviderAccountGoneError, (TokenProviderError,)),
    InheritanceCase("config-error", TokenProviderConfigError, (TokenProviderError,)),
    InheritanceCase("missing-creds", TokenProviderMissingCredsError, (TokenProviderError,)),
    InheritanceCase("rate-limit", TokenProviderRateLimitError, (TokenProviderError,)),
    InheritanceCase("server-error", TokenProviderServerError, (TokenProviderError,)),
    InheritanceCase("refresh-not-supported", TokenRefreshNotSupportedError, (TokenProviderError,)),
]


@pytest.mark.parametrize("case", INHERITANCE_TABLE, ids=lambda c: c.id)
def test_exception_inheritance(case: InheritanceCase):
    for base in case.expected_bases:
        assert issubclass(case.exc_class, base)


# ---------------------------------------------------------------------------
# Attribute tests
# ---------------------------------------------------------------------------


def test_base_carries_provider_kind_and_source():
    exc = TokenProviderError("boom", source_short_name="slack", provider_kind="oauth")
    assert exc.provider_kind == "oauth"
    assert exc.source_short_name == "slack"
    assert "boom" in str(exc)


def test_account_gone_carries_account_id():
    exc = TokenProviderAccountGoneError(
        "deleted", source_short_name="jira", provider_kind="auth_provider", account_id="acc-123"
    )
    assert exc.account_id == "acc-123"
    assert exc.provider_kind == "auth_provider"


def test_missing_creds_carries_fields():
    exc = TokenProviderMissingCredsError(
        "no token",
        source_short_name="github",
        provider_kind="auth_provider",
        missing_fields=["access_token", "refresh_token"],
    )
    assert exc.missing_fields == ["access_token", "refresh_token"]


def test_missing_creds_defaults_to_empty_list():
    exc = TokenProviderMissingCredsError("no token")
    assert exc.missing_fields == []


def test_rate_limit_carries_retry_after():
    exc = TokenProviderRateLimitError(retry_after=60.0)
    assert exc.retry_after == 60.0


def test_rate_limit_has_defaults():
    exc = TokenProviderRateLimitError()
    assert exc.retry_after == 30.0
    assert "rate-limited" in str(exc).lower()


def test_server_error_carries_status_code():
    exc = TokenProviderServerError(status_code=503)
    assert exc.status_code == 503


def test_server_error_defaults():
    exc = TokenProviderServerError()
    assert exc.status_code is None
    assert "server error" in str(exc).lower()
