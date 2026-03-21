"""StaticTokenProvider — holds a fixed token string.

Used for API keys, personal access tokens, direct token injection,
and OAuth callback validation where no refresh is possible.
"""

from airweave.domains.sources.token_providers.exceptions import TokenRefreshNotSupportedError
from airweave.domains.sources.token_providers.protocol import AuthProviderKind, TokenProviderProtocol


class StaticTokenProvider(TokenProviderProtocol):
    """TokenProvider backed by a single immutable token string."""

    def __init__(self, token: str, *, source_short_name: str = ""):
        """Initialize with a raw token string."""
        if not token:
            raise ValueError("StaticTokenProvider requires a non-empty token")
        self._token = token
        self._source_short_name = source_short_name

    @property
    def provider_kind(self) -> AuthProviderKind:
        """Discriminator for this auth provider type."""
        return AuthProviderKind.STATIC

    @property
    def supports_refresh(self) -> bool:
        """Static tokens cannot be refreshed."""
        return False

    async def get_token(self) -> str:
        """Return the static token."""
        return self._token

    async def force_refresh(self) -> str:
        """Always raises — static tokens cannot be refreshed."""
        raise TokenRefreshNotSupportedError(
            "Token refresh not supported (static token)",
            source_short_name=self._source_short_name,
            provider_kind=self.provider_kind,
        )
