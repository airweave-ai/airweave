"""TokenProvider protocol — the contract sources use to obtain auth tokens."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenProviderProtocol(Protocol):
    """Provides auth tokens to sources.

    Sources call ``get_token()`` to obtain a valid token for building
    their own auth headers.  When a 401 is received, sources call
    ``force_refresh()`` to get a fresh token after an explicit refresh.

    Implementations:
        - ``OAuthTokenProvider``  — proactive refresh, DB-backed credential store
        - ``StaticTokenProvider`` — raw string (API keys, PATs, validation)
        - ``AuthProviderTokenProvider`` — delegates to Pipedream / Composio

    All implementations raise exceptions from
    ``domains.sources.token_providers.exceptions``:
        - ``TokenCredentialsInvalidError`` — expired / revoked credentials
        - ``TokenProviderAccountGoneError`` — external account deleted
        - ``TokenProviderConfigError`` — fundamental misconfiguration
        - ``TokenProviderMissingCredsError`` — response missing required fields
        - ``TokenProviderRateLimitError`` — upstream rate-limiting
        - ``TokenProviderServerError`` — server error (5xx / timeout)
        - ``TokenRefreshNotSupportedError`` — static / no refresh_token
    """

    async def get_token(self) -> str:
        """Return a valid token, refreshing proactively if stale."""
        ...

    async def force_refresh(self) -> str:
        """Force an immediate token refresh (e.g. after a 401).

        Raises:
            TokenRefreshNotSupportedError: If refresh is not supported.
            TokenProviderError: If refresh fails.
        """
        ...
