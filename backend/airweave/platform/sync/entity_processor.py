"""Module for entity processing within the sync architecture."""

import time
from typing import Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.platform.entities._base import BaseEntity, DestinationAction
from airweave.platform.sync.context import SyncContext


class EntityProcessor:
    """Processes entities through a pipeline of stages."""

    def __init__(self):
        """Initialize the entity processor with empty tracking dictionary."""
        self._entities_encountered_count: Dict[str, Set[str]] = {}

    def initialize_tracking(self, sync_context: SyncContext) -> None:
        """Initialize entity tracking with entity types from the DAG.

        Args:
            sync_context: The sync context containing the DAG
        """
        self._entities_encountered_count.clear()

        # Get all entity nodes from the DAG
        entity_nodes = [
            node for node in sync_context.dag.nodes if node.type == schemas.dag.NodeType.entity
        ]

        # Create a dictionary with entity names as keys and empty sets as values
        for node in entity_nodes:
            if node.name.endswith("Entity"):
                self._entities_encountered_count[node.name] = set()

    async def process(
        self,
        entity: BaseEntity,
        source_node: schemas.DagNode,  # not sure about hard-coupling to dag node
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> List[BaseEntity]:
        """Process an entity through the complete pipeline."""
        try:
            sync_context.logger.debug(f"Processing entity {entity.entity_id} through pipeline")

            # Track the current entity
            entity_type = entity.__class__.__name__

            # Validate entity type is known
            if entity_type not in self._entities_encountered_count:
                self._entities_encountered_count[entity_type] = set()

            # If we encounter the same entity from a different path, silently skip it
            if entity.entity_id in self._entities_encountered_count[entity_type]:
                sync_context.logger.info("\nalready encountered this entity, so silently skip\n")
                return []

            # Add the entity id to the entity_type set - we're processing it now
            self._entities_encountered_count[entity_type].add(entity.entity_id)

            # Update progress tracker with latest entities encountered
            # NOTE: this will only be published when the other stats are being published
            await sync_context.progress.update_entities_encountered_count(
                self._entities_encountered_count
            )

            # Stage 1: Enrich entity with metadata
            enriched_entity = await self._enrich(entity, sync_context)

            # Stage 2: Determine action for entity
            db_entity, action = await self._determine_action(enriched_entity, sync_context, db)
            sync_context.logger.debug(f"Determined action {action} for entity {entity.entity_id}")

            # Stage 2.5: Skip further processing if KEEP
            if action == DestinationAction.KEEP:
                await sync_context.progress.increment("kept", 1)
                return []

            # Stage 3: Process entity through DAG
            processed_entities = await self._transform(
                enriched_entity, source_node, sync_context, db
            )
            sync_context.logger.debug(
                f"Transformed entity {entity.entity_id} into {len(processed_entities)} entities"
            )

            # Stage 4: Compute vector
            processed_entities_with_vector = await self._compute_vector(
                processed_entities, sync_context
            )

            # Stage 5: Persist entities based on action
            await self._persist(
                enriched_entity, processed_entities_with_vector, db_entity, action, sync_context, db
            )

            return processed_entities
        except Exception as e:
            sync_context.logger.error(f"Error processing entity {entity.entity_id}: {str(e)}")
            raise

    async def _enrich(self, entity: BaseEntity, sync_context: SyncContext) -> BaseEntity:
        """Enrich entity with sync metadata."""
        entity.source_name = sync_context.source._name
        entity.sync_id = sync_context.sync.id
        entity.sync_job_id = sync_context.sync_job.id
        entity.sync_metadata = sync_context.sync.sync_metadata

        return entity

    async def _determine_action(
        self, entity: BaseEntity, sync_context: SyncContext, db: AsyncSession
    ) -> tuple[schemas.Entity, DestinationAction]:
        """Determine what action to take for an entity."""
        sync_context.logger.info(
            f"Determining action for entity {entity.entity_id} (type: {type(entity).__name__})"
        )

        db_entity = await crud.entity.get_by_entity_and_sync_id(
            db=db, entity_id=entity.entity_id, sync_id=sync_context.sync.id
        )

        current_hash = entity.hash()

        if db_entity:
            sync_context.logger.info(
                f"Found existing entity in DB with id {db_entity.id}, "
                f"comparing hashes: stored={db_entity.hash}, current={current_hash}"
            )

            if db_entity.hash != current_hash:
                action = DestinationAction.UPDATE
                sync_context.logger.info(
                    f"Hashes differ for entity {entity.entity_id}, will UPDATE"
                )
            else:
                action = DestinationAction.KEEP
                sync_context.logger.info(
                    f"Hashes match for entity {entity.entity_id}, will KEEP (no changes)"
                )
        else:
            action = DestinationAction.INSERT
            sync_context.logger.info(
                f"No existing entity found for {entity.entity_id} in sync "
                f"{sync_context.sync.id}, will INSERT"
            )

        return db_entity, action

    async def _transform(
        self,
        entity: BaseEntity,
        source_node: schemas.DagNode,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> List[BaseEntity]:
        """Transform entity through DAG routing."""
        sync_context.logger.debug(
            f"Starting transformation for entity {entity.entity_id} "
            f"(type: {type(entity).__name__}) from source node {source_node.id}"
        )

        transformed_entities = await sync_context.router.process_entity(
            db=db,
            producer_id=source_node.id,
            entity=entity,
        )

        # Log details about the transformed entities
        entity_types = {}
        for e in transformed_entities:
            entity_type = type(e).__name__
            if entity_type in entity_types:
                entity_types[entity_type] += 1
            else:
                entity_types[entity_type] = 1

        type_summary = ", ".join([f"{count} {t}" for t, count in entity_types.items()])
        sync_context.logger.debug(
            f"Transformation complete: entity {entity.entity_id} transformed into "
            f"{len(transformed_entities)} entities ({type_summary})"
        )

        return transformed_entities

    async def _persist(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: schemas.Entity,
        action: DestinationAction,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Persist entities to destinations based on action.

        Args:
            parent_entity: The parent entity of the processed entities
            processed_entities: The entities to persist
            db_entity: The database entity to update
            action: The action to take
            sync_context: The sync context
            db: The database session
        """
        if action == DestinationAction.KEEP:
            await self._handle_keep(sync_context)
        elif action == DestinationAction.INSERT:
            await self._handle_insert(
                parent_entity, processed_entities, db_entity, sync_context, db
            )
        elif action == DestinationAction.UPDATE:
            await self._handle_update(
                parent_entity, processed_entities, db_entity, sync_context, db
            )

    async def _compute_vector(
        self,
        processed_entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        """Compute vector for entities.

        Args:
            processed_entities: The entities to compute vector for
            sync_context: The sync context

        Returns:
            The entities with vector computed
        """
        if not processed_entities:
            sync_context.logger.debug("No entities to vectorize, returning empty list")
            return []

        try:
            embedding_model = sync_context.embedding_model
            entity_count = len(processed_entities)

            sync_context.logger.info(
                f"Computing vectors for {entity_count} entities using {embedding_model.model_name}"
            )

            # Log entity content lengths for debugging
            content_lengths = [len(str(entity.to_storage_dict())) for entity in processed_entities]
            total_length = sum(content_lengths)
            avg_length = total_length / entity_count if entity_count else 0
            max_length = max(content_lengths) if content_lengths else 0

            sync_context.logger.debug(
                f"Entity content stats: total={total_length}, "
                f"avg={avg_length:.2f}, max={max_length}, count={entity_count}"
            )

            start_time = time.time()

            # Convert entities to dictionary representations
            entity_dicts = []
            for entity in processed_entities:
                try:
                    entity_dict = str(entity.to_storage_dict())
                    entity_dicts.append(entity_dict)
                except Exception as e:
                    sync_context.logger.error(f"Error converting entity to dict: {str(e)}")
                    # Provide a fallback empty string to maintain array alignment
                    entity_dicts.append("")

            # Get embeddings from the model
            embeddings = await embedding_model.embed_many(entity_dicts)

            elapsed = time.time() - start_time
            sync_context.logger.info(
                f"Vector computation completed in {elapsed:.2f}s for {len(embeddings)} entities"
            )

            # Validate we got the expected number of embeddings
            if len(embeddings) != len(processed_entities):
                sync_context.logger.warning(
                    f"Embedding count mismatch: got {len(embeddings)} embeddings "
                    f"for {len(processed_entities)} entities"
                )

            # Assign vectors to entities
            for i, (processed_entity, vector) in enumerate(
                zip(processed_entities, embeddings, strict=False)
            ):
                try:
                    if vector is None:
                        sync_context.logger.warning(f"Received None vector for entity at index {i}")
                        continue

                    vector_dim = len(vector) if vector else 0
                    sync_context.logger.debug(
                        f"Assigning vector of dimension {vector_dim} to "
                        f"entity {processed_entity.entity_id}"
                    )
                    processed_entity.vector = vector
                except Exception as e:
                    sync_context.logger.error(
                        f"Error assigning vector to entity at index {i}: {str(e)}"
                    )

            return processed_entities

        except Exception as e:
            sync_context.logger.error(f"Error computing vectors: {str(e)}")
            raise

    async def _handle_keep(self, sync_context: SyncContext) -> None:
        """Handle KEEP action."""
        await sync_context.progress.increment(kept=1)

    async def _handle_insert(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: Optional[schemas.Entity],
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Handle INSERT action."""
        if len(processed_entities) == 0:
            sync_context.logger.info("No processed entities to insert")
            return

        # Prepare entities with parent reference
        for processed_entity in processed_entities:
            if (
                not hasattr(processed_entity, "parent_entity_id")
                or not processed_entity.parent_entity_id
            ):
                processed_entity.parent_entity_id = parent_entity.entity_id

        # Insert into database
        new_db_entity = await crud.entity.create(
            db=db,
            obj_in=schemas.EntityCreate(
                sync_job_id=sync_context.sync_job.id,
                sync_id=sync_context.sync.id,
                entity_id=parent_entity.entity_id,
                hash=parent_entity.hash(),
            ),
            organization_id=sync_context.sync.organization_id,
        )
        parent_entity.db_entity_id = new_db_entity.id

        # Insert to destinations
        for destination in sync_context.destinations:
            await destination.bulk_insert(processed_entities)

        await sync_context.progress.increment("inserted", 1)

    async def _handle_update(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: schemas.Entity,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Handle UPDATE action."""
        if len(processed_entities) == 0:
            # TODO: keep track of skipped entities that could not be processed
            sync_context.logger.info("No processed entities to update")
            return

        # Prepare entities with parent reference
        for processed_entity in processed_entities:
            if (
                not hasattr(processed_entity, "parent_entity_id")
                or not processed_entity.parent_entity_id
            ):
                processed_entity.parent_entity_id = parent_entity.entity_id

        # Update hash in database
        await crud.entity.update(
            db=db,
            db_obj=db_entity,
            obj_in=schemas.EntityUpdate(hash=parent_entity.hash()),
        )
        parent_entity.db_entity_id = db_entity.id

        # Update in destinations (delete then insert)
        for destination in sync_context.destinations:
            await destination.bulk_delete_by_parent_id(
                parent_entity.entity_id, sync_context.sync.id
            )
            await destination.bulk_insert(processed_entities)

        await sync_context.progress.increment("updated", 1)
