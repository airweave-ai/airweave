"""DAG router."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.core.config import settings
from airweave.platform.entities._base import BaseEntity, CodeFileEntity, PolymorphicEntity
from airweave.platform.locator import resource_locator
from airweave.platform.transformers.code_file_chunker import code_file_chunker
from airweave.platform.transformers.code_file_summarizer import code_file_summarizer
from airweave.schemas.dag import DagNode, NodeType, SyncDag


class SyncDAGRouter:
    """Routes entities through the DAG based on producer and entity type."""

    def __init__(
        self,
        dag: SyncDag,
        entity_map: dict[type[BaseEntity], UUID],
    ):
        """Initialize the DAG router."""
        self.dag = dag
        self.entity_map = entity_map
        self.route = self._build_execution_route()

    def _build_execution_route(self) -> dict[tuple[UUID, UUID], list[Optional[UUID]]]:
        """Construct an execution route for the DAG.

        Maps a tuple of a producer node id with a entity definition id to a consumer node id.

        If the entity is sent to a destination, the route is set to None, this stops the entity
        from being routed further.
        """
        route_map = {}
        for node in self.dag.nodes:
            if node.type == NodeType.entity:
                edge_inwards = self.dag.get_edges_to_node(node.id)

                # Get the producer node
                producer = edge_inwards[0].from_node_id

                edges_outwards = self.dag.get_edges_from_node(node.id)

                # Check if all outgoing edges go to destination nodes
                if edges_outwards:
                    all_destinations = True
                    for edge in edges_outwards:
                        consumer_node = self.dag.get_node(edge.to_node_id)
                        if consumer_node.type != NodeType.destination:
                            all_destinations = False
                            break

                    if all_destinations:
                        # If all outgoing edges go to destinations, stop routing
                        route_map[(producer, node.entity_definition_id)] = None
                    elif len(edges_outwards) == 1:
                        # If there's only one outgoing edge and it's not to a destination,
                        # route to that node
                        route_map[(producer, node.entity_definition_id)] = edges_outwards[
                            0
                        ].to_node_id
                    else:
                        # If there are multiple outgoing edges and not all go to destinations,
                        # this is an invalid configuration
                        raise ValueError(
                            f"Entity node {node.id} has multiple outbound edges "
                            "to non-destination nodes."
                        )
                else:
                    # No outgoing edges, this is a terminal node
                    route_map[(producer, node.entity_definition_id)] = None

        return route_map

    def _get_entity_definition_id(self, entity_type: type) -> UUID:
        """Get entity definition ID for a given entity type.

        This method first tries to find the exact type in the entity map.
        If not found, it tries to find a matching class by name and module.
        This handles dynamically created classes like Parent and Chunk models.

        Args:
            entity_type: The entity type to look up

        Returns:
            The entity definition ID

        Raises:
            ValueError: If no matching entity definition is found
        """
        # First try direct lookup
        if entity_type in self.entity_map:
            return self.entity_map[entity_type]

        # If entity is a subclass of PolymorphicEntity return placeholder
        if hasattr(entity_type, "__mro__") and issubclass(entity_type, PolymorphicEntity):
            RESERVED_TABLE_ENTITY_ID = UUID("11111111-1111-1111-1111-111111111111")
            return RESERVED_TABLE_ENTITY_ID

        # For dynamically created classes, try to find by name pattern and module
        entity_name = entity_type.__name__
        entity_module = entity_type.__module__

        # Handle Parent and Chunk classes
        base_name = None
        if entity_name.endswith("Parent"):
            base_name = entity_name.replace("Parent", "Entity")
        elif entity_name.endswith("Chunk"):
            base_name = entity_name.replace("Chunk", "Entity")

        if base_name:
            # Look for the base entity class in the same module
            for cls, definition_id in self.entity_map.items():
                if cls.__name__ == base_name and cls.__module__ == entity_module:
                    # Cache the result for future lookups
                    self.entity_map[entity_type] = definition_id
                    return definition_id

        raise ValueError(f"No entity definition found for {entity_type}")

    async def process_entity(
        self, db: AsyncSession, producer_id: UUID, entity: BaseEntity
    ) -> list[BaseEntity]:
        """Route an entity to its next consumer based on DAG structure.

        Returning condition:
        - If the entity is sent to a destination, return it, so the orchestrator can send it to the
          destinations
        - If the entity is sent to a transformer, return the transformed entities, so the next
          transformer can be called until the entity is sent to a destination
        - Temp: if entity is a CodeFileEntity, apply code_file_chunker transformer
        """
        # If the entity is a CodeFileEntity, apply code_file_chunker transformer
        # TODO: This is a temporary solution to allow the code summarizer to work.
        #       We should remove this once we have a more permanent DAG structure.
        if issubclass(type(entity), CodeFileEntity) or isinstance(entity, CodeFileEntity):
            # Apply code_file_chunker transformer
            transformed_entities = await code_file_chunker(entity)
            if settings.CODE_SUMMARIZER_ENABLED:
                # Apply code_file_summarizer transformer
                for transformed_entity in transformed_entities:
                    transformed_entity = await code_file_summarizer(transformed_entity)
            return transformed_entities

        entity_definition_id = self._get_entity_definition_id(type(entity))
        route_key = (producer_id, entity_definition_id)
        if route_key not in self.route or self.route[route_key] is None:
            return [entity]

        consumer_id = self.route[route_key]

        # Get the consumer node
        consumer = self.dag.get_node(consumer_id)

        # Apply the transformer
        transformed_entities = await self._apply_transformer(db, consumer, entity)

        # Route the transformed entities
        result_entities = []
        for transformed_entity in transformed_entities:
            result_entities.extend(await self.process_entity(db, consumer_id, transformed_entity))

        return result_entities

    def _get_if_node_is_destination(self, node: DagNode) -> bool:
        """Get if a node is a destination."""
        return node.type == NodeType.destination

    async def _apply_transformer(
        self, db: AsyncSession, consumer: DagNode, entity: BaseEntity
    ) -> list[BaseEntity]:
        """Apply the transformer to the entity."""
        if consumer.transformer_id:
            transformer = await crud.transformer.get(
                db,
                id=consumer.transformer_id,
            )
            transformer_callable = resource_locator.get_transformer(transformer)
            return await transformer_callable(entity)
        else:
            raise ValueError(f"No transformer found for node {consumer.id}")
