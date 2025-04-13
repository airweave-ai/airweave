"""DAG service."""

from collections import Counter
from typing import Dict, List, Set, Tuple, Type
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.db.unit_of_work import UnitOfWork
from airweave.platform.entities._base import BaseEntity, ChunkEntity, FileEntity, ParentEntity
from airweave.platform.locator import resource_locator
from airweave.schemas.dag import DagEdgeCreate, DagNodeCreate, NodeType, SyncDagCreate


class DagService:
    """DAG service."""

    async def create_initial_dag(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        current_user: schemas.User,
        uow: UnitOfWork,
    ) -> schemas.SyncDag:
        """Create an initial DAG with source, entities, and destination."""
        sync = await self._get_and_validate_sync(db, sync_id, current_user)
        file_chunker = await self._get_file_chunker(db)
        source_data = await self._get_source_and_entity_definitions(db, sync, current_user)
        source, source_connection, entity_definitions = source_data
        dest_data = await self._get_destinations_and_destination_connections(db, sync, current_user)
        destinations, destination_connections = dest_data

        nodes, edges = await self._initialize_dag_components(
            source, source_connection, destinations, destination_connections
        )
        await self._process_entity_definitions(
            db, entity_definitions, file_chunker, nodes, edges
        )
        return await self._create_and_return_dag(db, sync, nodes, edges, current_user, uow)

    async def _initialize_dag_components(
        self,
        source: Any,
        source_connection: Any,
        destinations: List[Any],
        destination_connections: List[Any],
    ) -> Tuple[List[DagNodeCreate], List[DagEdgeCreate]]:
        nodes = [DagNodeCreate(id=uuid4(), type=NodeType.source, name=source.name, connection_id=source_connection.id)]
        edges = []
        destination_node_ids = []

        for destination, destination_connection in zip(destinations, destination_connections, strict=True):
            dest_node_id = uuid4()
            destination_node_ids.append(dest_node_id)
            nodes.append(
                DagNodeCreate(id=dest_node_id, type=NodeType.destination, name=destination.name, connection_id=destination_connection.id)
            )
        return nodes, edges

    async def _process_entity_definitions(
        self,
        db: AsyncSession,
        entity_definitions: Dict[UUID, Dict[str, Any]],
        file_chunker: Any,
        nodes: List[DagNodeCreate],
        edges: List[DagEdgeCreate],
    ) -> Set[UUID]:
        processed_entity_ids = set()
        source_node_id = next(node.id for node in nodes if node.type == NodeType.source)
        destination_node_ids = [node.id for node in nodes if node.type == NodeType.destination]

        for entity_definition_id, entity_data in entity_definitions.items():
            if entity_definition_id in processed_entity_ids:
                continue
            processed_entity_ids.add(entity_definition_id)
            entity_class = entity_data["entity_class"]
            entity_definition = entity_data["entity_definition"]

            if issubclass(entity_class, FileEntity):
                destination_node_id = destination_node_ids[0] if destination_node_ids else None
                if not destination_node_id:
                    raise ValueError("No destination node ID available for file entity processing")
                await self._process_file_entity(
                    db=db,
                    entity_class=entity_class,
                    entity_definition=entity_definition,
                    file_chunker=file_chunker,
                    source_node_id=source_node_id,
                    destination_node_id=destination_node_id,
                    nodes=nodes,
                    edges=edges,
                    processed_entity_ids=processed_entity_ids,
                )
            else:
                entity_node_id = uuid4()
                nodes.append(
                    DagNodeCreate(id=entity_node_id, type=NodeType.entity, name=entity_definition.name, entity_definition_id=entity_definition_id)
                )
                edges.append(DagEdgeCreate(from_node_id=source_node_id, to_node_id=entity_node_id))
                for dest_node_id in destination_node_ids:
                    edges.append(DagEdgeCreate(from_node_id=entity_node_id, to_node_id=dest_node_id))
        return processed_entity_ids

    async def _create_and_return_dag(
        self,
        db: AsyncSession,
        sync: Any,
        nodes: List[DagNodeCreate],
        edges: List[DagEdgeCreate],
        current_user: schemas.User,
        uow: UnitOfWork,
    ) -> schemas.SyncDag:
        sync_dag_create = SyncDagCreate(name=f"DAG for {sync.name}", sync_id=sync.id, nodes=nodes, edges=edges)
        try:
            from airweave.core.logging import logger
            logger.info(f"Creating DAG for sync {sync.name} with {len(nodes)} nodes and {len(edges)} edges")
            sync_dag = await crud.sync_dag.create_with_nodes_and_edges(db, obj_in=sync_dag_create, current_user=current_user, uow=uow)
            logger.info(f"Successfully created DAG with ID {sync_dag.id}")
            return schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
        except Exception as e:
            from airweave.core.logging import logger
            logger.error(f"Error creating DAG: {e}")
            logger.error(f"Total nodes: {len(nodes)}, Total edges: {len(edges)}")
            node_ids = [node.id for node in nodes]
            duplicate_ids = {id: count for id, count in Counter(node_ids).items() if count > 1}
            if duplicate_ids:
                logger.error(f"Found duplicate node IDs: {duplicate_ids}")
            edge_relationships = [(edge.from_node_id, edge.to_node_id) for edge in edges]
            node_id_set = set(node_ids)
            invalid_edges = [
                f"Edge from_node_id {from_id} not in nodes" if from_id not in node_id_set else
                f"Edge to_node_id {to_id} not in nodes" if to_id not in node_id_set else None
                for from_id, to_id in edge_relationships
            ]
            invalid_edges = [msg for msg in invalid_edges if msg]
            if invalid_edges:
                logger.error(f"Found invalid edges: {invalid_edges}")
            raise

    async def _get_and_validate_sync(
        self, db: AsyncSession, sync_id: UUID, current_user: schemas.User
    ) -> schemas.Sync:
        """Get and validate that the sync exists.

        Args:
        ----
            db (AsyncSession): The database session.
            sync_id (UUID): The ID of the sync to get.
            current_user (schemas.User): The current user.

        Returns:
        -------
            schemas.Sync: The sync.

        Raises:
        ------
            Exception: If the sync is not found.
        """
        sync = await crud.sync.get(db, id=sync_id, current_user=current_user, with_connections=True)
        if not sync:
            raise Exception(f"Sync for {sync_id} not found")
        return sync

    async def _get_file_chunker(self, db: AsyncSession) -> schemas.Transformer:
        """Get the file chunker transformer."""
        transformers = await crud.transformer.get_all(db)
        file_chunker = next(
            (t for t in transformers if t.method_name == "file_chunker"),
            None,
        )
        if not file_chunker:
            raise Exception("No file chunker found")
        return file_chunker

    async def _get_source_and_entity_definitions(
        self, db: AsyncSession, sync: schemas.Sync, current_user: schemas.User
    ) -> Tuple[schemas.Source, schemas.Connection, Dict]:
        """Get source connection and entity definitions."""
        source_connection = await crud.connection.get(
            db, id=sync.source_connection_id, current_user=current_user
        )
        if not source_connection:
            raise Exception(f"Source connection for {sync.source_connection_id} not found")

        source = await crud.source.get_by_short_name(db, short_name=source_connection.short_name)

        entity_definitions = await crud.entity_definition.get_multi_by_ids(
            db, ids=source.output_entity_definition_ids
        )

        entity_definitions_dict = {
            entity_definition.id: {
                "entity_class": resource_locator.get_entity_definition(entity_definition),
                "entity_definition": entity_definition,
            }
            for entity_definition in entity_definitions
        }

        return source, source_connection, entity_definitions_dict

    async def _get_destinations_and_destination_connections(
        self, db: AsyncSession, sync: schemas.Sync, current_user: schemas.User
    ) -> Tuple[List[schemas.Destination], List[schemas.Connection]]:
        """Get or create destinations and destination connections.

        Args:
        ----
            db (AsyncSession): The database session.
            sync (schemas.Sync): The sync to get the destinations and destination connections for.
            current_user (schemas.User): The current user.

        Returns:
        -------
            Tuple[List[schemas.Destination], List[schemas.Connection]]: The destinations and
                destination connections.

        Raises:
        ------
            HTTPException: If a destination or destination connection is not found.
        """
        # Initialize lists
        destinations = []
        destination_connections = []

        # Get destinations and destination connections
        if sync.destination_connection_ids:
            for destination_connection_id in sync.destination_connection_ids:
                destination_connection = await crud.connection.get(
                    db, id=destination_connection_id, current_user=current_user
                )
                if not destination_connection:
                    raise HTTPException(status_code=404, detail="Destination connection not found")
                destination_connections.append(destination_connection)

                destination = await crud.destination.get_by_short_name(
                    db, short_name=destination_connection.short_name
                )
                if not destination:
                    raise HTTPException(status_code=404, detail="Destination not found")
                destinations.append(destination)
        return destinations, destination_connections

    async def _process_file_entity(
        self,
        db: AsyncSession,
        entity_class: Type[FileEntity],
        entity_definition: schemas.EntityDefinition,
        file_chunker: schemas.Transformer,
        source_node_id: UUID,
        destination_node_id: UUID,
        nodes: List[DagNodeCreate],
        edges: List[DagEdgeCreate],
        processed_entity_ids: Set[UUID],
    ) -> None:
        """Process a file entity and create necessary nodes and edges."""
        # Get parent and chunk entity classes
        parent_entity_class, chunk_entity_class = entity_class.create_parent_chunk_models()

        # Get entity definitions for parent and chunk
        parent_entity_definition = await self._get_entity_definition_for_entity_class(
            db, parent_entity_class
        )
        chunk_entity_definition = await self._get_entity_definition_for_entity_class(
            db, chunk_entity_class
        )

        # Validate that we have the necessary entity definitions
        if not parent_entity_definition or not chunk_entity_definition:
            from airweave.core.logging import logger

            logger.error(f"Missing entity definitions for {entity_class.__name__}")
            if not parent_entity_definition:
                logger.error(f"Missing parent entity definition for {parent_entity_class.__name__}")
            if not chunk_entity_definition:
                logger.error(f"Missing chunk entity definition for {chunk_entity_class.__name__}")
            raise ValueError(f"Missing entity definitions for {entity_class.__name__}")

        # Mark parent and chunk entity definitions as processed
        processed_entity_ids.add(parent_entity_definition.id)
        processed_entity_ids.add(chunk_entity_definition.id)

        # Create file entity node
        file_node_id = uuid4()
        nodes.append(
            DagNodeCreate(
                id=file_node_id,
                type=NodeType.entity,
                name=entity_definition.name,
                entity_definition_id=entity_definition.id,
            )
        )

        # Create file chunker transformer node
        chunker_node_id = uuid4()
        nodes.append(
            DagNodeCreate(
                id=chunker_node_id,
                type=NodeType.transformer,
                name=file_chunker.name,
                transformer_id=file_chunker.id,
            )
        )

        # Create parent chunk node
        parent_node_id = uuid4()
        nodes.append(
            DagNodeCreate(
                id=parent_node_id,
                type=NodeType.entity,
                name=parent_entity_definition.name,
                entity_definition_id=parent_entity_definition.id,
            )
        )

        # Create chunk entity node
        chunk_node_id = uuid4()
        nodes.append(
            DagNodeCreate(
                id=chunk_node_id,
                type=NodeType.entity,
                name=chunk_entity_definition.name,
                entity_definition_id=chunk_entity_definition.id,
            )
        )

        # Create edges
        # Source -> File Entity
        edges.append(DagEdgeCreate(from_node_id=source_node_id, to_node_id=file_node_id))

        # File Entity -> File Chunker
        edges.append(DagEdgeCreate(from_node_id=file_node_id, to_node_id=chunker_node_id))

        # File Chunker -> Parent Entity
        edges.append(DagEdgeCreate(from_node_id=chunker_node_id, to_node_id=parent_node_id))

        # File Chunker -> Chunk Entity
        edges.append(DagEdgeCreate(from_node_id=chunker_node_id, to_node_id=chunk_node_id))

        # Parent Entity -> Destination
        edges.append(DagEdgeCreate(from_node_id=parent_node_id, to_node_id=destination_node_id))

        # Chunk Entity -> Destination
        edges.append(DagEdgeCreate(from_node_id=chunk_node_id, to_node_id=destination_node_id))

    async def _get_parent_and_chunk_entity_classes_for_entity_definition(
        self, entity_definition: schemas.EntityDefinition
    ) -> tuple[Type[ParentEntity], Type[ChunkEntity]]:
        """Get the parent and chunk entity classes for a given entity definition.

        Args:
        ----
            entity_definition (schemas.EntityDefinition): The entity definition to get the parent
                and chunk entity classes for.

        Returns:
        -------
            tuple[Type[ParentEntity], Type[ChunkEntity]]: The parent and chunk entity classes.
        """
        entity_class = resource_locator.get_entity_definition(entity_definition)
        return entity_class.create_parent_chunk_models()

    async def _get_entity_definition_for_entity_class(
        self, db: AsyncSession, entity_class: Type[BaseEntity]
    ) -> schemas.EntityDefinition:
        """Get the entity definition for a given entity class.

        Args:
        ----
            db (AsyncSession): The database session.
            entity_class (Type[BaseEntity]): The entity class to get the entity definition for.

        Returns:
        -------
            schemas.EntityDefinition: The entity definition.
        """
        entity_definition = await crud.entity_definition.get_by_entity_class_name(
            db, entity_class_name=entity_class.__name__
        )
        return entity_definition


dag_service = DagService()
