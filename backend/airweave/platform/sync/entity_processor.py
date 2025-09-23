"""Module for entity processing within the sync architecture."""

import asyncio
from typing import Dict, List, Optional, Set, Tuple

from fastembed import SparseTextEmbedding

from airweave import crud, models, schemas
from airweave.core.constants.reserved_ids import RESERVED_TABLE_ENTITY_ID
from airweave.core.exceptions import NotFoundException
from airweave.core.shared_models import ActionType
from airweave.db.session import get_db_context
from airweave.platform.entities._base import BaseEntity, DestinationAction, PolymorphicEntity
from airweave.platform.sync.async_helpers import compute_entity_hash_async, run_in_thread_pool
from airweave.platform.sync.context import SyncContext


class EntityProcessor:
    """Processes entities through a pipeline of stages.

    Exposes both:
      - process(...)       -> single-entity pipeline (original logic preserved)
      - process_batch(...) -> batched pipeline (same logic, better performance)
    """

    def __init__(self):
        """Initialize the entity processor with empty tracking dictionary."""
        self._entity_ids_encountered_by_type: Dict[str, Set[str]] = {}

    def initialize_tracking(self, sync_context: SyncContext) -> None:
        """Initialize entity tracking with entity types from the DAG.

        Args:
            sync_context: The sync context containing the DAG
        """
        self._entity_ids_encountered_by_type.clear()

        # Get all entity nodes from the DAG
        entity_nodes = [
            node for node in sync_context.dag.nodes if node.type == schemas.dag.NodeType.entity
        ]

        # Create a dictionary with entity names as keys and empty sets as values
        for node in entity_nodes:
            if node.name.endswith("Entity"):
                self._entity_ids_encountered_by_type[node.name] = set()

    # ------------------------------------------------------------------------------------
    # Original single entity processing (EXACT copy from old version)
    # ------------------------------------------------------------------------------------
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
            # Log removed - too verbose for normal operations

            # Track the current entity
            entity_type = entity.__class__.__name__
            if entity_type not in self._entity_ids_encountered_by_type:
                self._entity_ids_encountered_by_type[entity_type] = set()

            # Check for duplicate processing
            if entity.entity_id in self._entity_ids_encountered_by_type[entity_type]:
                # Silently skip duplicates - this is expected behavior
                return []

            # Update entity tracking
            self._entity_ids_encountered_by_type[entity_type].add(entity.entity_id)
            await sync_context.progress.update_entities_encountered_count(
                self._entity_ids_encountered_by_type
            )

            # Check if entity should be skipped (set by file_manager or source)
            if getattr(entity, "should_skip", False):
                await sync_context.progress.increment("skipped", 1)
                return []

            # Stage 1: Enrich entity with metadata
            enriched_entity = await self._enrich(entity, sync_context)

            # Stage 2: Determine action for entity (REQUIRES DATABASE)
            db_entity, action = await self._determine_action(enriched_entity, sync_context)

            # Stage 2.5: Skip further processing if KEEP
            if action == DestinationAction.KEEP:
                await sync_context.progress.increment("kept", 1)
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
            processed_entities = await self._transform(enriched_entity, source_node, sync_context)

            # Check if transformation resulted in no entities
            if len(processed_entities) == 0:
                sync_context.logger.warning(
                    f"📭 PROCESSOR_EMPTY_TRANSFORM [{entity_context}] "
                    f"No entities produced, marking skipped"
                )
                await sync_context.progress.increment("skipped", 1)
                return []

            # Stage 4: Compute vector
            processed_entities_with_vector = await self._compute_vector(
                processed_entities, sync_context
            )

            # Stage 5: Persist entities based on action (REQUIRES DATABASE)
            await self._persist(
                enriched_entity, processed_entities_with_vector, db_entity, action, sync_context
            )

            return processed_entities

        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e) if str(e) else "No error details available"

            # Log error (keep this as it's important for debugging)
            sync_context.logger.warning(
                f"Entity processing failed: {entity.entity_id} - {error_type}: {error_message}"
            )

            # Mark as skipped and continue
            await sync_context.progress.increment("skipped", 1)
            return []

    # ------------------------------------------------------------------------------------
    # NEW: Batch processing API (maintains old logic but with batching for performance)
    # ------------------------------------------------------------------------------------
    async def process_batch(
        self,
        entities: List[BaseEntity],
        source_node: schemas.DagNode,
        sync_context: SyncContext,
        *,
        inner_concurrency: int = 8,
    ) -> Dict[str, List[BaseEntity]]:
        """Process a batch of entities using the same logic as single processing.

        This maintains the exact same business logic and entity counting as the
        original process() method, but uses batching optimizations for better performance.

        Returns:
            Dict[parent_entity_id, List[BaseEntity]]: A mapping of parent entity IDs
            to their processed entities.
        """
        if not entities:
            return {}

        results: Dict[str, List[BaseEntity]] = {}

        # Process batch with controlled concurrency

        # Process entities with controlled concurrency, but maintain individual logic
        sem = asyncio.Semaphore(inner_concurrency)

        async def _process_one_with_sem(entity: BaseEntity) -> Tuple[str, List[BaseEntity]]:
            async with sem:
                processed_entities = await self.process(entity, source_node, sync_context)
                return entity.entity_id, processed_entities

        # Execute all entities concurrently with semaphore control
        batch_results = await asyncio.gather(
            *[_process_one_with_sem(entity) for entity in entities], return_exceptions=True
        )

        # Collect results and handle any exceptions
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                entity_id = entities[i].entity_id if i < len(entities) else "unknown"
                sync_context.logger.warning(
                    f"💥 BATCH_ENTITY_ERROR Entity {entity_id} failed: {result}"
                )
                # The individual process() call already handled the error and
                # incremented skipped count
                results[entity_id] = []
            else:
                entity_id, processed_entities = result
                results[entity_id] = processed_entities

        # Batch processing complete

        return results

    # ------------------------------------------------------------------------------------
    # Shared helpers (EXACT copies from old version)
    # ------------------------------------------------------------------------------------
    async def _enrich(self, entity: BaseEntity, sync_context: SyncContext) -> BaseEntity:
        """Enrich entity with sync metadata."""
        from datetime import datetime, timedelta, timezone

        from airweave.platform.entities._base import AirweaveSystemMetadata

        # Create or update system metadata
        if entity.airweave_system_metadata is None:
            entity.airweave_system_metadata = AirweaveSystemMetadata()

        # Set all system metadata fields
        entity.airweave_system_metadata.source_name = sync_context.source._short_name
        entity.airweave_system_metadata.entity_type = entity.__class__.__name__
        entity.airweave_system_metadata.sync_id = sync_context.sync.id
        entity.airweave_system_metadata.sync_job_id = sync_context.sync_job.id
        entity.airweave_system_metadata.sync_metadata = sync_context.sync.sync_metadata

        # Get harmonized timestamps and use updated_at if available
        timestamps = entity.get_harmonized_timestamps()
        updated_at = timestamps.get("updated_at")
        created_at = timestamps.get("created_at")

        if updated_at:
            entity.airweave_system_metadata.airweave_updated_at = updated_at
        elif created_at:
            entity.airweave_system_metadata.airweave_updated_at = created_at
        else:
            # Default to 2 weeks ago in UTC if no updated_at field
            entity.airweave_system_metadata.airweave_updated_at = datetime.now(
                timezone.utc
            ) - timedelta(weeks=2)

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

        # Create a new database session just for this lookup
        async with get_db_context() as db:
            try:
                db_entity = await crud.entity.get_by_entity_and_sync_id(
                    db=db, entity_id=entity.entity_id, sync_id=sync_context.sync.id
                )
            except NotFoundException:
                db_entity = None

        # Hash computation
        current_hash = await compute_entity_hash_async(entity)

        if db_entity:
            if db_entity.hash != current_hash:
                action = DestinationAction.UPDATE
            else:
                action = DestinationAction.KEEP
        else:
            action = DestinationAction.INSERT

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
        # The router will create its own DB session if needed
        transformed_entities = await sync_context.router.process_entity(
            producer_id=source_node.id,
            entity=entity,
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
            await self._handle_insert(parent_entity, processed_entities, sync_context)
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
            return []

        entity_context = self._get_entity_context(processed_entities)

        try:
            # Build embeddable texts (instead of stringifying full dicts)

            texts: list[str] = []
            for e in processed_entities:
                text = e.build_embeddable_text() if hasattr(e, "build_embeddable_text") else str(e)
                # Persist for downstream destinations/UI
                if hasattr(e, "embeddable_text"):
                    try:
                        e.embeddable_text = text
                    except Exception:
                        pass
                texts.append(text)

            # Text building complete

            # Get embeddings from the model

            embeddings, sparse_embeddings = await self._get_embeddings(
                texts, sync_context, entity_context
            )

            # Embeddings computed

            # Assign vectors to entities

            processed_entities = await self._assign_vectors_to_entities(
                processed_entities, embeddings, sparse_embeddings, sync_context
            )

            # Vectors assigned

            return processed_entities

        except Exception as e:
            sync_context.logger.warning(
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
                        sync_context.logger.warning(
                            f"🚨 ENTITY_TOO_LARGE Entity {entity.entity_id} ({entity_type}) "
                            f"stringified to {dict_length} chars (~{dict_length // 4} tokens)"
                        )
                        # Log first 1000 chars
                        sync_context.logger.warning(
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
                                sync_context.logger.warning(
                                    f"📊 LARGE_FIELDS in {entity.entity_id}: "
                                    f"{', '.join(large_fields)}"
                                )

                    entity_dicts.append(entity_dict)

                except Exception as e:
                    sync_context.logger.warning(f"Error converting entity to dict: {str(e)}")
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
        self, texts: List[str], sync_context: SyncContext, entity_context: str
    ) -> Tuple[List[List[float]], List[SparseTextEmbedding] | None]:
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
                embeddings = await embedding_model.embed_many(texts, entity_context=entity_context)
            else:
                embeddings = await embedding_model.embed_many(texts)
        else:
            embeddings = await embedding_model.embed_many(texts)

        # Some destinations might not have a BM25 index, so we need to check if we need to compute
        # sparse embeddings.
        calculate_sparse_embeddings = any(
            await asyncio.gather(
                *[destination.has_keyword_index() for destination in sync_context.destinations]
            )
        )

        if calculate_sparse_embeddings:
            sparse_embedder = sync_context.keyword_indexing_model
            sparse_embeddings = list(await sparse_embedder.embed_many(texts))
        else:
            sparse_embeddings = None

        cpu_elapsed = loop.time() - cpu_start
        sync_context.logger.debug(
            f"Vector computation completed in {cpu_elapsed:.2f}s for {len(embeddings)} entities"
        )

        return embeddings, sparse_embeddings

    async def _assign_vectors_to_entities(
        self,
        processed_entities: List[BaseEntity],
        embeddings: List[List[float]],
        sparse_embeddings: List[SparseTextEmbedding] | None,
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
        def _assign_vectors_to_entities_sync(entities, neural_vectors, sparse_vectors):
            for i, (processed_entity, neural_vector) in enumerate(
                zip(entities, neural_vectors, strict=False)
            ):
                try:
                    if neural_vector is None:
                        sync_context.logger.warning(
                            f"Received None vectors for entity at index {i}"
                        )
                        continue

                    sparse_vector = sparse_vectors[i] if sparse_vectors else None
                    # Ensure system metadata exists before setting vector
                    if processed_entity.airweave_system_metadata is None:
                        from airweave.platform.entities._base import AirweaveSystemMetadata

                        processed_entity.airweave_system_metadata = AirweaveSystemMetadata()
                    processed_entity.airweave_system_metadata.vectors = [
                        neural_vector,
                        sparse_vector,
                    ]
                except Exception as e:
                    sync_context.logger.warning(
                        f"Error assigning vector to entity at index {i}: {str(e)}"
                    )
            return entities

        return await run_in_thread_pool(
            _assign_vectors_to_entities_sync, processed_entities, embeddings, sparse_embeddings
        )

    async def _handle_keep(self, sync_context: SyncContext) -> None:
        """Handle KEEP action."""
        await sync_context.progress.increment("kept", 1)

    async def _handle_insert(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> None:
        """Handle INSERT action."""
        if len(processed_entities) == 0:
            await sync_context.progress.increment("skipped", 1)
            return

        # Database insertion
        parent_hash = await compute_entity_hash_async(parent_entity)

        # Get entity definition ID from the entity map
        entity_type = type(parent_entity)
        entity_definition_id = sync_context.entity_map.get(entity_type)
        if not entity_definition_id:
            if hasattr(entity_type, "__mro__") and issubclass(entity_type, PolymorphicEntity):
                entity_definition_id = RESERVED_TABLE_ENTITY_ID
            else:
                sync_context.logger.warning(
                    f"No entity definition found for type {entity_type.__name__}"
                )
                await sync_context.progress.increment("skipped", 1)
                return

        # Create a new database session just for this insert
        async with get_db_context() as db:
            new_db_entity = await crud.entity.create(
                db=db,
                obj_in=schemas.EntityCreate(
                    sync_job_id=sync_context.sync_job.id,
                    sync_id=sync_context.sync.id,
                    entity_id=parent_entity.entity_id,
                    entity_definition_id=entity_definition_id,
                    hash=parent_hash,
                ),
                ctx=sync_context.ctx,
            )

        # Update system metadata with DB entity ID for parent and all processed entities
        if parent_entity.airweave_system_metadata:
            parent_entity.airweave_system_metadata.db_entity_id = new_db_entity.id

        # CRITICAL: Set db_entity_id for all processed entities (chunks)
        for entity in processed_entities:
            if entity.airweave_system_metadata:
                entity.airweave_system_metadata.db_entity_id = new_db_entity.id

        # Destination insertion
        for destination in sync_context.destinations:
            await destination.bulk_insert(processed_entities)

        await sync_context.progress.increment("inserted", 1)

        # Update total count tracker
        if sync_context.entity_state_tracker and entity_definition_id:
            await sync_context.entity_state_tracker.update_entity_count(
                entity_definition_id=entity_definition_id,
                action="insert",
                entity_name=entity_type.__name__,
                entity_type=str(entity_type.__name__),
            )
        # Increment guard rail usage for actual entity processing
        await sync_context.guard_rail.increment(ActionType.ENTITIES)

    async def _handle_update(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: models.Entity,
        sync_context: SyncContext,
    ) -> None:
        """Handle UPDATE action."""
        if len(processed_entities) == 0:
            await sync_context.progress.increment("skipped", 1)
            return

        # Database update
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
                    ctx=sync_context.ctx,
                )
            except NotFoundException:
                sync_context.logger.warning(
                    f"Entity {parent_entity.entity_id} no longer exists in database"
                )
                await sync_context.progress.increment("skipped", 1)
                return

        # Update system metadata with DB entity ID for parent and all processed entities
        if parent_entity.airweave_system_metadata:
            parent_entity.airweave_system_metadata.db_entity_id = db_entity.id

        # CRITICAL: Set db_entity_id for all processed entities (chunks)
        for entity in processed_entities:
            if entity.airweave_system_metadata:
                entity.airweave_system_metadata.db_entity_id = db_entity.id

        # Destination update (delete then insert)

        for destination in sync_context.destinations:
            await destination.bulk_delete_by_parent_id(
                parent_entity.entity_id, sync_context.sync.id
            )
            await destination.bulk_delete(
                [entity.entity_id for entity in processed_entities],
                sync_context.sync.id,
            )

        # Insert updated data
        for destination in sync_context.destinations:
            await destination.bulk_insert(processed_entities)

        await sync_context.progress.increment("updated", 1)

        # NEW: For total counts, updates don't change count (entity already exists)
        # But we still track the operation for completeness
        if sync_context.entity_state_tracker and db_entity:
            entity_definition_id = db_entity.entity_definition_id
            if entity_definition_id:
                await sync_context.entity_state_tracker.update_entity_count(
                    entity_definition_id=entity_definition_id, action="update"
                )

        # Increment guard rail usage for actual entity processing
        await sync_context.guard_rail.increment(ActionType.ENTITIES)

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
            # Safety net: also delete by the parent entity's own entity_id in case
            # points were inserted without a parent_entity_id payload
            try:
                await destination.bulk_delete([parent_entity.entity_id], sync_context.sync.id)
            except Exception:
                # Don't fail deletion if this secondary path is unsupported by a destination
                sync_context.logger.debug(
                    (
                        f"DELETE_FALLBACK_SKIP [{entity_context}] bulk_delete by entity_id not "
                        "supported or failed: {e}"
                    )
                )

        delete_elapsed = asyncio.get_event_loop().time() - delete_start
        sync_context.logger.info(
            f"🗑️ DELETE_DEST_DONE [{entity_context}] All deletions complete in {delete_elapsed:.3f}s"
        )

        # Delete from database if it exists
        db_start = asyncio.get_event_loop().time()
        db_entity = None
        async with get_db_context() as db:
            try:
                db_entity = await crud.entity.get_by_entity_and_sync_id(
                    db=db, entity_id=parent_entity.entity_id, sync_id=sync_context.sync.id
                )
                if db_entity:
                    await crud.entity.remove(
                        db=db,
                        id=db_entity.id,
                        ctx=sync_context.ctx,
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

        # NEW: Update total count tracker
        if sync_context.entity_state_tracker and db_entity:
            entity_definition_id = db_entity.entity_definition_id
            if entity_definition_id:
                await sync_context.entity_state_tracker.update_entity_count(
                    entity_definition_id=entity_definition_id, action="delete"
                )
        total_elapsed = delete_elapsed + db_elapsed
        sync_context.logger.info(
            f"✅ DELETE_COMPLETE [{entity_context}] Delete complete in {total_elapsed:.3f}s"
        )

    async def cleanup_orphaned_entities(self, sync_context: SyncContext) -> None:
        """Clean up orphaned entities that exist in the database."""
        sync_context.logger.info("🧹 Starting cleanup of orphaned entities")

        try:
            async with get_db_context() as db:
                # Get all entities currently stored for this sync (by sync_id, not sync_job_id)
                stored_entities = await crud.entity.get_by_sync_id(
                    db=db, sync_id=sync_context.sync.id
                )

                if not stored_entities:
                    sync_context.logger.info("🧹 No stored entities found, nothing to clean up")
                    return

                # Find orphaned entities (stored but not encountered)
                orphaned_entities = []
                for stored_entity in stored_entities:
                    # Check if entity_id exists in any of the node sets
                    entity_was_encountered = any(
                        stored_entity.entity_id in entity_set
                        for entity_set in self._entity_ids_encountered_by_type.values()
                    )
                    if not entity_was_encountered:
                        orphaned_entities.append(stored_entity)

                if not orphaned_entities:
                    sync_context.logger.info("🧹 No orphaned entities found")
                    return

                sync_context.logger.info(
                    f"🧹 Found {len(orphaned_entities)} orphaned entities to delete"
                )

                # TODO: wrap this in a unit of work transaction

                # Extract entity IDs for bulk operations
                orphaned_entity_ids = [entity.entity_id for entity in orphaned_entities]
                orphaned_db_ids = [entity.id for entity in orphaned_entities]

                # Delete from destinations first using bulk_delete
                for destination in sync_context.destinations:
                    await destination.bulk_delete(orphaned_entity_ids, sync_context.sync.id)

                # Delete from database using bulk_remove
                await crud.entity.bulk_remove(db=db, ids=orphaned_db_ids, ctx=sync_context.ctx)

                # Update progress tracking
                await sync_context.progress.increment("deleted", len(orphaned_entities))

                sync_context.logger.info(
                    f"✅ Cleanup complete: deleted {len(orphaned_entities)} orphaned entities"
                )

        except Exception as e:
            sync_context.logger.error(f"💥 Cleanup failed: {str(e)}", exc_info=True)
            raise e
