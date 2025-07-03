"""Token provider for managing OAuth tokens during sync operations."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from airweave.core.logging import logger
from airweave.db.session import get_db_context
from airweave.platform.auth.services import oauth2_service
from airweave.schemas import WhiteLabel
from airweave.schemas.auth import AuthContext


class TokenProvider:
    """Provides access tokens with automatic, thread-safe refresh capability.

    This class encapsulates token management logic for a single sync run, handling:
    - Thread-safe token refresh to prevent race conditions from multiple workers.
    - Caching of the access token to avoid unnecessary database calls.
    - Proactive and reactive token refreshing.
    """

    def __init__(
        self,
        integration_short_name: str,
        auth_context: AuthContext,
        connection_id: UUID,
        decrypted_credential: dict,
        white_label: Optional[WhiteLabel] = None,
    ):
        """Initializes the TokenProvider.

        Args:
            integration_short_name: The short name of the integration (e.g., "google_drive").
            auth_context: The authentication context of the request.
            connection_id: The ID of the connection being used.
            decrypted_credential: The decrypted credential containing the initial tokens.
            white_label: Optional white label configuration.
        """
        self.integration_short_name = integration_short_name
        self.auth_context = auth_context
        self.connection_id = connection_id
        self.decrypted_credential = decrypted_credential
        self.white_label = white_label

        self._access_token: Optional[str] = self.decrypted_credential.get("access_token")
        self._token_expiry: Optional[datetime] = (
            None  # To be implemented if `expires_in` is available
        )

        self._refresh_lock = asyncio.Lock()
        self._last_refresh_time: Optional[datetime] = None

    async def get_valid_token(self) -> str:
        """Get a valid access token, refreshing if it's likely expired.

        This method is safe to call from multiple workers concurrently.
        """
        # Proactive refresh check (e.g., if token expiry time is known)
        if self._is_token_likely_expired():
            logger.info(
                f"Token for {self.integration_short_name} is likely expired. "
                "Attempting proactive refresh."
            )
            await self._refresh_token()

        return self._access_token

    async def handle_unauthorized(self) -> str:
        """Reactively handle a 401 error by refreshing the token.

        Returns the new, valid access token.
        """
        logger.warning(
            f"Received unauthorized error for {self.integration_short_name}. Forcing token refresh."
        )
        await self._refresh_token()
        return self._access_token

    def _is_token_likely_expired(self) -> bool:
        """Check if the token should be proactively refreshed."""
        if not self._token_expiry:
            return False  # Cannot proactively refresh without expiry info

        # Refresh 5 minutes before the official expiry time for safety
        safety_buffer = timedelta(minutes=5)
        return datetime.utcnow() + safety_buffer >= self._token_expiry

    async def _refresh_token(self) -> None:
        """Refresh the access token, ensuring only one worker does it at a time."""
        async with self._refresh_lock:
            # After acquiring the lock, check if another worker has already refreshed
            # the token while this one was waiting.
            if self._last_refresh_time and (
                datetime.utcnow() - self._last_refresh_time < timedelta(seconds=10)
            ):
                logger.info(
                    "Token was recently refreshed by another worker. Skipping redundant refresh."
                )
                return

            logger.info(f"Acquired lock. Refreshing token for {self.integration_short_name}...")

            try:
                # Use a new database session to ensure it's clean and available.
                async with get_db_context() as db:
                    oauth2_response = await oauth2_service.refresh_access_token(
                        db=db,
                        integration_short_name=self.integration_short_name,
                        auth_context=self.auth_context,
                        connection_id=self.connection_id,
                        decrypted_credential=self.decrypted_credential,
                        white_label=self.white_label,
                    )

                # Update internal state with the new token details
                self._access_token = oauth2_response.access_token
                if oauth2_response.refresh_token:
                    # Keep the decrypted credential up-to-date for subsequent refreshes
                    self.decrypted_credential["refresh_token"] = oauth2_response.refresh_token

                if oauth2_response.expires_in:
                    self._token_expiry = datetime.utcnow() + timedelta(
                        seconds=oauth2_response.expires_in
                    )

                self._last_refresh_time = datetime.utcnow()
                expires_in_msg = (
                    f"New token expires in {oauth2_response.expires_in} seconds."
                    if oauth2_response.expires_in
                    else "Token expiry not provided."
                )
                logger.info(
                    f"Successfully refreshed token for {self.integration_short_name}. "
                    f"{expires_in_msg}"
                )

            except Exception as e:
                logger.error(f"Failed to refresh token for {self.integration_short_name}: {str(e)}")
                raise
