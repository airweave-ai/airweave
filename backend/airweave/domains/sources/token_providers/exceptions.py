"""Token-provider exceptions — the vocabulary for credential-fetching failures.

Every token provider (OAuth, AuthProvider, Static) translates its
upstream errors into these types so the source lifecycle can take
differentiated action without inspecting ``__cause__``.

Hierarchy
---------
TokenProviderError (SourceError)         — base for all token-provider failures
├── TokenExpiredError                    — token is known-dead, cannot be refreshed (fast abort)
├── TokenCredentialsInvalidError         — token / refresh_token expired or revoked
├── TokenProviderAccountGoneError        — external account record deleted (Composio / Pipedream)
├── TokenProviderConfigError             — fundamental misconfiguration
├── TokenProviderMissingCredsError       — response lacks required credential fields
├── TokenProviderRateLimitError          — upstream rate-limiting
├── TokenProviderServerError              — server error (5xx / timeout)
└── TokenRefreshNotSupportedError        — static token / no refresh_token

Every exception carries:
    ``source_short_name``  — inherited from SourceError
    ``provider_kind``      — "oauth" | "auth_provider" | "static"
"""

from typing import Optional

from airweave.domains.sources.exceptions import SourceError


class TokenProviderError(SourceError):
    """Base for all token-provider runtime failures.

    Sits directly under ``SourceError`` so the lifecycle can catch it
    independently of the older ``SourceAuthError`` / ``SourceTokenRefreshError``
    hierarchy.
    """

    def __init__(
        self,
        message: str,
        *,
        source_short_name: str = "",
        provider_kind: str = "",
    ):
        """Initialize TokenProviderError."""
        self.provider_kind = provider_kind
        super().__init__(message, source_short_name=source_short_name)


class TokenExpiredError(TokenProviderError):
    """Token is known to be expired/invalid and cannot be refreshed.

    Raised by providers (e.g. JWT ``exp`` claim peek when
    ``supports_refresh`` is ``False``) or by sources when
    source-specific documentation indicates the token is dead.
    Lets the pipeline abort immediately instead of waiting for a 401.
    """

    pass


class TokenCredentialsInvalidError(TokenProviderError):
    """Token or refresh_token is expired, revoked, or otherwise invalid.

    The user needs to re-authenticate (OAuth) or re-link their account
    (auth provider).
    """

    pass


class TokenProviderAccountGoneError(TokenProviderError):
    """External account record was deleted from the auth provider.

    The Composio/Pipedream connected-account no longer exists.
    The user needs to re-create the connection in the provider.
    """

    def __init__(
        self,
        message: str,
        *,
        source_short_name: str = "",
        provider_kind: str = "",
        account_id: str = "",
    ):
        """Initialize TokenProviderAccountGoneError."""
        self.account_id = account_id
        super().__init__(message, source_short_name=source_short_name, provider_kind=provider_kind)


class TokenProviderConfigError(TokenProviderError):
    """Fundamental misconfiguration — retrying will never fix this.

    Examples: wrong app in the auth provider, missing template variables,
    credential record missing from DB.
    """

    pass


class TokenProviderMissingCredsError(TokenProviderError):
    """Response from the credential source lacks required fields.

    The account exists and responded, but the credential dict is
    incomplete (e.g. no ``access_token``).
    """

    def __init__(
        self,
        message: str,
        *,
        source_short_name: str = "",
        provider_kind: str = "",
        missing_fields: Optional[list[str]] = None,
    ):
        """Initialize TokenProviderMissingCredsError."""
        self.missing_fields = missing_fields or []
        super().__init__(message, source_short_name=source_short_name, provider_kind=provider_kind)


class TokenProviderRateLimitError(TokenProviderError):
    """Upstream credential source is rate-limiting us.

    The lifecycle / retry layer should wait ``retry_after`` seconds.
    """

    def __init__(
        self,
        message: str = "Token provider rate-limited",
        *,
        source_short_name: str = "",
        provider_kind: str = "",
        retry_after: float = 30.0,
    ):
        """Initialize TokenProviderRateLimitError."""
        self.retry_after = retry_after
        super().__init__(message, source_short_name=source_short_name, provider_kind=provider_kind)


class TokenProviderServerError(TokenProviderError):
    """The credential source returned a server error (5xx, timeout, connection error)."""

    def __init__(
        self,
        message: str = "Token provider returned a server error",
        *,
        source_short_name: str = "",
        provider_kind: str = "",
        status_code: Optional[int] = None,
    ):
        """Initialize TokenProviderServerError."""
        self.status_code = status_code
        super().__init__(message, source_short_name=source_short_name, provider_kind=provider_kind)


class TokenRefreshNotSupportedError(TokenProviderError):
    """Token refresh is not supported by this provider.

    Raised by ``StaticTokenProvider.force_refresh()`` and by
    ``OAuthTokenProvider.force_refresh()`` when no refresh_token exists.
    """

    pass
