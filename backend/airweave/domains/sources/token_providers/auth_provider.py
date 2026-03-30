"""AuthProviderTokenProvider — delegates to Pipedream / Composio."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.core.logging import ContextualLogger
from airweave.domains.auth_provider._base import BaseAuthProvider
from airweave.domains.auth_provider.exceptions import (
    AuthProviderAccountNotFoundError,
    AuthProviderAuthError,
    AuthProviderConfigError,
    AuthProviderMissingFieldsError,
    AuthProviderRateLimitError,
    AuthProviderServerError,
)
from airweave.domains.sources.token_providers.exceptions import (
    TokenCredentialsInvalidError,
    TokenProviderAccountGoneError,
    TokenProviderConfigError,
    TokenProviderMissingCredsError,
    TokenProviderRateLimitError,
    TokenProviderServerError,
)
from airweave.domains.sources.token_providers.protocol import (
    AuthProviderKind,
    TokenProviderProtocol,
)

if TYPE_CHECKING:
    from airweave.domains.sources.protocols import SourceRegistryProtocol


class AuthProviderTokenProvider(TokenProviderProtocol):
    """TokenProvider backed by an external auth provider (Pipedream / Composio).

    In direct mode the auth provider holds the user's OAuth connection
    and can vend fresh access tokens on demand.
    """

    _CACHE_TTL_SECONDS = 300  # 5 minutes — well within typical OAuth token lifetimes

    # OAuth lifecycle fields the auth provider handles — always optional when
    # fetching credentials since the provider manages token refresh.
    _AUTH_PROVIDER_OPTIONAL = frozenset({"refresh_token", "client_id", "client_secret"})

    def __init__(
        self,
        auth_provider_instance: BaseAuthProvider,
        source_short_name: str,
        source_registry: SourceRegistryProtocol,
        *,
        logger: ContextualLogger,
        source_connection_id: Optional[UUID] = None,
    ):
        """Initialize with an auth provider instance and source registry."""
        self._provider = auth_provider_instance
        self._source_short_name = source_short_name
        self._source_registry = source_registry
        self._logger = logger
        self._source_connection_id = source_connection_id
        self._cached_token: Optional[str] = None
        self._cached_at: float = 0.0

    @property
    def provider_kind(self) -> AuthProviderKind:
        """Discriminator for this auth provider type."""
        return AuthProviderKind.AUTH_PROVIDER

    @property
    def supports_refresh(self) -> bool:
        """Auth providers always support refresh (re-fetch from upstream)."""
        return True

    async def _fetch_token(self) -> str:
        """Call the auth provider and extract the access token.

        Retries up to 3 times on transient failures (5xx, rate limits)
        before translating the final exception.

        Raises:
            TokenCredentialsInvalidError: If the provider rejected our credentials.
            TokenProviderAccountGoneError: If the connected account was deleted.
            TokenProviderMissingCredsError: If the response lacks required fields.
            TokenProviderConfigError: If the provider configuration is invalid.
            TokenProviderRateLimitError: If the provider is throttling us.
            TokenProviderServerError: If the provider is temporarily unavailable.
        """
        entry = self._source_registry.get(self._source_short_name)

        try:
            creds = await self._call_provider_with_retry(entry)
        except AuthProviderAccountNotFoundError as e:
            raise TokenProviderAccountGoneError(
                f"Account deleted in auth provider for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=self.provider_kind,
                account_id=e.account_id,
            ) from e
        except AuthProviderAuthError as e:
            raise TokenCredentialsInvalidError(
                f"Auth provider credentials rejected for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=self.provider_kind,
            ) from e
        except AuthProviderMissingFieldsError as e:
            raise TokenProviderMissingCredsError(
                f"Auth provider response missing fields for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=self.provider_kind,
                missing_fields=e.missing_fields,
            ) from e
        except AuthProviderConfigError as e:
            raise TokenProviderConfigError(
                f"Auth provider misconfigured for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=self.provider_kind,
            ) from e
        except AuthProviderRateLimitError as e:
            raise TokenProviderRateLimitError(
                f"Auth provider rate-limited for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=self.provider_kind,
                retry_after=e.retry_after,
            ) from e
        except AuthProviderServerError as e:
            raise TokenProviderServerError(
                f"Auth provider server error for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=self.provider_kind,
                status_code=e.status_code,
            ) from e
        except Exception as e:
            raise TokenProviderServerError(
                f"Unexpected auth provider error for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=self.provider_kind,
            ) from e

        if not isinstance(creds, dict) or not creds:
            raise TokenProviderMissingCredsError(
                f"Empty auth provider response for {self._source_short_name}",
                source_short_name=self._source_short_name,
                provider_kind=self.provider_kind,
                missing_fields=entry.runtime_auth_all_fields,
            )

        # Extract the primary credential value. Prefer access_token if present,
        # otherwise use the first runtime auth field (e.g. personal_access_token,
        # api_key). This supports both OAuth and non-OAuth sources.
        for field in ["access_token"] + entry.runtime_auth_all_fields:
            if field in creds:
                return creds[field]

        raise TokenProviderMissingCredsError(
            f"No usable credential in auth provider response for {self._source_short_name}. "
            f"Expected one of: {entry.runtime_auth_all_fields}",
            source_short_name=self._source_short_name,
            provider_kind=self.provider_kind,
            missing_fields=entry.runtime_auth_all_fields,
        )

    @retry(
        retry=retry_if_exception_type((AuthProviderRateLimitError, AuthProviderServerError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _call_provider_with_retry(self, entry) -> dict:
        return await self._provider.get_creds_for_source(
            source_short_name=self._source_short_name,
            source_auth_config_fields=entry.runtime_auth_all_fields,
            optional_fields=entry.runtime_auth_optional_fields | self._AUTH_PROVIDER_OPTIONAL,
            source_connection_id=self._source_connection_id,
        )

    async def get_token(self) -> str:
        """Return a cached or fresh token from the auth provider.

        Returns the cached token if it was fetched within the last
        ``_CACHE_TTL_SECONDS``. Otherwise fetches a new one and caches it.
        """
        if self._cached_token and (time.monotonic() - self._cached_at) < self._CACHE_TTL_SECONDS:
            return self._cached_token

        token = await self._fetch_token()
        self._cached_token = token
        self._cached_at = time.monotonic()
        return token

    async def force_refresh(self) -> str:
        """Force-refresh by re-calling the auth provider (bypasses cache).

        Used after a 401 to get a genuinely new token.
        """
        token = await self._fetch_token()
        self._cached_token = token
        self._cached_at = time.monotonic()
        return token
