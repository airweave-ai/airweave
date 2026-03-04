"""Stateful token lifecycle manager.

Owns the timer, lock, and current-token state.  Delegates actual refresh
to a ``CredentialRefresherProtocol`` strategy.

Also provides ``build_token_refresher`` — a standalone factory used by both
``SourceLifecycleService`` and legacy callers (search factory, source builder).
"""

import asyncio
import time
from typing import Any, Optional
from uuid import UUID

from airweave.api.context import ApiContext
from airweave.core.exceptions import TokenRefreshError
from airweave.core.logging import ContextualLogger, logger as default_logger
from airweave.domains.credentials.protocols import CredentialRefresherProtocol
from airweave.domains.oauth.protocols import OAuth2ServiceProtocol
from airweave.domains.sources.protocols import SourceRegistryProtocol

REFRESH_INTERVAL_SECONDS = 25 * 60  # 25 min — safe margin for 1-hour tokens


class TokenRefresher:
    """Manages WHEN to refresh and stores the current token.

    Proactive path (``get_valid_token``): refreshes when the timer expires.
    Reactive path (``refresh_on_unauthorized``): forced refresh on 401.
    """

    def __init__(
        self,
        *,
        initial_token: str,
        refresher: Optional[CredentialRefresherProtocol] = None,
        source_short_name: str = "",
        logger: Optional[ContextualLogger] = None,
    ) -> None:
        self._current_token = initial_token
        self._refresher = refresher
        self._source_short_name = source_short_name
        self._logger = logger or default_logger

        # Force an immediate refresh on first call so syncs always start fresh
        self._last_refresh_time: float = 0
        self._refresh_lock = asyncio.Lock()
        self._can_refresh = refresher is not None

    @property
    def can_refresh(self) -> bool:
        return self._can_refresh

    async def get_valid_token(self) -> str:
        if not self._can_refresh:
            return self._current_token

        now = time.time()
        if (now - self._last_refresh_time) < REFRESH_INTERVAL_SECONDS:
            return self._current_token

        async with self._refresh_lock:
            now = time.time()
            if (now - self._last_refresh_time) < REFRESH_INTERVAL_SECONDS:
                return self._current_token

            if self._last_refresh_time == 0:
                self._logger.info(
                    f"Performing initial token refresh for {self._source_short_name}"
                )
            else:
                elapsed = now - self._last_refresh_time
                self._logger.debug(
                    f"Refreshing token for {self._source_short_name} "
                    f"(last refresh: {elapsed:.0f}s ago)"
                )

            try:
                assert self._refresher is not None
                new_token = await self._refresher.refresh()
                self._current_token = new_token
                self._last_refresh_time = now
                self._logger.debug(
                    f"Successfully refreshed token for {self._source_short_name}"
                )
                return new_token
            except Exception as exc:
                self._logger.warning(
                    f"Token refresh failed for {self._source_short_name}, "
                    f"falling back to current token: {exc}"
                )
                self._can_refresh = False
                return self._current_token

    async def refresh_on_unauthorized(self) -> str:
        if not self._can_refresh:
            raise TokenRefreshError(
                f"Token refresh not supported for {self._source_short_name}"
            )

        async with self._refresh_lock:
            self._logger.warning(
                f"Forcing token refresh for {self._source_short_name} due to 401"
            )
            try:
                assert self._refresher is not None
                new_token = await self._refresher.refresh()
                self._current_token = new_token
                self._last_refresh_time = time.time()
                self._logger.debug(
                    f"Successfully refreshed token for "
                    f"{self._source_short_name} after 401"
                )
                return new_token
            except Exception as exc:
                self._logger.error(
                    f"Failed to refresh token for "
                    f"{self._source_short_name} after 401: {exc}"
                )
                raise TokenRefreshError(
                    f"Token refresh failed after 401: {exc}"
                ) from exc


# ---------------------------------------------------------------------------
# Factory function — shared construction logic
# ---------------------------------------------------------------------------


def build_token_refresher(
    *,
    source_short_name: str,
    credentials: Any,
    connection_id: Optional[UUID],
    integration_credential_id: Optional[UUID],
    config_fields: Optional[dict],
    ctx: ApiContext,
    source_registry: SourceRegistryProtocol,
    oauth2_service: OAuth2ServiceProtocol,
    logger: Optional[ContextualLogger] = None,
    auth_provider_instance: Any = None,
) -> Optional["TokenRefresher"]:
    """Build a ``TokenRefresher`` for a source, or return *None* if not needed.

    This is the single place that decides which ``CredentialRefresher`` strategy
    to use and wraps it in the stateful ``TokenRefresher``.  Used by
    ``SourceLifecycleService``, the search factory, and the sync-source builder.
    """
    from airweave.domains.credentials.refresher import (
        AuthProviderCredentialRefresher,
        OAuthCredentialRefresher,
    )

    log = logger or default_logger

    initial_token = _extract_token(credentials)
    if not initial_token:
        log.error(
            f"No token in credentials for '{source_short_name}' — skipping refresher"
        )
        return None

    refresher: Optional[CredentialRefresherProtocol] = None

    if auth_provider_instance:
        try:
            entry = source_registry.get(source_short_name)
        except KeyError:
            log.error(
                f"Source '{source_short_name}' not found in registry "
                f"— cannot build auth-provider refresher"
            )
            return TokenRefresher(
                initial_token=initial_token,
                source_short_name=source_short_name,
                logger=log,
            )

        refresher = AuthProviderCredentialRefresher(
            auth_provider_instance=auth_provider_instance,
            source_short_name=source_short_name,
            integration_credential_id=integration_credential_id,
            ctx=ctx,
            runtime_auth_all_fields=entry.runtime_auth_all_fields,
            runtime_auth_optional_fields=entry.runtime_auth_optional_fields,
            logger=log,
        )
    elif _has_refresh_token(credentials) and connection_id:
        refresher = OAuthCredentialRefresher(
            source_short_name=source_short_name,
            connection_id=connection_id,
            integration_credential_id=integration_credential_id,
            ctx=ctx,
            config_fields=config_fields,
            oauth2_service=oauth2_service,
            logger=log,
        )

    return TokenRefresher(
        initial_token=initial_token,
        refresher=refresher,
        source_short_name=source_short_name,
        logger=log,
    )


# ---------------------------------------------------------------------------
# Credential extraction helpers
# ---------------------------------------------------------------------------


def _extract_token(creds: Any) -> Optional[str]:
    """Pull an OAuth access_token from various credential shapes."""
    if isinstance(creds, str):
        return creds
    if isinstance(creds, dict):
        return creds.get("access_token")
    if hasattr(creds, "access_token"):
        return creds.access_token
    return None


def _has_refresh_token(creds: Any) -> bool:
    """Check whether credentials contain a non-empty refresh_token."""
    if isinstance(creds, dict):
        val = creds.get("refresh_token")
        return bool(val and str(val).strip())
    if hasattr(creds, "refresh_token"):
        val = creds.refresh_token
        return bool(val and str(val).strip())
    return False
