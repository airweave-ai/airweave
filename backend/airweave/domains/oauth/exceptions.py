"""OAuth domain exceptions."""

from airweave.core.exceptions import BadGatewayError, BadRequestError, NotFoundException


class OAuthSessionNotFoundError(NotFoundException):
    """Raised when an OAuth init session cannot be found by state/token."""

    def __init__(self, detail: str = "OAuth session not found or expired"):
        super().__init__(detail)


class OAuthSessionAlreadyCompletedError(BadRequestError):
    """Raised when an OAuth session has already been completed/failed."""

    def __init__(self, status: str):
        super().__init__(f"OAuth session already {status}")


class OAuthNotConfiguredError(BadRequestError):
    """Raised when OAuth is not configured for a source."""

    def __init__(self, short_name: str):
        super().__init__(f"OAuth not configured for source: {short_name}")


class OAuthTokenExchangeError(BadGatewayError):
    """Raised when the token exchange with the OAuth provider fails."""

    def __init__(self, detail: str = "OAuth token exchange failed"):
        super().__init__(detail)
