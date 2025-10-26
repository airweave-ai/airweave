"""Base destination classes."""

from abc import ABC, abstractmethod
from typing import ClassVar, List, Optional
from uuid import UUID

from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.entities._base import BaseEntity


class BaseDestination(ABC):
    """Common base destination class. This is the umbrella interface for all destinations."""

    # Class variables for integration metadata
    _labels: ClassVar[List[str]] = []

    def __init__(self):
        """Initialize the base destination."""
        self._logger: Optional[ContextualLogger] = (
            None  # Store contextual logger as instance variable
        )

    @property
    def logger(self):
        """Get the logger for this destination, falling back to default if not set."""
        if self._logger is not None:
            return self._logger
        # Return a real default logger
        return default_logger

    def set_logger(self, logger: ContextualLogger) -> None:
        """Set a contextual logger for this destination."""
        self._logger = logger

    @classmethod
    @abstractmethod
    async def create(
        cls,
        credentials: Optional[any],
        config: Optional[dict],
        collection_id: UUID,
        organization_id: Optional[UUID] = None,
        logger: Optional[ContextualLogger] = None,
    ) -> "BaseDestination":
        """Create a new destination with credentials and config (matches source pattern).

        Args:
            credentials: Authentication credentials (e.g., S3AuthConfig, QdrantAuthConfig)
            config: Configuration parameters (e.g., bucket_name, url)
            collection_id: Collection UUID
            organization_id: Organization UUID
            logger: Logger instance
        """
        pass

    @abstractmethod
    async def setup_collection(self, collection_id: UUID, vector_size: int) -> None:
        """Set up the collection for storing entities."""
        pass

    @abstractmethod
    async def insert(self, entity: BaseEntity) -> None:
        """Insert a single entity into the destination."""
        pass

    @abstractmethod
    async def bulk_insert(self, entities: list[BaseEntity]) -> None:
        """Bulk insert entities into the destination."""
        pass

    @abstractmethod
    async def delete(self, db_entity_id: UUID) -> None:
        """Delete a single entity from the destination."""
        pass

    @abstractmethod
    async def bulk_delete(self, entity_ids: list[str], sync_id: UUID) -> None:
        """Bulk delete entities from the destination within a given sync."""
        pass

    @abstractmethod
    async def delete_by_sync_id(self, sync_id: UUID) -> None:
        """Delete entities from the destination by sync ID."""
        pass

    @abstractmethod
    async def bulk_delete_by_parent_id(self, parent_id: str, sync_id: UUID) -> None:
        """Bulk delete entities from the destination by parent ID within a given sync."""
        pass

    async def bulk_delete_by_parent_ids(self, parent_ids: list[str], sync_id: UUID) -> None:
        """Bulk delete entities for multiple parent IDs within a given sync.

        Default fan-out implementation that calls `bulk_delete_by_parent_id` for each ID.
        Destinations can override this to issue a single optimized call.
        """
        for pid in parent_ids:
            await self.bulk_delete_by_parent_id(pid, sync_id)

    @abstractmethod
    async def search(self, query_vector: list[float]) -> None:
        """Search for a sync_id in the destination."""
        pass

    @abstractmethod
    async def has_keyword_index(self) -> bool:
        """Check if the destination has a keyword index."""
        pass


class VectorDBDestination(BaseDestination):
    """Abstract base class for destinations backed by a vector database.

    Inherits from BaseDestination and can have additional vector-specific methods if necessary.
    """

    @abstractmethod
    async def get_vector_config_names(self) -> list[str]:
        """Get the vector config names for the destination."""
        pass
