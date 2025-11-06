"""Token manager for handling OAuth2 token refresh during sync operations."""

import asyncio
import time
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.exceptions import TokenRefreshError
from airweave.core.logging import ContextualLogger, logger
from airweave.platform.auth.oauth2_service import oauth2_service
from airweave.platform.auth.schemas import (
    BaseAuthSettings,
    ClientCredentialsSettings,
    OAuth2Settings,
)
from airweave.platform.auth_providers._base import BaseAuthProvider


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
        auth_settings: BaseAuthSettings,
        integration_credential_id: UUID,
        connection_id: UUID,
        ctx: ApiContext,
        initial_credentials: Any,
        config_fields: Optional[Dict[str, Any]] = None,
        is_direct_injection: bool = False,
        logger_instance: Optional[ContextualLogger] = None,
        auth_provider_instance: Optional[BaseAuthProvider] = None,
    ):
        """Initialize the token manager.

        Args:
            db: Database session
            auth_settings: Typed auth settings schema (OAuth2Settings or ClientCredentialsSettings)
            integration_credential_id: ID of the integration credential
            connection_id: ID of the connection
            ctx: The API context
            initial_credentials: The initial credentials (dict, string token, or auth config object)
            config_fields: Optional config fields for template rendering (e.g., tenant_id)
            is_direct_injection: Whether token was directly injected (no refresh)
            logger_instance: Optional logger instance for contextual logging
            auth_provider_instance: Optional auth provider instance for token refresh
        """
        self.db = db
        self.auth_settings = auth_settings
        self.integration_credential_id = integration_credential_id
        self.connection_id = connection_id
        self.ctx = ctx
        self.config_fields = config_fields
        self.source_short_name = auth_settings.integration_short_name

        self.is_direct_injection = is_direct_injection
        self.logger = logger_instance or logger

        # Auth provider instance
        self.auth_provider_instance = auth_provider_instance

        # Log if config_fields available
        if self.config_fields and self.logger:
            self.logger.debug(
                f"TokenManager initialized with config_fields: {list(self.config_fields.keys())}"
            )

        # Extract the token from credentials
        self._current_token = self._extract_token_from_credentials(initial_credentials)
        if not self._current_token:
            raise ValueError(
                f"No token found in credentials for source '{self.source_short_name}'. "
                f"TokenManager requires a token to manage."
            )

        # Set last refresh time to 0 to force an immediate refresh on first use
        # This ensures we always start a sync with a fresh token, even if the stored
        # token was issued hours/days ago and has since expired
        self._last_refresh_time = 0
        self._refresh_lock = asyncio.Lock()

        # For sources without refresh tokens, we can't refresh
        self._can_refresh = self._determine_refresh_capability()

    def _determine_refresh_capability(self) -> bool:
        """Determine if this source supports token refresh/acquisition."""
        # Direct injection tokens should not be refreshed
        if self.is_direct_injection:
            return False

        # If auth provider instance is available, we can always refresh through it
        if self.auth_provider_instance:
            return True

        # Client Credentials sources need token acquisition
        if isinstance(self.auth_settings, ClientCredentialsSettings):
            return True

        # For standard OAuth (without auth provider), we assume refresh is possible
        # The actual refresh capability will be determined when attempting refresh
        return True

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
                self.logger.error(f"Failed to refresh token for {self.source_short_name}: {str(e)}")
                raise TokenRefreshError(f"Token refresh failed: {str(e)}") from e

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

                self.logger.debug(
                    f"Successfully refreshed token for {self.source_short_name} after 401"
                )
                return new_token

            except Exception as e:
                self.logger.error(
                    f"Failed to refresh token for {self.source_short_name} after 401: {str(e)}"
                )
                raise TokenRefreshError(f"Token refresh failed after 401: {str(e)}") from e

    async def _refresh_token(self) -> str:
        """Internal method to perform the actual token refresh/acquisition.

        Returns:
            The new access token

        Raises:
            Exception: If refresh/acquisition fails
        """
        # Client Credentials flow (service-to-service)
        if isinstance(self.auth_settings, ClientCredentialsSettings):
            return await self._acquire_client_credentials_token()

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
            # Get the runtime auth fields required by the source (excluding BYOC fields)
            from airweave.core.auth_provider_service import auth_provider_service

            source_auth_config_fields = (
                await auth_provider_service.get_runtime_auth_fields_for_source(
                    self.db, self.source_short_name
                )
            )

            # Get fresh credentials from auth provider instance
            fresh_credentials = await self.auth_provider_instance.get_creds_for_source(
                source_short_name=self.source_short_name,
                source_auth_config_fields=source_auth_config_fields,
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
        # Type check
        if not isinstance(self.auth_settings, OAuth2Settings):
            raise TokenRefreshError("OAuth refresh requires OAuth2Settings")

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

                # Use the oauth2_service to refresh the token
                oauth2_response = await oauth2_service.refresh_access_token(
                    db=refresh_db,
                    integration_short_name=self.source_short_name,
                    ctx=self.ctx,
                    connection_id=self.connection_id,
                    decrypted_credential=decrypted_credential,
                    config_fields=self.config_fields,
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

    async def _acquire_client_credentials_token(self) -> str:
        """Acquire access token using OAuth2 Client Credentials Flow.

        Used for service-to-service authentication (e.g., SharePoint Enterprise with Azure AD).
        No refresh token - just re-acquire with same client credentials.

        Returns:
            New access token

        Raises:
            TokenRefreshError: If token acquisition fails
        """
        # Type check for safety
        if not isinstance(self.auth_settings, ClientCredentialsSettings):
            raise TokenRefreshError(
                "Client Credentials token acquisition requires ClientCredentialsSettings"
            )

        try:
            from airweave.db.session import get_db_context

            async with get_db_context() as token_db:
                # Get stored credentials
                if not self.integration_credential_id:
                    raise TokenRefreshError("No integration credential for Client Credentials flow")

                credential = await crud.integration_credential.get(
                    token_db, self.integration_credential_id, self.ctx
                )
                if not credential:
                    raise TokenRefreshError("Integration credential not found")

                decrypted = credentials.decrypt(credential.encrypted_credentials)

                # Extract client credentials
                client_id = decrypted.get("client_id")
                client_secret = decrypted.get("client_secret")

                if not all([client_id, client_secret]):
                    raise TokenRefreshError(
                        "Client Credentials flow requires client_id and client_secret"
                    )

                # Use oauth2_service instead of manual httpx call
                token_response = await oauth2_service.exchange_client_credentials_for_token(
                    self.ctx,
                    self.source_short_name,
                    client_id,
                    client_secret,
                    self.config_fields,
                )

                # Update stored credentials with new token
                decrypted["access_token"] = token_response.access_token
                credential_update = schemas.IntegrationCredentialUpdate(
                    encrypted_credentials=credentials.encrypt(decrypted)
                )

                await crud.integration_credential.update(
                    token_db,
                    db_obj=credential,
                    obj_in=credential_update,
                    ctx=self.ctx,
                )

                self.logger.info(
                    f"Successfully acquired Client Credentials token for {self.source_short_name}"
                )

                return token_response.access_token

        except Exception as e:
            try:
                await self.db.rollback()
            except Exception:
                pass

            if isinstance(e, TokenRefreshError):
                raise
            raise TokenRefreshError(f"Client Credentials token acquisition failed: {str(e)}") from e

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
