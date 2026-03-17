"""Auth provider domain exceptions.

Hierarchy
---------
AuthProviderError                   — base for all auth-provider failures
├── AuthProviderAuthError           — provider rejected our credentials (401)
├── AuthProviderAccountNotFoundError— connected account not found (404)
├── AuthProviderMissingFieldsError  — response lacks required credential fields
├── AuthProviderConfigError         — app mismatch, unsupported source, etc.
├── AuthProviderRateLimitError      — provider is throttling us (429)
└── AuthProviderServerError         — 5xx / timeout / connection issue

Translation to source exceptions (done by the token provider):
    AuthProviderAuthError           → SourceTokenRefreshError
    AuthProviderAccountNotFoundError→ SourceServerError
    AuthProviderMissingFieldsError  → SourceServerError
    AuthProviderConfigError         → SourceServerError
    AuthProviderRateLimitError      → SourceRateLimitError
    AuthProviderServerError         → SourceServerError
"""

from typing import Optional


class AuthProviderError(Exception):
    """Base for all auth-provider runtime errors.

    Every subclass carries ``provider_name`` so callers can log and
    route without inspecting the message.
    """

    def __init__(self, message: str, *, provider_name: str = ""):
        """Initialize AuthProviderError."""
        self.provider_name = provider_name
        super().__init__(message)


# -- Credential / auth failures ------------------------------------------------


class AuthProviderAuthError(AuthProviderError):
    """Provider rejected our credentials (HTTP 401).

    Typically means the client_id/client_secret or API key is invalid
    or has been revoked.
    """

    pass


class AuthProviderAccountNotFoundError(AuthProviderError):
    """Connected account does not exist in the provider (HTTP 404)."""

    def __init__(self, message: str, *, provider_name: str = "", account_id: str = ""):
        """Initialize AuthProviderAccountNotFoundError."""
        self.account_id = account_id
        super().__init__(message, provider_name=provider_name)


class AuthProviderMissingFieldsError(AuthProviderError):
    """Provider response lacks required credential fields.

    The account exists and responded, but the credential dict does not
    contain the fields the source requires (e.g. ``access_token``).
    """

    def __init__(
        self,
        message: str,
        *,
        provider_name: str = "",
        missing_fields: Optional[list[str]] = None,
        available_fields: Optional[list[str]] = None,
    ):
        """Initialize AuthProviderMissingFieldsError."""
        self.missing_fields = missing_fields or []
        self.available_fields = available_fields or []
        super().__init__(message, provider_name=provider_name)


class AuthProviderConfigError(AuthProviderError):
    """Static configuration issue — wrong app, blocked source, etc.

    Retrying will never fix this; the connection setup is wrong.
    """

    pass


# -- Rate-limit / server errors ------------------------------------------------


class AuthProviderRateLimitError(AuthProviderError):
    """Provider is throttling requests (HTTP 429)."""

    def __init__(
        self,
        message: str = "Auth provider rate limit exceeded",
        *,
        provider_name: str = "",
        retry_after: float = 30.0,
    ):
        """Initialize AuthProviderRateLimitError."""
        self.retry_after = retry_after
        super().__init__(message, provider_name=provider_name)


class AuthProviderServerError(AuthProviderError):
    """Server error — 5xx, timeout, connection refused."""

    def __init__(
        self,
        message: str = "Auth provider server error",
        *,
        provider_name: str = "",
        status_code: Optional[int] = None,
    ):
        """Initialize AuthProviderServerError."""
        self.status_code = status_code
        super().__init__(message, provider_name=provider_name)


AuthProviderTemporaryError = AuthProviderServerError
