"""Exception-to-category classifier for credential/auth failures.

Pure function — no side effects, no I/O, fully testable.
Maps (exception, auth_method) pairs to structured error categories
that the frontend can render into actionable UI.
"""

from airweave.core.shared_models import SourceConnectionErrorCategory
from airweave.domains.source_connections.types import ErrorClassification
from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceTokenRefreshError,
    SourceValidationError,
)
from airweave.domains.sources.token_providers.exceptions import (
    TokenCredentialsInvalidError,
    TokenProviderAccountGoneError,
    TokenProviderError,
)

_AUTH_METHOD_OAUTH_PREFIXES = ("oauth",)
_AUTH_METHOD_AUTH_PROVIDER = "auth_provider"


def _category_for_auth_method(
    auth_method: str,
) -> SourceConnectionErrorCategory:
    """Map a generic credential-invalid error to a category based on auth method."""
    if auth_method.startswith(_AUTH_METHOD_OAUTH_PREFIXES):
        return SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED
    if auth_method == _AUTH_METHOD_AUTH_PROVIDER:
        return SourceConnectionErrorCategory.AUTH_PROVIDER_CREDENTIALS_INVALID
    return SourceConnectionErrorCategory.API_KEY_INVALID


_MESSAGES = {
    SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED: (
        "Your OAuth access token has expired and could not be refreshed. "
        "Please re-authorize this connection."
    ),
    SourceConnectionErrorCategory.API_KEY_INVALID: (
        "The API key for this connection is invalid or has been revoked."
    ),
    SourceConnectionErrorCategory.CLIENT_CREDENTIALS_INVALID: (
        "The client credentials (client ID / client secret) are invalid "
        "or the app has been deleted."
    ),
    SourceConnectionErrorCategory.AUTH_PROVIDER_ACCOUNT_GONE: (
        "The connected account in your auth provider could not be found. It may have been deleted."
    ),
    SourceConnectionErrorCategory.AUTH_PROVIDER_CREDENTIALS_INVALID: (
        "The auth provider credentials are invalid. Please check your auth provider configuration."
    ),
}


_NOT_AUTH = ErrorClassification()


def _classified(cat: SourceConnectionErrorCategory) -> ErrorClassification:
    return ErrorClassification(category=cat, message=_MESSAGES[cat])


def classify_error(exc: Exception, auth_method: str) -> ErrorClassification:
    """Classify an exception into an error category with a human message.

    Returns ErrorClassification with None fields for non-auth errors.
    """
    if isinstance(exc, SourceValidationError) and exc.__cause__:
        return classify_error(exc.__cause__, auth_method)

    if isinstance(exc, TokenProviderAccountGoneError):
        return _classified(SourceConnectionErrorCategory.AUTH_PROVIDER_ACCOUNT_GONE)

    if isinstance(exc, TokenCredentialsInvalidError):
        return _classified(_category_for_auth_method(auth_method))

    if isinstance(exc, (TokenProviderError, SourceTokenRefreshError, SourceAuthError)):
        return _classified(_category_for_auth_method(auth_method))

    return _NOT_AUTH
