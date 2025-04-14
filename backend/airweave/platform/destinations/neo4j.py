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
        """Convert a ChunkEntity to Neo4j-compatible node properties.

        Converts UUIDs to strings and serializes complex objects (dicts/lists) to JSON strings.
        Handles breadcrumbs specially to ensure they're stored in Neo4j-compatible format.

        Args:
        ----
            entity (ChunkEntity): The entity to convert.

        Returns:
        -------
            dict: The Neo4j-compatible node properties.
        """
        # Get the serialized properties directly from the model
        properties = entity.model_dump()

        # Special handling for breadcrumbs - convert to Neo4j-compatible format
        if "breadcrumbs" in properties and properties["breadcrumbs"]:
            # Convert each breadcrumb object to a dict with primitive values
            breadcrumbs_list = []
            for breadcrumb in properties["breadcrumbs"]:
                if hasattr(breadcrumb, "model_dump"):
                    # If it's a Pydantic model, convert to dict
                    breadcrumb_dict = breadcrumb.model_dump()
                else:
                    # If it's already a dict, use it as is
                    breadcrumb_dict = breadcrumb

                breadcrumbs_list.append(breadcrumb_dict)

            # Store as properly formatted breadcrumbs
            properties["breadcrumbs"] = breadcrumbs_list

        # Ensure all properties are properly serialized
        for key, value in properties.items():
            if isinstance(value, UUID):
                properties[key] = str(value)
            elif isinstance(value, (dict, list)) and key != "breadcrumbs":
                properties[key] = json.dumps(value)

        # Debugging
        logger.debug(f"Converted properties: {properties}")

        return properties

    def _get_parent_from_breadcrumbs(self, entity: ChunkEntity) -> Optional[str]:
        """Extract parent entity ID from breadcrumbs if available.

        This method attempts to find the parent entity ID by looking at the last
        breadcrumb in the entity's breadcrumb list, which represents the immediate parent.

        Args:
        ----
            entity (ChunkEntity): The entity to extract parent from.

        Returns:
        -------
            Optional[str]: The parent entity ID if found, None otherwise.
        """
        # If no breadcrumbs, we can't determine a parent
        if not entity.breadcrumbs or len(entity.breadcrumbs) < 1:
            return None

        # The last breadcrumb before the current entity is the immediate parent
        # We assume breadcrumbs are ordered from root to leaf (parent to child)
        parent_breadcrumb = entity.breadcrumbs[-1]
        return parent_breadcrumb.entity_id

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
            # Index on IS_PARENT_OF relationship for faster traversal
            "CREATE INDEX is_parent_of_rel IF NOT EXISTS FOR ()-[r:IS_PARENT_OF]->() ON (r)",
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

        # Create node - use the entity_id which has a unique constraint for efficient merging
        query = """
        MERGE (e:Entity {entity_id: $entity_id})
        SET e = $props
        """

        # Create relationship to parent if parent_entity_id exists
        # The MATCH clauses will use the entity_id_unique constraint for efficient lookup
        parent_query = """
        MATCH (e:Entity {entity_id: $entity_id})
        MATCH (parent:Entity {entity_id: $parent_id})
        MERGE (parent)-[:IS_PARENT_OF]->(e)
        """

        async with Neo4jService(
            uri=self.uri, username=self.username, password=self.password
        ) as service:
            async with await service.get_session() as session:
                # Create node
                await session.run(query, entity_id=properties["entity_id"], props=properties)

                # Determine parent ID - first try parent_entity_id, then fall back to breadcrumbs
                parent_id = entity.parent_entity_id
                if not parent_id:
                    parent_id = self._get_parent_from_breadcrumbs(entity)

                # Create relationship if parent exists
                if parent_id:
                    try:
                        await session.run(
                            parent_query,
                            entity_id=entity.entity_id,
                            parent_id=parent_id,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to create parent relationship: {str(e)}")

    async def bulk_insert(self, entities: list[ChunkEntity]) -> None:
        """Bulk insert entities as nodes in Neo4j using UNWIND.

        This method optimizes bulk inserts by:
        1. Batching node creation with UNWIND
        2. Batching relationship creation
        3. Using indexes for efficient matching
        4. Handling both direct parent references and breadcrumb-based relationships

        Args:
        ----
            entities (list[ChunkEntity]): The entities to insert.
        """
        if not entities:
            return

        # For very large datasets, process in batches to avoid memory issues
        batch_size = 1000
        for i in range(0, len(entities), batch_size):
            batch = entities[i : i + batch_size]
            await self._process_entity_batch(batch)

    async def _process_entity_batch(self, entities: list[ChunkEntity]) -> None:
        """Process a batch of entities for insertion.

        Args:
        ----
            entities (list[ChunkEntity]): The batch of entities to process.
        """
        # Convert entities to Neo4j-friendly properties
        node_props = [self._entity_to_node_properties(entity) for entity in entities]

        # Create nodes with UNWIND for efficiency
        # The MERGE uses the entity_id_unique constraint for efficiency
        node_query = """
        UNWIND $props AS prop
        MERGE (e:Entity {entity_id: prop.entity_id})
        SET e = prop
        """

        # Create parent relationships for all entities with parent_entity_id
        # The MATCH clauses will use the entity_id_unique constraint for efficient lookup
        relationships_query = """
        UNWIND $relationships AS rel
        MATCH (e:Entity {entity_id: rel.entity_id})
        MATCH (parent:Entity {entity_id: rel.parent_id})
        WHERE e <> parent // Prevent circular references
        MERGE (parent)-[:IS_PARENT_OF]->(e)
        """

        # Collect parent relationships from both parent_entity_id and breadcrumbs
        relationships = []
        for entity in entities:
            parent_id = entity.parent_entity_id

            # If no explicit parent_entity_id, try to get from breadcrumbs
            if not parent_id:
                parent_id = self._get_parent_from_breadcrumbs(entity)

            # Add relationship only if parent exists and isn't entity itself (prevent circular refs)
            if parent_id and parent_id != entity.entity_id:
                relationships.append({"entity_id": entity.entity_id, "parent_id": parent_id})

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

        This method deletes all entities that have the specified parent_id,
        whether through direct parent_entity_id or through breadcrumb relationships.

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
            MATCH (parent:Entity {entity_id: $parent_id})-[:IS_PARENT_OF]->(child:Entity)
            WHERE child.sync_id = $sync_id
            DETACH DELETE child
            """
            params["sync_id"] = str(sync_id)
        else:
            query = """
            MATCH (parent:Entity {entity_id: $parent_id})-[:IS_PARENT_OF]->(child:Entity)
            DETACH DELETE child
            """

        async with Neo4jService(
            uri=self.uri, username=self.username, password=self.password
        ) as service:
            async with await service.get_session() as session:
                await session.run(query, **params)

    async def search_for_sync_id(self, query_text: str, sync_id: UUID) -> list[dict]:
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

    async def search_with_relations(
        self, query_text: str, sync_id: UUID, max_depth: int = 2
    ) -> list[dict]:
        """Search for entities with related parent/child entities.

        This method performs a graph traversal search that returns not just matching entities
        but also their related entities (parents and children) up to a specified depth.

        Args:
        ----
            query_text (str): The query text to search for.
            sync_id (UUID): The sync ID to filter by.
            max_depth (int): Maximum depth for relationship traversal (default: 2).

        Returns:
        -------
            list[dict]: Search results including related entities and relationship info.
        """
        # Graph traversal query that finds matching entities and their relationships
        # Uses efficient graph traversal with variable length paths
        graph_query = """
        MATCH (e:Entity)
        WHERE e.sync_id = $sync_id
        OPTIONAL MATCH path = (e)-[r:IS_PARENT_OF*0..{max_depth}]-(related)
        WHERE related.sync_id = $sync_id
        RETURN e, related, r, path
        LIMIT 20
        """

        async with Neo4jService(
            uri=self.uri, username=self.username, password=self.password
        ) as service:
            async with await service.get_session() as session:
                result = await session.run(
                    graph_query.format(max_depth=max_depth),
                    sync_id=str(sync_id),
                    query_text=query_text,
                )

                # Process complex graph results
                graph_results = []
                nodes_seen = set()

                async for record in result:
                    # Extract entity
                    entity = dict(record["e"])
                    entity_id = entity.get("entity_id")

                    if entity_id not in nodes_seen:
                        nodes_seen.add(entity_id)
                        result_item = {"entity": entity, "relationships": []}

                        # Add relationships if they exist
                        if record["path"] is not None:
                            path = record["path"]
                            for rel in path.relationships:
                                start_node = dict(rel.start_node)
                                end_node = dict(rel.end_node)
                                result_item["relationships"].append(
                                    {
                                        "type": rel.type,
                                        "from": start_node.get("entity_id"),
                                        "to": end_node.get("entity_id"),
                                    }
                                )

                        graph_results.append(result_item)

                return graph_results
