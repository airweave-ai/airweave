"""OAuthTokenProvider — proactive token refresh for OAuth2 sources.

Thin wrapper: timer + lock + cache. The actual refresh is delegated to
``oauth2_service.refresh_and_persist()``.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Optional, Union
from uuid import UUID

from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.core.logging import ContextualLogger
from airweave.db.session import get_db_context
from airweave.domains.oauth.exceptions import (
    OAuthRefreshBadRequestError,
    OAuthRefreshCredentialMissingError,
    OAuthRefreshRateLimitError,
    OAuthRefreshServerError,
    OAuthRefreshTokenRevokedError,
)
from airweave.domains.oauth.types import RefreshResult
from airweave.domains.sources.token_providers.exceptions import (
    TokenCredentialsInvalidError,
    TokenProviderConfigError,
    TokenProviderError,
    TokenProviderRateLimitError,
    TokenProviderServerError,
    TokenRefreshNotSupportedError,
)
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol

if TYPE_CHECKING:
    from airweave.api.context import ApiContext
    from airweave.domains.oauth.protocols import OAuth2ServiceProtocol

_REFRESHABLE_OAUTH_TYPES = frozenset({"with_refresh", "with_rotating_refresh"})
_DEFAULT_REFRESH_INTERVAL_SECONDS = 25 * 60
_REFRESH_LIFETIME_FRACTION = 0.80
_MIN_REFRESH_INTERVAL_SECONDS = 60
_MAX_REFRESH_INTERVAL_SECONDS = 50 * 60
_PROVIDER_KIND = "oauth"


class OAuthTokenProvider(TokenProviderProtocol):
    """TokenProvider backed by OAuth2 credentials.

    Accepts raw credentials and determines refresh capability internally:
    - If oauth_type supports refresh AND a refresh_token is present,
      proactively refreshes before expiry.
    - Otherwise serves the initial access_token as a static token.

    """

    def __init__(
        self,
        credentials: Union[str, dict, BaseModel],
        *,
        oauth_type: Optional[str],
        oauth2_service: OAuth2ServiceProtocol,
        source_short_name: str,
        connection_id: UUID,
        ctx: ApiContext,
        logger: ContextualLogger,
        config_fields: Optional[dict] = None,
    ):
        """Initialize the OAuth token provider.

        Args:
            credentials: Raw credentials (str token, dict, or Pydantic model).
            oauth_type: OAuth type from the source connection (e.g. "with_refresh").
            oauth2_service: Service that handles the actual refresh + persistence.
            source_short_name: Source identifier.
            connection_id: Connection UUID (passed to oauth2_service for refresh).
            ctx: API context (passed to oauth2_service for refresh).
            logger: Contextual logger with sync metadata.
            config_fields: Optional config fields for templated backend URLs.

        Raises:
            ValueError: If no access token can be extracted from credentials.
        """
        token = _extract_access_token(credentials)
        if not token:
            raise ValueError(f"No access token found in credentials for {source_short_name}")

        self._token = token
        self._oauth2_service = oauth2_service
        self._source_short_name = source_short_name
        self._connection_id = connection_id
        self._ctx = ctx
        self._logger = logger
        self._config_fields = config_fields
        self._can_refresh = oauth_type in _REFRESHABLE_OAUTH_TYPES and _has_refresh_token(
            credentials
        )
        self._needs_initial_refresh = True
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # TokenProvider protocol
    # ------------------------------------------------------------------

    async def get_token(self) -> str:
        """Return a valid access token, refreshing proactively if stale.

        Raises:
            TokenProviderError: On refresh failure (see _refresh_and_translate).
        """
        if not self._can_refresh:
            return self._token

        if not self._needs_initial_refresh and time.monotonic() < self._expires_at:
            return self._token

        async with self._lock:
            if not self._needs_initial_refresh and time.monotonic() < self._expires_at:
                return self._token

            result = await self._refresh()
            self._apply_refresh(result)
            return self._token

    async def force_refresh(self) -> str:
        """Force an immediate token refresh (e.g. after a 401).

        Raises:
            TokenRefreshNotSupportedError: If refresh is not possible.
            TokenProviderError: On refresh failure (see _translate_refresh_error).
        """
        if not self._can_refresh:
            raise TokenRefreshNotSupportedError(
                f"Token refresh not supported for {self._source_short_name}",
                source_short_name=self._source_short_name,
                provider_kind=_PROVIDER_KIND,
            )

        async with self._lock:
            self._logger.warning(f"Forcing token refresh for {self._source_short_name} due to 401")
            result = await self._refresh()
            self._apply_refresh(result)
            return self._token

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _apply_refresh(self, result: RefreshResult) -> None:
        """Update token and schedule next refresh based on expires_in."""
        self._token = result.access_token
        self._needs_initial_refresh = False

        interval = self._compute_refresh_interval(result.expires_in)
        self._expires_at = time.monotonic() + interval

        if result.expires_in is not None:
            self._logger.debug(
                f"Token for {self._source_short_name} expires in {result.expires_in}s, "
                f"next refresh in {interval:.0f}s"
            )

    @staticmethod
    def _compute_refresh_interval(expires_in: Optional[int]) -> float:
        """Derive refresh interval from provider-reported expires_in.

        Uses 80% of the reported lifetime, clamped to [60s, 50min].
        Falls back to the default 25-min interval when expires_in is unavailable.
        """
        if expires_in is None or expires_in <= 0:
            return _DEFAULT_REFRESH_INTERVAL_SECONDS
        interval = expires_in * _REFRESH_LIFETIME_FRACTION
        return max(_MIN_REFRESH_INTERVAL_SECONDS, min(interval, _MAX_REFRESH_INTERVAL_SECONDS))

    async def _refresh(self) -> RefreshResult:
        """Refresh the token via oauth2_service, translating errors to TokenProvider types.

        Retries up to 3 times on transient failures (5xx, rate limits)
        before translating the final exception.
        """
        try:
            return await self._refresh_with_retry()
        except Exception as e:
            raise self._translate_refresh_error(e) from e

    @retry(
        retry=retry_if_exception_type((OAuthRefreshServerError, OAuthRefreshRateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _refresh_with_retry(self) -> RefreshResult:
        async with get_db_context() as db:
            return await self._oauth2_service.refresh_and_persist(
                db=db,
                integration_short_name=self._source_short_name,
                connection_id=self._connection_id,
                ctx=self._ctx,
                config_fields=self._config_fields,
            )

    def _translate_refresh_error(self, exc: Exception) -> TokenProviderError:
        """Map an OAuth refresh exception to the corresponding TokenProvider exception."""
        sn = self._source_short_name

        if isinstance(exc, (OAuthRefreshTokenRevokedError, OAuthRefreshBadRequestError)):
            return TokenCredentialsInvalidError(
                f"OAuth credentials invalid for {sn}: {exc}",
                source_short_name=sn,
                provider_kind=_PROVIDER_KIND,
            )

        if isinstance(exc, OAuthRefreshCredentialMissingError):
            return TokenProviderConfigError(
                f"Credential missing for {sn}: {exc}",
                source_short_name=sn,
                provider_kind=_PROVIDER_KIND,
            )

        if isinstance(exc, OAuthRefreshRateLimitError):
            return TokenProviderRateLimitError(
                f"OAuth rate-limited for {sn}: {exc}",
                source_short_name=sn,
                provider_kind=_PROVIDER_KIND,
                retry_after=exc.retry_after,
            )

        if isinstance(exc, OAuthRefreshServerError):
            return TokenProviderServerError(
                f"OAuth server error for {sn}: {exc}",
                source_short_name=sn,
                provider_kind=_PROVIDER_KIND,
                status_code=exc.status_code,
            )

        return TokenProviderServerError(
            f"Unexpected OAuth error for {sn}: {exc}",
            source_short_name=sn,
            provider_kind=_PROVIDER_KIND,
        )


# ---------------------------------------------------------------------------
# Module-private credential helpers
# ---------------------------------------------------------------------------


def _extract_access_token(creds: Union[str, dict, object]) -> Optional[str]:
    """Extract access token from credentials (str, dict, or object)."""
    if isinstance(creds, str):
        return creds
    if isinstance(creds, dict):
        return creds.get("access_token")
    if hasattr(creds, "access_token"):
        return creds.access_token
    return None


def _has_refresh_token(creds: Union[str, dict, object]) -> bool:
    """Check if credentials contain a non-empty refresh token."""
    if isinstance(creds, dict):
        rt = creds.get("refresh_token")
        return bool(rt and str(rt).strip())
    if hasattr(creds, "refresh_token"):
        rt = creds.refresh_token
        return bool(rt and str(rt).strip())
    return False
