"""Neo4j destination implementation."""

import json
import logging
import os
from typing import Optional
from uuid import UUID

from airweave.core.config import settings
from airweave.graph_db.neo4j_service import Neo4jService
from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs.auth import Neo4jAuthConfig
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import GraphDBDestination
from airweave.platform.entities._base import ChunkEntity

logger = logging.getLogger(__name__)


@destination("Neo4j", "neo4j", AuthType.config_class, "Neo4jAuthConfig", labels=["Graph"])
class Neo4jDestination(GraphDBDestination):
    """Neo4j destination implementation.

    Attributes:
    ----------
        uri (str): The URI of the Neo4j database.
        username (str): The username for the Neo4j database.
        password (str): The password for the Neo4j database.
        sync_id (UUID): The ID of the sync.
    """

    def __init__(self):
        """Initialize Neo4j destination."""
        self.uri: Optional[str] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.sync_id: Optional[UUID] = None

    @classmethod
    async def create(
        cls,
        sync_id: UUID,
    ) -> "Neo4jDestination":
        """Create a new Neo4j destination.

        Args:
        ----
            sync_id (UUID): The ID of the sync.

        Returns:
        -------
            Neo4jDestination: The created destination.
        """
        instance = cls()
        instance.sync_id = sync_id

        # Get credentials for sync_id
        credentials = await cls.get_credentials()
        if credentials:
            instance.uri = credentials.uri
            instance.username = credentials.username
            instance.password = credentials.password
        else:
            # Check if running locally outside Docker
            if os.environ.get("LOCAL_DEVELOPMENT") == "true":
                instance.uri = "bolt://localhost:7687"
            else:
                # Fall back to environment config
                instance.uri = f"bolt://{settings.NEO4J_HOST}:{settings.NEO4J_PORT}"

            instance.username = settings.NEO4J_USER
            instance.password = settings.NEO4J_PASSWORD

        # Set up initial constraints and indexes
        await instance.setup_collection(sync_id)
        return instance

    @classmethod
    async def get_credentials(cls) -> Neo4jAuthConfig | None:
        """Get credentials for the destination.

        Returns:
        -------
            Neo4jAuthConfig | None: The credentials for the destination.
        """
        # TODO: Implement credential retrieval
        return None

    def _entity_to_node_properties(self, entity: ChunkEntity) -> dict:
        """Convert a ChunkEntity to Neo4j-compatible node properties."""
        # Get the serialized properties directly from the model
        properties = entity.model_dump()

        # Ensure all properties are properly serialized
        for key, value in properties.items():
            if isinstance(value, UUID):
                properties[key] = str(value)
            elif isinstance(value, (dict, list)) and key != "breadcrumbs":
                properties[key] = json.dumps(value)

        # Debugging
        logger.debug(f"Converted properties: {properties}")

        return properties

    async def setup_collection(self, sync_id: UUID) -> None:
        """Set up Neo4j constraints and indexes for the sync.

        Args:
        ----
            sync_id (UUID): The ID of the sync.
        """
        # Despite Neo4j being schema-optional, we implement constraints and indexes for consistency,
        # performance, and to ensure that the database is always in a valid state.
        constraints = [
            # Unique constraint on entity_id
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",  # noqa: E501
            # Index on sync_id for faster filtering
            "CREATE INDEX entity_sync_id IF NOT EXISTS FOR (e:Entity) ON (e.sync_id)",
            # Index on parent_entity_id for relationship queries
            "CREATE INDEX entity_parent_id IF NOT EXISTS FOR (e:Entity) ON (e.parent_entity_id)",
        ]

        async with Neo4jService(
            uri=self.uri, username=self.username, password=self.password
        ) as service:
            async with await service.get_session() as session:
                for constraint in constraints:
                    try:
                        await session.run(constraint)
                    except Exception as e:
                        logger.error(f"Failed to create constraint: {constraint}, error: {str(e)}")

    async def insert(self, entity: ChunkEntity) -> None:
        """Insert a single entity as a node in Neo4j.

        Args:
        ----
            entity (ChunkEntity): The entity to insert.
        """
        # Convert entity to Neo4j-friendly properties
        properties = self._entity_to_node_properties(entity)

        # Create node
        query = """
        MERGE (e:Entity {entity_id: $entity_id})
        SET e = $props
        """

        # Create relationship to parent if parent_entity_id exists
        parent_query = """
        MATCH (e:Entity {entity_id: $entity_id})
        MATCH (parent:Entity {entity_id: $parent_id})
        MERGE (parent)-[:PARENT_OF]->(e)
        """

        async with Neo4jService(
            uri=self.uri, username=self.username, password=self.password
        ) as service:
            async with await service.get_session() as session:
                # Create node
                await session.run(query, entity_id=properties["entity_id"], props=properties)

                # Create relationship if parent exists
                if entity.parent_entity_id:
                    try:
                        await session.run(
                            parent_query,
                            entity_id=entity.entity_id,
                            parent_id=entity.parent_entity_id,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to create parent relationship: {str(e)}")

    async def bulk_insert(self, entities: list[ChunkEntity]) -> None:
        """Bulk insert entities as nodes in Neo4j using UNWIND.

        Args:
        ----
            entities (list[ChunkEntity]): The entities to insert.
        """
        if not entities:
            return

        # Convert entities to Neo4j-friendly properties
        node_props = [self._entity_to_node_properties(entity) for entity in entities]

        # Create nodes with UNWIND for efficiency
        node_query = """
        UNWIND $props AS prop
        MERGE (e:Entity {entity_id: prop.entity_id})
        SET e = prop
        """

        # Create parent relationships for all entities with parent_entity_id
        relationships_query = """
        UNWIND $relationships AS rel
        MATCH (e:Entity {entity_id: rel.entity_id})
        MATCH (parent:Entity {entity_id: rel.parent_id})
        MERGE (parent)-[:PARENT_OF]->(e)
        """

        # Collect parent relationships
        relationships = [
            {"entity_id": entity.entity_id, "parent_id": entity.parent_entity_id}
            for entity in entities
            if entity.parent_entity_id
        ]

        async with Neo4jService(
            uri=self.uri, username=self.username, password=self.password
        ) as service:
            async with await service.get_session() as session:
                # Create nodes
                await session.run(node_query, props=node_props)

                # Create relationships
                if relationships:
                    try:
                        await session.run(relationships_query, relationships=relationships)
                    except Exception as e:
                        logger.warning(f"Failed to create bulk parent relationships: {str(e)}")

    async def delete(self, db_entity_id: UUID) -> None:
        """Delete a single entity node from Neo4j.

        Args:
        ----
            db_entity_id (UUID): The ID of the entity to delete.
        """
        query = """
        MATCH (e:Entity {db_entity_id: $id})
        DETACH DELETE e
        """

        async with Neo4jService(
            uri=self.uri, username=self.username, password=self.password
        ) as service:
            async with await service.get_session() as session:
                await session.run(query, id=str(db_entity_id))

    async def bulk_delete(self, entity_ids: list[str]) -> None:
        """Bulk delete entity nodes from Neo4j.

        Args:
        ----
            entity_ids (list[str]): The IDs of the entities to delete.
        """
        if not entity_ids:
            return

        query = """
        UNWIND $ids AS id
        MATCH (e:Entity {entity_id: id})
        DETACH DELETE e
        """

        async with Neo4jService(
            uri=self.uri, username=self.username, password=self.password
        ) as service:
            async with await service.get_session() as session:
                await session.run(query, ids=entity_ids)

    async def bulk_delete_by_parent_id(self, parent_id: str, sync_id: str = None) -> None:
        """Bulk delete entities by parent ID and optionally sync ID.

        Args:
        ----
            parent_id (str): The parent ID to delete children for.
            sync_id (str, optional): The sync ID to filter by.
        """
        if not parent_id:
            return

        params = {"parent_id": parent_id}

        if sync_id:
            query = """
            MATCH (parent:Entity {entity_id: $parent_id})-[:PARENT_OF]->(child:Entity)
            WHERE child.sync_id = $sync_id
            DETACH DELETE child
            """
            params["sync_id"] = str(sync_id)
        else:
            query = """
            MATCH (parent:Entity {entity_id: $parent_id})-[:PARENT_OF]->(child:Entity)
            DETACH DELETE child
            """

        async with Neo4jService(
            uri=self.uri, username=self.username, password=self.password
        ) as service:
            async with await service.get_session() as session:
                await session.run(query, **params)

    async def search(self, query_text: str, sync_id: UUID) -> list[dict]:
        """Search for entities with the specified sync_id.

        Args:
        ----
            query_text (str): The query text to search for.
            sync_id (UUID): The sync ID to filter by.

        Returns:
        -------
            list[dict]: The search results.
        """
        # For simple implementation, we'll just do a text-based CONTAINS search
        # In a production environment, you might want to use Neo4j's full-text search capabilities

        search_query = """
        MATCH (e:Entity)
        WHERE e.sync_id = $sync_id
        RETURN e
        LIMIT 10
        """
        # TODO: This is a temporary implementation. We need to use the full-text search capabilities
        # WHERE line could be: WHERE e.sync_id = $sync_id AND e.content CONTAINS $query_text
        async with Neo4jService(
            uri=self.uri, username=self.username, password=self.password
        ) as service:
            async with await service.get_session() as session:
                result = await session.run(
                    search_query, sync_id=str(sync_id), query_text=query_text
                )

                # Convert to list of dictionaries
                records = []
                async for record in result:
                    # Extract node properties
                    node = record["e"]
                    records.append(dict(node))

                return records
