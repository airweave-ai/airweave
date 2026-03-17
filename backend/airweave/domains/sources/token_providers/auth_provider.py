"""AuthProviderTokenProvider — delegates to Pipedream / Composio.

The auth provider is the source of truth for credentials. Every
``get_token()`` call fetches fresh credentials from the provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol

if TYPE_CHECKING:
    from airweave.domains.sources.protocols import SourceRegistryProtocol

_PROVIDER_KIND = "auth_provider"


class AuthProviderTokenProvider(TokenProviderProtocol):
    """TokenProvider backed by an external auth provider (Pipedream / Composio).

    In *direct* mode the auth provider holds the user's OAuth connection
    and can vend fresh access tokens on demand.
    """

    def __init__(
        self,
        auth_provider_instance: BaseAuthProvider,
        source_short_name: str,
        source_registry: SourceRegistryProtocol,
        *,
        logger: ContextualLogger,
    ):
        """Initialize with an auth provider instance.

        Args:
            auth_provider_instance: A ``BaseAuthProvider`` subclass instance.
            source_short_name: Source identifier.
            source_registry: Registry to look up runtime auth field names.
            logger: Contextual logger with sync metadata.
        """
        self._provider = auth_provider_instance
        self._source_short_name = source_short_name
        self._source_registry = source_registry
        self._logger = logger

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
                provider_kind=_PROVIDER_KIND,
                account_id=e.account_id,
            ) from e
        except AuthProviderAuthError as e:
            raise TokenCredentialsInvalidError(
                f"Auth provider credentials rejected for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=_PROVIDER_KIND,
            ) from e
        except AuthProviderMissingFieldsError as e:
            raise TokenProviderMissingCredsError(
                f"Auth provider response missing fields for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=_PROVIDER_KIND,
                missing_fields=e.missing_fields,
            ) from e
        except AuthProviderConfigError as e:
            raise TokenProviderConfigError(
                f"Auth provider misconfigured for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=_PROVIDER_KIND,
            ) from e
        except AuthProviderRateLimitError as e:
            raise TokenProviderRateLimitError(
                f"Auth provider rate-limited for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=_PROVIDER_KIND,
                retry_after=e.retry_after,
            ) from e
        except AuthProviderServerError as e:
            raise TokenProviderServerError(
                f"Auth provider server error for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=_PROVIDER_KIND,
                status_code=e.status_code,
            ) from e
        except Exception as e:
            raise TokenProviderServerError(
                f"Unexpected auth provider error for {self._source_short_name}: {e}",
                source_short_name=self._source_short_name,
                provider_kind=_PROVIDER_KIND,
            ) from e

        if not isinstance(creds, dict) or "access_token" not in creds:
            raise TokenProviderMissingCredsError(
                f"No access_token in auth provider response for {self._source_short_name}",
                source_short_name=self._source_short_name,
                provider_kind=_PROVIDER_KIND,
                missing_fields=["access_token"],
            )

        return creds["access_token"]

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
            optional_fields=entry.runtime_auth_optional_fields,
        )

    async def get_token(self) -> str:
        """Return a fresh token from the auth provider.

        Raises:
            TokenProviderError: If the provider call fails (see _fetch_token).
        """
        return await self._fetch_token()

    async def force_refresh(self) -> str:
        """Force-refresh by re-calling the auth provider.

        Auth providers always return the latest token, so this is
        identical to ``get_token()``.

        Raises:
            TokenProviderError: If the provider call fails (see _fetch_token).
        """
        return await self._fetch_token()
