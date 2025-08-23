"""Module for entity processing within the sync architecture."""

import asyncio
from collections import defaultdict
from typing import DefaultDict, Dict, List, Optional, Set, Tuple

from fastembed import SparseTextEmbedding

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
    # Public API — single entity (kept for backward compatibility)
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
        # Delegate to the batch processor with a single-item list, and return that parent's chunks
        results_by_parent = await self.process_batch([entity], source_node, sync_context)
        return results_by_parent.get(entity.entity_id, [])

    # ------------------------------------------------------------------------------------
    # New: batch processing entrypoint
    # ------------------------------------------------------------------------------------
    async def process_batch(
        self,
        entities: List[BaseEntity],
        source_node: schemas.DagNode,
        sync_context: SyncContext,
        *,
        inner_concurrency: int = 8,
        max_embed_batch: int = 512,
    ) -> Dict[str, List[BaseEntity]]:
        """Process a batch of parent entities with batching & limited inner concurrency.

        Returns:
            Dict[parent_entity_id, List[BaseEntity]]: A mapping of parent entity
            IDs to their produced (and persisted) chunk entities.
        """
        loop = asyncio.get_event_loop()
        batch_start = loop.time()
        if not entities:
            return {}

        # Stage 0: Deduplicate, track, and filter entities
        unique_entities = await self._filter_and_track_entities(entities, sync_context)
        if not unique_entities:
            return {}

        # Stage 1: Enrich entities in parallel
        enrich_start = loop.time()
        enriched = await self._batch_enrich(
            unique_entities, sync_context, inner_concurrency=inner_concurrency
        )
        enrich_elapsed = loop.time() - enrich_start

        # Stage 2: Determine actions for each entity
        action_start = loop.time()
        partitions = await self._partition_by_action(
            enriched, sync_context, inner_concurrency=inner_concurrency
        )
        action_elapsed = loop.time() - action_start

        # Early exit if no actions are needed
        if not any(partitions.values()):
            if partitions["keeps"]:
                await sync_context.progress.increment("kept", len(partitions["keeps"]))
            return {k.entity_id: [] for k in partitions["keeps"]}

        # Stage 3: Transform parents that are being inserted or updated
        transform_start = loop.time()
        to_transform = partitions["inserts"] + partitions["updates"]
        children_by_parent = await self._transform_parents(
            to_transform, source_node, sync_context, inner_concurrency
        )
        # Filter out parents whose transforms failed or produced no children
        successful_pids = set(children_by_parent.keys())
        partitions["inserts"] = [e for e in partitions["inserts"] if e.entity_id in successful_pids]
        partitions["updates"] = [e for e in partitions["updates"] if e.entity_id in successful_pids]
        transform_elapsed = loop.time() - transform_start

        # Stage 4: Vectorize all newly created child entities
        vector_start = loop.time()
        all_children = [child for children in children_by_parent.values() for child in children]
        if all_children:
            await self._compute_vector(all_children, sync_context)
        vector_elapsed = loop.time() - vector_start

        # Stage 5: Persist all changes to the database and destinations
        persist_start = loop.time()
        results = await self._persist_batch(
            partitions=partitions,
            existing_map=partitions.pop("existing_map"),
            parent_hashes=partitions.pop("parent_hashes"),
            children_by_parent=children_by_parent,
            sync_context=sync_context,
        )
        persist_elapsed = loop.time() - persist_start

        # Stage 6: Final progress accounting and logging
        if partitions["keeps"]:
            await sync_context.progress.increment("kept", len(partitions["keeps"]))
        total_elapsed = loop.time() - batch_start
        sync_context.logger.debug(
            f"✅ BATCH_COMPLETE parents={len(entities)} "
            f"(enrich: {enrich_elapsed:.3f}s, action: {action_elapsed:.3f}s, "
            f"transform: {transform_elapsed:.3f}s, vector: {vector_elapsed:.3f}s, "
            f"persist: {persist_elapsed:.3f}s, total: {total_elapsed:.3f}s)"
        )

        return results

    async def _filter_and_track_entities(
        self, entities: List[BaseEntity], sync_context: SyncContext
    ) -> List[BaseEntity]:
        """Deduplicate, track, and apply skip flags to a batch of entities."""
        unique_entities: List[BaseEntity] = []
        skipped_due_to_dup = 0
        skipped_due_to_flag = 0

        for e in entities:
            et = e.__class__.__name__
            self._entity_ids_encountered_by_type.setdefault(et, set())

            if e.entity_id in self._entity_ids_encountered_by_type[et]:
                skipped_due_to_dup += 1
                continue
            self._entity_ids_encountered_by_type[et].add(e.entity_id)

            sys_meta = getattr(e, "airweave_system_metadata", None)
            should_skip_flag = getattr(e, "should_skip", False) or (
                sys_meta and getattr(sys_meta, "should_skip", False)
            )
            if should_skip_flag:
                skipped_due_to_flag += 1
                continue

            unique_entities.append(e)

        if skipped_due_to_dup:
            sync_context.logger.debug(
                f"⏭️  BATCH_DUPLICATES Skipped {skipped_due_to_dup} duplicates"
            )
            await sync_context.progress.increment("skipped", skipped_due_to_dup)
        if skipped_due_to_flag:
            await sync_context.progress.increment("skipped", skipped_due_to_flag)

        await sync_context.progress.update_entities_encountered_count(
            self._entity_ids_encountered_by_type
        )
        return unique_entities

    async def _partition_by_action(
        self, entities: List[BaseEntity], sync_context: SyncContext, inner_concurrency: int
    ) -> Dict:
        """Fetch existing DB state, compute hashes, and partition entities by action."""
        deletes = [e for e in entities if getattr(e, "deletion_status", "") == "removed"]
        non_deletes = [e for e in entities if getattr(e, "deletion_status", "") != "removed"]

        existing_map: Dict[str, models.Entity] = {}
        if non_deletes:
            try:
                async with get_db_context() as db:
                    existing_map = await crud.entity.get_by_entity_and_sync_id_many(
                        db,
                        sync_id=sync_context.sync.id,
                        entity_ids=[e.entity_id for e in non_deletes],
                    )
            except Exception as e:
                sync_context.logger.warning(f"💥 BATCH_DB_LOOKUP_ERROR Bulk lookup failed: {e}.")

        hashes, failed_hashes = await self._compute_hashes_concurrently(
            non_deletes, inner_concurrency=inner_concurrency, sync_context=sync_context
        )

        partitions = defaultdict(list)
        for e in non_deletes:
            if e.entity_id in failed_hashes:
                continue
            db_row = existing_map.get(e.entity_id)
            if db_row is None:
                partitions["inserts"].append(e)
            elif db_row.hash != hashes.get(e.entity_id):
                partitions["updates"].append(e)
            else:
                partitions["keeps"].append(e)

        partitions["deletes"] = deletes
        partitions["existing_map"] = existing_map
        partitions["parent_hashes"] = hashes

        sync_context.logger.debug(
            "📋 BATCH_ACTION_DONE partitions — "
            f"INSERT={len(partitions['inserts'])}, UPDATE={len(partitions['updates'])}, "
            f"KEEP={len(partitions['keeps'])}, DELETE={len(partitions['deletes'])}"
        )
        return partitions

    async def _transform_parents(
        self,
        parents: List[BaseEntity],
        source_node: schemas.DagNode,
        sync_context: SyncContext,
        inner_concurrency: int,
    ) -> DefaultDict[str, List[BaseEntity]]:
        """Transform a list of parent entities into chunk entities concurrently."""
        children_by_parent = defaultdict(list)
        if not parents:
            return children_by_parent

        async def _do_transform(p: BaseEntity):
            try:
                return p.entity_id, await self._transform(p, source_node, sync_context)
            except Exception as e:
                sync_context.logger.warning(
                    f"💥 BATCH_TRANSFORM_ERROR [{p.entity_id}] {type(e).__name__}: {e}"
                )
                return p.entity_id, []

        sem = asyncio.Semaphore(inner_concurrency)

        async def _wrapped(p: BaseEntity):
            async with sem:
                return await _do_transform(p)

        results = await asyncio.gather(*[_wrapped(p) for p in parents])
        for pid, kids in results:
            if kids:
                children_by_parent[pid].extend(kids)
            else:
                await sync_context.progress.increment("skipped", 1)

        total_children = sum(len(v) for v in children_by_parent.values())
        sync_context.logger.debug(
            f"🔄 BATCH_TRANSFORM_DONE Produced {total_children} chunks from {len(parents)} parents"
        )
        return children_by_parent

    # ------------------------------------------------------------------------------------
    # Existing single-entity helpers (mostly unchanged)
    # ------------------------------------------------------------------------------------
    async def _enrich(self, entity: BaseEntity, sync_context: SyncContext) -> BaseEntity:
        """Enrich entity with sync metadata."""
        from datetime import datetime, timedelta, timezone

        from airweave.platform.entities._base import AirweaveSystemMetadata

        # Check if entity needs lazy materialization
        if hasattr(entity, "needs_materialization") and entity.needs_materialization:
            sync_context.logger.debug(
                f"🔄 PROCESSOR_LAZY_DETECT [Entity({entity.entity_id})] "
                f"Entity requires materialization"
            )
            await entity.materialize()

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
            sync_context.logger.debug("📭 VECTOR_EMPTY No entities to vectorize")
            return []

        entity_context = self._get_entity_context(processed_entities)
        sync_context.logger.debug(
            f"🧮 VECTOR_START [{entity_context}] Computing vectors for {len(processed_entities)}"
        )
        try:
            texts: list[str] = []
            for e in processed_entities:
                text = e.build_embeddable_text() if hasattr(e, "build_embeddable_text") else str(e)
                if hasattr(e, "embeddable_text"):
                    e.embeddable_text = text
                texts.append(text)

            embeddings, sparse_embeddings = await self._get_embeddings(
                texts, sync_context, entity_context
            )
            processed_entities = await self._assign_vectors_to_entities(
                processed_entities, embeddings, sparse_embeddings, sync_context
            )
            sync_context.logger.debug(
                f"🎯 BATCH_VECTOR_DONE Vectored {len(processed_entities)} chunks"
            )
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
                    vector_dim = len(neural_vector) if neural_vector else 0
                    sync_context.logger.debug(
                        f"Assigning vector of dimension {vector_dim} to "
                        f"entity {processed_entity.entity_id}"
                    )
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
        # normalize progress increment signature
        await sync_context.progress.increment("kept", 1)

    async def _handle_insert(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
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
        # Update system metadata with DB entity ID for parent and all processed entities
        if parent_entity.airweave_system_metadata:
            parent_entity.airweave_system_metadata.db_entity_id = new_db_entity.id

        # CRITICAL: Set db_entity_id for all processed entities (chunks)
        for entity in processed_entities:
            if entity.airweave_system_metadata:
                entity.airweave_system_metadata.db_entity_id = new_db_entity.id

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
                    ctx=sync_context.ctx,
                )
            except NotFoundException:
                sync_context.logger.warning(
                    f"📭 UPDATE_ENTITY_NOT_FOUND [{entity_context}] "
                    f"Entity no longer exists in database"
                )
                await sync_context.progress.increment("skipped", 1)
                return

        db_elapsed = asyncio.get_event_loop().time() - db_start
        # Update system metadata with DB entity ID for parent and all processed entities
        if parent_entity.airweave_system_metadata:
            parent_entity.airweave_system_metadata.db_entity_id = db_entity.id

        # CRITICAL: Set db_entity_id for all processed entities (chunks)
        for entity in processed_entities:
            if entity.airweave_system_metadata:
                entity.airweave_system_metadata.db_entity_id = db_entity.id

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
            await destination.bulk_delete(
                [entity.entity_id for entity in processed_entities],
                sync_context.sync.id,
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

    # ------------------------------------------------------------------------------------
    # New: batch helpers
    # ------------------------------------------------------------------------------------
    async def _batch_enrich(
        self, parents: List[BaseEntity], sync_context: SyncContext, *, inner_concurrency: int
    ) -> List[BaseEntity]:
        """Enrich a list of parent entities with bounded concurrency."""
        sem = asyncio.Semaphore(inner_concurrency)

        async def _one(e: BaseEntity) -> BaseEntity:
            async with sem:
                try:
                    return await self._enrich(e, sync_context)
                except Exception as ex:
                    sync_context.logger.warning(
                        f"💥 ENRICH_ERROR [{e.entity_id}] {type(ex).__name__}: {ex}"
                    )
                    # Mark as skipped and propagate no-op
                    await sync_context.progress.increment("skipped", 1)
                    return e

        enriched = await asyncio.gather(*[_one(e) for e in parents])
        return list(enriched)

    async def _compute_hashes_concurrently(
        self, parents: List[BaseEntity], *, inner_concurrency: int, sync_context: SyncContext
    ) -> Tuple[Dict[str, str], Set[str]]:
        """Compute entity hashes for many parents concurrently (bounded).

        Returns:
            Tuple of (hashes_dict, failed_entity_ids_set)
        """
        sem = asyncio.Semaphore(inner_concurrency)
        hashes: Dict[str, str] = {}
        failed_entities: Set[str] = set()

        async def _one(e: BaseEntity):
            async with sem:
                try:
                    h = await compute_entity_hash_async(e)
                    hashes[e.entity_id] = h
                except Exception as ex:
                    sync_context.logger.warning(
                        f"💥 HASH_ERROR [{e.entity_id}] {type(ex).__name__}: {ex}"
                    )
                    failed_entities.add(e.entity_id)
                    await sync_context.progress.increment("skipped", 1)

        await asyncio.gather(*[_one(e) for e in parents])
        return hashes, failed_entities

    async def _persist_batch(
        self,
        *,
        partitions: Dict[str, List[BaseEntity]],
        existing_map: Dict[str, models.Entity],
        parent_hashes: Dict[str, str],
        children_by_parent: Dict[str, List[BaseEntity]],
        sync_context: SyncContext,
    ) -> Dict[str, List[BaseEntity]]:
        """Orchestrate persisting batch changes to DB and destinations."""
        inserts, updates, deletes = (
            partitions["inserts"],
            partitions["updates"],
            partitions["deletes"],
        )
        async with get_db_context() as db:
            await self._persist_db_inserts(
                db, inserts, parent_hashes, children_by_parent, sync_context
            )
            await self._persist_db_updates(
                db, updates, parent_hashes, existing_map, children_by_parent, sync_context
            )

        await self._update_destinations(inserts, updates, deletes, children_by_parent, sync_context)
        await self._persist_db_deletes(deletes, sync_context)
        await self._update_progress_and_guard_rails(partitions, sync_context)

        results_by_parent: Dict[str, List[BaseEntity]] = {
            p.entity_id: children for p, children in children_by_parent.items()
        }
        for p_list in partitions.values():
            for p in p_list:
                results_by_parent.setdefault(p.entity_id, [])
        return results_by_parent

    async def _persist_db_inserts(
        self, db, inserts, parent_hashes, children_by_parent, sync_context
    ):
        """Handle batch insertion of parent entities into the database."""
        if not inserts:
            return
        create_objs = [
            schemas.EntityCreate(
                sync_job_id=sync_context.sync_job.id,
                sync_id=sync_context.sync.id,
                entity_id=p.entity_id,
                hash=parent_hashes[p.entity_id],
            )
            for p in inserts
            if p.entity_id in parent_hashes
        ]
        if create_objs:
            created_rows = await crud.entity.bulk_create(
                db=db, objs=create_objs, ctx=sync_context.ctx
            )
            created_map = {row.entity_id: row.id for row in created_rows}
            for p in inserts:
                if (db_id := created_map.get(p.entity_id)) and p.airweave_system_metadata:
                    p.airweave_system_metadata.db_entity_id = db_id
                    for c in children_by_parent.get(p.entity_id, []):
                        if c.airweave_system_metadata:
                            c.airweave_system_metadata.db_entity_id = db_id

    async def _persist_db_updates(
        self, db, updates, parent_hashes, existing_map, children_by_parent, sync_context
    ):
        """Handle batch updates of parent entity hashes in the database."""
        if not updates:
            return
        update_pairs = [
            (existing_map[p.entity_id].id, parent_hashes[p.entity_id])
            for p in updates
            if p.entity_id in existing_map and p.entity_id in parent_hashes
        ]
        if update_pairs:
            await crud.entity.bulk_update_hash(db=db, rows=update_pairs)
        for p in updates:
            if (db_row := existing_map.get(p.entity_id)) and p.airweave_system_metadata:
                p.airweave_system_metadata.db_entity_id = db_row.id
                for c in children_by_parent.get(p.entity_id, []):
                    if c.airweave_system_metadata:
                        c.airweave_system_metadata.db_entity_id = db_row.id

    async def _update_destinations(
        self, inserts, updates, deletes, children_by_parent, sync_context
    ):
        """Handle deletions and insertions for destinations."""
        parent_ids_to_clear = [p.entity_id for p in updates] + [p.entity_id for p in deletes]
        if parent_ids_to_clear:
            for dest in sync_context.destinations:
                await dest.bulk_delete_by_parent_ids(parent_ids_to_clear, sync_context.sync.id)

        to_insert = [
            child for p in inserts + updates for child in children_by_parent.get(p.entity_id, [])
        ]
        if to_insert:
            for dest in sync_context.destinations:
                await dest.bulk_insert(to_insert)

    async def _persist_db_deletes(self, deletes, sync_context):
        """Handle batch deletion of parent entities from the database."""
        if not deletes:
            return
        async with get_db_context() as db:
            del_map = await crud.entity.get_by_entity_and_sync_id_many(
                db=db,
                sync_id=sync_context.sync.id,
                entity_ids=[p.entity_id for p in deletes],
            )
            db_ids = [row.id for row in del_map.values()]
            if db_ids:
                await crud.entity.bulk_remove(db=db, ids=db_ids, ctx=sync_context.ctx)

    async def _update_progress_and_guard_rails(self, partitions, sync_context):
        """Update progress counters and guard rails based on actions taken."""
        actions = {"inserted": "inserts", "updated": "updates", "deleted": "deletes"}
        for key, partition_key in actions.items():
            count = len(partitions[partition_key])
            if count > 0:
                await sync_context.progress.increment(key, count)

        # Guard rail increments for actual work (insert/update parents)
        work_count = len(partitions["inserts"]) + len(partitions["updates"])
        for _ in range(work_count):
            await sync_context.guard_rail.increment(ActionType.ENTITIES)
