"""Table-driven tests for classify_error().

One parametrized test per exception type × auth_method combination.
"""

from dataclasses import dataclass
from typing import Optional

import pytest

from airweave.core.shared_models import SourceConnectionErrorCategory
from airweave.domains.source_connections.error_classifier import classify_error
from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceError,
    SourceServerError,
    SourceTokenRefreshError,
    SourceValidationError,
)
from airweave.domains.sources.token_providers.exceptions import (
    TokenCredentialsInvalidError,
    TokenProviderAccountGoneError,
    TokenProviderError,
    TokenProviderServerError,
)


@dataclass
class ClassifyCase:
    name: str
    exc: Exception
    auth_method: str
    expected_category: Optional[SourceConnectionErrorCategory]
    expected_has_message: bool = True


def _validation_wrapping(cause: Exception) -> SourceValidationError:
    """Build a SourceValidationError with __cause__ set."""
    try:
        raise cause
    except Exception:
        try:
            raise SourceValidationError("test", "wrapped") from cause
        except SourceValidationError as e:
            return e


CASES = [
    ClassifyCase(
        name="token_invalid_oauth",
        exc=TokenCredentialsInvalidError("expired", provider_kind="oauth"),
        auth_method="oauth_browser",
        expected_category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED,
    ),
    ClassifyCase(
        name="token_invalid_oauth_token",
        exc=TokenCredentialsInvalidError("expired", provider_kind="oauth"),
        auth_method="oauth_token",
        expected_category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED,
    ),
    ClassifyCase(
        name="token_invalid_direct",
        exc=TokenCredentialsInvalidError("bad key", provider_kind="static"),
        auth_method="direct",
        expected_category=SourceConnectionErrorCategory.API_KEY_INVALID,
    ),
    ClassifyCase(
        name="token_invalid_auth_provider",
        exc=TokenCredentialsInvalidError("bad creds", provider_kind="auth_provider"),
        auth_method="auth_provider",
        expected_category=SourceConnectionErrorCategory.AUTH_PROVIDER_CREDENTIALS_INVALID,
    ),
    ClassifyCase(
        name="account_gone_regardless_of_method",
        exc=TokenProviderAccountGoneError(
            "account deleted", provider_kind="auth_provider", account_id="acc-123"
        ),
        auth_method="auth_provider",
        expected_category=SourceConnectionErrorCategory.AUTH_PROVIDER_ACCOUNT_GONE,
    ),
    ClassifyCase(
        name="account_gone_even_with_oauth_method",
        exc=TokenProviderAccountGoneError(
            "gone", provider_kind="auth_provider", account_id="x"
        ),
        auth_method="oauth_browser",
        expected_category=SourceConnectionErrorCategory.AUTH_PROVIDER_ACCOUNT_GONE,
    ),
    ClassifyCase(
        name="token_provider_error_oauth_byoc",
        exc=TokenProviderError("failed", provider_kind="oauth"),
        auth_method="oauth_byoc",
        expected_category=SourceConnectionErrorCategory.CLIENT_CREDENTIALS_INVALID,
    ),
    ClassifyCase(
        name="token_provider_error_oauth_browser",
        exc=TokenProviderError("failed", provider_kind="oauth"),
        auth_method="oauth_browser",
        expected_category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED,
    ),
    ClassifyCase(
        name="token_provider_error_direct",
        exc=TokenProviderError("failed", provider_kind="static"),
        auth_method="direct",
        expected_category=SourceConnectionErrorCategory.API_KEY_INVALID,
    ),
    ClassifyCase(
        name="token_invalid_oauth_byoc",
        exc=TokenCredentialsInvalidError("bad", provider_kind="oauth"),
        auth_method="oauth_byoc",
        expected_category=SourceConnectionErrorCategory.CLIENT_CREDENTIALS_INVALID,
    ),
    ClassifyCase(
        name="source_auth_error_oauth_byoc",
        exc=SourceAuthError("401"),
        auth_method="oauth_byoc",
        expected_category=SourceConnectionErrorCategory.CLIENT_CREDENTIALS_INVALID,
    ),
    ClassifyCase(
        name="source_token_refresh_oauth",
        exc=SourceTokenRefreshError("refresh failed"),
        auth_method="oauth_browser",
        expected_category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED,
    ),
    ClassifyCase(
        name="source_token_refresh_direct",
        exc=SourceTokenRefreshError("refresh failed"),
        auth_method="direct",
        expected_category=SourceConnectionErrorCategory.API_KEY_INVALID,
    ),
    ClassifyCase(
        name="source_auth_error_oauth",
        exc=SourceAuthError("401 unauthorized"),
        auth_method="oauth_token",
        expected_category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED,
    ),
    ClassifyCase(
        name="source_auth_error_direct",
        exc=SourceAuthError("401 unauthorized"),
        auth_method="direct",
        expected_category=SourceConnectionErrorCategory.API_KEY_INVALID,
    ),
    ClassifyCase(
        name="source_auth_error_auth_provider",
        exc=SourceAuthError("401 unauthorized"),
        auth_method="auth_provider",
        expected_category=SourceConnectionErrorCategory.AUTH_PROVIDER_CREDENTIALS_INVALID,
    ),
    ClassifyCase(
        name="validation_wrapping_token_invalid",
        exc=_validation_wrapping(
            TokenCredentialsInvalidError("expired", provider_kind="oauth")
        ),
        auth_method="oauth_browser",
        expected_category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED,
    ),
    ClassifyCase(
        name="validation_wrapping_account_gone",
        exc=_validation_wrapping(
            TokenProviderAccountGoneError(
                "gone", provider_kind="auth_provider", account_id="x"
            )
        ),
        auth_method="auth_provider",
        expected_category=SourceConnectionErrorCategory.AUTH_PROVIDER_ACCOUNT_GONE,
    ),
    ClassifyCase(
        name="non_auth_source_error",
        exc=SourceServerError("500 internal"),
        auth_method="oauth_browser",
        expected_category=None,
        expected_has_message=False,
    ),
    ClassifyCase(
        name="non_auth_generic_error",
        exc=RuntimeError("something broke"),
        auth_method="direct",
        expected_category=None,
        expected_has_message=False,
    ),
    ClassifyCase(
        name="validation_without_cause",
        exc=SourceValidationError("github", "validate returned False"),
        auth_method="direct",
        expected_category=None,
        expected_has_message=False,
    ),
    ClassifyCase(
        name="token_provider_server_error",
        exc=TokenProviderServerError("timeout", provider_kind="oauth", status_code=500),
        auth_method="oauth_browser",
        expected_category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_classify_error(case: ClassifyCase):
    result = classify_error(case.exc, case.auth_method)
    assert result.category == case.expected_category
    assert result.is_auth_error == (case.expected_category is not None)
    if case.expected_has_message:
        assert result.message is not None and len(result.message) > 0
    else:
        assert result.message is None
