"""Module for entity processing within the sync architecture (TRUE batching + legacy path)."""

import asyncio
from collections import defaultdict
from typing import DefaultDict, Dict, List, Optional, Set, Tuple

from fastembed import SparseTextEmbedding
from sqlalchemy.exc import DBAPIError

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
      - process(...)       -> single-entity pipeline (legacy path)
      - process_batch(...) -> micro-batched pipeline with inner concurrency (TRUE batching)
    """

    def __init__(self):
        """Initialize the entity processor with empty tracking dictionary."""
        self._entity_ids_encountered_by_type: Dict[str, Set[str]] = {}

    @staticmethod
    async def _retry_on_deadlock(coro_func, *args, max_retries: int = 3, **kwargs):
        """Retry a coroutine function on deadlock errors with exponential backoff.

        Handles both DeadlockDetectedError (concurrent transactions) and
        CardinalityViolationError (duplicate entities in batch). Uses exponential
        backoff to give conflicting transactions time to complete.

        Args:
            coro_func: The coroutine function to retry
            *args: Positional arguments for the function
            max_retries: Maximum number of retry attempts (default: 3)
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the coroutine function

        Raises:
            DBAPIError: If all retry attempts are exhausted
            asyncio.CancelledError: Immediately on cancellation (no retry)
        """
        for attempt in range(max_retries + 1):
            try:
                return await coro_func(*args, **kwargs)
            except DBAPIError as e:
                # Check if it's a retryable database error
                error_msg = str(e).lower()
                is_deadlock = "deadlock detected" in error_msg
                is_cardinality = "cannot affect row a second time" in error_msg

                if (is_deadlock or is_cardinality) and attempt < max_retries:
                    # Exponential backoff: 0.1s, 0.2s, 0.4s
                    wait_time = 0.1 * (2**attempt)

                    # Log retry attempt if logger is available
                    if "sync_context" in kwargs and hasattr(kwargs["sync_context"], "logger"):
                        logger = kwargs["sync_context"].logger
                        error_type = "Deadlock" if is_deadlock else "Cardinality violation"
                        logger.warning(
                            f"🔄 {error_type} detected, retrying in {wait_time}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )

                    await asyncio.sleep(wait_time)
                    continue

                # Not a retryable error or out of retries, re-raise
                raise
            except asyncio.CancelledError:
                # Don't retry on cancellation - propagate immediately
                raise

        # Should never reach here, but just in case
        raise RuntimeError("Retry logic failed unexpectedly")

    def initialize_tracking(self, sync_context: SyncContext) -> None:
        """Initialize entity tracking with entity types from the DAG."""
        self._entity_ids_encountered_by_type.clear()
        entity_nodes = [
            node for node in sync_context.dag.nodes if node.type == schemas.dag.NodeType.entity
        ]
        for node in entity_nodes:
            if node.name.endswith("Entity"):
                self._entity_ids_encountered_by_type[node.name] = set()

    # ------------------------------------------------------------------------------------
    # Public API — single entity (legacy path)
    # ------------------------------------------------------------------------------------
    async def process(  # noqa: C901
        self,
        entity: BaseEntity,
        source_node: schemas.DagNode,
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        """Process an entity through the complete pipeline (legacy per-entity)."""
        try:
            entity_type_name = entity.__class__.__name__
            if entity_type_name not in self._entity_ids_encountered_by_type:
                self._entity_ids_encountered_by_type[entity_type_name] = set()

            if entity.entity_id in self._entity_ids_encountered_by_type[entity_type_name]:
                await sync_context.progress.increment("skipped", 1)
                return []

            self._entity_ids_encountered_by_type[entity_type_name].add(entity.entity_id)
            await sync_context.progress.update_entities_encountered_count(
                self._entity_ids_encountered_by_type
            )

            # Entities always have airweave_system_metadata with should_skip defaulting to False
            if entity.airweave_system_metadata.should_skip:
                await sync_context.progress.increment("skipped", 1)
                return []

            enriched_entity = await self._enrich(entity, sync_context)
            db_entity, action = await self._determine_action(enriched_entity, sync_context)

            if action == DestinationAction.KEEP:
                await sync_context.progress.increment("kept", 1)
                return []

            if action == DestinationAction.DELETE:
                await self._handle_delete(enriched_entity, sync_context)
                return []

            processed_entities = await self._transform(enriched_entity, source_node, sync_context)
            if len(processed_entities) == 0:
                await sync_context.progress.increment("skipped", 1)
                return []

            processed_entities_with_vector = await self._compute_vector(
                processed_entities, sync_context
            )

            if action == DestinationAction.INSERT:
                await self._handle_insert(
                    enriched_entity, processed_entities_with_vector, sync_context
                )
            elif action == DestinationAction.UPDATE:
                await self._handle_update(
                    enriched_entity, processed_entities_with_vector, db_entity, sync_context
                )

            return processed_entities

        except asyncio.CancelledError:
            # Ensure cooperative cancellation propagates immediately
            raise
        except Exception:
            await sync_context.progress.increment("skipped", 1)
            return []

    # ------------------------------------------------------------------------------------
    # Public API — batch processing entrypoint (TRUE batching)
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
        """Process a batch of parent entities with batching & limited inner concurrency."""
        if not entities:
            return {}

        unique_entities = await self._filter_and_track_entities(entities, sync_context)
        if not unique_entities:
            return {e.entity_id: [] for e in entities}

        enriched = await self._batch_enrich(
            unique_entities, sync_context, inner_concurrency=inner_concurrency
        )

        partitions = await self._partition_by_action(
            enriched, sync_context, inner_concurrency=inner_concurrency
        )

        if not any(partitions[k] for k in ("inserts", "updates", "deletes")):
            if partitions["keeps"]:
                await sync_context.progress.increment("kept", len(partitions["keeps"]))
            return {k.entity_id: [] for k in partitions["keeps"]}

        to_transform = partitions["inserts"] + partitions["updates"]
        children_by_parent = await self._transform_parents(
            to_transform, source_node, sync_context, inner_concurrency
        )

        successful_pids = set(children_by_parent.keys())
        partitions["inserts"] = [e for e in partitions["inserts"] if e.entity_id in successful_pids]
        partitions["updates"] = [e for e in partitions["updates"] if e.entity_id in successful_pids]

        all_children = [child for children in children_by_parent.values() for child in children]
        if all_children:
            await self._compute_vector(all_children, sync_context)

        results = await self._persist_batch(
            partitions=partitions,
            existing_map=partitions.pop("existing_map"),
            parent_hashes=partitions.pop("parent_hashes"),
            children_by_parent=children_by_parent,
            sync_context=sync_context,
        )

        if partitions["keeps"]:
            await sync_context.progress.increment("kept", len(partitions["keeps"]))

        return results

    # ------------------------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------------------------
    async def _filter_and_track_entities(
        self, entities: List[BaseEntity], sync_context: SyncContext
    ) -> List[BaseEntity]:
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

            # Entities always have airweave_system_metadata with should_skip defaulting to False
            if e.airweave_system_metadata.should_skip:
                skipped_due_to_flag += 1
                continue

            unique_entities.append(e)

        if skipped_due_to_dup:
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
        deletes = [e for e in entities if getattr(e, "deletion_status", "") == "removed"]
        non_deletes = [e for e in entities if getattr(e, "deletion_status", "") != "removed"]

        existing_map: Dict[str, models.Entity] = {}
        if non_deletes:
            try:
                async with get_db_context() as db:
                    existing_map = await crud.entity.bulk_get_by_entity_and_sync(
                        db,
                        sync_id=sync_context.sync.id,
                        entity_ids=[e.entity_id for e in non_deletes],
                    )
            except asyncio.CancelledError:
                # Propagate cancellation during DB prefetch
                raise
            except Exception as e:
                sync_context.logger.warning(f"💥 BATCH_DB_LOOKUP_ERROR: {e}")

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

        return partitions

    async def _transform_parents(
        self,
        parents: List[BaseEntity],
        source_node: schemas.DagNode,
        sync_context: SyncContext,
        inner_concurrency: int,
    ) -> DefaultDict[str, List[BaseEntity]]:
        children_by_parent: DefaultDict[str, List[BaseEntity]] = defaultdict(list)
        if not parents:
            return children_by_parent

        async def _do_transform(p: BaseEntity):
            try:
                return p.entity_id, await self._transform(p, source_node, sync_context)
            except asyncio.CancelledError:
                # Propagate cancellation to caller
                raise
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

        return children_by_parent

    # ------------------------------------------------------------------------------------
    # Existing single-entity helpers
    # ------------------------------------------------------------------------------------
    async def _enrich(self, entity: BaseEntity, sync_context: SyncContext) -> BaseEntity:
        from datetime import datetime, timedelta, timezone

        from airweave.platform.entities._base import AirweaveSystemMetadata

        if hasattr(entity, "needs_materialization") and entity.needs_materialization:
            await entity.materialize()

        if entity.airweave_system_metadata is None:
            entity.airweave_system_metadata = AirweaveSystemMetadata()

        entity.airweave_system_metadata.source_name = sync_context.source._short_name
        entity.airweave_system_metadata.entity_type = entity.__class__.__name__
        entity.airweave_system_metadata.sync_id = sync_context.sync.id
        entity.airweave_system_metadata.sync_job_id = sync_context.sync_job.id
        entity.airweave_system_metadata.sync_metadata = sync_context.sync.sync_metadata

        timestamps = entity.get_harmonized_timestamps()
        updated_at = timestamps.get("updated_at")
        created_at = timestamps.get("created_at")

        if updated_at:
            entity.airweave_system_metadata.airweave_updated_at = updated_at
        elif created_at:
            entity.airweave_system_metadata.airweave_updated_at = created_at
        else:
            entity.airweave_system_metadata.airweave_updated_at = datetime.now(
                timezone.utc
            ) - timedelta(weeks=2)

        return entity

    async def _determine_action(
        self, entity: BaseEntity, sync_context: SyncContext
    ) -> tuple[Optional[models.Entity], DestinationAction]:
        if hasattr(entity, "deletion_status") and entity.deletion_status == "removed":
            return None, DestinationAction.DELETE

        async with get_db_context() as db:
            try:
                db_entity = await crud.entity.get_by_entity_and_sync_id(
                    db=db, entity_id=entity.entity_id, sync_id=sync_context.sync.id
                )
            except NotFoundException:
                db_entity = None

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
        return await sync_context.router.process_entity(
            producer_id=source_node.id,
            entity=entity,
        )

    # ---------------- Single-entity persist handlers (legacy path) ----------------
    async def _handle_keep(self, sync_context: SyncContext) -> None:
        await sync_context.progress.increment("kept", 1)

    async def _handle_insert(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> None:
        if len(processed_entities) == 0:
            await sync_context.progress.increment("skipped", 1)
            return

        parent_hash = await compute_entity_hash_async(parent_entity)

        entity_type = type(parent_entity)
        entity_definition_id = self._resolve_entity_definition_id(parent_entity, sync_context)
        if not entity_definition_id:
            await sync_context.progress.increment("skipped", 1)
            return

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

        if parent_entity.airweave_system_metadata:
            parent_entity.airweave_system_metadata.db_entity_id = new_db_entity.id
        for entity in processed_entities:
            if entity.airweave_system_metadata:
                entity.airweave_system_metadata.db_entity_id = new_db_entity.id

        for destination in sync_context.destinations:
            await destination.bulk_insert(processed_entities)

        await sync_context.progress.increment("inserted", 1)
        await sync_context.guard_rail.increment(ActionType.ENTITIES)

        if sync_context.entity_state_tracker and entity_definition_id:
            await sync_context.entity_state_tracker.update_entity_count(
                entity_definition_id=entity_definition_id,
                action="insert",
                entity_name=entity_type.__name__,
                entity_type=str(entity_type.__name__),
            )

    async def _handle_update(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: models.Entity,
        sync_context: SyncContext,
    ) -> None:
        if len(processed_entities) == 0:
            await sync_context.progress.increment("skipped", 1)
            return

        parent_hash = await compute_entity_hash_async(parent_entity)

        async with get_db_context() as db:
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
                await sync_context.progress.increment("skipped", 1)
                return

        if parent_entity.airweave_system_metadata:
            parent_entity.airweave_system_metadata.db_entity_id = db_entity.id
        for entity in processed_entities:
            if entity.airweave_system_metadata:
                entity.airweave_system_metadata.db_entity_id = db_entity.id

        for destination in sync_context.destinations:
            await destination.bulk_delete_by_parent_id(
                parent_entity.entity_id, sync_context.sync.id
            )
            await destination.bulk_delete(
                [entity.entity_id for entity in processed_entities],
                sync_context.sync.id,
            )
        for destination in sync_context.destinations:
            await destination.bulk_insert(processed_entities)

        await sync_context.progress.increment("updated", 1)
        await sync_context.guard_rail.increment(ActionType.ENTITIES)

        if sync_context.entity_state_tracker and hasattr(db_entity, "entity_definition_id"):
            await sync_context.entity_state_tracker.update_entity_count(
                entity_definition_id=db_entity.entity_definition_id,
                action="update",
            )

    async def _handle_delete(
        self,
        parent_entity: BaseEntity,
        sync_context: SyncContext,
    ) -> None:
        for destination in sync_context.destinations:
            await destination.bulk_delete_by_parent_id(
                parent_entity.entity_id, sync_context.sync.id
            )
            # Safety net: also delete by the parent entity's own entity_id in case
            # points were inserted without a parent_entity_id payload
            try:
                await destination.bulk_delete([parent_entity.entity_id], sync_context.sync.id)
            except Exception as ex:
                # Don't fail deletion if this secondary path is unsupported by a destination
                msg = f"DELETE_FALLBACK_SKIP bulk_delete by entity_id not supported or failed: {ex}"
                sync_context.logger.debug(msg)

        db_entity = None
        async with get_db_context() as db:
            try:
                db_entity = await crud.entity.get_by_entity_and_sync_id(
                    db=db, entity_id=parent_entity.entity_id, sync_id=sync_context.sync.id
                )
                if db_entity:
                    await crud.entity.remove(db=db, id=db_entity.id, ctx=sync_context.ctx)
            except NotFoundException:
                pass

        await sync_context.progress.increment("deleted", 1)

        if (
            sync_context.entity_state_tracker
            and db_entity
            and hasattr(db_entity, "entity_definition_id")
        ):
            await sync_context.entity_state_tracker.update_entity_count(
                entity_definition_id=db_entity.entity_definition_id,
                action="delete",
            )

    async def cleanup_orphaned_entities(self, sync_context: SyncContext) -> None:
        """Remove entities from the database that were not encountered during sync."""
        try:
            stored_entities = await self._get_stored_entities(sync_context)
            if not stored_entities:
                return

            orphaned_entities = self._find_orphaned_entities(stored_entities)
            if not orphaned_entities:
                return

            await self._remove_orphaned_entities(orphaned_entities, sync_context)

        except asyncio.CancelledError:
            # Respect cancellation during cleanup
            raise
        except Exception as e:
            sync_context.logger.error(f"💥 Cleanup failed: {str(e)}", exc_info=True)
            raise e

    async def _get_stored_entities(self, sync_context: SyncContext):
        """Get all stored entities for the current sync."""
        async with get_db_context() as db:
            return await crud.entity.get_by_sync_id(db=db, sync_id=sync_context.sync.id)

    def _find_orphaned_entities(self, stored_entities):
        """Find entities that were not encountered during sync."""
        orphaned_entities = []
        for stored_entity in stored_entities:
            entity_was_encountered = any(
                stored_entity.entity_id in entity_set
                for entity_set in self._entity_ids_encountered_by_type.values()
            )
            if not entity_was_encountered:
                orphaned_entities.append(stored_entity)
        return orphaned_entities

    async def _remove_orphaned_entities(self, orphaned_entities, sync_context: SyncContext):
        """Remove orphaned entities from destinations and database."""
        orphaned_entity_ids = [entity.entity_id for entity in orphaned_entities]
        orphaned_db_ids = [entity.id for entity in orphaned_entities]

        # Remove from destinations
        for destination in sync_context.destinations:
            await destination.bulk_delete(orphaned_entity_ids, sync_context.sync.id)

        # Remove from database
        async with get_db_context() as db:
            await crud.entity.bulk_remove(db=db, ids=orphaned_db_ids, ctx=sync_context.ctx)

        await sync_context.progress.increment("deleted", len(orphaned_entities))
        await self._update_entity_state_tracker_for_cleanup(orphaned_entities, sync_context)

    async def _update_entity_state_tracker_for_cleanup(
        self, orphaned_entities, sync_context: SyncContext
    ):
        """Update entity state tracker for cleaned up entities."""
        if not getattr(sync_context, "entity_state_tracker", None):
            return

        counts_by_def: Dict = defaultdict(int)
        for row in orphaned_entities:
            if hasattr(row, "entity_definition_id") and row.entity_definition_id:
                counts_by_def[row.entity_definition_id] += 1

        for def_id, count in counts_by_def.items():
            await sync_context.entity_state_tracker.update_entity_count(
                entity_definition_id=def_id, action="delete", delta=count
            )

    # ------------------------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------------------------
    async def _batch_enrich(
        self, parents: List[BaseEntity], sync_context: SyncContext, *, inner_concurrency: int
    ) -> List[BaseEntity]:
        sem = asyncio.Semaphore(inner_concurrency)

        async def _one(e: BaseEntity) -> BaseEntity:
            async with sem:
                try:
                    return await self._enrich(e, sync_context)
                except asyncio.CancelledError:
                    # Allow cancellation to bubble up
                    raise
                except Exception as ex:
                    sync_context.logger.warning(
                        f"💥 ENRICH_ERROR [{e.entity_id}] {type(ex).__name__}: {ex}"
                    )
                    await sync_context.progress.increment("skipped", 1)
                    return e

        enriched = await asyncio.gather(*[_one(e) for e in parents])
        return list(enriched)

    async def _compute_hashes_concurrently(
        self, parents: List[BaseEntity], *, inner_concurrency: int, sync_context: SyncContext
    ) -> Tuple[Dict[str, str], Set[str]]:
        sem = asyncio.Semaphore(inner_concurrency)
        hashes: Dict[str, str] = {}
        failed_entities: Set[str] = set()

        async def _one(e: BaseEntity):
            async with sem:
                try:
                    h = await compute_entity_hash_async(e)
                    hashes[e.entity_id] = h
                except asyncio.CancelledError:
                    # Allow cooperative cancellation
                    raise
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
        """Persist a batch of entities with automatic retry on database conflicts."""
        return await self._retry_on_deadlock(
            self._persist_batch_impl,
            partitions=partitions,
            existing_map=existing_map,
            parent_hashes=parent_hashes,
            children_by_parent=children_by_parent,
            sync_context=sync_context,
        )

    async def _persist_batch_impl(
        self,
        *,
        partitions: Dict[str, List[BaseEntity]],
        existing_map: Dict[str, models.Entity],
        parent_hashes: Dict[str, str],
        children_by_parent: Dict[str, List[BaseEntity]],
        sync_context: SyncContext,
    ) -> Dict[str, List[BaseEntity]]:
        """Internal implementation of batch persistence with retry support."""
        inserts, updates, deletes = (
            partitions["inserts"],
            partitions["updates"],
            partitions["deletes"],
        )

        # Persist to database in a transaction
        async with get_db_context() as db:
            async with db.begin():
                await self._batch_persist_db_inserts(
                    db, inserts, parent_hashes, children_by_parent, sync_context
                )
                await self._batch_persist_db_updates(
                    db, updates, parent_hashes, existing_map, children_by_parent, sync_context
                )
                await self._batch_persist_db_deletes(db, deletes, sync_context)

        await self._batch_update_destinations(
            inserts, updates, deletes, children_by_parent, sync_context
        )
        await self._update_progress_and_guard_rails(partitions, sync_context)

        results_by_parent: dict[str, List[BaseEntity]] = dict(children_by_parent)
        for p_list in (
            partitions["inserts"],
            partitions["updates"],
            partitions["keeps"],
            partitions["deletes"],
        ):
            for p in p_list:
                results_by_parent.setdefault(p.entity_id, [])

        return results_by_parent

    async def _batch_persist_db_inserts(
        self,
        db,
        inserts: List[BaseEntity],
        parent_hashes: Dict[str, str],
        children_by_parent: Dict[str, List[BaseEntity]],
        sync_context: SyncContext,
    ) -> None:
        if not inserts:
            return

        create_objs, valid_parent_ids, skipped_count = await self._prepare_insert_objects(
            inserts, parent_hashes, children_by_parent, sync_context
        )

        if skipped_count:
            await sync_context.progress.increment("skipped", skipped_count)

        if valid_parent_ids:
            inserts[:] = [p for p in inserts if p.entity_id in valid_parent_ids]
        else:
            inserts.clear()

        if create_objs:
            # Deduplicate both DB payload AND the inserts list to keep them in sync
            deduped_objs, kept_parent_ids = await self._execute_bulk_insert(
                db, create_objs, inserts, children_by_parent, sync_context
            )

            # Remove duplicate parents from inserts to match deduplicated DB payload
            # This ensures downstream consumers (destinations, metrics) see consistent data
            inserts[:] = [p for p in inserts if p.entity_id in kept_parent_ids]

            await self._update_state_tracker_for_inserts(inserts, sync_context)

    async def _prepare_insert_objects(
        self,
        inserts: List[BaseEntity],
        parent_hashes: Dict[str, str],
        children_by_parent: Dict[str, List[BaseEntity]],
        sync_context: SyncContext,
    ) -> Tuple[List[schemas.EntityCreate], Set[str], int]:
        create_objs: List[schemas.EntityCreate] = []
        valid_parent_ids: Set[str] = set()
        skipped_count = 0

        for p in inserts:
            def_id = self._resolve_entity_definition_id(p, sync_context)
            parent_hash = parent_hashes.get(p.entity_id)

            if not def_id or parent_hash is None:
                skipped_count += 1
                children_by_parent.pop(p.entity_id, None)
                continue

            create_objs.append(
                schemas.EntityCreate(
                    sync_job_id=sync_context.sync_job.id,
                    sync_id=sync_context.sync.id,
                    entity_id=p.entity_id,
                    entity_definition_id=def_id,
                    hash=parent_hash,
                )
            )
            valid_parent_ids.add(p.entity_id)

        return create_objs, valid_parent_ids, skipped_count

    def _resolve_entity_definition_id(
        self, entity: BaseEntity, sync_context: SyncContext
    ) -> Optional[str]:
        """Resolve entity definition via exact match, then MRO, then polymorphic fallback."""
        et = type(entity)

        # 1) Exact class match
        def_id = sync_context.entity_map.get(et)
        if def_id:
            return def_id

        # 2) Walk MRO to find the nearest mapped ancestor (excluding BaseEntity/object)
        for base in et.__mro__[1:]:
            if base is BaseEntity or base is object:
                break
            def_id = sync_context.entity_map.get(base)
            if def_id:
                return def_id

        # 3) Polymorphic fallback
        if issubclass(et, PolymorphicEntity):
            return RESERVED_TABLE_ENTITY_ID

        return None

    def _deduplicate_entity_creates(
        self,
        create_objs: List[schemas.EntityCreate],
        sync_context: SyncContext,
    ) -> Tuple[List[schemas.EntityCreate], Set[str]]:
        """Deduplicate entities by entity_id, keeping only the last occurrence.

        This prevents CardinalityViolationError when the same entity_id appears
        multiple times in a batch (e.g., shared calendars referenced by multiple parents).

        Args:
            create_objs: List of entity create objects to deduplicate
            sync_context: Sync context for logging

        Returns:
            Tuple of (deduplicated objects, set of kept entity_ids)
        """
        seen_entity_ids: Dict[str, int] = {}
        deduped_objs: List[schemas.EntityCreate] = []

        for obj in create_objs:
            if obj.entity_id in seen_entity_ids:
                # Replace previous occurrence with this one (keep latest)
                deduped_objs[seen_entity_ids[obj.entity_id]] = obj
            else:
                seen_entity_ids[obj.entity_id] = len(deduped_objs)
                deduped_objs.append(obj)

        # Log deduplication activity for observability
        if len(deduped_objs) < len(create_objs):
            removed_count = len(create_objs) - len(deduped_objs)
            sync_context.logger.info(
                f"🔧 Deduplicated {len(create_objs)} entities → {len(deduped_objs)} "
                f"(removed {removed_count} duplicates - shared resources in batch)"
            )

        # Return both deduplicated objects and the set of kept entity_ids
        kept_entity_ids = {obj.entity_id for obj in deduped_objs}
        return deduped_objs, kept_entity_ids

    async def _execute_bulk_insert(
        self,
        db,
        create_objs: List[schemas.EntityCreate],
        inserts: List[BaseEntity],
        children_by_parent: Dict[str, List[BaseEntity]],
        sync_context: SyncContext,
    ) -> Tuple[List[schemas.EntityCreate], Set[str]]:
        """Execute bulk insert with deduplication and metadata assignment.

        Returns:
            Tuple of (deduplicated objects, set of kept entity_ids)
        """
        # Deduplicate entities to prevent CardinalityViolationError
        deduped_objs, kept_entity_ids = self._deduplicate_entity_creates(create_objs, sync_context)

        # Bulk insert to database
        created_rows = await crud.entity.bulk_create(db=db, objs=deduped_objs, ctx=sync_context.ctx)

        # Map database IDs back to entities
        created_map = {row.entity_id: row.id for row in created_rows}

        # Assign database IDs to parent entities (only those that were kept)
        for parent in inserts:
            if parent.entity_id not in kept_entity_ids:
                continue
            db_id = created_map.get(parent.entity_id)
            if db_id and parent.airweave_system_metadata:
                parent.airweave_system_metadata.db_entity_id = db_id

        # Assign database IDs to child entities (only for kept parents)
        for parent in inserts:
            if parent.entity_id not in kept_entity_ids:
                continue
            db_id = created_map.get(parent.entity_id)
            for child in children_by_parent.get(parent.entity_id, []):
                if child.airweave_system_metadata and db_id:
                    child.airweave_system_metadata.db_entity_id = db_id

        return deduped_objs, kept_entity_ids

    async def _batch_persist_db_updates(
        self,
        db,
        updates: List[BaseEntity],
        parent_hashes: Dict[str, str],
        existing_map: Dict[str, models.Entity],
        children_by_parent: Dict[str, List[BaseEntity]],
        sync_context: SyncContext,
    ) -> None:
        if not updates:
            return

        await self._update_entity_hashes(updates, parent_hashes, existing_map, db)
        await self._assign_metadata_ids_for_updates(updates, existing_map, children_by_parent)
        await self._update_state_tracker_for_updates(updates, existing_map, sync_context)

    async def _update_entity_hashes(
        self,
        updates: List[BaseEntity],
        parent_hashes: Dict[str, str],
        existing_map: Dict[str, models.Entity],
        db,
    ) -> None:
        update_pairs = [
            (existing_map[p.entity_id].id, parent_hashes[p.entity_id])
            for p in updates
            if p.entity_id in existing_map and p.entity_id in parent_hashes
        ]
        if update_pairs:
            await crud.entity.bulk_update_hash(db=db, rows=update_pairs)

    async def _assign_metadata_ids_for_updates(
        self,
        updates: List[BaseEntity],
        existing_map: Dict[str, models.Entity],
        children_by_parent: Dict[str, List[BaseEntity]],
    ) -> None:
        for p in updates:
            db_row = existing_map.get(p.entity_id)
            if db_row and p.airweave_system_metadata:
                p.airweave_system_metadata.db_entity_id = db_row.id
        for p in updates:
            db_row = existing_map.get(p.entity_id)
            for c in children_by_parent.get(p.entity_id, []):
                if c.airweave_system_metadata and db_row:
                    c.airweave_system_metadata.db_entity_id = db_row.id

    async def _update_state_tracker_for_updates(
        self,
        updates: List[BaseEntity],
        existing_map: Dict[str, models.Entity],
        sync_context: SyncContext,
    ) -> None:
        if not sync_context.entity_state_tracker or not existing_map:
            return
        counts_by_def: Dict = defaultdict(int)
        for p in updates:
            row = existing_map.get(p.entity_id)
            if row and hasattr(row, "entity_definition_id"):
                counts_by_def[row.entity_definition_id] += 1
        for def_id, count in counts_by_def.items():
            await sync_context.entity_state_tracker.update_entity_count(
                entity_definition_id=def_id, action="update", delta=count
            )

    async def _batch_update_destinations(
        self,
        inserts: List[BaseEntity],
        updates: List[BaseEntity],
        deletes: List[BaseEntity],
        children_by_parent: Dict[str, List[BaseEntity]],
        sync_context: SyncContext,
    ) -> None:
        """Update all destinations. Primary (first) must succeed; others are best-effort."""
        parent_ids_to_clear = [p.entity_id for p in updates] + [p.entity_id for p in deletes]
        to_insert = [
            child for p in inserts + updates for child in children_by_parent.get(p.entity_id, [])
        ]

        for idx, dest in enumerate(sync_context.destinations):
            is_primary = idx == 0
            try:
                if parent_ids_to_clear:
                    if hasattr(dest, "bulk_delete_by_parent_ids"):
                        await dest.bulk_delete_by_parent_ids(
                            parent_ids_to_clear, sync_context.sync.id
                        )
                    else:
                        for pid in parent_ids_to_clear:
                            await dest.bulk_delete_by_parent_id(pid, sync_context.sync.id)

                # Also delete main entities by their entity_id
                if deletes:
                    entity_ids_to_delete = [d.entity_id for d in deletes]
                    await dest.bulk_delete(entity_ids_to_delete, sync_context.sync.id)
                if to_insert:
                    await dest.bulk_insert(to_insert)
            except NotImplementedError:
                pass  # Some destinations don't support all operations
            except Exception as e:
                dest_name = dest.__class__.__name__
                if is_primary:
                    sync_context.logger.error(f"Primary destination {dest_name} failed: {e}")
                    raise
                sync_context.logger.warning(
                    f"Secondary destination {dest_name} failed (continuing): {e}"
                )

    async def _batch_persist_db_deletes(
        self,
        db,
        deletes: List[BaseEntity],
        sync_context: SyncContext,
    ) -> None:
        if not deletes:
            return
        del_map = await crud.entity.bulk_get_by_entity_and_sync(
            db=db,
            sync_id=sync_context.sync.id,
            entity_ids=[p.entity_id for p in deletes],
        )
        db_ids = [row.id for row in del_map.values()]
        if db_ids:
            await crud.entity.bulk_remove(db=db, ids=db_ids, ctx=sync_context.ctx)

        if sync_context.entity_state_tracker and del_map:
            counts_by_def: Dict = defaultdict(int)
            for row in del_map.values():
                if hasattr(row, "entity_definition_id") and row.entity_definition_id:
                    counts_by_def[row.entity_definition_id] += 1
            for def_id, count in counts_by_def.items():
                await sync_context.entity_state_tracker.update_entity_count(
                    entity_definition_id=def_id, action="delete", delta=count
                )

    async def _update_progress_and_guard_rails(
        self, partitions: Dict[str, List[BaseEntity]], sync_context: SyncContext
    ) -> None:
        actions = {"inserted": "inserts", "updated": "updates", "deleted": "deletes"}
        for key, partition_key in actions.items():
            count = len(partitions[partition_key])
            if count > 0:
                await sync_context.progress.increment(key, count)
        work_count = len(partitions["inserts"]) + len(partitions["updates"])
        for _ in range(work_count):
            await sync_context.guard_rail.increment(ActionType.ENTITIES)

    async def _update_state_tracker_for_inserts(
        self, inserts: List[BaseEntity], sync_context: SyncContext
    ) -> None:
        if not inserts or not getattr(sync_context, "entity_state_tracker", None):
            return
        counts_by_def: Dict = defaultdict(int)
        sample_name_by_def: Dict[str, str] = {}
        for p in inserts:
            def_id = self._resolve_entity_definition_id(p, sync_context)
            if def_id:
                counts_by_def[def_id] += 1
                sample_name_by_def.setdefault(def_id, type(p).__name__)
        for def_id, count in counts_by_def.items():
            await sync_context.entity_state_tracker.update_entity_count(
                entity_definition_id=def_id,
                action="insert",
                delta=count,  # Pass the actual count, not default 1
                entity_name=sample_name_by_def.get(def_id),
                entity_type=sample_name_by_def.get(def_id),
            )

    # ------------------------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------------------------
    async def _compute_vector(
        self,
        processed_entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        if not processed_entities:
            return []
        entity_context = "Entity batch"
        try:
            texts: list[str] = []
            for e in processed_entities:
                text = e.build_embeddable_text() if hasattr(e, "build_embeddable_text") else str(e)
                if hasattr(e, "embeddable_text"):
                    try:
                        e.embeddable_text = text
                    except Exception:
                        pass
                texts.append(text)

            embeddings, sparse_embeddings = await self._get_embeddings(
                texts, sync_context, entity_context
            )

            processed_entities = await self._assign_vectors_to_entities(
                processed_entities, embeddings, sparse_embeddings, sync_context
            )
            return processed_entities

        except asyncio.CancelledError:
            # Propagate cancellation so orchestrator can stop and cancel workers
            raise
        except Exception as e:
            sync_context.logger.warning(
                f"💥 VECTOR_ERROR [{entity_context}] Vectorization failed: {str(e)}"
            )
            raise

    async def _get_embeddings(
        self, texts: List[str], sync_context: SyncContext, entity_context: str
    ) -> Tuple[List[List[float]], List[SparseTextEmbedding] | None]:
        import inspect

        embedding_model = sync_context.embedding_model

        if hasattr(embedding_model, "embed_many"):
            sig = inspect.signature(embedding_model.embed_many)
            if "entity_context" in sig.parameters:
                embeddings = await embedding_model.embed_many(texts, entity_context=entity_context)
            else:
                embeddings = await embedding_model.embed_many(texts)
        else:
            embeddings = await embedding_model.embed_many(texts)

        # Use precomputed destination capability from SyncContext instead of
        # hitting destinations per batch (avoids Qdrant 408s under load).
        calculate_sparse_embeddings = bool(getattr(sync_context, "has_keyword_index", False))

        if calculate_sparse_embeddings:
            sparse_embedder = sync_context.keyword_indexing_model
            sparse_embeddings = list(await sparse_embedder.embed_many(texts))
        else:
            sparse_embeddings = None

        return embeddings, sparse_embeddings

    async def _assign_vectors_to_entities(
        self,
        processed_entities: List[BaseEntity],
        embeddings: List[List[float]],
        sparse_embeddings: List[SparseTextEmbedding] | None,
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        if len(embeddings) != len(processed_entities):
            sync_context.logger.warning(
                f"Embedding count mismatch: got {len(embeddings)} embeddings "
                f"for {len(processed_entities)} entities"
            )

        def _assign_vectors_to_entities_sync(entities, neural_vectors, sparse_vectors):
            for i, (processed_entity, neural_vector) in enumerate(
                zip(entities, neural_vectors, strict=False)
            ):
                try:
                    if neural_vector is None:
                        continue
                    sparse_vector = sparse_vectors[i] if sparse_vectors else None
                    if processed_entity.airweave_system_metadata is None:
                        from airweave.platform.entities._base import AirweaveSystemMetadata

                        processed_entity.airweave_system_metadata = AirweaveSystemMetadata()
                    processed_entity.airweave_system_metadata.vectors = [
                        neural_vector,
                        sparse_vector,
                    ]
                except Exception:
                    pass
            return entities

        return await run_in_thread_pool(
            _assign_vectors_to_entities_sync, processed_entities, embeddings, sparse_embeddings
        )
