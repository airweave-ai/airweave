"""Base source class."""

import base64  # for JWT payload peek
import json  # for JWT payload peek
import time  # for exp checks
from abc import abstractmethod
from typing import Any, AsyncGenerator, ClassVar, Dict, Optional

import httpx
from pydantic import BaseModel

from airweave.core.logging import logger
from airweave.platform.entities._base import ChunkEntity, FileEntity
from airweave.platform.file_handling.file_manager import file_manager


class BaseSource:
    """Base class for all sources."""

    _labels: ClassVar[list[str]] = []

    def __init__(self):
        """Initialize the base source."""
        self._logger: Optional[Any] = None  # Store contextual logger as instance variable
        self._token_manager: Optional[Any] = None  # Store token manager for OAuth sources

    @property
    def logger(self):
        """Get the logger for this source, falling back to default if not set."""
        if self._logger is not None:
            return self._logger
        # Fall back to default logger
        return logger

    def set_logger(self, logger) -> None:
        """Set a contextual logger for this source."""
        self._logger = logger

    @property
    def token_manager(self):
        """Get the token manager for this source."""
        return self._token_manager

    def set_token_manager(self, token_manager) -> None:
        """Set a token manager for this source.

        Args:
            token_manager: TokenManager instance for handling OAuth token refresh
        """
        self._token_manager = token_manager

    def set_cursor(self, cursor) -> None:
        """Set the cursor for this source.

        Args:
            cursor: SyncCursor instance for tracking sync progress
        """
        self._cursor = cursor

    @property
    def cursor(self):
        """Get the cursor for this source."""
        return getattr(self, "_cursor", None)

    def get_default_cursor_field(self) -> Optional[str]:
        """Get the default cursor field for this source.

        Override this in subclasses to provide a default cursor field.
        Return None if the source doesn't have a default (requires user to specify).

        Returns:
            The default cursor field name, or None if no default
        """
        return None

    def get_effective_cursor_field(self) -> Optional[str]:
        """Get the cursor field to use for this sync.

        Returns the user-specified cursor field if available,
        otherwise falls back to the source's default.

        Returns:
            The cursor field to use, or None if no cursor field is defined
        """
        # Use cursor field from cursor if specified
        if self.cursor and hasattr(self, "cursor_field") and self.cursor.cursor_field:
            return self.cursor.cursor_field

        # Fall back to source default
        return self.get_default_cursor_field()

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate if the given cursor field is valid for this source.

        Override this method in sources that have specific cursor field requirements.
        By default, any cursor field is considered valid (sources like PostgreSQL
        can use any column as cursor).

        Args:
            cursor_field: The cursor field to validate

        Raises:
            ValueError: If the cursor field is invalid for this source
        """
        # By default, accept any cursor field (e.g., for database sources)
        # Sources with specific requirements should override this
        pass

    async def get_access_token(self) -> Optional[str]:
        """Get a valid access token using the token manager.

        Returns:
            A valid access token if token manager is set and source uses OAuth,
            None otherwise
        """
        if self._token_manager:
            return await self._token_manager.get_valid_token()

        # Fallback to instance access_token if no token manager
        return getattr(self, "access_token", None)

    async def refresh_on_unauthorized(self) -> Optional[str]:
        """Refresh token after receiving a 401 error.

        Returns:
            New access token if refresh was successful, None otherwise
        """
        if self._token_manager:
            return await self._token_manager.refresh_on_unauthorized()
        return None

    @classmethod
    @abstractmethod
    async def create(
        cls, credentials: Optional[Any] = None, config: Optional[Dict[str, Any]] = None
    ) -> "BaseSource":
        """Create a new source instance.

        Args:
            credentials: Optional credentials for authenticated sources.
                       For AuthType.none sources, this can be None.
            config: Optional configuration parameters

        Returns:
            A configured source instance
        """
        pass

    @abstractmethod
    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate entities for the source."""
        pass

    async def process_file_entity(
        self, file_entity: FileEntity, download_url=None, access_token=None, headers=None
    ) -> Optional[ChunkEntity]:
        """Process a file entity with automatic size limit checking.

        Args:
            file_entity: The FileEntity to process
            download_url: Override the download URL (uses entity.download_url if None)
            access_token: OAuth token for authentication
            headers: Custom headers for the download

        Returns:
            The processed entity if it should be included, None if it should be skipped
        """
        # Use entity download_url if not explicitly provided
        url = download_url or file_entity.download_url
        if not url:
            self.logger.warning(f"No download URL for file {file_entity.name}")
            return None

        # Get access token (from parameter, token manager, or instance)
        token = access_token or await self.get_access_token()

        # Validate we have an access token for authentication
        if not token:
            self.logger.error(f"No access token provided for file {file_entity.name}")
            raise ValueError(f"No access token available for processing file {file_entity.name}")

        self.logger.debug(f"Processing file entity: {file_entity.name}")

        try:
            # Create stream (pass token as before)
            file_stream = file_manager.stream_file_from_url(
                url, access_token=token, headers=headers, logger=self.logger
            )

            # Process entity - Fix the stream handling issue
            processed_entity = await file_manager.handle_file_entity(
                stream=file_stream, entity=file_entity, logger=self.logger
            )

            # Skip if file was too large
            if processed_entity.airweave_system_metadata.should_skip:
                self.logger.warning(
                    f"Skipping file {processed_entity.name}: "
                    f"{processed_entity.metadata.get('error', 'Unknown reason')}"
                )

            return processed_entity
        except httpx.HTTPStatusError as e:
            # Handle specific HTTP errors gracefully
            status_code = e.response.status_code if hasattr(e, "response") else None
            error_msg = f"HTTP {status_code}: {str(e)}" if status_code else str(e)

            self.logger.error(f"HTTP error downloading file {file_entity.name}: {error_msg}")

            # Mark entity as skipped instead of failing
            file_entity.airweave_system_metadata.should_skip = True
            if not hasattr(file_entity, "metadata") or file_entity.metadata is None:
                file_entity.metadata = {}
            file_entity.metadata["error"] = error_msg
            file_entity.metadata["http_status"] = status_code

            return file_entity
        except Exception as e:
            # Log other errors but don't let them stop the sync
            self.logger.error(f"Error processing file {file_entity.name}: {str(e)}")

            # Mark entity as skipped
            file_entity.airweave_system_metadata.should_skip = True
            if not hasattr(file_entity, "metadata") or file_entity.metadata is None:
                file_entity.metadata = {}
            file_entity.metadata["error"] = str(e)

            return file_entity

    async def process_file_entity_with_content(
        self, file_entity, content_stream, metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ChunkEntity]:
        """Process a file entity with content directly available as a stream."""
        self.logger.debug(f"Processing file entity with direct content: {file_entity.name}")

        try:
            # Process entity with the file manager directly
            processed_entity = await file_manager.handle_file_entity(
                stream=content_stream, entity=file_entity, logger=self.logger
            )

            # Add any additional metadata
            if metadata and processed_entity:
                # Initialize metadata if it doesn't exist
                if not hasattr(processed_entity, "metadata") or processed_entity.metadata is None:
                    processed_entity.metadata = {}
                processed_entity.metadata.update(metadata)

            # Skip if file was too large
            if processed_entity.airweave_system_metadata.should_skip:
                self.logger.warning(
                    f"Skipping file {processed_entity.name}: "
                    f"{processed_entity.metadata.get('error', 'Unknown reason')}"
                )

            return processed_entity
        except Exception as e:
            self.logger.error(f"Error processing file {file_entity.name} with direct content: {e}")
            return None

    @abstractmethod
    async def validate(self) -> bool:
        """Validate that this source is reachable and credentials are usable.

        Returns:
            True if the source is healthy/authorized; False otherwise.

        Notes:
            OAuth2-based sources should generally implement this by calling
            `await self._validate_oauth2(...)` with the appropriate endpoints/
            credentials from their config.
        """
        raise NotImplementedError

    # ------------- NEW: reusable OAuth2 validator ----------
    async def _validate_oauth2(  # noqa: C901
        self,
        *,
        # Option A: RFC 7662 token introspection
        introspection_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        # Option B: Minimal authenticated ping
        ping_url: Optional[str] = None,
        # Overrides
        access_token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> bool:
        """Generic OAuth2 validation: introspection and/or a bearer ping.

        You can supply either:
          - `introspection_url` (+ `client_id` and `client_secret`) for RFC 7662,
          - or `ping_url` for a simple authorized GET using the access token,
          - or both (introspection first, then ping).

        Token refresh is attempted automatically on 401 via `token_manager`.

        Returns:
            True if the token is active and the endpoint(s) respond as expected; otherwise False.
        """
        token = access_token or await self.get_access_token()
        if not token:
            self.logger.error("OAuth2 validation failed: no access token available.")
            return False

        # Helper: safe JWT 'exp' peek (no signature verification).
        def _is_jwt_unexpired(tok: str) -> Optional[bool]:
            try:
                parts = tok.split(".")
                if len(parts) != 3:
                    return None
                # base64url decode payload
                pad = "=" * (-len(parts[1]) % 4)
                payload_bytes = base64.urlsafe_b64decode(parts[1] + pad)
                payload = json.loads(payload_bytes.decode("utf-8"))
                exp = payload.get("exp")
                if exp is None:
                    return None
                return time.time() < float(exp)
            except Exception:
                return None

        async def _do_ping(bearer: str) -> bool:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    hdrs = {"Authorization": f"Bearer {bearer}"}
                    if headers:
                        hdrs.update(headers)
                    resp = await client.get(ping_url, headers=hdrs)
                    if 200 <= resp.status_code < 300:
                        return True
                    if resp.status_code == 401:
                        self.logger.info("Ping unauthorized (401); attempting token refresh.")
                        new_token = await self.refresh_on_unauthorized()
                        if new_token:
                            hdrs["Authorization"] = f"Bearer {new_token}"
                            resp = await client.get(ping_url, headers=hdrs)
                            return 200 <= resp.status_code < 300
                    self.logger.warning(f"Ping failed: HTTP {resp.status_code} - {resp.text[:200]}")
                    return False
            except httpx.RequestError as e:
                self.logger.error(f"Ping request error: {e}")
                return False

        # 1) Try RFC 7662 introspection if configured
        if introspection_url:
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    auth = (client_id, client_secret) if client_id and client_secret else None
                    data = {"token": token, "token_type_hint": "access_token"}
                    resp = await client.post(
                        introspection_url,
                        data=data,
                        auth=auth,
                        headers={"Accept": "application/json", **(headers or {})},
                    )
                    # Handle unauthorized by refreshing once
                    if resp.status_code == 401:
                        self.logger.info(
                            "Introspection unauthorized (401); attempting token refresh."
                        )
                        new_token = await self.refresh_on_unauthorized()
                        if new_token:
                            data["token"] = new_token
                            resp = await client.post(
                                introspection_url,
                                data=data,
                                auth=auth,
                                headers={"Accept": "application/json", **(headers or {})},
                            )

                    resp.raise_for_status()
                    body = resp.json()
                    active = bool(body.get("active", False))

                    # If the server returns exp, double-check it
                    exp = body.get("exp")
                    if exp is not None:
                        try:
                            if time.time() >= float(exp):
                                active = False
                        except Exception:
                            pass

                    if active:
                        return True

                    # If introspection says inactive, do one last lightweight check:
                    # peek exp from JWT (if it is a JWT) to avoid false negatives
                    # on non-standard servers.
                    peek = _is_jwt_unexpired(token)
                    if peek is True:
                        self.logger.debug(
                            "Token appears unexpired by JWT payload, "
                            "but introspection returned inactive."
                        )
                    else:
                        self.logger.warning("Token reported inactive by introspection.")
                    # Fall through to optional ping if provided
            except httpx.HTTPStatusError as e:
                status = e.response.status_code if getattr(e, "response", None) else "N/A"
                self.logger.error(f"Introspection HTTP error {status}: {e}")
            except httpx.RequestError as e:
                self.logger.error(f"Introspection request error: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected introspection error: {e}")

        # 2) Try an authenticated ping if configured
        if ping_url:
            return await _do_ping(token)

        # 3) Last resort: if neither endpoint provided, do a best-effort JWT exp peek
        peek = _is_jwt_unexpired(token)
        if peek is not None:
            self.logger.debug("Validated via JWT 'exp' claim peek.")
            return peek

        self.logger.warning(
            "OAuth2 validation inconclusive: no endpoints provided and token format is opaque."
        )
        return False


class Relation(BaseModel):
    """A relation between two entities."""

    source_entity_type: type[ChunkEntity]
    source_entity_id_attribute: str
    target_entity_type: type[ChunkEntity]
    target_entity_id_attribute: str
    relation_type: str
