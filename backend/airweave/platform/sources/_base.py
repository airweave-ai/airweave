"""Base source class."""

from abc import abstractmethod
from typing import Any, AsyncGenerator, ClassVar, Dict, Optional

import httpx
from pydantic import BaseModel

from airweave.core.logging import logger
from airweave.platform.entities._base import ChunkEntity
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
        self, file_entity, download_url=None, access_token=None, headers=None
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

        self.logger.info(f"Processing file entity: {file_entity.name}")

        try:
            # Create stream (pass token as before)
            file_stream = file_manager.stream_file_from_url(
                url, access_token=token, headers=headers
            )

            # Process entity - Fix the stream handling issue
            processed_entity = await file_manager.handle_file_entity(
                stream=file_stream, entity=file_entity
            )

            # Skip if file was too large
            if hasattr(processed_entity, "should_skip") and processed_entity.should_skip:
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
            file_entity.should_skip = True
            if not hasattr(file_entity, "metadata") or file_entity.metadata is None:
                file_entity.metadata = {}
            file_entity.metadata["error"] = error_msg
            file_entity.metadata["http_status"] = status_code

            return file_entity
        except Exception as e:
            # Log other errors but don't let them stop the sync
            self.logger.error(f"Error processing file {file_entity.name}: {str(e)}")

            # Mark entity as skipped
            file_entity.should_skip = True
            if not hasattr(file_entity, "metadata") or file_entity.metadata is None:
                file_entity.metadata = {}
            file_entity.metadata["error"] = str(e)

            return file_entity

    async def process_file_entity_with_content(
        self, file_entity, content_stream, metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ChunkEntity]:
        """Process a file entity with content directly available as a stream."""
        self.logger.info(f"Processing file entity with direct content: {file_entity.name}")

        try:
            # Process entity with the file manager directly
            processed_entity = await file_manager.handle_file_entity(
                stream=content_stream, entity=file_entity
            )

            # Add any additional metadata
            if metadata and processed_entity:
                # Initialize metadata if it doesn't exist
                if not hasattr(processed_entity, "metadata") or processed_entity.metadata is None:
                    processed_entity.metadata = {}
                processed_entity.metadata.update(metadata)

            # Skip if file was too large
            if hasattr(processed_entity, "should_skip") and processed_entity.should_skip:
                self.logger.warning(
                    f"Skipping file {processed_entity.name}: "
                    f"{processed_entity.metadata.get('error', 'Unknown reason')}"
                )

            return processed_entity
        except Exception as e:
            self.logger.error(f"Error processing file {file_entity.name} with direct content: {e}")
            return None


class Relation(BaseModel):
    """A relation between two entities."""

    source_entity_type: type[ChunkEntity]
    source_entity_id_attribute: str
    target_entity_type: type[ChunkEntity]
    target_entity_id_attribute: str
    relation_type: str
