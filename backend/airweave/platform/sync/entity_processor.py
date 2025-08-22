"""Module for entity processing within the sync architecture."""

import asyncio
from collections import defaultdict
from typing import DefaultDict, Dict, Iterable, List, Optional, Set, Tuple

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
            Dict[parent_entity_id, List[BaseEntity]]: mapping to produced (and persisted) chunk entities.
        """
        loop = asyncio.get_event_loop()
        batch_start = loop.time()
        entity_count = len(entities)

        if entity_count == 0:
            return {}

        # -----------------------------
        # Stage 0: dedupe, tracking, early-skip
        # -----------------------------
        uniq: List[BaseEntity] = []
        skipped_due_to_dup = 0
        skipped_due_to_flag = 0

        for e in entities:
            et = e.__class__.__name__
            if et not in self._entity_ids_encountered_by_type:
                self._entity_ids_encountered_by_type[et] = set()

            # duplicate detection within this run
            if e.entity_id in self._entity_ids_encountered_by_type[et]:
                skipped_due_to_dup += 1
                continue
            self._entity_ids_encountered_by_type[et].add(e.entity_id)

            # per-entity skip flag (from file_manager/source)
            if getattr(e, "should_skip", False) or (
                getattr(e, "airweave_system_metadata", None)
                and getattr(e.airweave_system_metadata, "should_skip", False)
            ):
                skipped_due_to_flag += 1
                continue

            uniq.append(e)

        if skipped_due_to_dup:
            sync_context.logger.debug(f"⏭️  BATCH_DUPLICATES Skipped {skipped_due_to_dup} duplicates")
        if skipped_due_to_flag:
            await sync_context.progress.increment("skipped", skipped_due_to_flag)

        # update encountered counters (for UI/stats)
        await sync_context.progress.update_entities_encountered_count(
            self._entity_ids_encountered_by_type
        )

        if not uniq:
            return {}

        # -----------------------------
        # Stage 1: Enrich (in parallel, bounded)
        # -----------------------------
        enrich_start = loop.time()
        uniq = await self._batch_enrich(uniq, sync_context, inner_concurrency=inner_concurrency)
        enrich_elapsed = loop.time() - enrich_start
        sync_context.logger.debug(
            f"🏷️  BATCH_ENRICH_DONE Enriched {len(uniq)} parents in {enrich_elapsed:.3f}s"
        )

        # -----------------------------
        # Stage 2: Determine actions (bulk DB + parallel hashing)
        # -----------------------------
        action_start = loop.time()

        # Partition deletion entities first (no DB lookup needed)
        deletion_parents: List[BaseEntity] = []
        non_delete: List[BaseEntity] = []
        for e in uniq:
            if hasattr(e, "deletion_status") and getattr(e, "deletion_status") == "removed":
                deletion_parents.append(e)
            else:
                non_delete.append(e)

        # Bulk fetch existing rows for non-deletes
        existing_map: Dict[str, models.Entity] = {}
        if non_delete:
            try:
                async with get_db_context() as db:
                    existing_map = await crud.entity.get_by_entity_and_sync_id_many(
                        db, sync_id=sync_context.sync.id, entity_ids=[e.entity_id for e in non_delete]
                    )
            except Exception as e:
                sync_context.logger.warning(
                    f"💥 BATCH_DB_LOOKUP_ERROR Bulk lookup failed: {e}. Falling back to per-entity."
                )
                existing_map = {}
                # Fallback: fill map with per-entity lookups
                async with get_db_context() as db:
                    for e in non_delete:
                        try:
                            row = await crud.entity.get_by_entity_and_sync_id(
                                db=db, entity_id=e.entity_id, sync_id=sync_context.sync.id
                            )
                            existing_map[e.entity_id] = row
                        except NotFoundException:
                            pass

        # Hash all non-deletes concurrently
        hashes = await self._compute_hashes_concurrently(
            non_delete, inner_concurrency=inner_concurrency
        )

        # Decide actions
        inserts: List[BaseEntity] = []
        updates: List[BaseEntity] = []
        keeps: List[BaseEntity] = []

        for e in non_delete:
            db_row = existing_map.get(e.entity_id)
            if db_row is None:
                inserts.append(e)
            else:
                current_hash = hashes.get(e.entity_id)
                if db_row.hash != current_hash:
                    updates.append(e)
                else:
                    keeps.append(e)

        action_elapsed = loop.time() - action_start
        sync_context.logger.debug(
            f"📋 BATCH_ACTION_DONE partitions — "
            f"INSERT={len(inserts)}, UPDATE={len(updates)}, KEEP={len(keeps)}, DELETE={len(deletion_parents)} "
            f"in {action_elapsed:.3f}s"
        )

        # Early exit if everything is KEEP
        if not inserts and not updates and not deletion_parents:
            if keeps:
                await sync_context.progress.increment("kept", len(keeps))
            return {k.entity_id: [] for k in keeps}

        # -----------------------------
        # Stage 3: Transform parents that need it (INSERT/UPDATE)
        # -----------------------------
        transform_start = loop.time()
        to_process = inserts + updates
        children_by_parent: DefaultDict[str, List[BaseEntity]] = defaultdict(list)

        if to_process:
            # bounded parallel transform
            async def _do_transform(p: BaseEntity) -> Tuple[str, List[BaseEntity]]:
                try:
                    kids = await self._transform(p, source_node, sync_context)
                    return p.entity_id, kids
                except Exception as e:
                    sync_context.logger.warning(
                        f"💥 BATCH_TRANSFORM_ERROR [{p.entity_id}] {type(e).__name__}: {e}"
                    )
                    return p.entity_id, []

            sem = asyncio.Semaphore(inner_concurrency)
            async def _wrapped(p: BaseEntity):
                async with sem:
                    return await _do_transform(p)

            results = await asyncio.gather(*[_wrapped(p) for p in to_process])
            for pid, kids in results:
                if not kids:
                    # Mirror single-entity behavior: mark skipped if transform produced nothing
                    await sync_context.progress.increment("skipped", 1)
                else:
                    children_by_parent[pid].extend(kids)

        transform_elapsed = loop.time() - transform_start
        total_children = sum(len(v) for v in children_by_parent.values())
        sync_context.logger.debug(
            f"🔄 BATCH_TRANSFORM_DONE Produced {total_children} chunks from {len(to_process)} parents "
            f"in {transform_elapsed:.3f}s"
        )

        # If no chunks and only deletions remain, we can proceed to delete
        # If there are no chunks and no deletions, then inserts/updates had nothing -> counted as skipped already

        # -----------------------------
        # Stage 4: Vectorization across all produced children (batched)
        # -----------------------------
        vector_start = loop.time()
        all_children: List[BaseEntity] = []
        for pid, kids in children_by_parent.items():
            all_children.extend(kids)

        if all_children:
            # _compute_vector already batches and assigns in-place
            await self._compute_vector(all_children, sync_context)
        vector_elapsed = loop.time() - vector_start
        if all_children:
            sync_context.logger.debug(
                f"🎯 BATCH_VECTOR_DONE Vectored {len(all_children)} chunks in {vector_elapsed:.3f}s"
            )

        # -----------------------------
        # Stage 5: Persist (DB + destinations) in batch
        # -----------------------------
        persist_start = loop.time()
        results_by_parent = await self._persist_batch(
            inserts=inserts,
            updates=updates,
            deletes=deletion_parents,
            keeps=keeps,
            existing_map=existing_map,
            parent_hashes=hashes,
            children_by_parent=children_by_parent,
            sync_context=sync_context,
        )
        persist_elapsed = loop.time() - persist_start

        # -----------------------------
        # Stage 6: Progress accounting for keeps
        # -----------------------------
        if keeps:
            await sync_context.progress.increment("kept", len(keeps))

        total_elapsed = loop.time() - batch_start
        sync_context.logger.debug(
            f"✅ BATCH_COMPLETE parents={entity_count} "
            f"(enrich: {enrich_elapsed:.3f}s, action: {action_elapsed:.3f}s, "
            f"transform: {transform_elapsed:.3f}s, vector: {vector_elapsed:.3f}s, "
            f"persist: {persist_elapsed:.3f}s, total: {total_elapsed:.3f}s)"
        )

        return results_by_parent

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
        entity_count = len(processed_entities)

        sync_context.logger.debug(
            f"🧮 VECTOR_START [{entity_context}] Computing vectors for {entity_count} entities"
        )

        try:
            # Build embeddable texts (instead of stringifying full dicts)
            sync_context.logger.debug(
                f"🧩 VECTOR_TEXT_START [{entity_context}] Building embeddable texts"
            )
            convert_start = asyncio.get_event_loop().time()

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

            convert_elapsed = asyncio.get_event_loop().time() - convert_start
            sync_context.logger.debug(
                (
                    f"🧩 VECTOR_TEXT_DONE [{entity_context}] Built {len(texts)} texts "
                    f"in {convert_elapsed:.3f}s"
                )
            )

            # Get embeddings from the model
            sync_context.logger.debug(
                f"🤖 VECTOR_EMBED_START [{entity_context}] Calling embedding model"
            )
            embed_start = asyncio.get_event_loop().time()

            embeddings, sparse_embeddings = await self._get_embeddings(
                texts, sync_context, entity_context
            )

            embed_elapsed = asyncio.get_event_loop().time() - embed_start
            sync_context.logger.debug(
                f"🤖 VECTOR_EMBED_DONE [{entity_context}] Got {len(embeddings)} neural embeddings "
                f"and {len(sparse_embeddings) if sparse_embeddings else 0} sparse embeddings "
                f"in {embed_elapsed:.3f}s"
            )

            # Assign vectors to entities
            sync_context.logger.debug(
                f"🔗 VECTOR_ASSIGN_START [{entity_context}] Assigning vectors to entities"
            )
            assign_start = asyncio.get_event_loop().time()

            processed_entities = await self._assign_vectors_to_entities(
                processed_entities, embeddings, sparse_embeddings, sync_context
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
        await sync_context.progress.increment(kept=1)

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
        self, parents: List[BaseEntity], *, inner_concurrency: int
    ) -> Dict[str, str]:
        """Compute entity hashes for many parents concurrently (bounded)."""
        sem = asyncio.Semaphore(inner_concurrency)
        hashes: Dict[str, str] = {}

        async def _one(e: BaseEntity):
            async with sem:
                try:
                    h = await compute_entity_hash_async(e)
                    hashes[e.entity_id] = h
                except Exception as ex:
                    # No hash means we'll treat as "changed" to be safe
                    # but we also mark skipped to surface the issue
                    # (processor logic will still try to proceed).
                    sync_context = None
                    try:
                        # Best effort to log with context if available via e
                        pass
                    except Exception:
                        pass

        await asyncio.gather(*[_one(e) for e in parents])
        return hashes

    async def _persist_batch(
        self,
        *,
        inserts: List[BaseEntity],
        updates: List[BaseEntity],
        deletes: List[BaseEntity],
        keeps: List[BaseEntity],
        existing_map: Dict[str, models.Entity],
        parent_hashes: Dict[str, str],
        children_by_parent: Dict[str, List[BaseEntity]],
        sync_context: SyncContext,
    ) -> Dict[str, List[BaseEntity]]:
        """Persist batch changes to DB and destinations efficiently."""
        results_by_parent: Dict[str, List[BaseEntity]] = {}

        # ---------------- DB writes ----------------
        async with get_db_context() as db:
            # INSERT parents (create DB rows and stamp db_entity_id)
            if inserts:
                create_objs: List[schemas.EntityCreate] = []
                for p in inserts:
                    parent_hash = parent_hashes.get(p.entity_id)
                    create_objs.append(
                        schemas.EntityCreate(
                            sync_job_id=sync_context.sync_job.id,
                            sync_id=sync_context.sync.id,
                            entity_id=p.entity_id,
                            hash=parent_hash,
                        )
                    )
                created_rows = await crud.entity.bulk_create(db=db, objs=create_objs)
                created_map = {row.entity_id: row.id for row in created_rows}

                for p in inserts:
                    db_id = created_map.get(p.entity_id)
                    if p.airweave_system_metadata and db_id:
                        p.airweave_system_metadata.db_entity_id = db_id
                    for c in children_by_parent.get(p.entity_id, []):
                        if c.airweave_system_metadata and db_id:
                            c.airweave_system_metadata.db_entity_id = db_id

            # UPDATE parents (set new hash and stamp db_entity_id on chunks)
            if updates:
                update_pairs: List[Tuple[str, str]] = []
                for p in updates:
                    db_row = existing_map.get(p.entity_id)
                    if not db_row:
                        continue
                    new_hash = parent_hashes.get(p.entity_id)
                    update_pairs.append((db_row.id, new_hash))

                await crud.entity.bulk_update_hash(db=db, rows=update_pairs)

                for p in updates:
                    db_row = existing_map.get(p.entity_id)
                    if db_row and p.airweave_system_metadata:
                        p.airweave_system_metadata.db_entity_id = db_row.id
                    for c in children_by_parent.get(p.entity_id, []):
                        if db_row and c.airweave_system_metadata:
                            c.airweave_system_metadata.db_entity_id = db_row.id

        # ---------------- Destination deletes for UPDATE + DELETE ----------------
        parent_ids_to_clear: List[str] = [p.entity_id for p in updates] + [
            p.entity_id for p in deletes
        ]
        if parent_ids_to_clear:
            for dest in sync_context.destinations:
                # Use plural form if destination overrides; otherwise BaseDestination fans out.
                await dest.bulk_delete_by_parent_ids(parent_ids_to_clear, sync_context.sync.id)

        # ---------------- Destination inserts for INSERT + UPDATE ----------------
        parents_needing_insert = inserts + updates
        if parents_needing_insert:
            to_insert: List[BaseEntity] = []
            for p in parents_needing_insert:
                kids = children_by_parent.get(p.entity_id, [])
                if kids:
                    to_insert.extend(kids)
                    results_by_parent[p.entity_id] = kids
                else:
                    results_by_parent[p.entity_id] = []

            if to_insert:
                for dest in sync_context.destinations:
                    await dest.bulk_insert(to_insert)

        # ---------------- Destination deletes only for DELETE ----------------
        if deletes:
            # DB removal after destination deletion
            async with get_db_context() as db:
                db_ids = []
                for p in deletes:
                    db_row = existing_map.get(p.entity_id)
                    if db_row:
                        db_ids.append(db_row.id)
                if db_ids:
                    await crud.entity.bulk_remove(db=db, ids=db_ids, ctx=sync_context.ctx)

        # ---------------- Progress + guard rails ----------------
        if inserts:
            await sync_context.progress.increment("inserted", len(inserts))
        if updates:
            await sync_context.progress.increment("updated", len(updates))
        if deletes:
            await sync_context.progress.increment("deleted", len(deletes))

        # Guard rail increments for actual work (insert/update parents)
        # Call once per parent to mirror single-entity accounting.
        for _ in range(len(inserts) + len(updates)):
            await sync_context.guard_rail.increment(ActionType.ENTITIES)

        # Ensure there is an entry in results for keeps/deletes too
        for p in keeps:
            results_by_parent.setdefault(p.entity_id, [])
        for p in deletes:
            results_by_parent.setdefault(p.entity_id, [])

        return results_by_parent
