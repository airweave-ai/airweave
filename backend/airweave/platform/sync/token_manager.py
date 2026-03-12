"""Token manager for handling OAuth2 token refresh during sync operations."""

import asyncio
import time
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

import airweave.core.container as _container_module  # TODO(code-blue): inject via constructor
from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.exceptions import TokenRefreshError
from airweave.core.logging import logger


class TokenManager:
    """Manages OAuth2 token refresh for sources during sync operations.

    This class provides centralized token management to ensure sources always
    have valid access tokens during long-running sync jobs. It handles:
    - Automatic token refresh before expiry
    - Concurrent refresh prevention
    - Direct token injection scenarios
    - Auth provider token refresh
    """

    # Token refresh interval (25 minutes to be safe with 1-hour tokens)
    REFRESH_INTERVAL_SECONDS = 25 * 60

    def __init__(
        self,
        db: AsyncSession,
        source_short_name: str,
        source_connection: schemas.SourceConnection,
        ctx: ApiContext,
        initial_credentials: Any,
        is_direct_injection: bool = False,
        logger_instance=None,
        auth_provider_instance: Optional[Any] = None,
    ):
        """Initialize the token manager.

        Args:
            db: Database session
            source_short_name: Short name of the source
            source_connection: Source connection configuration
            ctx: The API context
            initial_credentials: The initial credentials (dict, string token, or auth config object)
            is_direct_injection: Whether token was directly injected (no refresh)
            logger_instance: Optional logger instance for contextual logging
            auth_provider_instance: Optional auth provider instance for token refresh
        """
        self.db = db
        self.source_short_name = source_short_name
        self.connection_id = source_connection.id
        self.integration_credential_id = source_connection.integration_credential_id
        self.ctx = ctx

        self.is_direct_injection = is_direct_injection
        self.logger = logger_instance or logger

        # Auth provider instance
        self.auth_provider_instance = auth_provider_instance

        # NEW: Store config fields for token refresh (needed for templated backend URLs)
        self.config_fields = getattr(source_connection, "config_fields", None)

        # Log if config_fields available
        if self.config_fields and self.logger:
            self.logger.debug(
                f"TokenManager initialized with config_fields: {list(self.config_fields.keys())}"
            )

        # Extract the token from credentials
        self._current_token = self._extract_token_from_credentials(initial_credentials)
        if not self._current_token:
            raise ValueError(
                f"No token found in credentials for source '{source_short_name}'. "
                f"TokenManager requires a token to manage."
            )

        # Check if credentials have a refresh token (needed for refresh capability check)
        self._has_refresh_token = self._check_has_refresh_token(initial_credentials)

        # Set last refresh time to 0 to force an immediate refresh on first use
        # This ensures we always start a sync with a fresh token, even if the stored
        # token was issued hours/days ago and has since expired
        self._last_refresh_time = 0
        self._refresh_lock = asyncio.Lock()

        # Cache for tokens obtained for alternative resource scopes
        # (e.g. SharePoint REST API token vs Graph API token)
        # Stores (token, fetch_timestamp) tuples for TTL enforcement
        self._resource_tokens: Dict[str, tuple] = {}

        # For sources without refresh tokens, we can't refresh
        self._can_refresh = self._determine_refresh_capability()

    def _determine_refresh_capability(self) -> bool:
        """Determine if this source supports token refresh."""
        # Direct injection tokens should not be refreshed
        if self.is_direct_injection:
            self.logger.debug(
                f"Token refresh disabled for {self.source_short_name}: direct injection mode"
            )
            return False

        # If auth provider instance is available, we can always refresh through it
        if self.auth_provider_instance:
            return True

        # Check if credentials contain a refresh token
        # This handles OAuthTokenAuthentication where user provided access_token only
        if not self._has_refresh_token:
            self.logger.debug(
                f"Token refresh disabled for {self.source_short_name}: no refresh "
                "token in credentials"
            )
            return False

        # For standard OAuth with refresh token, refresh is possible
        return True

    def _check_has_refresh_token(self, credentials: Any) -> bool:
        """Check if credentials contain a refresh token.

        This is used to determine if token refresh is possible for OAuth sources
        created via direct token injection (OAuthTokenAuthentication).
        """
        if isinstance(credentials, dict):
            refresh_token = credentials.get("refresh_token")
            return bool(refresh_token and str(refresh_token).strip())

        if hasattr(credentials, "refresh_token"):
            refresh_token = credentials.refresh_token
            return bool(refresh_token and str(refresh_token).strip())

        return False

    async def get_valid_token(self) -> str:
        """Get a valid access token, refreshing if necessary.

        This method ensures the token is fresh and handles refresh logic
        with proper concurrency control.

        Returns:
            A valid access token

        Raises:
            TokenRefreshError: If token refresh fails
        """
        # If we can't refresh, just return the current token
        if not self._can_refresh:
            return self._current_token

        # Check if token needs refresh (proactive refresh before expiry)
        current_time = time.time()
        time_since_refresh = current_time - self._last_refresh_time

        if time_since_refresh < self.REFRESH_INTERVAL_SECONDS:
            return self._current_token

        # Token needs refresh - use lock to prevent concurrent refreshes
        async with self._refresh_lock:
            # Double-check after acquiring lock (another worker might have refreshed)
            current_time = time.time()
            time_since_refresh = current_time - self._last_refresh_time

            if time_since_refresh < self.REFRESH_INTERVAL_SECONDS:
                return self._current_token

            # Perform the refresh
            if self._last_refresh_time == 0:
                self.logger.info(
                    f"🔄 Performing initial token refresh for {self.source_short_name} "
                    f"(ensuring fresh token at sync start)"
                )
            else:
                self.logger.debug(
                    f"Refreshing token for {self.source_short_name} "
                    f"(last refresh: {time_since_refresh:.0f}s ago)"
                )

            try:
                new_token = await self._refresh_token()
                self._current_token = new_token
                self._last_refresh_time = current_time

                self.logger.debug(f"Successfully refreshed token for {self.source_short_name}")
                return new_token

            except Exception as e:
                self.logger.warning(
                    f"Token refresh failed for {self.source_short_name}, "
                    f"falling back to current token: {str(e)}"
                )
                self._can_refresh = False
                return self._current_token

    async def refresh_on_unauthorized(self) -> str:
        """Force a token refresh after receiving an unauthorized error.

        This method is called when a source receives a 401 error, indicating
        the token has expired unexpectedly.

        Returns:
            A fresh access token

        Raises:
            TokenRefreshError: If token refresh fails or is not supported
        """
        if not self._can_refresh:
            raise TokenRefreshError(f"Token refresh not supported for {self.source_short_name}")

        async with self._refresh_lock:
            self.logger.warning(
                f"Forcing token refresh for {self.source_short_name} due to 401 error"
            )

            try:
                new_token = await self._refresh_token()
                self._current_token = new_token
                self._last_refresh_time = time.time()
                self._resource_tokens.clear()

                self.logger.debug(
                    f"Successfully refreshed token for {self.source_short_name} after 401"
                )
                return new_token

            except Exception as e:
                self.logger.error(
                    f"Failed to refresh token for {self.source_short_name} after 401: {str(e)}"
                )
                raise TokenRefreshError(f"Token refresh failed after 401: {str(e)}") from e

    async def get_token_for_resource(self, resource_scope: str) -> str:
        """Get a token for a different resource scope using the stored refresh token.

        Used for cross-resource access, e.g. obtaining a SharePoint REST API token
        when the primary token is scoped to Microsoft Graph.

        Args:
            resource_scope: The target scope, e.g. "https://tenant.sharepoint.com/.default"

        Returns:
            An access token scoped to the requested resource.

        Raises:
            TokenRefreshError: If the token exchange fails.
        """
        cache_key = resource_scope.lower()
        if cache_key in self._resource_tokens:
            cached_token, fetch_time = self._resource_tokens[cache_key]
            if (time.time() - fetch_time) < self.REFRESH_INTERVAL_SECONDS:
                return cached_token
            self.logger.debug(f"Resource token for {resource_scope} expired, refreshing")
            del self._resource_tokens[cache_key]

        if not self._has_refresh_token:
            raise TokenRefreshError(
                f"Cannot get token for resource {resource_scope}: no refresh token available"
            )

        try:
            from airweave.db.session import get_db_context
            from airweave.platform.auth.settings import integration_settings

            async with get_db_context() as refresh_db:
                credential = await crud.integration_credential.get(
                    refresh_db, self.integration_credential_id, self.ctx
                )
                if not credential:
                    raise TokenRefreshError("Integration credential not found")

                decrypted_credential = credentials.decrypt(credential.encrypted_credentials)
                refresh_token = decrypted_credential.get("refresh_token")
                if not refresh_token:
                    raise TokenRefreshError("No refresh token for resource token exchange")

            config = await integration_settings.get_by_short_name(self.source_short_name)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config.backend_url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": config.client_id,
                        "client_secret": config.client_secret,
                        "scope": resource_scope,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

            token = data.get("access_token")
            if not token:
                raise TokenRefreshError(
                    f"No access_token in response for resource scope {resource_scope}"
                )

            self._resource_tokens[cache_key] = (token, time.time())
            self.logger.info(
                f"Obtained token for resource scope {resource_scope} "
                f"(source: {self.source_short_name})"
            )
            return token

        except TokenRefreshError:
            raise
        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"Resource token exchange failed ({e.response.status_code}): "
                f"{e.response.text[:300]}"
            )
            raise TokenRefreshError(
                f"Resource token exchange failed: {e.response.status_code}"
            ) from e
        except Exception as e:
            raise TokenRefreshError(f"Resource token exchange failed: {str(e)}") from e

    async def _refresh_token(self) -> str:
        """Internal method to perform the actual token refresh.

        Returns:
            The new access token

        Raises:
            Exception: If refresh fails
        """
        # If auth provider instance is available, refresh through it
        if self.auth_provider_instance:
            return await self._refresh_via_auth_provider()

        # Otherwise use standard OAuth refresh
        return await self._refresh_via_oauth()

    async def _refresh_via_auth_provider(self) -> str:
        """Refresh token using auth provider instance.

        Returns:
            The new access token

        Raises:
            TokenRefreshError: If refresh fails
        """
        self.logger.debug(
            f"Refreshing token via auth provider instance for source '{self.source_short_name}'"
        )

        try:
            if _container_module.container is None:
                raise RuntimeError("Container not initialized")
            entry = _container_module.container.source_registry.get(self.source_short_name)

            # Get fresh credentials from auth provider instance
            fresh_credentials = await self.auth_provider_instance.get_creds_for_source(
                source_short_name=self.source_short_name,
                source_auth_config_fields=entry.runtime_auth_all_fields,
                optional_fields=entry.runtime_auth_optional_fields,
            )

            # Extract access token
            access_token = fresh_credentials.get("access_token")
            if not access_token:
                raise TokenRefreshError("No access token in credentials from auth provider")

            # Update the stored credentials in the database
            if self.integration_credential_id:
                credential_update = schemas.IntegrationCredentialUpdate(
                    encrypted_credentials=credentials.encrypt(fresh_credentials)
                )

                # Use a separate database session for the update to avoid transaction issues
                from airweave.db.session import get_db_context

                try:
                    async with get_db_context() as update_db:
                        # Get the credential in the new session
                        credential = await crud.integration_credential.get(
                            update_db, self.integration_credential_id, self.ctx
                        )
                        if credential:
                            await crud.integration_credential.update(
                                update_db,
                                db_obj=credential,
                                obj_in=credential_update,
                                ctx=self.ctx,
                            )
                except Exception as db_error:
                    self.logger.error(f"Failed to update credentials in database: {str(db_error)}")
                    # Continue anyway - we have the token, just couldn't persist it

            return access_token

        except Exception as e:
            # Ensure the main session is rolled back if it's in a bad state
            try:
                await self.db.rollback()
            except Exception:
                # Session might not be in a transaction, that's OK
                pass

            self.logger.error(f"Failed to refresh token via auth provider instance: {str(e)}")
            raise TokenRefreshError(f"Auth provider refresh failed: {str(e)}") from e

    async def _refresh_via_oauth(self) -> str:
        """Refresh token using standard OAuth flow.

        Returns:
            The new access token

        Raises:
            TokenRefreshError: If refresh fails
        """
        try:
            # Use a separate database session to avoid transaction issues
            from airweave.db.session import get_db_context

            async with get_db_context() as refresh_db:
                # Get the stored credentials
                if not self.integration_credential_id:
                    raise TokenRefreshError("No integration credential found for token refresh")

                credential = await crud.integration_credential.get(
                    refresh_db, self.integration_credential_id, self.ctx
                )
                if not credential:
                    raise TokenRefreshError("Integration credential not found")

                decrypted_credential = credentials.decrypt(credential.encrypted_credentials)

                oauth2_response = (
                    await _container_module.container.oauth2_service.refresh_access_token(
                        db=refresh_db,
                        integration_short_name=self.source_short_name,
                        ctx=self.ctx,
                        connection_id=self.connection_id,
                        decrypted_credential=decrypted_credential,
                        config_fields=self.config_fields,
                    )
                )

                return oauth2_response.access_token

        except Exception as e:
            # Ensure the main session is rolled back if it's in a bad state
            try:
                await self.db.rollback()
            except Exception:
                # Session might not be in a transaction, that's OK
                pass

            # Re-raise the original error
            if isinstance(e, TokenRefreshError):
                raise
            raise TokenRefreshError(f"OAuth refresh failed: {str(e)}") from e

    def _extract_token_from_credentials(self, credentials: Any) -> Optional[str]:
        """Extract OAuth access token from credentials.

        This method only handles OAuth tokens, not API keys or other auth types.
        """
        # If it's already a string, assume it's the token
        if isinstance(credentials, str):
            return credentials

        # If it's a dict, look for access_token (OAuth standard)
        if isinstance(credentials, dict):
            return credentials.get("access_token")

        # If it's an object with attributes, try to get access_token
        if hasattr(credentials, "access_token"):
            return credentials.access_token

        return None
