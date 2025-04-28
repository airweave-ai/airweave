"""Base source class."""

from abc import abstractmethod
from typing import Any, AsyncGenerator, ClassVar, List, Optional

from pydantic import BaseModel

from airweave.core.logging import logger
from airweave.platform.entities._base import ChunkEntity
from airweave.platform.file_handling.file_manager import file_manager


class BaseSource:
    """Base source class."""

    # Class variables for integration metadata
    _labels: ClassVar[List[str]] = []

    @classmethod
    @abstractmethod
    async def create(cls, credentials: Optional[Any] = None) -> "BaseSource":
        """Create a new source instance.

        Args:
            credentials: Optional credentials for authenticated sources.
                       For AuthType.none sources, this can be None.
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
            logger.warning(f"No download URL for file {file_entity.name}")
            return None

        # Get access token (from parameter or instance)
        token = access_token or getattr(self, "access_token", None)

        # Validate we have an access token for authentication
        if not token:
            logger.error(f"No access token provided for file {file_entity.name}")
            raise ValueError(f"No access token available for processing file {file_entity.name}")

        logger.info(f"Processing file entity: {file_entity.name}")

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
                logger.warning(
                    f"Skipping file {processed_entity.name}: "
                    f"{processed_entity.metadata.get('error', 'Unknown reason')}"
                )

            return processed_entity
        except Exception as e:
            logger.error(f"Error processing file {file_entity.name}: {e}")
            return None


class Relation(BaseModel):
    """A relation between two entities."""

    source_entity_type: type[ChunkEntity]
    source_entity_id_attribute: str
    target_entity_type: type[ChunkEntity]
    target_entity_id_attribute: str
    relation_type: str
