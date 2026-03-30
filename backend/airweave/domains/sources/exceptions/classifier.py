"""Error classifier for credential/auth failures on source connections.

Maps source exceptions to SourceConnectionErrorCategory values.

Three exception hierarchies can signal credential errors:
1. AuthProviderError  — raised by auth providers (Composio, Pipedream) directly
2. TokenProviderError — raised by token providers wrapping auth provider errors
3. SourceAuthError    — raised by sources on HTTP 401/403 responses
"""

from __future__ import annotations

from airweave.core.shared_models import SourceConnectionErrorCategory
from airweave.domains.auth_provider.exceptions import (
    AuthProviderAccountNotFoundError,
    AuthProviderAuthError,
    AuthProviderError,
)
from airweave.domains.source_connections.types import ErrorClassification
from airweave.domains.sources.exceptions import SourceAuthError, SourceTokenRefreshError
from airweave.domains.sources.token_providers.exceptions import (
    TokenCredentialsInvalidError,
    TokenExpiredError,
    TokenProviderAccountGoneError,
    TokenProviderError,
)
from airweave.domains.sources.token_providers.protocol import AuthProviderKind

# All exception types the classifier can recognise directly or via __cause__
_CLASSIFIABLE = (
    AuthProviderError,
    SourceAuthError,
    SourceTokenRefreshError,
    TokenProviderError,
)


def classify_error(exc: Exception) -> ErrorClassification:
    """Classify an exception into an error category for UI remediation.

    Args:
        exc: The exception that caused the sync failure.

    Returns:
        ErrorClassification with category and message, or empty if not a
        credential error.
    """
    # Unwrap chained exceptions (e.g. SourceValidationError wrapping a classifiable cause)
    if (
        not isinstance(exc, _CLASSIFIABLE)
        and exc.__cause__
        and isinstance(exc.__cause__, _CLASSIFIABLE)
    ):
        return classify_error(exc.__cause__)

    # --- AuthProviderError hierarchy (direct auth provider failures) ---
    if isinstance(exc, AuthProviderAccountNotFoundError):
        return ErrorClassification(
            category=SourceConnectionErrorCategory.AUTH_PROVIDER_ACCOUNT_GONE,
            message=str(exc),
        )

    if isinstance(exc, AuthProviderAuthError):
        return ErrorClassification(
            category=SourceConnectionErrorCategory.AUTH_PROVIDER_CREDENTIALS_INVALID,
            message=str(exc),
        )

    # Catch-all for remaining AuthProviderError subtypes (e.g. MissingFieldsError,
    # ConfigError) — these are auth provider issues the user needs to address.
    if isinstance(exc, AuthProviderError):
        return ErrorClassification(
            category=SourceConnectionErrorCategory.AUTH_PROVIDER_CREDENTIALS_INVALID,
            message=str(exc),
        )

    # --- Legacy SourceTokenRefreshError ---
    if isinstance(exc, SourceTokenRefreshError):
        return ErrorClassification(
            category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED,
            message=str(exc),
        )

    # --- Legacy SourceAuthError ---
    if isinstance(exc, SourceAuthError):
        return _classify_by_provider_kind(exc.token_provider_kind, exc)

    # --- TokenProviderError hierarchy ---
    if isinstance(exc, TokenProviderAccountGoneError):
        return ErrorClassification(
            category=SourceConnectionErrorCategory.AUTH_PROVIDER_ACCOUNT_GONE,
            message=str(exc),
        )

    if isinstance(exc, TokenExpiredError):
        return ErrorClassification(
            category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED,
            message=str(exc),
        )

    if isinstance(exc, TokenCredentialsInvalidError):
        return _classify_by_provider_kind(exc.provider_kind, exc)

    # Not a credential error — return empty classification
    return ErrorClassification(category=None, message=None)


def _classify_by_provider_kind(
    kind: str,
    exc: Exception,
) -> ErrorClassification:
    """Map a provider_kind string to an error category."""
    if kind in (AuthProviderKind.CREDENTIAL, AuthProviderKind.STATIC):
        return ErrorClassification(
            category=SourceConnectionErrorCategory.API_KEY_INVALID,
            message=str(exc),
        )

    if kind == AuthProviderKind.OAUTH:
        return ErrorClassification(
            category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED,
            message=str(exc),
        )

    if kind == AuthProviderKind.AUTH_PROVIDER:
        return ErrorClassification(
            category=SourceConnectionErrorCategory.AUTH_PROVIDER_CREDENTIALS_INVALID,
            message=str(exc),
        )

    return ErrorClassification(category=None, message=None)
