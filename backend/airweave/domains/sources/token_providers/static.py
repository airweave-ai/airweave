"""StaticTokenProvider — holds a fixed token string.

Used for API keys, personal access tokens, direct token injection,
and OAuth callback validation where no refresh is possible.
"""

from airweave.domains.sources.token_providers.exceptions import TokenRefreshNotSupportedError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol

_PROVIDER_KIND = "static"


class StaticTokenProvider(TokenProviderProtocol):
    """TokenProvider backed by a single immutable token string."""

    def __init__(self, token: str, *, source_short_name: str = ""):
        """Initialize with a raw token.

        Args:
            token: The static token value.
            source_short_name: Source identifier (for error context).
        """
        if not token:
            raise ValueError("StaticTokenProvider requires a non-empty token")
        self._token = token
        self._source_short_name = source_short_name

    async def get_token(self) -> str:
        """Return the static token."""
        return self._token

    async def force_refresh(self) -> str:
        """Always raises — static tokens cannot be refreshed.

        Raises:
            TokenRefreshNotSupportedError: Refresh is not supported for static tokens.
        """
        raise TokenRefreshNotSupportedError(
            "Token refresh not supported (static token)",
            source_short_name=self._source_short_name,
            provider_kind=_PROVIDER_KIND,
        )
