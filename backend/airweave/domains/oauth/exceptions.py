"""OAuth domain exceptions.

Hierarchy
---------
OAuthRefreshError                       — base for all token-refresh failures
├── OAuthRefreshTokenRevokedError       — 401 from token endpoint (refresh_token dead)
├── OAuthRefreshBadRequestError         — 400 / invalid_grant
├── OAuthRefreshRateLimitError          — 429 or exhausted rate-limit retries
├── OAuthRefreshServerError              — 5xx / timeout / connection error
└── OAuthRefreshCredentialMissingError  — no connection or credential in DB
"""

from typing import Optional


class OAuthRefreshError(Exception):
    """Base for all OAuth token-refresh failures.

    Carries ``integration_short_name`` so callers can log/route
    without parsing the message.
    """

    def __init__(self, message: str, *, integration_short_name: str = ""):
        """Initialize OAuthRefreshError."""
        self.integration_short_name = integration_short_name
        super().__init__(message)


class OAuthRefreshTokenRevokedError(OAuthRefreshError):
    """Token endpoint returned 401 — the refresh_token is expired or revoked.

    The user needs to re-authenticate.
    """

    def __init__(
        self,
        message: str = "Refresh token revoked or expired",
        *,
        integration_short_name: str = "",
        status_code: int = 401,
    ):
        """Initialize OAuthRefreshTokenRevokedError."""
        self.status_code = status_code
        super().__init__(message, integration_short_name=integration_short_name)


class OAuthRefreshBadRequestError(OAuthRefreshError):
    """Token endpoint returned 400 — invalid grant or malformed request.

    Typically means the refresh_token is invalid (e.g. already rotated
    and the old one was replayed).
    """

    def __init__(
        self,
        message: str = "Invalid grant or malformed refresh request",
        *,
        integration_short_name: str = "",
        error_code: str = "",
    ):
        """Initialize OAuthRefreshBadRequestError."""
        self.error_code = error_code
        super().__init__(message, integration_short_name=integration_short_name)


class OAuthRefreshRateLimitError(OAuthRefreshError):
    """Token endpoint is rate-limiting us (429 or equivalent).

    Raised after exhausting internal retries.
    """

    def __init__(
        self,
        message: str = "OAuth token refresh rate-limited",
        *,
        integration_short_name: str = "",
        retry_after: float = 30.0,
    ):
        """Initialize OAuthRefreshRateLimitError."""
        self.retry_after = retry_after
        super().__init__(message, integration_short_name=integration_short_name)


class OAuthRefreshServerError(OAuthRefreshError):
    """The token endpoint returned a server error (5xx, timeout, connection error)."""

    def __init__(
        self,
        message: str = "Token endpoint returned a server error",
        *,
        integration_short_name: str = "",
        status_code: Optional[int] = None,
    ):
        """Initialize OAuthRefreshServerError."""
        self.status_code = status_code
        super().__init__(message, integration_short_name=integration_short_name)


class OAuthRefreshCredentialMissingError(OAuthRefreshError):
    """Connection or credential record not found in the database.

    Either the connection was deleted, or the credential row is missing.
    This is a data-integrity / configuration issue, not a transient failure.
    """

    pass
