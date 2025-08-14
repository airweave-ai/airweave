"""Module for entity processing within the sync architecture."""

import asyncio
from typing import Dict, List, Optional, Set

from airweave import crud, models, schemas
from airweave.core.exceptions import NotFoundException
from airweave.core.shared_models import ActionType
from airweave.db.session import get_db_context
from airweave.platform.entities._base import BaseEntity, DestinationAction
from airweave.platform.sync.async_helpers import compute_entity_hash_async, run_in_thread_pool
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
        source_node: schemas.DagNode,
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        """Process an entity through the complete pipeline.

        Note: Database sessions are created only when needed to minimize connection usage.
        """
        entity_context = f"Entity({entity.entity_id})"
        pipeline_start = asyncio.get_event_loop().time()

        try:
            sync_context.logger.debug(
                f"🛠 PROCESSOR_START [{entity_context}] Starting entity processing pipeline "
                f"(type: {entity.__class__.__name__})"
            )

            # Track the current entity
            entity_type = entity.__class__.__name__
            if entity_type not in self._entities_encountered_count:
                self._entities_encountered_count[entity_type] = set()

            # Check for duplicate processing
            if entity.entity_id in self._entities_encountered_count[entity_type]:
                sync_context.logger.debug(
                    f"⏭️  PROCESSOR_DUPLICATE [{entity_context}] Already processed, skipping"
                )
                return []

            # Update entity tracking
            self._entities_encountered_count[entity_type].add(entity.entity_id)
            await sync_context.progress.update_entities_encountered_count(
                self._entities_encountered_count
            )

            # Check if entity should be skipped (set by file_manager or source)
            if getattr(entity, "should_skip", False):
                sync_context.logger.debug(
                    f"⏭️  PROCESSOR_SKIP [{entity_context}] Entity marked to skip"
                )
                await sync_context.progress.increment("skipped", 1)
                return []

            # Stage 1: Enrich entity with metadata
            sync_context.logger.debug(
                f"🏷️  PROCESSOR_ENRICH_START [{entity_context}] Enriching entity metadata"
            )
            enrich_start = asyncio.get_event_loop().time()

            enriched_entity = await self._enrich(entity, sync_context)

            enrich_elapsed = asyncio.get_event_loop().time() - enrich_start
            sync_context.logger.debug(
                f"✅ PROCESSOR_ENRICH_DONE [{entity_context}] Enriched in {enrich_elapsed:.3f}s"
            )

            # Stage 2: Determine action for entity (REQUIRES DATABASE)
            sync_context.logger.debug(
                f"🔍 PROCESSOR_ACTION_START [{entity_context}] Determining action"
            )
            action_start = asyncio.get_event_loop().time()

            db_entity, action = await self._determine_action(enriched_entity, sync_context)

            action_elapsed = asyncio.get_event_loop().time() - action_start
            sync_context.logger.debug(
                f"📋 PROCESSOR_ACTION_DONE [{entity_context}] Action: {action} "
                f"(determined in {action_elapsed:.3f}s)"
            )

            # Stage 2.5: Skip further processing if KEEP
            if action == DestinationAction.KEEP:
                await sync_context.progress.increment("kept", 1)
                total_elapsed = asyncio.get_event_loop().time() - pipeline_start
                sync_context.logger.debug(
                    f"⏭️  PROCESSOR_KEEP [{entity_context}] Entity kept, pipeline complete "
                    f"in {total_elapsed:.3f}s"
                )
                return []

            # Stage 2.6: Skip transformation and vectorization for DELETE
            if action == DestinationAction.DELETE:
                sync_context.logger.info(
                    f"🗑️ PROCESSOR_DELETE [{entity_context}] "
                    "Processing deletion, skipping transform/vector"
                )
                # Process deletion directly
                await self._persist(enriched_entity, [], None, action, sync_context)
                total_elapsed = asyncio.get_event_loop().time() - pipeline_start
                sync_context.logger.info(
                    f"✅ PROCESSOR_DELETE_COMPLETE [{entity_context}] Deletion complete "
                    f"in {total_elapsed:.3f}s"
                )
                return []

            # Stage 3: Process entity through DAG
            sync_context.logger.debug(
                f"🔀 PROCESSOR_TRANSFORM_START [{entity_context}] Starting DAG transformation"
            )
            transform_start = asyncio.get_event_loop().time()

            processed_entities = await self._transform(enriched_entity, source_node, sync_context)

            transform_elapsed = asyncio.get_event_loop().time() - transform_start
            sync_context.logger.debug(
                f"🔄 PROCESSOR_TRANSFORM_DONE [{entity_context}] Transformed into "
                f"{len(processed_entities)} entities in {transform_elapsed:.3f}s"
            )

            # Check if transformation resulted in no entities
            if len(processed_entities) == 0:
                sync_context.logger.warning(
                    f"📭 PROCESSOR_EMPTY_TRANSFORM [{entity_context}] "
                    f"No entities produced, marking skipped"
                )
                await sync_context.progress.increment("skipped", 1)
                return []

            # Stage 4: Compute vector
            sync_context.logger.debug(
                f"🧮 PROCESSOR_VECTOR_START [{entity_context}] Computing vectors"
            )
            vector_start = asyncio.get_event_loop().time()

            processed_entities_with_vector = await self._compute_vector(
                processed_entities, sync_context
            )

            vector_elapsed = asyncio.get_event_loop().time() - vector_start
            sync_context.logger.debug(
                f"🎯 PROCESSOR_VECTOR_DONE [{entity_context}] Computed vectors for "
                f"{len(processed_entities_with_vector)} entities in {vector_elapsed:.3f}s"
            )

            # Stage 5: Persist entities based on action (REQUIRES DATABASE)
            sync_context.logger.debug(
                f"💾 PROCESSOR_PERSIST_START [{entity_context}] Persisting to destinations"
            )
            persist_start = asyncio.get_event_loop().time()

            await self._persist(
                enriched_entity, processed_entities_with_vector, db_entity, action, sync_context
            )

            persist_elapsed = asyncio.get_event_loop().time() - persist_start

            total_elapsed = asyncio.get_event_loop().time() - pipeline_start
            sync_context.logger.debug(
                f"✅ PROCESSOR_COMPLETE [{entity_context}] "
                f"Pipeline complete in {total_elapsed:.3f}s "
                f"(enrich: {enrich_elapsed:.3f}s, action: {action_elapsed:.3f}s, "
                f"transform: {transform_elapsed:.3f}s, vector: {vector_elapsed:.3f}s, "
                f"persist: {persist_elapsed:.3f}s)"
            )

            return processed_entities

        except Exception as e:
            pipeline_elapsed = asyncio.get_event_loop().time() - pipeline_start
            error_type = type(e).__name__
            error_message = str(e) if str(e) else "No error details available"

            # Log detailed error information
            sync_context.logger.error(
                f"💥 PROCESSOR_ERROR [{entity_context}] Pipeline failed after "
                f"{pipeline_elapsed:.3f}s: {error_type}: {error_message}"
            )

            # For debugging empty errors
            if not str(e):
                sync_context.logger.error(
                    f"🔍 PROCESSOR_ERROR_DETAILS [{entity_context}] "
                    f"Empty error of type {error_type}, repr: {repr(e)}"
                )

            # Mark as skipped and continue
            await sync_context.progress.increment("skipped", 1)
            sync_context.logger.warning(
                f"📊 PROCESSOR_SKIP_COUNT [{entity_context}] Marked as skipped due to error"
            )

            return []

    async def _enrich(self, entity: BaseEntity, sync_context: SyncContext) -> BaseEntity:
        """Enrich entity with sync metadata."""
        # Check if entity needs lazy materialization
        if hasattr(entity, "needs_materialization") and entity.needs_materialization:
            sync_context.logger.debug(
                f"🔄 PROCESSOR_LAZY_DETECT [Entity({entity.entity_id})] "
                f"Entity requires materialization"
            )
            await entity.materialize()

        entity.source_name = sync_context.source._name
        entity.sync_id = sync_context.sync.id
        entity.sync_job_id = sync_context.sync_job.id
        entity.sync_metadata = sync_context.sync.sync_metadata

        return entity

    async def _determine_action(
        self, entity: BaseEntity, sync_context: SyncContext
    ) -> tuple[Optional[models.Entity], DestinationAction]:
        """Determine what action to take for an entity.

        Creates a temporary database session for the lookup.
        """
        entity_context = f"Entity({entity.entity_id})"

        # Check if this is a deletion entity
        if hasattr(entity, "deletion_status") and entity.deletion_status == "removed":
            sync_context.logger.info(f"🗑️ ACTION_DELETE [{entity_context}] Detected deletion entity")
            return None, DestinationAction.DELETE

        sync_context.logger.info(
            f"🔍 ACTION_DB_LOOKUP [{entity_context}] Looking up existing entity in database"
        )
        db_start = asyncio.get_event_loop().time()

        # Create a new database session just for this lookup
        async with get_db_context() as db:
            try:
                db_entity = await crud.entity.get_by_entity_and_sync_id(
                    db=db, entity_id=entity.entity_id, sync_id=sync_context.sync.id
                )
            except NotFoundException:
                db_entity = None

        db_elapsed = asyncio.get_event_loop().time() - db_start

        if db_entity:
            sync_context.logger.debug(
                f"📋 ACTION_FOUND [{entity_context}] Found existing entity "
                f"(DB lookup: {db_elapsed:.3f}s)"
            )
        else:
            sync_context.logger.debug(
                f"🆕 ACTION_NEW [{entity_context}] No existing entity found "
                f"(DB lookup: {db_elapsed:.3f}s)"
            )

        # Hash computation
        sync_context.logger.debug(f"🔢 ACTION_HASH_START [{entity_context}] Computing entity hash")
        hash_start = asyncio.get_event_loop().time()

        current_hash = await compute_entity_hash_async(entity)

        hash_elapsed = asyncio.get_event_loop().time() - hash_start
        sync_context.logger.debug(
            f"🔢 ACTION_HASH_DONE [{entity_context}] Hash computed in {hash_elapsed:.3f}s"
        )

        if db_entity:
            if db_entity.hash != current_hash:
                action = DestinationAction.UPDATE
                sync_context.logger.debug(
                    f"🔄 ACTION_UPDATE [{entity_context}] Hash differs "
                    f"(stored: {db_entity.hash[:8]}..., current: {current_hash[:8]}...)"
                )
            else:
                action = DestinationAction.KEEP
                sync_context.logger.debug(
                    f"✅ ACTION_KEEP [{entity_context}] Hash matches, no changes needed"
                )
        else:
            action = DestinationAction.INSERT
            sync_context.logger.debug(
                f"➕ ACTION_INSERT [{entity_context}] New entity, will insert"
            )

        return db_entity, action

    async def _transform(
        self,
        entity: BaseEntity,
        source_node: schemas.DagNode,
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        """Transform entity through DAG routing.

        The router will create its own database session if needed.
        """
        sync_context.logger.debug(
            f"Starting transformation for entity {entity.entity_id} "
            f"(type: {type(entity).__name__}) from source node {source_node.id}"
        )

        # The router will create its own DB session if needed
        transformed_entities = await sync_context.router.process_entity(
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
        db_entity: Optional[models.Entity],
        action: DestinationAction,
        sync_context: SyncContext,
    ) -> None:
        """Persist entities to destinations based on action.

        Args:
            parent_entity: The parent entity of the processed entities
            processed_entities: The entities to persist
            db_entity: The database entity to update
            action: The action to take
            sync_context: The sync context
        """
        if action == DestinationAction.KEEP:
            await self._handle_keep(sync_context)
        elif action == DestinationAction.INSERT:
            await self._handle_insert(parent_entity, processed_entities, db_entity, sync_context)
        elif action == DestinationAction.UPDATE:
            await self._handle_update(parent_entity, processed_entities, db_entity, sync_context)
        elif action == DestinationAction.DELETE:
            await self._handle_delete(parent_entity, sync_context)

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
            sync_context.logger.debug("📭 VECTOR_EMPTY No entities to vectorize")
            return []

        entity_context = self._get_entity_context(processed_entities)
        entity_count = len(processed_entities)

        sync_context.logger.debug(
            f"🧮 VECTOR_START [{entity_context}] Computing vectors for {entity_count} entities"
        )

        try:
            # Convert entities to dictionaries for embedding
            sync_context.logger.debug(
                f"📦 VECTOR_CONVERT_START [{entity_context}] Converting entities to dicts"
            )
            convert_start = asyncio.get_event_loop().time()

            entity_dicts = await self._convert_entities_to_dicts(processed_entities, sync_context)

            convert_elapsed = asyncio.get_event_loop().time() - convert_start
            sync_context.logger.debug(
                f"📦 VECTOR_CONVERT_DONE [{entity_context}] Converted {len(entity_dicts)} entities "
                f"in {convert_elapsed:.3f}s"
            )

            # Get embeddings from the model
            sync_context.logger.debug(
                f"🤖 VECTOR_EMBED_START [{entity_context}] Calling embedding model"
            )
            embed_start = asyncio.get_event_loop().time()

            embeddings = await self._get_embeddings(entity_dicts, sync_context, entity_context)

            embed_elapsed = asyncio.get_event_loop().time() - embed_start
            sync_context.logger.debug(
                f"🤖 VECTOR_EMBED_DONE [{entity_context}] Got {len(embeddings)} embeddings "
                f"in {embed_elapsed:.3f}s"
            )

            # Assign vectors to entities
            sync_context.logger.debug(
                f"🔗 VECTOR_ASSIGN_START [{entity_context}] Assigning vectors to entities"
            )
            assign_start = asyncio.get_event_loop().time()

            processed_entities = await self._assign_vectors_to_entities(
                processed_entities, embeddings, sync_context
            )

            assign_elapsed = asyncio.get_event_loop().time() - assign_start
            sync_context.logger.debug(
                f"🔗 VECTOR_ASSIGN_DONE [{entity_context}] "
                f"Assigned vectors in {assign_elapsed:.3f}s"
            )

            total_elapsed = convert_elapsed + embed_elapsed + assign_elapsed
            sync_context.logger.debug(
                f"✅ VECTOR_COMPLETE [{entity_context}] "
                f"Vectorization complete in {total_elapsed:.3f}s "
                f"(convert: {convert_elapsed:.3f}s, embed: {embed_elapsed:.3f}s, "
                f"assign: {assign_elapsed:.3f}s)"
            )

            return processed_entities

        except Exception as e:
            sync_context.logger.error(
                f"💥 VECTOR_ERROR [{entity_context}] Vectorization failed: {str(e)}"
            )
            raise

    def _get_entity_context(self, processed_entities: List[BaseEntity]) -> str:
        """Get entity context string for logging."""
        if processed_entities:
            return "Entity batch"
        return "Entity batch"

    def _log_vectorization_start(
        self, processed_entities: List[BaseEntity], sync_context: SyncContext, entity_context: str
    ) -> None:
        """Log vectorization startup information."""
        embedding_model = sync_context.embedding_model
        entity_count = len(processed_entities)

        sync_context.logger.debug(
            f"Computing vectors for {entity_count} entities using {embedding_model.model_name}"
        )

        # # Log entity content lengths for debugging
        # content_lengths = [len(str(entity.to_storage_dict())) for entity in processed_entities]
        # total_length = sum(content_lengths)
        # avg_length = total_length / entity_count if entity_count else 0
        # max_length = max(content_lengths) if content_lengths else 0

        # sync_context.logger.debug(
        #     f"Entity content stats: total={total_length}, "
        #     f"avg={avg_length:.2f}, max={max_length}, count={entity_count}"
        # )

    async def _convert_entities_to_dicts(
        self, processed_entities: List[BaseEntity], sync_context: SyncContext
    ) -> List[str]:
        """Convert entities to dictionary representations."""

        def _convert_entities_to_dicts_sync(entities):
            entity_dicts = []
            for _i, entity in enumerate(entities):
                try:
                    entity_dict = str(entity.to_storage_dict())

                    # Log large entities for debugging
                    dict_length = len(entity_dict)
                    if dict_length > 30000:  # ~7500 tokens
                        entity_type = type(entity).__name__
                        sync_context.logger.error(
                            f"🚨 ENTITY_TOO_LARGE Entity {entity.entity_id} ({entity_type}) "
                            f"stringified to {dict_length} chars (~{dict_length // 4} tokens)"
                        )
                        # Log first 1000 chars
                        sync_context.logger.error(
                            f"📄 ENTITY_PREVIEW First 1000 chars of {entity.entity_id}:\n"
                            f"{entity_dict[:1000]}..."
                        )
                        # Log field info if available
                        if hasattr(entity, "model_dump"):
                            fields = entity.model_dump()
                            large_fields = []
                            for field_name, field_value in fields.items():
                                if isinstance(field_value, str) and len(field_value) > 1000:
                                    large_fields.append(f"{field_name}: {len(field_value)} chars")
                            if large_fields:
                                sync_context.logger.error(
                                    f"📊 LARGE_FIELDS in {entity.entity_id}: "
                                    f"{', '.join(large_fields)}"
                                )

                    entity_dicts.append(entity_dict)

                except Exception as e:
                    sync_context.logger.error(f"Error converting entity to dict: {str(e)}")
                    # Provide a fallback empty string to maintain array alignment
                    entity_dicts.append("")
            return entity_dicts

        # Process in smaller batches to prevent long blocking periods
        batch_size = 10
        all_dicts = []

        for i in range(0, len(processed_entities), batch_size):
            batch = processed_entities[i : i + batch_size]

            sync_context.logger.debug(
                f"📦 CONVERT_BATCH Converting batch {i // batch_size + 1} ({len(batch)} entities)"
            )

            batch_dicts = await run_in_thread_pool(_convert_entities_to_dicts_sync, batch)
            all_dicts.extend(batch_dicts)

            # Yield control between batches
            await asyncio.sleep(0)

        return all_dicts

    async def _get_embeddings(
        self, entity_dicts: List[str], sync_context: SyncContext, entity_context: str
    ) -> List[List[float]]:
        """Get embeddings from the embedding model."""
        import asyncio
        import inspect

        embedding_model = sync_context.embedding_model
        loop = asyncio.get_event_loop()
        cpu_start = loop.time()

        # Get embeddings from the model with entity context
        if hasattr(embedding_model, "embed_many"):
            # Check if the embedding model supports entity_context parameter
            embed_many_signature = inspect.signature(embedding_model.embed_many)
            if "entity_context" in embed_many_signature.parameters:
                embeddings = await embedding_model.embed_many(
                    entity_dicts, entity_context=entity_context
                )
            else:
                embeddings = await embedding_model.embed_many(entity_dicts)
        else:
            embeddings = await embedding_model.embed_many(entity_dicts)

        cpu_elapsed = loop.time() - cpu_start
        sync_context.logger.debug(
            f"Vector computation completed in {cpu_elapsed:.2f}s for {len(embeddings)} entities"
        )

        return embeddings

    async def _assign_vectors_to_entities(
        self,
        processed_entities: List[BaseEntity],
        embeddings: List[List[float]],
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        """Assign vectors to entities."""
        # Validate we got the expected number of embeddings
        if len(embeddings) != len(processed_entities):
            sync_context.logger.warning(
                f"Embedding count mismatch: got {len(embeddings)} embeddings "
                f"for {len(processed_entities)} entities"
            )

        # Assign vectors to entities in thread pool (CPU-bound operation for many entities)
        def _assign_vectors_to_entities_sync(entities, vectors):
            for i, (processed_entity, vector) in enumerate(zip(entities, vectors, strict=False)):
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
            return entities

        return await run_in_thread_pool(
            _assign_vectors_to_entities_sync, processed_entities, embeddings
        )

    async def _handle_keep(self, sync_context: SyncContext) -> None:
        """Handle KEEP action."""
        await sync_context.progress.increment(kept=1)

    async def _handle_insert(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: Optional[models.Entity],
        sync_context: SyncContext,
    ) -> None:
        """Handle INSERT action."""
        entity_context = f"Entity({parent_entity.entity_id})"

        if len(processed_entities) == 0:
            sync_context.logger.warning(f"📭 INSERT_EMPTY [{entity_context}] No entities to insert")
            await sync_context.progress.increment("skipped", 1)
            return

        sync_context.logger.debug(
            f"➕ INSERT_START [{entity_context}] Inserting {len(processed_entities)} entities"
        )

        # Database insertion
        sync_context.logger.debug(f"💾 INSERT_DB_START [{entity_context}] Creating database entity")
        db_start = asyncio.get_event_loop().time()

        parent_hash = await compute_entity_hash_async(parent_entity)

        # Create a new database session just for this insert
        async with get_db_context() as db:
            new_db_entity = await crud.entity.create(
                db=db,
                obj_in=schemas.EntityCreate(
                    sync_job_id=sync_context.sync_job.id,
                    sync_id=sync_context.sync.id,
                    entity_id=parent_entity.entity_id,
                    hash=parent_hash,
                ),
                ctx=sync_context.ctx,
            )

        db_elapsed = asyncio.get_event_loop().time() - db_start
        parent_entity.db_entity_id = new_db_entity.id
        sync_context.logger.debug(
            f"💾 INSERT_DB_DONE [{entity_context}] Database entity created in {db_elapsed:.3f}s"
        )
        # Destination insertion
        sync_context.logger.debug(
            f"🎯 INSERT_DEST_START [{entity_context}] "
            f"Writing to {len(sync_context.destinations)} destinations"
        )
        dest_start = asyncio.get_event_loop().time()

        for i, destination in enumerate(sync_context.destinations):
            sync_context.logger.debug(
                f"📤 INSERT_DEST_{i} [{entity_context}] Writing to destination {i + 1}"
            )
            await destination.bulk_insert(processed_entities)

        dest_elapsed = asyncio.get_event_loop().time() - dest_start
        sync_context.logger.debug(
            f"🎯 INSERT_DEST_DONE [{entity_context}] "
            f"All destinations written in {dest_elapsed:.3f}s"
        )

        await sync_context.progress.increment("inserted", 1)

        # Increment guard rail usage for actual entity processing
        await sync_context.guard_rail.increment(ActionType.ENTITIES)

        total_elapsed = db_elapsed + dest_elapsed
        sync_context.logger.debug(
            f"✅ INSERT_COMPLETE [{entity_context}] Insert complete in {total_elapsed:.3f}s"
        )

    async def _handle_update(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: models.Entity,
        sync_context: SyncContext,
    ) -> None:
        """Handle UPDATE action."""
        entity_context = f"Entity({parent_entity.entity_id})"

        if len(processed_entities) == 0:
            sync_context.logger.warning(f"📭 UPDATE_EMPTY [{entity_context}] No entities to update")
            await sync_context.progress.increment("skipped", 1)
            return

        sync_context.logger.debug(
            f"🔄 UPDATE_START [{entity_context}] Updating {len(processed_entities)} entities"
        )

        # Database update
        sync_context.logger.debug(f"💾 UPDATE_DB_START [{entity_context}] Updating database entity")
        db_start = asyncio.get_event_loop().time()

        parent_hash = await compute_entity_hash_async(parent_entity)

        # Create a new database session just for this update
        # Re-fetch entity in this session (original was from a different session)
        async with get_db_context() as db:
            # Re-query the entity in the new session to avoid session issues
            try:
                fresh_db_entity = await crud.entity.get_by_entity_and_sync_id(
                    db=db, entity_id=parent_entity.entity_id, sync_id=sync_context.sync.id
                )
                await crud.entity.update(
                    db=db,
                    db_obj=fresh_db_entity,
                    obj_in=schemas.EntityUpdate(hash=parent_hash),
                    auth_context=sync_context.auth_context,
                )
            except NotFoundException:
                sync_context.logger.warning(
                    f"📭 UPDATE_ENTITY_NOT_FOUND [{entity_context}] "
                    f"Entity no longer exists in database"
                )
                await sync_context.progress.increment("skipped", 1)
                return

        db_elapsed = asyncio.get_event_loop().time() - db_start
        parent_entity.db_entity_id = db_entity.id
        sync_context.logger.debug(
            f"💾 UPDATE_DB_DONE [{entity_context}] Database updated in {db_elapsed:.3f}s"
        )

        # Destination update (delete then insert)
        sync_context.logger.debug(
            f"🗑️  UPDATE_DELETE_START [{entity_context}] Deleting old data from destinations"
        )
        delete_start = asyncio.get_event_loop().time()

        for i, destination in enumerate(sync_context.destinations):
            sync_context.logger.debug(
                f"🗑️  UPDATE_DELETE_{i} [{entity_context}] Deleting from destination {i + 1}"
            )
            await destination.bulk_delete_by_parent_id(
                parent_entity.entity_id, sync_context.sync.id
            )

        delete_elapsed = asyncio.get_event_loop().time() - delete_start
        sync_context.logger.debug(
            f"🗑️  UPDATE_DELETE_DONE [{entity_context}] "
            f"All deletions complete in {delete_elapsed:.3f}s"
        )

        sync_context.logger.debug(
            f"📤 UPDATE_INSERT_START [{entity_context}] Inserting new data to destinations"
        )
        insert_start = asyncio.get_event_loop().time()

        for i, destination in enumerate(sync_context.destinations):
            sync_context.logger.debug(
                f"📤 UPDATE_INSERT_{i} [{entity_context}] Inserting to destination {i + 1}"
            )
            await destination.bulk_insert(processed_entities)

        insert_elapsed = asyncio.get_event_loop().time() - insert_start
        sync_context.logger.debug(
            f"✅ UPDATE_INSERT_DONE [{entity_context}] "
            f"All insertions complete in {insert_elapsed:.3f}s"
        )

        await sync_context.progress.increment("updated", 1)

        # Increment guard rail usage for actual entity processing
        await sync_context.guard_rail.increment(ActionType.ENTITIES)

        total_elapsed = db_elapsed + delete_elapsed + insert_elapsed
        sync_context.logger.debug(
            f"✅ UPDATE_COMPLETE [{entity_context}] Update complete in {total_elapsed:.3f}s"
        )

    async def _handle_delete(
        self,
        parent_entity: BaseEntity,
        sync_context: SyncContext,
    ) -> None:
        """Handle DELETE action."""
        entity_context = f"Entity({parent_entity.entity_id})"

        sync_context.logger.info(
            f"🗑️ DELETE_START [{entity_context}] Deleting entity from destinations"
        )

        # Delete from destinations
        delete_start = asyncio.get_event_loop().time()

        for i, destination in enumerate(sync_context.destinations):
            sync_context.logger.info(
                f"🗑️ DELETE_DEST_{i} [{entity_context}] Deleting from destination {i + 1}"
            )
            await destination.bulk_delete_by_parent_id(
                parent_entity.entity_id, sync_context.sync.id
            )

        delete_elapsed = asyncio.get_event_loop().time() - delete_start
        sync_context.logger.info(
            f"🗑️ DELETE_DEST_DONE [{entity_context}] All deletions complete in {delete_elapsed:.3f}s"
        )

        # Delete from database if it exists
        db_start = asyncio.get_event_loop().time()
        async with get_db_context() as db:
            try:
                db_entity = await crud.entity.get_by_entity_and_sync_id(
                    db=db, entity_id=parent_entity.entity_id, sync_id=sync_context.sync.id
                )
                if db_entity:
                    await crud.entity.remove(
                        db=db, id=db_entity.id, auth_context=sync_context.auth_context
                    )
                    sync_context.logger.info(
                        f"💾 DELETE_DB_DONE [{entity_context}] Database entity deleted"
                    )
                else:
                    sync_context.logger.info(
                        f"💾 DELETE_DB_SKIP [{entity_context}] No database entity to delete"
                    )
            except NotFoundException:
                sync_context.logger.info(
                    f"💾 DELETE_DB_SKIP [{entity_context}] Database entity not found"
                )

        db_elapsed = asyncio.get_event_loop().time() - db_start

        await sync_context.progress.increment("deleted", 1)
        total_elapsed = delete_elapsed + db_elapsed
        sync_context.logger.info(
            f"✅ DELETE_COMPLETE [{entity_context}] Delete complete in {total_elapsed:.3f}s"
        )
