"""Entity pipeline - orchestrates entity processing through sync stages.

Lifecycle:
1. Entities produced by source
2. Batched and submitted to pipeline
3. TRACKED in EntityTracker (first thing - dedup + encounter tracking)
4. Hash computed
5. Action resolved (INSERT/UPDATE/DELETE/KEEP)
6. Actions dispatched to handlers (handlers process content as needed)
7. Orphan cleanup dispatched through handlers at sync end
"""

from collections import defaultdict
from typing import Any, Dict, List
from uuid import UUID

from airweave.core.shared_models import AirweaveFieldFlag
from airweave.platform.contexts import SyncContext
from airweave.platform.contexts.runtime import SyncRuntime
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sync.actions import (
    EntityActionBatch,
    EntityActionDispatcher,
    EntityActionResolver,
)
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.pipeline.cleanup_service import cleanup_service
from airweave.platform.sync.pipeline.entity_tracker import EntityTracker
from airweave.platform.sync.pipeline.hash_computer import hash_computer
from airweave.platform.sync.state_publisher import SyncStatePublisher


class EntityPipeline:
    """Pipeline for processing entities with stateful tracking across sync lifecycle.

    Uses dependency injection for all major components, configured at factory time.
    """

    def __init__(
        self,
        entity_tracker: EntityTracker,
        state_publisher: SyncStatePublisher,
        action_resolver: EntityActionResolver,
        action_dispatcher: EntityActionDispatcher,
    ):
        """Initialize pipeline with injected dependencies.

        Args:
            entity_tracker: Centralized entity state tracker
            state_publisher: Publishes progress to Redis pubsub
            action_resolver: Resolves entities to actions
            action_dispatcher: Dispatches actions to handlers
        """
        self._tracker = entity_tracker
        self._state_publisher = state_publisher
        self._resolver = action_resolver
        self._dispatcher = action_dispatcher

    # -------------------------------------------------------------------------
    # Public API - Called from Orchestrator
    # -------------------------------------------------------------------------

    async def process(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
        runtime: SyncRuntime,
    ) -> None:
        """Process a batch of entities through the full pipeline.

        Args:
            entities: Entities to process
            sync_context: Sync context (frozen data)
            runtime: Sync runtime (live services)
        """
        unique_entities = await self._track_and_dedupe(entities, sync_context)
        if not unique_entities:
            return

        await self._prepare_entities(unique_entities, sync_context, runtime)

        batch = await self._resolver.resolve(unique_entities, sync_context)

        if not batch.has_mutations:
            await self._handle_keep_only_batch(batch, sync_context)
            return

        await self._dispatcher.dispatch(batch, sync_context, runtime)

        await self._update_tracker(batch, sync_context)

        await self._cleanup_temp_files_for_batch(batch, sync_context)

    async def cleanup_orphaned_entities(
        self, sync_context: SyncContext, runtime: SyncRuntime
    ) -> None:
        """Remove entities from database/destinations that were not encountered during sync.

        Args:
            sync_context: Sync context
            runtime: Sync runtime
        """
        orphans_by_definition = await self._identify_orphans(sync_context)
        if not orphans_by_definition:
            return

        all_orphan_ids = [
            entity_id for entity_ids in orphans_by_definition.values() for entity_id in entity_ids
        ]

        await self._dispatcher.dispatch_orphan_cleanup(all_orphan_ids, sync_context)

        for definition_id, entity_ids in orphans_by_definition.items():
            await self._tracker.record_deletes(definition_id, len(entity_ids))

    async def cleanup_temp_files(self, sync_context: SyncContext, runtime: SyncRuntime) -> None:
        """Remove entire sync_job_id directory (final cleanup safety net).

        Args:
            sync_context: Sync context
            runtime: Sync runtime (provides source.file_downloader)
        """
        await cleanup_service.cleanup_temp_files(sync_context, runtime)

    # -------------------------------------------------------------------------
    # Phase 1: Track and Deduplicate
    # -------------------------------------------------------------------------

    async def _track_and_dedupe(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        """Track entities and filter duplicates."""
        for entity in entities:
            self._populate_base_entity_fields_from_flags(entity)

        unique = []
        skipped_count = 0

        for entity in entities:
            is_new = await self._tracker.track_entity(
                entity.__class__.__name__,
                entity.entity_id,
            )
            if is_new:
                unique.append(entity)
            else:
                skipped_count += 1
                sync_context.logger.debug(
                    f"Skipping duplicate: {entity.__class__.__name__}[{entity.entity_id}]"
                )

        if skipped_count > 0:
            await self._tracker.record_skipped(skipped_count)
            sync_context.logger.debug(
                f"Filtered {skipped_count} duplicates from batch of {len(entities)}"
            )

        if not unique:
            sync_context.logger.debug("All entities in batch were duplicates")

        return unique

    # -------------------------------------------------------------------------
    # Phase 2: Prepare Entities
    # -------------------------------------------------------------------------

    async def _prepare_entities(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
        runtime: SyncRuntime,
    ) -> None:
        """Prepare entities: enrich metadata and compute hashes."""
        await self._enrich_early_metadata(entities, sync_context)
        await hash_computer.compute_for_batch(entities, sync_context, runtime)

    # -------------------------------------------------------------------------
    # Phase 4: Handle KEEP-only batches
    # -------------------------------------------------------------------------

    async def _handle_keep_only_batch(
        self,
        batch: EntityActionBatch,
        sync_context: SyncContext,
    ) -> None:
        """Handle batch where all entities are KEEP (unchanged)."""
        if batch.keeps:
            await self._tracker.record_kept(len(batch.keeps))
            await self._state_publisher.check_and_publish()

            sync_context.logger.debug(
                f"All {len(batch.keeps)} entities unchanged - skipping pipeline"
            )

            await self._cleanup_temp_files_for_batch(batch, sync_context)

    # -------------------------------------------------------------------------
    # Phase 6: Update Entity Tracker
    # -------------------------------------------------------------------------

    async def _update_tracker(
        self,
        batch: EntityActionBatch,
        sync_context: SyncContext,
    ) -> None:
        """Update entity tracker with successful operations."""
        inserts_by_def: Dict[UUID, int] = defaultdict(int)
        updates_by_def: Dict[UUID, int] = defaultdict(int)
        deletes_by_def: Dict[UUID, int] = defaultdict(int)
        entity_names: Dict[UUID, str] = {}

        for action in batch.inserts:
            inserts_by_def[action.entity_definition_id] += 1
            entity_names[action.entity_definition_id] = action.entity_type

        for action in batch.updates:
            updates_by_def[action.entity_definition_id] += 1
            entity_names[action.entity_definition_id] = action.entity_type

        for action in batch.deletes:
            deletes_by_def[action.entity_definition_id] += 1
            entity_names[action.entity_definition_id] = action.entity_type

        await self._tracker.record_batch_results(
            inserts_by_def=inserts_by_def,
            updates_by_def=updates_by_def,
            deletes_by_def=deletes_by_def,
            keeps_count=len(batch.keeps),
            entity_names=entity_names,
        )

        await self._state_publisher.check_and_publish()

    # -------------------------------------------------------------------------
    # Orphan Identification
    # -------------------------------------------------------------------------

    async def _identify_orphans(self, sync_context: SyncContext) -> Dict[UUID, List[str]]:
        """Identify orphaned entity IDs (in DB but not encountered), grouped by definition."""
        from airweave import crud
        from airweave.db.session import get_db_context

        encountered_ids = self._tracker.get_all_encountered_ids_flat()

        async with get_db_context() as db:
            stored_entities = await crud.entity.get_by_sync_id(db=db, sync_id=sync_context.sync.id)

        orphans_by_definition: Dict[UUID, List[str]] = defaultdict(list)
        for entity in stored_entities:
            if entity.entity_id not in encountered_ids:
                orphans_by_definition[entity.entity_definition_id].append(entity.entity_id)

        total_orphans = sum(len(ids) for ids in orphans_by_definition.values())
        if total_orphans:
            sync_context.logger.info(
                f"🔍 Identified {total_orphans} orphaned entities "
                f"across {len(orphans_by_definition)} definitions "
                f"out of {len(stored_entities)} stored"
            )

        return dict(orphans_by_definition)

    # -------------------------------------------------------------------------
    # Temp File Cleanup
    # -------------------------------------------------------------------------

    async def _cleanup_temp_files_for_batch(
        self,
        batch: EntityActionBatch,
        sync_context: SyncContext,
    ) -> None:
        """Clean up temp files for processed batch."""
        partitions = {
            "inserts": [a.entity for a in batch.inserts],
            "updates": [a.entity for a in batch.updates],
            "keeps": [a.entity for a in batch.keeps],
        }
        await cleanup_service.cleanup_processed_files(partitions, sync_context)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _get_flagged_field_value(self, entity: BaseEntity, flag_name: str) -> Any:
        """Extract value of field marked with specified flag."""
        flag_key = flag_name.value if hasattr(flag_name, "value") else flag_name

        for field_name, field_info in entity.model_fields.items():
            json_extra = field_info.json_schema_extra
            if json_extra and isinstance(json_extra, dict):
                if json_extra.get(flag_key):
                    return getattr(entity, field_name, None)

        return None

    def _populate_base_entity_fields_from_flags(self, entity: BaseEntity) -> None:
        """Populate BaseEntity fields from flagged fields."""
        if not entity.entity_id:
            flagged_value = self._get_flagged_field_value(entity, AirweaveFieldFlag.IS_ENTITY_ID)
            if flagged_value:
                entity.entity_id = str(flagged_value)

        if not entity.name:
            flagged_value = self._get_flagged_field_value(entity, AirweaveFieldFlag.IS_NAME)
            if flagged_value:
                entity.name = str(flagged_value)

        if not entity.created_at:
            flagged_value = self._get_flagged_field_value(entity, AirweaveFieldFlag.IS_CREATED_AT)
            if flagged_value is not None:
                entity.created_at = flagged_value

        if not entity.updated_at:
            flagged_value = self._get_flagged_field_value(entity, AirweaveFieldFlag.IS_UPDATED_AT)
            if flagged_value is not None:
                entity.updated_at = flagged_value

    async def _enrich_early_metadata(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> None:
        """Set early metadata fields from sync_context."""
        from airweave.platform.entities._base import AirweaveSystemMetadata

        for entity in entities:
            if entity.airweave_system_metadata is None:
                entity.airweave_system_metadata = AirweaveSystemMetadata()

            is_snapshot = sync_context.source_short_name == "snapshot"
            if not (is_snapshot and entity.airweave_system_metadata.source_name):
                entity.airweave_system_metadata.source_name = sync_context.source_short_name
            entity.airweave_system_metadata.entity_type = entity.__class__.__name__
            entity.airweave_system_metadata.sync_id = sync_context.sync.id
            entity.airweave_system_metadata.sync_job_id = sync_context.sync_job.id

        for entity in entities:
            if entity.airweave_system_metadata is None:
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: airweave_system_metadata not initialized "
                    f"for entity {entity.entity_id}"
                )
