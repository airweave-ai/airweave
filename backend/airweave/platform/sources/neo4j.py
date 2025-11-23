"""Neo4j graph database source implementation.

This source connects to a Neo4j graph database and generates entities for each node label
based on the graph schema. It dynamically creates entity classes at runtime
using the PolymorphicEntity system.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, Union

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import AuthError, DriverError, ServiceUnavailable

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, PolymorphicEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

# Mapping of Neo4j types to Python types
NEO4J_TYPE_MAP = {
    "String": str,
    "Integer": int,
    "Long": int,
    "Float": float,
    "Double": float,
    "Boolean": bool,
    "DateTime": datetime,
    "LocalDateTime": datetime,
    "Date": datetime,
    "Time": datetime,
    "LocalTime": datetime,
    "Duration": str,
    "Point": dict,
    "List": list,
    "Map": dict,
}


@source(
    name="Neo4j",
    short_name="neo4j",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class="Neo4jAuthConfig",
    config_class="Neo4jConfig",
    labels=["Graph Database"],
    rate_limit_level=RateLimitLevel.ORG,
)
class Neo4jSource(BaseSource):
    """Neo4j graph database connector integrates with Neo4j databases to extract graph data.

    Synchronizes data from graph nodes.

    It uses dynamic schema introspection to create appropriate entity classes
    and provides comprehensive access to graph data with proper type mapping.
    """

    _RESERVED_ENTITY_FIELDS = {
        "entity_id",
        "breadcrumbs",
        "name",
        "created_at",
        "updated_at",
        "textual_representation",
        "airweave_system_metadata",
        "label",
        "node_id",
        "table_name",
        "schema_name",
        "primary_key_columns",
    }

    def __init__(self):
        """Initialize the Neo4j source."""
        super().__init__()
        self.driver: Optional[AsyncDriver] = None
        self.entity_classes: Dict[str, Type[PolymorphicEntity]] = {}
        self.property_field_mappings: Dict[str, Dict[str, str]] = {}

    @classmethod
    async def create(
        cls, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> "Neo4jSource":
        """Create a new Neo4j source instance.

        Args:
            credentials: Dictionary containing connection details:
                - uri: Neo4j URI (e.g., neo4j://localhost:7687)
                - username: Database username
                - password: Database password
            config: Optional configuration parameters for the Neo4j source.
        """
        instance = cls()
        instance.config = (
            credentials.model_dump() if hasattr(credentials, "model_dump") else dict(credentials)
        )
        return instance

    def _get_label_key(self, label: str) -> str:
        """Generate consistent label key for identification."""
        return f"neo4j:{label}"

    def _normalize_model_field_name(self, property_name: str) -> str:
        """Normalize property names to avoid collisions with entity base fields."""
        if property_name == "id":
            return "id_"
        if property_name in self._RESERVED_ENTITY_FIELDS:
            return f"{property_name}_field"
        return property_name

    async def _connect(self) -> None:
        """Establish Neo4j driver connection with timeout and error handling."""
        if not self.driver:
            try:
                uri = self.config["uri"]
                username = self.config["username"]
                password = self.config["password"]

                self.driver = AsyncGraphDatabase.driver(
                    uri,
                    auth=(username, password),
                    max_connection_lifetime=3600,
                    max_connection_pool_size=50,
                    connection_acquisition_timeout=60.0,
                )

                # Verify connectivity
                await self.driver.verify_connectivity()
                self.logger.info(f"Connected to Neo4j at {uri}")

            except AuthError as e:
                raise ValueError("Invalid Neo4j credentials") from e
            except ServiceUnavailable as e:
                raise ValueError(
                    f"Could not connect to Neo4j at {self.config['uri']}. "
                    f"Please check if the database is running."
                ) from e
            except DriverError as e:
                raise ValueError(f"Neo4j connection failed: {str(e)}") from e
            except Exception as e:
                raise ValueError(f"Neo4j connection failed: {str(e)}") from e

    async def _ensure_connection(self) -> None:
        """Ensure connection is alive and reconnect if needed."""
        if self.driver:
            try:
                # Test connection with verify_connectivity
                await self.driver.verify_connectivity()
            except Exception as e:
                self.logger.warning(f"Connection lost, reconnecting: {e}")
                await self.driver.close()
                self.driver = None
                await self._connect()
        else:
            await self._connect()

    async def _get_node_labels(self) -> List[str]:
        """Get all node labels from the database.

        Returns:
            List of node label names
        """
        async with self.driver.session() as session:  # type: ignore[union-attr]
            result = await session.run("CALL db.labels()")
            labels = [record["label"] async for record in result]
            return labels

    async def _get_label_properties(self, label: str) -> Dict[str, str]:
        """Get property information for a specific label.

        Args:
            label: Node label name

        Returns:
            Dictionary mapping property names to their types
        """
        async with self.driver.session() as session:  # type: ignore[union-attr]
            # Sample nodes to infer property types
            query = f"MATCH (n:{label}) RETURN n LIMIT 100"
            result = await session.run(query)

            properties: Dict[str, Any] = {}
            async for record in result:
                node = record["n"]
                for key, value in node.items():
                    if key not in properties:
                        # Infer type from value
                        if value is None:
                            properties[key] = "String"  # Default to string for null values
                        elif isinstance(value, bool):
                            properties[key] = "Boolean"
                        elif isinstance(value, int):
                            properties[key] = "Integer"
                        elif isinstance(value, float):
                            properties[key] = "Float"
                        elif isinstance(value, str):
                            properties[key] = "String"
                        elif isinstance(value, datetime):
                            properties[key] = "DateTime"
                        elif isinstance(value, list):
                            properties[key] = "List"
                        elif isinstance(value, dict):
                            properties[key] = "Map"
                        else:
                            properties[key] = "String"

            return properties

    async def _create_entity_class_for_label(
        self, label: str, properties: Dict[str, str]
    ) -> Type[PolymorphicEntity]:
        """Create a polymorphic entity class for a given label.

        Args:
            label: Node label name
            properties: Dictionary mapping property names to types

        Returns:
            Dynamically created PolymorphicEntity subclass
        """
        # Build column metadata similar to PostgreSQL
        columns: Dict[str, Dict[str, Any]] = {}

        for prop_name, prop_type in properties.items():
            python_type = NEO4J_TYPE_MAP.get(prop_type, str)
            normalized_name = self._normalize_model_field_name(prop_name)

            columns[prop_name] = {
                "name": prop_name,
                "python_type": python_type,
                "normalized_name": normalized_name,
            }

            # Track field mapping
            label_key = self._get_label_key(label)
            if label_key not in self.property_field_mappings:
                self.property_field_mappings[label_key] = {}
            self.property_field_mappings[label_key][prop_name] = normalized_name

        # Create entity class using PolymorphicEntity factory
        entity_class = PolymorphicEntity.create_table_entity_class(
            table_name=label,
            schema_name="neo4j",
            columns=columns,
            primary_keys=["id"],  # Neo4j nodes have internal id
        )

        return entity_class

    async def _convert_field_values(
        self, data: Dict[str, Any], model_fields: Dict[str, Any], label_key: str
    ) -> Dict[str, Any]:
        """Convert and validate field values to match expected types.

        Args:
            data: Raw data dictionary
            model_fields: The model fields from the entity class
            label_key: Unique identifier for the label to resolve property mappings

        Returns:
            Dict with processed field values matching the expected types
        """
        processed_data = {}
        property_mapping = self.property_field_mappings.get(label_key, {})

        for field_name, field_value in data.items():
            model_field_name = property_mapping.get(field_name)
            if not model_field_name:
                model_field_name = self._normalize_model_field_name(field_name)

            # Skip if the field doesn't exist in the model
            if model_field_name not in model_fields:
                continue

            # If value is None, keep it as None
            if field_value is None:
                processed_data[model_field_name] = None
                continue

            # Get expected type from model field
            field_info = model_fields[model_field_name]
            field_type = field_info.annotation

            # Handle Union types (including Optional which is Union[T, None])
            if hasattr(field_type, "__origin__") and field_type.__origin__ is Union:
                # For Union types, get the non-None type
                union_args = field_type.__args__
                non_none_types = [arg for arg in union_args if arg is not type(None)]
                if non_none_types:
                    field_type = non_none_types[0]

            # Simple conversion: if target is string, convert to string
            if field_type is str and field_value is not None:
                processed_data[model_field_name] = str(field_value)
            else:
                # Let Pydantic handle everything else
                processed_data[model_field_name] = field_value

        return processed_data

    def _generate_entity_id(self, label: str, node_id: int, data: Dict[str, Any]) -> str:
        """Generate entity ID from Neo4j node ID or properties.

        Args:
            label: Node label
            node_id: Neo4j internal node ID
            data: Node properties

        Returns:
            Generated entity ID
        """
        label_key = self._get_label_key(label)

        # Try to use common ID properties if available
        if "id" in data and data["id"] is not None:
            return f"{label_key}:{data['id']}"
        if "uuid" in data and data["uuid"] is not None:
            return f"{label_key}:{data['uuid']}"
        if "guid" in data and data["guid"] is not None:
            return f"{label_key}:{data['guid']}"

        # Use Neo4j internal ID
        return f"{label_key}:{node_id}"

    def _ensure_entity_id_length(self, entity_id: str, label: str) -> str:
        """Ensure entity ID is within acceptable length limits.

        Args:
            entity_id: Original entity ID
            label: Node label

        Returns:
            Entity ID (possibly hashed if too long)
        """
        if len(entity_id) <= 2000:
            return entity_id

        # Hash if too long
        entity_hash = hashlib.sha256(entity_id.encode()).hexdigest()
        label_key = self._get_label_key(label)
        self.logger.warning(
            f"Entity ID for {label_key} exceeds 2000 characters. Using hashed ID: {entity_hash}"
        )
        return f"{label_key}:hashed_{entity_hash}"

    async def _process_node_to_entity(
        self,
        node: Any,
        label: str,
        entity_class: Type[PolymorphicEntity],
    ) -> BaseEntity:
        """Convert Neo4j node to entity.

        Args:
            node: Neo4j node object
            label: Node label
            entity_class: Entity class to instantiate

        Returns:
            BaseEntity instance
        """
        # Extract node data
        data = dict(node.items())
        node_id = node.element_id  # Neo4j 5.x uses element_id instead of id

        # Generate entity ID
        entity_id = self._generate_entity_id(label, node.id, data)
        entity_id = self._ensure_entity_id_length(entity_id, label)

        # Convert field values
        label_key = self._get_label_key(label)
        processed_data = await self._convert_field_values(data, entity_class.model_fields, label_key)

        # Determine entity name
        entity_name = (
            processed_data.get("name_field")
            or processed_data.get("name")
            or processed_data.get("title")
            or f"{label}_{node.id}"
        )

        # Create entity
        return entity_class(
            entity_id=entity_id,
            breadcrumbs=[],  # Top-level entities
            name=str(entity_name),
            created_at=None,
            updated_at=None,
            **processed_data,
        )

    async def _process_label(
        self, label: str, entity_class: Type[PolymorphicEntity]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process all nodes for a given label with streaming.

        Args:
            label: Node label to process
            entity_class: Entity class for this label

        Yields:
            BaseEntity instances for each node
        """
        async with self.driver.session() as session:  # type: ignore[union-attr]
            # Stream nodes in batches
            query = f"MATCH (n:{label}) RETURN n"
            result = await session.run(query)

            buffer = []
            BUFFER_SIZE = 1000

            async for record in result:
                node = record["n"]
                try:
                    entity = await self._process_node_to_entity(node, label, entity_class)
                    buffer.append(entity)

                    if len(buffer) >= BUFFER_SIZE:
                        for e in buffer:
                            yield e
                        buffer = []

                except Exception as e:
                    self.logger.error(f"Error processing node in label {label}: {e}")
                    continue

            # Yield remaining entities
            for e in buffer:
                yield e

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities for all node labels in the Neo4j database."""
        try:
            await self._connect()
            labels = await self._get_node_labels()

            self.logger.info(f"Found {len(labels)} label(s) to sync: {', '.join(labels)}")

            # Process each label
            for i, label in enumerate(labels, 1):
                label_key = self._get_label_key(label)
                self.logger.info(f"Processing label {i}/{len(labels)}: {label_key}")

                # Check connection health before processing each label
                await self._ensure_connection()

                # Get properties for this label
                properties = await self._get_label_properties(label)

                # Create entity class
                entity_class = await self._create_entity_class_for_label(label, properties)
                self.entity_classes[label_key] = entity_class

                # Process and yield entities
                async for entity in self._process_label(label, entity_class):
                    yield entity

            self.logger.info(f"Successfully completed sync for all {len(labels)} label(s)")

        finally:
            if self.driver:
                self.logger.info("Closing Neo4j connection")
                await self.driver.close()
                self.driver = None

    async def validate(self) -> bool:
        """Verify Neo4j credentials and database access."""
        try:
            await self._connect()

            # Test connection with a simple query
            async with self.driver.session() as session:  # type: ignore[union-attr]
                result = await session.run("RETURN 1 AS test")
                record = await result.single()
                if record["test"] != 1:
                    self.logger.error("Validation query returned unexpected result")
                    return False

            self.logger.info("Neo4j validation successful")
            return True

        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return False

        finally:
            if self.driver:
                await self.driver.close()
                self.driver = None
