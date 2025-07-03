"""Base source class."""

import asyncio
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, AsyncGenerator, Awaitable, Callable, ClassVar, Dict, Optional

import httpx
from pydantic import BaseModel

from airweave.core.logging import logger
from airweave.platform.entities._base import ChunkEntity
from airweave.platform.file_handling.file_manager import file_manager

if TYPE_CHECKING:
    from airweave.platform.auth.token_provider import TokenProvider


class BaseSource:
    """Base class for all sources."""

    _labels: ClassVar[list[str]] = []

    def __init__(self):
        """Initialize the base source."""
        self._logger: Optional[Any] = None
        self._token_provider: Optional["TokenProvider"] = None
        # This will be set by the create classmethod
        self.access_token: Optional[str] = None

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

    def set_token_provider(self, token_provider: "TokenProvider") -> None:
        """Set a token provider for automatic token refresh."""
        self._token_provider = token_provider

    async def get_access_token(self) -> str:
        """Get a valid access token, using the token provider if available."""
        if self._token_provider:
            token = await self._token_provider.get_valid_token()
            # Keep the local access_token in sync.
            self.access_token = token
            return token
        return self.access_token

    async def _make_authenticated_request(
        self, request_func: Callable[[str], Awaitable[httpx.Response]]
    ) -> Dict[str, Any]:
        """Execute an authenticated request with automatic token refresh on 401 errors.

        Args:
            request_func: An awaitable function that takes an access token string and
                          returns an httpx.Response.

        Returns:
            The JSON response as a dictionary.

        Raises:
            httpx.HTTPStatusError: If the request fails with a non-401 error, or if
                                   the retry after a 401 also fails.
            Exception: If token refresh is attempted without a configured token provider.
        """
        for attempt in range(2):  # Allow one retry
            token = await self.get_access_token()
            if not token:
                raise ValueError("Could not obtain access token for authenticated request.")

            try:
                response = await request_func(token)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # If we get a 401 and can retry, refresh the token.
                if e.response.status_code == 401 and attempt == 0:
                    self.logger.warning(
                        f"Request to {e.request.url} failed with 401. Attempting token refresh."
                    )
                    if not self._token_provider:
                        self.logger.error("Cannot refresh token: No TokenProvider is configured.")
                        raise e  # Re-raise the original error

                    try:
                        # Force a refresh and get the new token.
                        await self._token_provider.handle_unauthorized()
                        # Add a small delay for propagation, if necessary.
                        await asyncio.sleep(0.1)
                        continue  # Go to the next loop iteration to retry the request.
                    except Exception as refresh_error:
                        self.logger.error(f"Token refresh failed: {refresh_error}")
                        raise e from refresh_error  # Re-raise the original 401 error
                else:
                    # If it's not a 401, or if it's the second attempt, fail.
                    self.logger.error(
                        f"HTTP Error {e.response.status_code} for {e.request.url}: "
                        f"{e.response.text}"
                    )
                    raise e
        # This line should not be reachable, but as a fallback, raise an error.
        raise Exception("Failed to execute authenticated request after multiple attempts.")

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
        self, file_entity, download_url=None, headers=None
    ) -> Optional[ChunkEntity]:
        """Process a file entity with token-refresh-aware download logic.

        Args:
            file_entity: The FileEntity to process.
            download_url: Override the download URL (uses entity.download_url if None).
            headers: Custom headers for the download.

        Returns:
            The processed entity if it should be included, None if it should be skipped.
        """
        url = download_url or file_entity.download_url
        if not url:
            self.logger.warning(f"No download URL for file {file_entity.name}")
            return None

        for attempt in range(2):  # Allow one retry for auth errors
            token = await self.get_access_token()
            if not token:
                raise ValueError(
                    f"Could not obtain access token for downloading file {file_entity.name}"
                )

            try:
                # The file_manager will stream the file using the provided token.
                # If the token is expired, this will raise an HTTPStatusError.
                file_stream = file_manager.stream_file_from_url(
                    url, access_token=token, headers=headers
                )

                # If the stream is created successfully, process the entity and return.
                return await file_manager.handle_file_entity(stream=file_stream, entity=file_entity)

            except httpx.HTTPStatusError as e:
                # If we get a 401 and it's our first attempt, refresh the token and retry.
                if e.response.status_code == 401 and attempt == 0:
                    self.logger.warning(
                        f"File download for {file_entity.name} failed with 401. "
                        "Refreshing token and retrying."
                    )
                    if not self._token_provider:
                        self.logger.error("Cannot refresh token: No TokenProvider is configured.")
                        raise e  # Re-raise the original error

                    try:
                        # Force a refresh via the provider.
                        await self._token_provider.handle_unauthorized()
                        await asyncio.sleep(0.1)  # Small delay for safety.
                        continue  # Retry the loop.
                    except Exception as refresh_error:
                        self.logger.error(
                            f"Token refresh failed during file download: {refresh_error}"
                        )
                        raise e from refresh_error  # Re-raise the original 401 error
                else:
                    # If it's not a 401, or if it's the second attempt, fail hard.
                    self.logger.error(
                        f"HTTP Error {e.response.status_code} during file download for "
                        f"{file_entity.name}: {e.response.text}"
                    )
                    raise e
            except Exception as e:
                self.logger.error(f"Error processing file {file_entity.name}: {e}")
                # For non-HTTP errors, we don't retry. Return None to skip the file.
                return None

        self.logger.error(f"Failed to download file {file_entity.name} after multiple attempts.")
        return None

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
