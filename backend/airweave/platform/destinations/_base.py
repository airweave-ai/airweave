"""Base destination classes."""

import json
from abc import ABC, abstractmethod
from typing import ClassVar, List
from uuid import UUID

from airweave import schemas
from airweave.platform.entities._base import ChunkEntity


class BaseDestination(ABC):
    """Common base destination class. This is the umbrella interface for all destinations."""

    # Class variables for integration metadata
    _labels: ClassVar[List[str]] = []

    @abstractmethod
    async def create(self, sync_id: UUID) -> "BaseDestination":
        """Create a new destination."""
        pass

    @abstractmethod
    async def setup_collection(self, sync_id: UUID) -> None:
        """Set up the collection for storing entities."""
        pass

    @abstractmethod
    async def insert(self, entity: ChunkEntity) -> None:
        """Insert a single entity into the destination."""
        pass

    @abstractmethod
    async def bulk_insert(self, entities: list[ChunkEntity]) -> None:
        """Bulk insert entities into the destination."""
        pass

    @abstractmethod
    async def delete(self, db_entity_id: UUID) -> None:
        """Delete a single entity from the destination."""
        pass

    @abstractmethod
    async def bulk_delete(self, entity_ids: list[str]) -> None:
        """Bulk delete entities from the destination."""
        pass

    @abstractmethod
    async def bulk_delete_by_parent_id(self, parent_id: UUID) -> None:
        """Bulk delete entities from the destination by parent ID and entity ID."""
        pass

    @abstractmethod
    async def search(self, query_vector: list[float]) -> None:
        """Search for a sync_id in the destination."""
        pass

    @abstractmethod
    async def get_credentials(self, user: schemas.User) -> None:
        """Get credentials for the destination."""
        pass


class VectorDBDestination(BaseDestination):
    """Abstract base class for destinations backed by a vector database.

    Inherits from BaseDestination and can have additional vector-specific methods if necessary.
    """

    # For now, no additional abstract methods are defined here; it uses BaseDestination's interface.
    pass


class GraphDBDestination(BaseDestination):
    """Abstract base class for destinations backed by a graph database."""

    # No additional abstract methods needed - the graph-specific operations
    # should be implementation details of the standard methods.

    # If needed, add helper methods that are not abstract:

    def _entity_to_node_properties(self, entity: ChunkEntity) -> dict:
        """Convert a ChunkEntity to Neo4j-compatible node properties."""
        # Get the basic serialized properties
        properties = entity.to_storage_dict()

        # Handle special fields like breadcrumbs for Neo4j
        if "breadcrumbs" in properties and isinstance(properties["breadcrumbs"], list):
            # Either serialize breadcrumbs to JSON string
            properties["breadcrumbs"] = json.dumps(properties["breadcrumbs"])
            # OR extract the most important properties from breadcrumbs
            # and store them as separate properties

        return properties
