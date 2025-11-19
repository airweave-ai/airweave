"""Module for entity pipeline."""

import asyncio
import hashlib
import json
import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import UUID

import aiofiles
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from airweave import crud, models
from airweave.core.constants.reserved_ids import RESERVED_TABLE_ENTITY_ID
from airweave.core.shared_models import ActionType, AirweaveFieldFlag
from airweave.db.session import get_db_context
from airweave.platform.entities._base import (
    BaseEntity,
    CodeFileEntity,
    FileEntity,
    PolymorphicEntity,
)
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.exceptions import EntityProcessingError, SyncFailureError
from airweave.platform.sync.file_types import SUPPORTED_FILE_EXTENSIONS


class EntityPipeline:
    """Pipeline for processing entities with stateful tracking across sync lifecycle."""

    def __init__(self):
        """Initialize pipeline with empty entity tracking."""
        self._entity_ids_encountered_by_type: Dict[str, Set[str]] = {}
        self._dedupe_lock = asyncio.Lock()
        self._entities_printed_count: int = 0

    # ------------------------------------------------------------------------------------
    # Cleanup orphaned entities
    # ------------------------------------------------------------------------------------

    async def cleanup_orphaned_entities(self, sync_context: SyncContext) -> None:
        """Remove entities from database/destinations that were not encountered during sync."""
        try:
            orphaned = await self._identify_orphaned_entities(sync_context)

            if not orphaned:
                return

            await self._remove_orphaned_entities(orphaned, sync_context)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            sync_context.logger.error(f"💥 Cleanup failed: {str(e)}", exc_info=True)
            raise

    async def _identify_orphaned_entities(self, sync_context: SyncContext) -> List[models.Entity]:
        """Fetch stored entities and filter to those not encountered during sync."""
        # Log start of DB query
        query_start = time.time()
        sync_context.logger.info(
            "🔍 [ORPHAN CLEANUP] Fetching all stored entities from database..."
        )

        async with get_db_context() as db:
            stored_entities = await crud.entity.get_by_sync_id(db=db, sync_id=sync_context.sync.id)

        query_duration = time.time() - query_start
        sync_context.logger.info(
            f"✅ [ORPHAN CLEANUP] Retrieved {len(stored_entities)} stored entities "
            f"in {query_duration:.2f}s"
        )

        if not stored_entities:
            return []

        # Log comparison phase
        compare_start = time.time()
        encountered_ids = set().union(*self._entity_ids_encountered_by_type.values())
        orphaned = [e for e in stored_entities if e.entity_id not in encountered_ids]
        compare_duration = time.time() - compare_start

        sync_context.logger.info(
            f"📊 [ORPHAN CLEANUP] Analysis complete in {compare_duration:.2f}s: "
            f"{len(encountered_ids)} encountered, {len(orphaned)} orphaned "
            f"out of {len(stored_entities)} total"
        )

        return orphaned

    async def _remove_orphaned_entities(
        self, orphaned_entities: List[models.Entity], sync_context: SyncContext
    ) -> None:
        """Remove orphaned entities from destinations and database, update trackers."""
        entity_ids = [e.entity_id for e in orphaned_entities]
        db_ids = [e.id for e in orphaned_entities]

        # Delete all chunks for these parent entities (using bulk_delete_by_parent_ids)
        for destination in sync_context.destinations:
            await self._retry_destination_operation(
                operation=lambda dest=destination: dest.bulk_delete_by_parent_ids(
                    entity_ids, sync_context.sync.id
                ),
                operation_name="orphan cleanup delete",
                sync_context=sync_context,
            )

        async with get_db_context() as db:
            await crud.entity.bulk_remove(db=db, ids=db_ids, ctx=sync_context.ctx)
            await db.commit()

        await sync_context.progress.increment("deleted", len(orphaned_entities))

        # Update entity state tracker (already has the right logic)
        await self._update_entity_state_tracker(orphaned_entities, sync_context)

    async def _update_entity_state_tracker(
        self, orphaned_entities: List[models.Entity], sync_context: SyncContext
    ) -> None:
        """Update entity state tracker with deletion counts by entity definition."""
        if not getattr(sync_context, "entity_state_tracker", None):
            return

        counts_by_def = defaultdict(int)
        for entity in orphaned_entities:
            if hasattr(entity, "entity_definition_id") and entity.entity_definition_id:
                counts_by_def[entity.entity_definition_id] += 1

        for def_id, count in counts_by_def.items():
            await sync_context.entity_state_tracker.update_entity_count(
                entity_definition_id=def_id, action="delete", delta=count
            )

    # ------------------------------------------------------------------------------------
    # Process
    # ------------------------------------------------------------------------------------

    async def process(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> None:
        """Process a list of entities."""
        # Populate BaseEntity fields from flagged fields BEFORE duplicate detection
        for entity in entities:
            self._populate_base_entity_fields_from_flags(entity)

        unique_entities = await self._filter_duplicates(entities, sync_context)

        if not unique_entities:
            sync_context.logger.debug("All entities in batch were duplicates, skipping processing")
            return

        await self._enrich_early_metadata(unique_entities, sync_context)

        await self.compute_hashes_for_batch(unique_entities, sync_context)

        partitions = await self._determine_actions(unique_entities, sync_context)

        # Early exit: If nothing needs to be processed (only KEEP entities)
        if not any(partitions[k] for k in ("inserts", "updates", "deletes")):
            if partitions["keeps"]:
                await sync_context.progress.increment("kept", len(partitions["keeps"]))
                sync_context.logger.debug(
                    f"All {len(partitions['keeps'])} entities unchanged - skipping pipeline"
                )
            return

        # Handle DELETES early (don't need chunking/embedding)
        if partitions["deletes"]:
            await self._handle_deletes(partitions, sync_context)

        # Process INSERTS/UPDATES through full pipeline
        entities_to_process = partitions["inserts"] + partitions["updates"]
        if not entities_to_process:
            # Only deletes and/or keeps - deletes already handled, just update progress
            await self._update_progress(partitions, sync_context)
            return

        await self._build_textual_representations(entities_to_process, sync_context)

        for entity in entities_to_process:
            if not hasattr(entity, "textual_representation") or not entity.textual_representation:
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: Entity {entity.__class__.__name__}[{entity.entity_id}] "
                    f"has no textual_representation after _build_textual_representations(). "
                    f"This should never happen - failed entities should be removed from the list."
                )

        # Chunk entities (entity multiplication: 1 entity → N chunk entities)
        # entities_to_process may be empty if all failed conversion (handled in method)
        if not entities_to_process:
            sync_context.logger.debug("No entities to chunk - all failed conversion")
            return

        chunk_entities = await self._chunk_entities(entities_to_process, sync_context)

        # Release large textual bodies on parent entities once chunks are created
        for entity in entities_to_process:
            entity.textual_representation = None

        # Embed chunk entities (sets vectors field)
        await self._embed_entities(chunk_entities, sync_context)

        # Persist to destinations (COMMIT POINT)
        await self._persist_to_destinations(chunk_entities, partitions, sync_context)

        # Drop chunk payloads/vectors ASAP to minimise concurrent memory footprint
        for chunk in chunk_entities:
            chunk.textual_representation = None
            if chunk.airweave_system_metadata:
                chunk.airweave_system_metadata.vectors = None
        chunk_entities.clear()

        # Persist to database (only after destination success)
        await self._persist_to_database(partitions, sync_context)

        # Update progress
        await self._update_progress(partitions, sync_context)

        # Progressive cleanup: delete temp files after successful processing
        await self._cleanup_processed_files(partitions, sync_context)

    # ------------------------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------------------------

    async def _filter_duplicates(
        self, entities: List[BaseEntity], sync_context: SyncContext
    ) -> List[BaseEntity]:
        """Filter out duplicate entities that have already been encountered in this sync."""
        unique_entities: List[BaseEntity] = []
        skipped_count = 0

        for entity in entities:
            # Track by entity type to allow same IDs across different types
            entity_type = entity.__class__.__name__

            is_duplicate = False
            async with self._dedupe_lock:
                entity_ids = self._entity_ids_encountered_by_type.setdefault(entity_type, set())

                # Check if we've already seen this entity ID for this type
                if entity.entity_id in entity_ids:
                    is_duplicate = True
                else:
                    # Mark as encountered
                    entity_ids.add(entity.entity_id)

            if is_duplicate:
                skipped_count += 1
                sync_context.logger.debug(
                    f"Skipping duplicate entity: {entity_type}[{entity.entity_id}]"
                )
                continue

            unique_entities.append(entity)

        # Update progress with skip count
        if skipped_count > 0:
            await sync_context.progress.increment("skipped", skipped_count)
            sync_context.logger.debug(
                f"Filtered {skipped_count} duplicate entities from batch of {len(entities)}"
            )

        # Update entity encounter tracking for orphan detection
        await sync_context.progress.update_entities_encountered_count(
            self._entity_ids_encountered_by_type
        )

        return unique_entities

    # ------------------------------------------------------------------------------------
    # Early Metadata Enrichment
    # ------------------------------------------------------------------------------------

    def _get_flagged_field_value(self, entity: BaseEntity, flag_name: str) -> Any:
        """Extract value of field marked with specified flag."""
        # Support both raw string keys ("is_entity_id") and AirweaveFieldFlag enum values
        flag_key = flag_name.value if hasattr(flag_name, "value") else flag_name

        # Iterate through entity's model fields
        for field_name, field_info in entity.model_fields.items():
            # Check if field has json_schema_extra with the flag
            json_extra = field_info.json_schema_extra
            if json_extra and isinstance(json_extra, dict):
                if json_extra.get(flag_key):
                    return getattr(entity, field_name, None)

        return None

    def _populate_base_entity_fields_from_flags(self, entity: BaseEntity) -> None:
        """Populate BaseEntity fields from flagged fields."""
        # Extract entity_id from is_entity_id flag if not already set
        if not entity.entity_id:
            flagged_value = self._get_flagged_field_value(entity, AirweaveFieldFlag.IS_ENTITY_ID)
            if flagged_value:
                entity.entity_id = str(flagged_value)

        # Extract name from is_name flag if not already set
        if not entity.name:
            flagged_value = self._get_flagged_field_value(entity, AirweaveFieldFlag.IS_NAME)
            if flagged_value:
                entity.name = str(flagged_value)

        # Extract timestamps (Optional - no error if missing)
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
            # Initialize metadata if not present
            if entity.airweave_system_metadata is None:
                entity.airweave_system_metadata = AirweaveSystemMetadata()

            # Set early metadata fields
            entity.airweave_system_metadata.source_name = sync_context.source._short_name
            entity.airweave_system_metadata.entity_type = entity.__class__.__name__
            entity.airweave_system_metadata.sync_id = sync_context.sync.id
            entity.airweave_system_metadata.sync_job_id = sync_context.sync_job.id

        # Validate all entities have metadata initialized
        for entity in entities:
            if entity.airweave_system_metadata is None:
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: airweave_system_metadata not initialized "
                    f"for entity {entity.entity_id}"
                )

            # Validate required early fields are set
            if not all(
                [
                    entity.airweave_system_metadata.source_name,
                    entity.airweave_system_metadata.entity_type,
                    entity.airweave_system_metadata.sync_id,
                    entity.airweave_system_metadata.sync_job_id,
                ]
            ):
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: Early metadata incomplete for entity {entity.entity_id}"
                )

    # ------------------------------------------------------------------------------------
    # Hash Computation
    # ------------------------------------------------------------------------------------

    @staticmethod
    def _stable_serialize(obj: Any) -> Any:
        """Recursively serialize object in a stable way for hashing."""
        if isinstance(obj, dict):
            return {k: EntityPipeline._stable_serialize(v) for k, v in sorted(obj.items())}
        elif isinstance(obj, (list, tuple)):
            return [EntityPipeline._stable_serialize(x) for x in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # Convert other types to stable string representation
            return str(obj)

    async def compute_hash_for_entity(self, entity: BaseEntity) -> Optional[str]:
        """Compute stable content hash for a single entity."""
        try:
            # Step 1: Get entity dict
            entity_dict = entity.model_dump(mode="python", exclude_none=True)

            # Step 2: For file entities, compute and add content hash
            if isinstance(entity, (FileEntity, CodeFileEntity)):
                # Check local_path exists
                local_path = getattr(entity, "local_path", None)
                if not local_path:
                    raise EntityProcessingError(
                        f"FileEntity {entity.__class__.__name__}[{entity.entity_id}] "
                        f"missing local_path - cannot compute hash"
                    )

                # Compute file content hash asynchronously
                try:
                    content_hash = hashlib.sha256()
                    async with aiofiles.open(local_path, "rb") as f:
                        while True:
                            chunk = await f.read(8192)  # 8KB chunks
                            if not chunk:
                                break
                            content_hash.update(chunk)

                    # Add content hash to entity dict
                    entity_dict["_content_hash"] = content_hash.hexdigest()

                except Exception as e:
                    raise EntityProcessingError(
                        f"Failed to read file for {entity.__class__.__name__}[{entity.entity_id}] "
                        f"at {local_path}: {e}"
                    ) from e

            # Step 3: Exclude volatile fields
            excluded_fields = {
                "airweave_system_metadata",  # Not initialized yet
                "breadcrumbs",  # Parent relationships are volatile
                "local_path",  # Temp path changes per run
                "url",  # Contains access tokens
            }

            # Add fields marked with unhashable=True (composition over inheritance)
            for field_name, field_info in entity.__class__.model_fields.items():
                json_extra = field_info.json_schema_extra
                if json_extra and isinstance(json_extra, dict):
                    if json_extra.get(
                        AirweaveFieldFlag.UNHASHABLE.value
                        if hasattr(AirweaveFieldFlag.UNHASHABLE, "value")
                        else AirweaveFieldFlag.UNHASHABLE
                    ):
                        excluded_fields.add(field_name)

            content_dict = {k: v for k, v in entity_dict.items() if k not in excluded_fields}

            # Step 4: Stable serialize
            stable_data = self._stable_serialize(content_dict)

            # Step 5: JSON serialize with stable order
            json_str = json.dumps(stable_data, sort_keys=True, separators=(",", ":"))

            # Step 6: Compute SHA256 hash
            return hashlib.sha256(json_str.encode()).hexdigest()

        except EntityProcessingError:
            # Re-raise EntityProcessingError as-is
            raise
        except Exception:
            # Other errors - caller will handle logging
            raise

    async def compute_hashes_for_batch(  # noqa: C901
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> None:
        """Compute hashes for entire batch and set on entity.airweave_system_metadata.hash."""
        if not entities:
            return

        # Semaphore to limit concurrent file reads (10 at a time)
        semaphore = asyncio.Semaphore(10)

        async def _compute_with_semaphore(
            entity: BaseEntity,
        ) -> tuple[tuple[str, str], Optional[str]]:
            """Compute hash with semaphore control.

            Returns:
                Tuple of ((entity_type, entity_id), hash_value)
            """
            async with semaphore:
                entity_key = (entity.__class__.__name__, entity.entity_id)
                try:
                    hash_value = await self.compute_hash_for_entity(entity)
                    return entity_key, hash_value
                except EntityProcessingError as e:
                    # Log entity processing errors and return None
                    sync_context.logger.warning(
                        f"Hash computation failed for {entity.__class__.__name__}"
                        f"[{entity.entity_id}]: {e}"
                    )
                    return entity_key, None
                except Exception as e:
                    # Log unexpected errors and return None
                    sync_context.logger.warning(
                        f"Unexpected error computing hash for {entity.__class__.__name__}"
                        f"[{entity.entity_id}]: {e}"
                    )
                    return entity_key, None

        # Run all hash computations concurrently
        results = await asyncio.gather(*[_compute_with_semaphore(e) for e in entities])

        # Set hash on entities and track failures
        failed_entities = []
        file_count = 0
        regular_count = 0

        for entity, (_, hash_value) in zip(entities, results, strict=True):
            if hash_value is not None:
                # Set hash directly on entity metadata
                entity.airweave_system_metadata.hash = hash_value

                # Track counts for logging
                if isinstance(entity, (FileEntity, CodeFileEntity)):
                    file_count += 1
                else:
                    regular_count += 1
            else:
                failed_entities.append(entity)

        # Remove failed entities from list and mark as skipped
        for entity in failed_entities:
            entities.remove(entity)

        if failed_entities:
            await sync_context.progress.increment("skipped", len(failed_entities))
            sync_context.logger.warning(
                f"Skipped {len(failed_entities)} entities with hash computation failures"
            )

        # Log summary
        sync_context.logger.debug(
            f"Computed {file_count + regular_count} hashes: "
            f"{file_count} files, {regular_count} regular entities"
        )

        # Validate all remaining entities have hash set
        for entity in entities:
            if not entity.airweave_system_metadata.hash:
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: Hash not set for entity "
                    f"{entity.entity_id} after computation"
                )

    # ------------------------------------------------------------------------------------
    # Action Determination
    # ------------------------------------------------------------------------------------

    async def _determine_actions(  # noqa: C901
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> Dict[str, Any]:
        """Partition entities by action (INSERT/UPDATE/DELETE/KEEP)."""
        from airweave.platform.entities._base import DeletionEntity

        # Step 1: Separate deletions from non-deletions
        deletes = [
            e for e in entities if isinstance(e, DeletionEntity) and e.deletion_status == "removed"
        ]
        non_deletes = [e for e in entities if e not in deletes]

        # Step 2: Build entity requests with definition IDs
        entity_requests = []
        for entity in non_deletes:
            entity_definition_id = self._resolve_entity_definition_id(entity, sync_context)
            if entity_definition_id is None:
                # Entity type not in map → fatal error
                sync_context.logger.error(
                    f"Entity type {entity.__class__.__name__} not found in entity_map"
                )
                raise SyncFailureError(
                    f"Entity type {entity.__class__.__name__} not in sync_context.entity_map"
                )
            entity_requests.append((entity.entity_id, entity_definition_id))

        # Also add deletes to lookup (need existing_map for _handle_deletes)
        for entity in deletes:
            entity_definition_id = self._resolve_entity_definition_id(entity, sync_context)
            if entity_definition_id is None:
                raise SyncFailureError(
                    f"DELETE entity type {entity.__class__.__name__} not in entity_map"
                )
            entity_requests.append((entity.entity_id, entity_definition_id))

        # Step 3: Bulk fetch existing DB records with composite key lookup
        existing_map: Dict[tuple[str, UUID], models.Entity] = {}
        if entity_requests:
            try:
                lookup_start = time.time()
                num_chunks = (len(entity_requests) + 999) // 1000
                sync_context.logger.info(
                    f"🔍 [BULK LOOKUP] Starting bulk entity lookup for {len(entity_requests)} "
                    f"entities ({num_chunks} chunks of ~1000)..."
                )

                async with get_db_context() as db:
                    existing_map = await crud.entity.bulk_get_by_entity_sync_and_definition(
                        db,
                        sync_id=sync_context.sync.id,
                        entity_requests=entity_requests,
                    )

                lookup_duration = time.time() - lookup_start
                sync_context.logger.info(
                    f"✅ [BULK LOOKUP] Complete in {lookup_duration:.2f}s - "
                    f"found {len(existing_map)}/{len(entity_requests)} existing entities"
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                sync_context.logger.error(f"Failed to fetch existing entities: {e}")
                raise SyncFailureError(f"Failed to fetch existing entities: {e}")

        # Step 4: Partition non-deletes by action
        partitions = {
            "inserts": [],
            "updates": [],
            "keeps": [],
            "deletes": deletes,
            "existing_map": existing_map,
        }

        for entity in non_deletes:
            # Read hash directly from entity metadata
            if not entity.airweave_system_metadata.hash:
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: Entity {entity.__class__.__name__}"
                    f"[{entity.entity_id}] has no hash. "
                    f"Hash should have been set during compute_hashes_for_batch."
                )

            entity_hash = entity.airweave_system_metadata.hash

            # Get entity_definition_id (already validated in Step 2)
            entity_definition_id = self._resolve_entity_definition_id(entity, sync_context)
            if entity_definition_id is None:
                raise SyncFailureError(
                    f"Entity type {entity.__class__.__name__} not in sync_context.entity_map"
                )

            # Get existing DB record using composite key
            db_key = (entity.entity_id, entity_definition_id)
            db_row = existing_map.get(db_key)

            if db_row is None:
                # No DB record for this entity type → INSERT
                partitions["inserts"].append(entity)
            elif db_row.hash != entity_hash:
                # DB exists, hash differs → UPDATE
                partitions["updates"].append(entity)
            else:
                # DB exists, hash matches → KEEP
                partitions["keeps"].append(entity)

        # Log summary
        sync_context.logger.debug(
            f"Action determination: {len(partitions['inserts'])} inserts, "
            f"{len(partitions['updates'])} updates, {len(partitions['keeps'])} keeps, "
            f"{len(partitions['deletes'])} deletes"
        )

        return partitions

    def _resolve_entity_definition_id(
        self, entity: BaseEntity, sync_context: SyncContext
    ) -> Optional[UUID]:
        """Resolve entity definition ID with polymorphic fallback."""
        entity_class = entity.__class__

        definition_id = sync_context.entity_map.get(entity_class)
        if definition_id:
            return definition_id

        if issubclass(entity_class, PolymorphicEntity):
            return RESERVED_TABLE_ENTITY_ID

        return None

    # ------------------------------------------------------------------------------------
    # Delete Handling
    # ------------------------------------------------------------------------------------

    async def _handle_deletes(  # noqa: C901
        self,
        partitions: Dict[str, Any],
        sync_context: SyncContext,
    ) -> None:
        """Handle entity deletions (separate from insert/update pipeline).

        Deletes don't need chunking/embedding - just remove from destinations and DB.
        """
        from airweave import crud
        from airweave.db.session import get_db_context

        deletes = partitions["deletes"]
        if not deletes:
            return

        parent_ids_to_delete = [e.entity_id for e in deletes]

        # Delete from destinations (by original_entity_id)
        sync_context.logger.debug(
            f"Deleting {len(parent_ids_to_delete)} entities from destinations"
        )
        for dest in sync_context.destinations:
            await self._retry_destination_operation(
                operation=lambda d=dest: d.bulk_delete_by_parent_ids(
                    parent_ids_to_delete, sync_context.sync.id
                ),
                operation_name="delete",
                sync_context=sync_context,
            )

        # Delete from database
        existing_map = partitions["existing_map"]
        db_ids = []

        for entity in deletes:
            entity_def_id = self._resolve_entity_definition_id(entity, sync_context)
            if not entity_def_id:
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: DELETE entity {entity.entity_id} type "
                    f"{entity.__class__.__name__} not in entity_map"
                )
            key = (entity.entity_id, entity_def_id)
            if key in existing_map:
                db_ids.append(existing_map[key].id)
            else:
                # OK - source can report deletions for entities never synced
                sync_context.logger.debug(
                    f"DELETE entity {entity.entity_id} not in DB (never synced)"
                )

        if db_ids:
            async with get_db_context() as db:
                await crud.entity.bulk_remove(db, ids=db_ids, ctx=sync_context.ctx)
                await db.commit()
            sync_context.logger.debug(f"Deleted {len(db_ids)} DB records")

            # Update entity state tracker for real-time UI updates
            if hasattr(sync_context, "entity_state_tracker") and sync_context.entity_state_tracker:
                counts_by_def: Dict[UUID, int] = defaultdict(int)
                for entity in deletes:
                    entity_def_id = self._resolve_entity_definition_id(entity, sync_context)
                    key = (entity.entity_id, entity_def_id) if entity_def_id else None
                    if key and key in existing_map:
                        counts_by_def[entity_def_id] += 1

                for def_id, count in counts_by_def.items():
                    await sync_context.entity_state_tracker.update_entity_count(
                        entity_definition_id=def_id,
                        action="delete",
                        delta=count,
                    )

    # ------------------------------------------------------------------------------------
    # Textual Representation Building
    # ------------------------------------------------------------------------------------

    def _extract_embeddable_fields(self, entity: BaseEntity) -> Dict[str, Any]:
        """Extract fields marked with embeddable=True.

        Args:
            entity: Entity to extract fields from

        Returns:
            Dict mapping field names to their values
        """
        fields = {}
        for field_name, field_info in entity.__class__.model_fields.items():
            json_extra = field_info.json_schema_extra
            if json_extra and isinstance(json_extra, dict):
                if json_extra.get(
                    AirweaveFieldFlag.EMBEDDABLE.value
                    if hasattr(AirweaveFieldFlag.EMBEDDABLE, "value")
                    else AirweaveFieldFlag.EMBEDDABLE
                ):
                    value = getattr(entity, field_name, None)
                    if value is not None:
                        fields[field_name] = value
        return fields

    def _format_value(self, value: Any) -> str:
        """Format value for markdown - NO TRUNCATION.

        Args:
            value: Value to format

        Returns:
            Formatted string representation
        """
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    def _format_embeddable_fields_as_markdown(self, fields: Dict[str, Any]) -> str:
        """Convert embeddable fields dict to markdown.

        Args:
            fields: Dict of field names to values

        Returns:
            Markdown formatted string
        """
        lines = []
        for field_name, value in fields.items():
            label = field_name.replace("_", " ").title()
            formatted_value = self._format_value(value)
            lines.append(f"**{label}**: {formatted_value}")
        return "\n".join(lines)

    def _build_metadata_section(self, entity: BaseEntity, source_name: str) -> str:
        """Build metadata section for any entity type.

        For CodeFileEntity, returns empty string - code is self-documenting.

        Args:
            entity: Entity to build metadata for
            source_name: Name of the source

        Returns:
            Markdown formatted metadata section
        """
        # Skip metadata for code files - AST chunking works better on raw code
        if isinstance(entity, CodeFileEntity):
            return ""

        entity_type = entity.__class__.__name__
        lines = [
            "# Metadata",
            "",
            f"**Source**: {source_name}",
            f"**Type**: {entity_type}",
            f"**Name**: {entity.name}",
        ]

        # Add breadcrumb path if present (shows hierarchy with types)
        if entity.breadcrumbs and len(entity.breadcrumbs) > 0:
            # Format: "Type: Name → Type: Name" (strip source prefix and "Entity" suffix)
            path_parts = []
            for bc in entity.breadcrumbs:
                # Clean entity type: "AsanaProjectEntity" → "Project"
                clean_type = bc.entity_type
                # Remove "Entity" suffix
                if clean_type.endswith("Entity"):
                    clean_type = clean_type[:-6]  # Remove last 6 chars ("Entity")
                # Remove source prefix (e.g., "Asana", "Jira", "GitHub")
                # Look for capital letter after first one as delimiter
                for i in range(1, len(clean_type)):
                    if clean_type[i].isupper():
                        clean_type = clean_type[i:]
                        break
                path_parts.append(f"{clean_type}: {bc.name}")
            path_str = " → ".join(path_parts)
            lines.append(f"**Path**: {path_str}")

        embeddable_fields = self._extract_embeddable_fields(entity)
        if embeddable_fields:
            lines.append("")
            lines.append(self._format_embeddable_fields_as_markdown(embeddable_fields))

        return "\n".join(lines)

    def _determine_converter_for_file(self, file_path: str):
        """Determine converter module based on file extension.

        Args:
            file_path: Path to the file

        Returns:
            Converter module with convert_batch function

        Raises:
            EntityProcessingError: If file type is not supported
        """
        from airweave.platform import converters

        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        # Check if file type is supported using single source of truth
        if ext not in SUPPORTED_FILE_EXTENSIONS:
            raise EntityProcessingError(f"Unsupported file type: {ext}")

        # Map extensions to converter modules
        converter_map = {
            # Mistral OCR - Documents
            ".pdf": converters.mistral_converter,
            ".docx": converters.mistral_converter,
            ".pptx": converters.mistral_converter,
            # Mistral OCR - Images
            ".jpg": converters.mistral_converter,
            ".jpeg": converters.mistral_converter,
            ".png": converters.mistral_converter,
            # XLSX - local extraction
            ".xlsx": converters.xlsx_converter,
            # HTML
            ".html": converters.html_converter,
            ".htm": converters.html_converter,
            # Text files
            ".txt": converters.txt_converter,
            ".csv": converters.txt_converter,
            ".json": converters.txt_converter,
            ".xml": converters.txt_converter,
            ".md": converters.txt_converter,
            ".yaml": converters.txt_converter,
            ".yml": converters.txt_converter,
            ".toml": converters.txt_converter,
            # Code file extensions
            ".py": converters.code_converter,
            ".js": converters.code_converter,
            ".ts": converters.code_converter,
            ".tsx": converters.code_converter,
            ".jsx": converters.code_converter,
            ".java": converters.code_converter,
            ".cpp": converters.code_converter,
            ".c": converters.code_converter,
            ".h": converters.code_converter,
            ".hpp": converters.code_converter,
            ".go": converters.code_converter,
            ".rs": converters.code_converter,
            ".rb": converters.code_converter,
            ".php": converters.code_converter,
            ".swift": converters.code_converter,
            ".kt": converters.code_converter,
            ".kts": converters.code_converter,
            ".tf": converters.code_converter,
            ".tfvars": converters.code_converter,
        }

        converter = converter_map.get(ext)
        if not converter:
            raise EntityProcessingError(f"Unsupported file type: {ext}")

        return converter

    async def _build_textual_representations(  # noqa: C901
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> None:
        """Build textual_representation with batch-optimized conversion."""
        source_name = sync_context.source._short_name

        # Step 1: Build metadata section
        async def _build_metadata(entity: BaseEntity):
            metadata = self._build_metadata_section(entity, source_name)
            if not metadata and not isinstance(entity, CodeFileEntity):
                raise EntityProcessingError(f"Empty metadata for {entity.entity_id}")
            entity.textual_representation = metadata

        await asyncio.gather(*[_build_metadata(e) for e in entities])

        # Step 2: Partition FileEntities by converter
        converter_groups = {}  # {converter_module: [entity, ...]}
        failed_entities = []  # Track entities that failed (including unsupported types)

        for entity in entities:
            if isinstance(entity, FileEntity):
                # Validate local_path exists
                if not entity.local_path:
                    sync_context.logger.warning(
                        f"FileEntity {entity.__class__.__name__}[{entity.entity_id}] "
                        f"missing local_path"
                    )
                    failed_entities.append(entity)
                    continue

                try:
                    converter = self._determine_converter_for_file(entity.local_path)
                    if converter not in converter_groups:
                        converter_groups[converter] = []
                    converter_groups[converter].append(entity)
                except EntityProcessingError as e:
                    sync_context.logger.warning(
                        f"Skipping {entity.__class__.__name__}[{entity.entity_id}]: {e}"
                    )
                    failed_entities.append(entity)
                    continue

        # Step 3: Batch convert each partition and append to entities
        # Process in smaller sub-batches for progressive completion (especially for Mistral)
        CONVERTER_BATCH_SIZE = 10  # Max files per converter batch (prevents waterfall delay)

        for converter, file_entities in converter_groups.items():
            # Split into sub-batches to avoid blocking on large Mistral uploads
            for i in range(0, len(file_entities), CONVERTER_BATCH_SIZE):
                sub_batch = file_entities[i : i + CONVERTER_BATCH_SIZE]
                file_paths = [e.local_path for e in sub_batch]

                try:
                    # Batch convert returns Dict[file_path, text_content]
                    results = await converter.convert_batch(file_paths)

                    # Append content to each entity's textual_representation
                    # Track entities that fail (None results)
                    for entity in sub_batch:
                        text_content = results.get(entity.local_path)

                        if not text_content:
                            sync_context.logger.warning(
                                f"Conversion returned no content for "
                                f"{entity.__class__.__name__}[{entity.entity_id}] "
                                f"at {entity.local_path} - entity will be skipped"
                            )
                            # Mark for removal - don't process this entity further
                            failed_entities.append(entity)
                            continue

                        # Append content section
                        entity.textual_representation += f"\n\n# Content\n\n{text_content}"

                except SyncFailureError:
                    # Infrastructure failure from converter - propagate to fail entire sync
                    raise
                except Exception as e:
                    # Unexpected errors - mark entire sub-batch as failed but continue
                    converter_name = converter.__class__.__name__
                    sync_context.logger.error(
                        f"Batch conversion failed for {converter_name} sub-batch: {e}",
                        exc_info=True,
                    )
                    # Mark all entities in this sub-batch as failed
                    failed_entities.extend(sub_batch)
                    # Log each entity being skipped
                    for entity in sub_batch:
                        sync_context.logger.warning(
                            f"Skipping {entity.__class__.__name__}[{entity.entity_id}] "
                            f"due to batch failure"
                        )
                    # Don't raise - continue with other sub-batches/converters

        # Remove failed entities from the entities list and mark as skipped
        # This cleanup ALWAYS runs now since we don't raise exceptions above
        if failed_entities:
            for entity in failed_entities:
                if entity in entities:
                    entities.remove(entity)
            await sync_context.progress.increment("skipped", len(failed_entities))
            sync_context.logger.warning(
                f"Removed {len(failed_entities)} entities that failed conversion"
            )

    # ------------------------------------------------------------------------------------
    # Chunking (Entity Multiplication)
    # ------------------------------------------------------------------------------------

    async def _multiply_entities_from_chunks(  # noqa: C901
        self,
        entities: List[BaseEntity],
        chunk_lists: List[List[Dict[str, Any]]],
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        """Create chunk entities from chunk dicts (shared logic for all chunkers).

        Args:
            entities: Original entities
            chunk_lists: Chunks for each entity (from chunker.chunk_batch)
            sync_context: Sync context

        Returns:
            List of chunk entities with chunk_index set
        """
        chunk_entities = []
        failed_entities = []

        for entity, chunks in zip(entities, chunk_lists, strict=True):
            if not chunks:
                sync_context.logger.warning(
                    f"No chunks for {entity.__class__.__name__}[{entity.entity_id}]"
                )
                failed_entities.append(entity)
                continue

            original_entity_id = entity.entity_id

            # Create one new entity per chunk
            for chunk_idx, chunk in enumerate(chunks):
                if not chunk["text"] or not chunk["text"].strip():
                    sync_context.logger.error(
                        f"Empty chunk for {entity.entity_id} - skipping entity"
                    )
                    failed_entities.append(entity)
                    break

                chunk_entity = entity.model_copy(deep=True)
                chunk_entity.textual_representation = chunk["text"]

                # Set unique chunk entity_id
                chunk_entity.entity_id = f"{original_entity_id}__chunk_{chunk_idx}"

                # Set system metadata
                if chunk_entity.airweave_system_metadata is None:
                    raise SyncFailureError(f"No metadata for {entity.entity_id}")

                chunk_entity.airweave_system_metadata.chunk_index = chunk_idx
                chunk_entity.airweave_system_metadata.original_entity_id = original_entity_id

                chunk_entities.append(chunk_entity)

            # Log entity multiplication
            if not (failed_entities and entity in failed_entities):
                sync_context.logger.debug(
                    f"{entity.__class__.__name__}[{entity.entity_id}]: "
                    f"multiplied into {len(chunks)} chunk entities"
                )

        # Mark failed entities as skipped
        if failed_entities:
            failed_entities = list(set(failed_entities))
            await sync_context.progress.increment("skipped", len(failed_entities))

        # Validate required metadata
        for chunk_entity in chunk_entities:
            if chunk_entity.airweave_system_metadata.chunk_index is None:
                raise SyncFailureError(f"chunk_index not set for {chunk_entity.entity_id}")
            if not chunk_entity.airweave_system_metadata.original_entity_id:
                raise SyncFailureError(f"original_entity_id not set for {chunk_entity.entity_id}")

        return chunk_entities

    async def _filter_unsupported_code_languages(
        self, entities: List[BaseEntity], sync_context: SyncContext
    ) -> Tuple[List[BaseEntity], List[BaseEntity]]:
        """Filter code entities to find those with unsupported tree-sitter languages.

        Uses Magika to detect language from textual_representation, then validates
        tree-sitter support.

        Returns:
            Tuple of (supported_entities, unsupported_entities)
        """
        code_entities = [e for e in entities if isinstance(e, CodeFileEntity)]
        if not code_entities:
            return entities, []

        try:
            from magika import Magika
            from tree_sitter_language_pack import get_parser
        except ImportError:
            sync_context.logger.warning(
                "Magika or tree-sitter not available - cannot validate language support"
            )
            return entities, []

        magika = Magika()
        supported = []
        unsupported = []

        for entity in code_entities:
            try:
                # Detect language from raw code (same as Chonkie)
                text_bytes = entity.textual_representation.encode("utf-8")
                result = magika.identify_bytes(text_bytes)
                detected_lang = result.output.label.lower()

                # Try to get parser to validate support
                try:
                    get_parser(detected_lang)
                    supported.append(entity)
                    sync_context.logger.debug(
                        f"Language {detected_lang} supported for {entity.name}"
                    )
                except LookupError:
                    unsupported.append(entity)
                    sync_context.logger.warning(
                        f"Tree-sitter does not support language '{detected_lang}' "
                        f"for {entity.name} - skipping entity"
                    )
            except Exception as e:
                sync_context.logger.warning(
                    f"Language detection failed for {entity.entity_id}: {e} - skipping"
                )
                unsupported.append(entity)

        return supported, unsupported

    async def _chunk_code_entities(
        self, entities: List[BaseEntity], sync_context: SyncContext
    ) -> List[BaseEntity]:
        """Chunk code entities with CodeChunker (AST-based)."""
        from airweave.platform.chunkers.code import CodeChunker

        # Filter out entities with unsupported languages
        supported_entities, unsupported_entities = await self._filter_unsupported_code_languages(
            entities, sync_context
        )

        # Skip unsupported entities
        if unsupported_entities:
            await sync_context.progress.increment("skipped", len(unsupported_entities))
            sync_context.logger.warning(
                f"Skipped {len(unsupported_entities)} code entities with unsupported languages"
            )

        if not supported_entities:
            sync_context.logger.debug("No supported code entities to chunk")
            return []

        # Chunk only supported entities
        chunker = CodeChunker()
        texts = [e.textual_representation for e in supported_entities]

        sync_context.logger.debug(
            f"Chunking {len(supported_entities)} code entities with CodeChunker"
        )

        try:
            chunk_lists = await chunker.chunk_batch(texts)
        except SyncFailureError:
            raise
        except Exception as e:
            raise SyncFailureError(f"CodeChunker failed: {e}")

        return await self._multiply_entities_from_chunks(
            supported_entities, chunk_lists, sync_context
        )

    async def _chunk_textual_entities(
        self, entities: List[BaseEntity], sync_context: SyncContext
    ) -> List[BaseEntity]:
        """Chunk textual entities with SemanticChunker (embedding similarity)."""
        from airweave.platform.chunkers.semantic import SemanticChunker

        chunker = SemanticChunker()
        texts = [e.textual_representation for e in entities]

        sync_context.logger.debug(f"Chunking {len(entities)} textual entities with SemanticChunker")

        try:
            chunk_lists = await chunker.chunk_batch(texts)
        except SyncFailureError:
            raise
        except Exception as e:
            raise SyncFailureError(f"SemanticChunker failed: {e}")

        return await self._multiply_entities_from_chunks(entities, chunk_lists, sync_context)

    async def _chunk_entities(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        """Chunk entities using type-specific chunkers (entity multiplication).

        Routes entities to appropriate chunkers:
        - CodeFileEntity → CodeChunker (AST-based)
        - All others → SemanticChunker (embedding similarity)

        Args:
            entities: List of entities with textual_representation set
            sync_context: Sync context

        Returns:
            List of chunk entities with chunk_index set
        """
        if not entities:
            sync_context.logger.debug("No entities to chunk (all failed conversion)")
            return []

        # Partition entities by type
        from airweave.platform.entities._base import CodeFileEntity

        code_entities = [e for e in entities if isinstance(e, CodeFileEntity)]
        textual_entities = [e for e in entities if not isinstance(e, CodeFileEntity)]

        sync_context.logger.debug(
            f"Entity routing: {len(code_entities)} code, {len(textual_entities)} textual"
        )

        # Chunk each partition with appropriate chunker
        all_chunk_entities = []

        if code_entities:
            code_chunk_entities = await self._chunk_code_entities(code_entities, sync_context)
            all_chunk_entities.extend(code_chunk_entities)

        if textual_entities:
            textual_chunk_entities = await self._chunk_textual_entities(
                textual_entities, sync_context
            )
            all_chunk_entities.extend(textual_chunk_entities)

        # Log statistics
        if all_chunk_entities:
            import tiktoken

            tokenizer = tiktoken.get_encoding("cl100k_base")
            token_counts = [
                len(tokenizer.encode(chunk_entity.textual_representation))
                for chunk_entity in all_chunk_entities
            ]

            sync_context.logger.debug(
                f"Chunk statistics: min={min(token_counts)}, max={max(token_counts)}, "
                f"avg={sum(token_counts) / len(token_counts):.1f} tokens"
            )

        sync_context.logger.debug(
            f"Entity multiplication: {len(entities)} → {len(all_chunk_entities)} chunk entities"
        )

        return all_chunk_entities

    # ------------------------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------------------------

    async def _embed_entities(
        self,
        chunk_entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> None:
        """Compute dense and sparse embeddings for chunk entities.

        Dense: textual_representation only (for cosine similarity)
        Sparse: JSON serialized entity excluding metadata (for keyword search)

        Args:
            chunk_entities: List of chunk entities with textual_representation set
            sync_context: Sync context with logger and settings

        Raises:
            SyncFailureError: If ANY embedding fails
        """
        if not chunk_entities:
            return

        # Prepare dense texts (textual_representation only)
        dense_texts = [e.textual_representation for e in chunk_entities]

        # Prepare sparse texts (JSON stringify entire entity excluding metadata)
        sparse_texts = []
        for entity in chunk_entities:
            entity_dict = entity.model_dump(mode="json", exclude={"airweave_system_metadata"})
            sparse_texts.append(json.dumps(entity_dict, sort_keys=True))

        # Compute dense embeddings (always required)
        # Create embedder with collection's vector_size (creates fresh instance)
        from airweave.platform.embedders import DenseEmbedder

        dense_embedder = DenseEmbedder(vector_size=sync_context.collection.vector_size)
        dense_embeddings = await dense_embedder.embed_many(dense_texts, sync_context)

        # Compute sparse embeddings (only if destination supports keyword index)
        sparse_embeddings = None
        if sync_context.has_keyword_index:
            from airweave.platform.embedders import SparseEmbedder

            sparse_embedder = SparseEmbedder()
            sparse_embeddings = await sparse_embedder.embed_many(sparse_texts, sync_context)

        # Assign vectors to entities
        # Metadata is already initialized during early enrichment
        for i, entity in enumerate(chunk_entities):
            # Dense vector (always present)
            dense_vector = dense_embeddings[i]

            # Sparse vector (only if keyword index supported)
            sparse_vector = sparse_embeddings[i] if sparse_embeddings else None

            entity.airweave_system_metadata.vectors = [dense_vector, sparse_vector]

        # Validation (should never fail - embedders guarantee correct length)
        for entity in chunk_entities:
            if not entity.airweave_system_metadata.vectors:
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: Entity {entity.entity_id} has no vectors"
                )
            if entity.airweave_system_metadata.vectors[0] is None:
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: Entity {entity.entity_id} has no dense vector"
                )

        sync_context.logger.debug(
            f"Embedded {len(chunk_entities)} chunk entities "
            f"(dense: {len(dense_embeddings)}, "
            f"sparse: {len(sparse_embeddings) if sparse_embeddings else 0})"
        )

    # ------------------------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------------------------

    async def _persist_to_destinations(
        self,
        chunk_entities: List[BaseEntity],
        partitions: Dict[str, Any],
        sync_context: SyncContext,
    ) -> None:
        """Persist chunks to vector databases (COMMIT POINT).

        Only handles INSERT/UPDATE. Deletes handled separately in _handle_deletes().
        """
        if not chunk_entities:
            return

        # Collect parent IDs needing clear (ONLY updates)
        parent_ids_to_clear = []
        if partitions["updates"]:
            parent_ids_to_clear.extend([e.entity_id for e in partitions["updates"]])

        # Clear old chunks for updates
        if parent_ids_to_clear:
            sync_context.logger.debug(
                f"Clearing {len(parent_ids_to_clear)} updated entities from destinations"
            )
            for dest in sync_context.destinations:
                await self._retry_destination_operation(
                    operation=lambda d=dest: d.bulk_delete_by_parent_ids(
                        parent_ids_to_clear, sync_context.sync.id
                    ),
                    operation_name="update clear",
                    sync_context=sync_context,
                )

        # Insert new chunks
        sync_context.logger.debug(f"Inserting {len(chunk_entities)} chunk entities to destinations")
        for dest in sync_context.destinations:
            await self._retry_destination_operation(
                operation=lambda d=dest: d.bulk_insert(chunk_entities),
                operation_name="insert",
                sync_context=sync_context,
            )

        sync_context.logger.debug("Destination persistence complete (commit point)")

    async def _persist_to_database(  # noqa: C901
        self,
        partitions: Dict[str, Any],
        sync_context: SyncContext,
    ) -> None:
        """Persist INSERT/UPDATE to PostgreSQL after destination success.

        Deletes handled separately in _handle_deletes().
        """
        from sqlalchemy.exc import DBAPIError

        from airweave import crud, schemas
        from airweave.db.session import get_db_context

        inserts = partitions["inserts"]
        updates = partitions["updates"]
        existing_map = partitions["existing_map"]

        if not inserts and not updates:
            return

        # Retry wrapper for deadlock handling
        async def _with_deadlock_retry(operation, max_retries=3):
            for attempt in range(max_retries + 1):
                try:
                    return await operation()
                except DBAPIError as e:
                    error_msg = str(e).lower()
                    is_deadlock = "deadlock detected" in error_msg

                    if is_deadlock and attempt < max_retries:
                        wait_time = 0.1 * (2**attempt)
                        sync_context.logger.warning(
                            f"Deadlock detected, retrying in {wait_time}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    raise

        async def _execute_db_operations():  # noqa: C901
            async with get_db_context() as db:
                # Handle INSERTs
                if inserts:
                    # Deduplicate within batch (same entity from different paths)
                    seen = {}
                    deduped = []
                    for entity in inserts:
                        if entity.entity_id in seen:
                            sync_context.logger.debug(
                                f"Duplicate in batch: {entity.entity_id} - using latest"
                            )
                            deduped[seen[entity.entity_id]] = entity
                        else:
                            seen[entity.entity_id] = len(deduped)
                            deduped.append(entity)

                    if len(deduped) < len(inserts):
                        sync_context.logger.debug(
                            f"Deduplicated {len(inserts)} → {len(deduped)} inserts"
                        )

                    # Build create objects (with deterministic ordering to avoid deadlock cycles)
                    ordered_entities: List[Tuple[UUID, BaseEntity]] = []
                    for entity in deduped:
                        entity_def_id = self._resolve_entity_definition_id(entity, sync_context)
                        if not entity_def_id:
                            raise SyncFailureError(
                                f"Entity type {entity.__class__.__name__} not in entity_map"
                            )
                        if not entity.airweave_system_metadata.hash:
                            raise SyncFailureError(f"Entity {entity.entity_id} missing hash")

                        ordered_entities.append((entity_def_id, entity))

                    if ordered_entities:
                        ordered_entities.sort(
                            key=lambda item: (item[0].int if item[0] else 0, item[1].entity_id)
                        )

                    create_objs = [
                        schemas.EntityCreate(
                            sync_job_id=sync_context.sync_job.id,
                            sync_id=sync_context.sync.id,
                            entity_id=entity.entity_id,
                            entity_definition_id=entity_def_id,
                            hash=entity.airweave_system_metadata.hash,
                        )
                        for entity_def_id, entity in ordered_entities
                    ]

                    # Diagnostics: record which worker is performing this DB batch
                    current_task = asyncio.current_task()
                    task_name = (
                        current_task.get_name()
                        if current_task and current_task.get_name()
                        else "unknown"
                    )
                    sample_ids = [entity.entity_id for _, entity in ordered_entities[:10]]
                    sync_context.logger.debug(
                        "[DB] Task %s upserting %d inserts (sample: %s)",
                        task_name,
                        len(create_objs),
                        sample_ids,
                    )

                    # Bulk upsert (handles cross-batch duplicates)
                    await crud.entity.bulk_create(db, objs=create_objs, ctx=sync_context.ctx)
                    sync_context.logger.debug(f"Created {len(create_objs)} DB records")

                # Handle UPDATEs
                if updates:
                    update_records = []
                    for entity in updates:
                        entity_def_id = self._resolve_entity_definition_id(entity, sync_context)
                        if entity_def_id is None:
                            raise SyncFailureError(
                                f"PROGRAMMING ERROR: UPDATE entity {entity.entity_id} "
                                f"type {entity.__class__.__name__} not in entity_map"
                            )
                        key = (entity.entity_id, entity_def_id)

                        if key not in existing_map:
                            raise SyncFailureError(
                                f"PROGRAMMING ERROR: UPDATE entity {entity.entity_id} not in "
                                f"existing_map. Entity was determined as UPDATE during action "
                                f"determination but DB record is missing."
                            )

                        if not entity.airweave_system_metadata.hash:
                            raise SyncFailureError(f"Entity {entity.entity_id} missing hash")

                        db_id = existing_map[key].id
                        new_hash = entity.airweave_system_metadata.hash
                        update_records.append((db_id, new_hash, entity))

                    if update_records:
                        update_records.sort(key=lambda item: item[0])
                        update_pairs = [(db_id, new_hash) for db_id, new_hash, _ in update_records]
                        current_task = asyncio.current_task()
                        task_name = (
                            current_task.get_name()
                            if current_task and current_task.get_name()
                            else "unknown"
                        )
                        sample_update_ids = [
                            entity.entity_id for _, _, entity in update_records[:10]
                        ]
                        sync_context.logger.debug(
                            "[DB] Task %s updating %d hashes (sample: %s)",
                            task_name,
                            len(update_pairs),
                            sample_update_ids,
                        )

                        await crud.entity.bulk_update_hash(db, rows=update_pairs)
                        sync_context.logger.debug(f"Updated {len(update_pairs)} hashes")

                # Commit the transaction
                await db.commit()

        # Execute with deadlock retry
        await _with_deadlock_retry(_execute_db_operations)

        # Increment guard rail usage for synced entities (inserts + updates)
        # Both count as "entities synced" since they represent work done
        total_synced = len(inserts) + len(updates)
        if total_synced > 0:
            await sync_context.guard_rail.increment(ActionType.ENTITIES, amount=total_synced)
            sync_context.logger.debug(
                f"Incremented guard_rail ENTITIES usage by {total_synced} "
                f"({len(inserts)} inserts + {len(updates)} updates)"
            )

        # Update entity state tracker for real-time UI updates via pubsub
        if hasattr(sync_context, "entity_state_tracker") and sync_context.entity_state_tracker:
            # Track inserts
            if inserts:
                counts_by_def: Dict[UUID, int] = defaultdict(int)
                sample_name_by_def: Dict[UUID, str] = {}
                for entity in inserts:
                    entity_def_id = self._resolve_entity_definition_id(entity, sync_context)
                    if entity_def_id:
                        counts_by_def[entity_def_id] += 1
                        sample_name_by_def.setdefault(entity_def_id, entity.__class__.__name__)

                for def_id, count in counts_by_def.items():
                    await sync_context.entity_state_tracker.update_entity_count(
                        entity_definition_id=def_id,
                        action="insert",
                        delta=count,
                        entity_name=sample_name_by_def.get(def_id),
                        entity_type=sample_name_by_def.get(def_id),
                    )

            # Track updates
            if updates:
                counts_by_def_updates: Dict[UUID, int] = defaultdict(int)
                for entity in updates:
                    entity_def_id = self._resolve_entity_definition_id(entity, sync_context)
                    if entity_def_id:
                        counts_by_def_updates[entity_def_id] += 1

                for def_id, count in counts_by_def_updates.items():
                    await sync_context.entity_state_tracker.update_entity_count(
                        entity_definition_id=def_id,
                        action="update",
                        delta=count,
                    )

        sync_context.logger.debug(
            f"Database persistence complete: {len(inserts)} inserts, {len(updates)} updates"
        )

    async def _update_progress(
        self,
        partitions: Dict[str, Any],
        sync_context: SyncContext,
    ) -> None:
        """Update sync progress counters."""
        counts = {
            "inserted": len(partitions["inserts"]),
            "updated": len(partitions["updates"]),
            "deleted": len(partitions["deletes"]),
            "kept": len(partitions["keeps"]),
        }

        for stat, count in counts.items():
            if count > 0:
                await sync_context.progress.increment(stat, count)

    # ------------------------------------------------------------------------------------
    # Retry Logic for Destination Operations - Helper Methods
    # ------------------------------------------------------------------------------------

    def _get_retryable_exception_types(self) -> tuple[type[Exception], ...]:
        """Get tuple of exception types that should be retried.

        Returns:
            Tuple of exception classes for transient errors (timeouts, connections, etc.)
        """
        retry_exception_types: tuple[type[Exception], ...] = (ConnectionError, TimeoutError)

        try:
            import httpcore
            import httpx

            retry_exception_types = (
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.ConnectTimeout,
                httpx.RemoteProtocolError,  # Server disconnected
                httpcore.ReadTimeout,
                httpcore.WriteTimeout,
                httpcore.ConnectTimeout,
                httpcore.RemoteProtocolError,
                ConnectionError,
                TimeoutError,
            )
        except ImportError:
            pass  # Use fallback

        # Add Qdrant-specific exceptions if available
        try:
            from qdrant_client.http.exceptions import ApiException

            # Catch all Qdrant API exceptions (base class catches UnexpectedResponse, etc.)
            retry_exception_types = retry_exception_types + (ApiException,)
        except ImportError:
            pass

        return retry_exception_types

    def _build_base_error_context(
        self,
        e: Exception,
        operation_name: str,
        attempt_count: int,
        sync_context: SyncContext,
    ) -> dict:
        """Build base error context with operation and sync details.

        Args:
            e: Exception that occurred
            operation_name: Human-readable operation name
            attempt_count: Current attempt number
            sync_context: Sync context with sync/job IDs and source

        Returns:
            Dict with base error context
        """
        return {
            "operation_name": operation_name,
            "exception_type": type(e).__name__,
            "exception_message": str(e)[:500],
            "attempt": attempt_count,
            "max_attempts": 4,
            "sync_id": str(sync_context.sync.id),
            "sync_job_id": str(sync_context.sync_job.id),
            "source_name": sync_context.source._short_name,
        }

    async def _add_destination_details_to_error_context(
        self,
        error_context: dict,
        sync_context: SyncContext,
        attempt_count: int,
    ) -> None:
        """Add destination details and health info to error context.

        Args:
            error_context: Error context dict to enrich
            sync_context: Sync context with destinations
            attempt_count: Current attempt number (health fetched on attempt 1)
        """
        if not sync_context.destinations:
            return

        dest = sync_context.destinations[0]
        error_context["destination_type"] = dest.__class__.__name__

        if hasattr(dest, "collection_name"):
            error_context["collection_name"] = dest.collection_name
        if hasattr(dest, "collection_id"):
            error_context["collection_id"] = str(dest.collection_id)
        if hasattr(dest, "url"):
            error_context["destination_url"] = dest.url or "native"

        # Fetch collection health info on first retry attempt for diagnostics
        if attempt_count == 1 and hasattr(dest, "get_collection_health_info"):
            try:
                health_info = await dest.get_collection_health_info()
                error_context["collection_health"] = health_info
            except Exception:
                pass  # Don't fail on diagnostics

    def _extract_qdrant_error_details(self, e: Exception, error_context: dict) -> None:
        """Extract Qdrant-specific error details from exception.

        Args:
            e: Exception to extract from
            error_context: Error context dict to enrich
        """
        try:
            from qdrant_client.http.exceptions import UnexpectedResponse

            if not isinstance(e, UnexpectedResponse):
                return

            error_context["http_status"] = e.status_code
            error_context["reason_phrase"] = e.reason_phrase

            # Try to extract structured error from Qdrant
            try:
                error_data = e.structured()
                if isinstance(error_data.get("status"), dict):
                    error_context["qdrant_error"] = error_data["status"].get("error")
                else:
                    qdrant_status = error_data.get("status")
                    qdrant_msg = error_data.get("message")
                    error_context["qdrant_error"] = qdrant_status or qdrant_msg
                error_context["qdrant_full_response"] = error_data
            except Exception:
                # Fallback to raw content
                if e.content:
                    raw_content = e.content.decode("utf-8")[:500]
                    error_context["qdrant_raw_response"] = raw_content
        except ImportError:
            pass

    def _extract_http_error_details(self, e: Exception, error_context: dict) -> None:
        """Extract HTTP request details from exception if available.

        Args:
            e: Exception to extract from
            error_context: Error context dict to enrich
        """
        if hasattr(e, "request"):
            try:
                error_context["request_method"] = e.request.method
                error_context["request_url"] = str(e.request.url)
            except Exception:
                pass

    def _is_permanent_error(
        self,
        e: Exception,
        operation_name: str,
        error_context: dict,
        sync_context: SyncContext,
    ) -> bool:
        """Check if error is permanent (auth, not found) and log accordingly.

        Args:
            e: Exception to check
            operation_name: Human-readable operation name
            error_context: Error context dict for logging
            sync_context: Sync context with logger

        Returns:
            True if error is permanent (should not retry)
        """
        error_msg = str(e).lower()
        permanent_indicators = ["401", "403", "404", "400", "unauthorized", "forbidden"]

        if any(indicator in error_msg for indicator in permanent_indicators):
            error_context["is_permanent"] = True
            sync_context.logger.error(
                f"🚫 Destination '{operation_name}' permanent error: {type(e).__name__}",
                extra={"error_context": error_context},
            )
            # Log full error details
            sync_context.logger.error(f"[Destination] Error context: {error_context}")
            return True

        return False

    async def _build_final_error_context(
        self,
        e: Exception,
        operation_name: str,
        attempt_count: int,
        total_time: float,
        sync_context: SyncContext,
    ) -> dict:
        """Build comprehensive error context for final failure logging.

        Args:
            e: Exception that occurred
            operation_name: Human-readable operation name
            attempt_count: Total attempts made
            total_time: Total time elapsed across all retries
            sync_context: Sync context

        Returns:
            Dict with comprehensive final error context
        """
        final_error_context = {
            "operation_name": operation_name,
            "exception_type": type(e).__name__,
            "exception_message": str(e)[:500],
            "total_attempts": attempt_count,
            "total_time_seconds": round(total_time, 2),
            "sync_id": str(sync_context.sync.id),
            "sync_job_id": str(sync_context.sync_job.id),
            "source_name": sync_context.source._short_name,
            "retries_exhausted": True,
        }

        # Add destination details and health info
        if sync_context.destinations:
            dest = sync_context.destinations[0]
            final_error_context["destination_type"] = dest.__class__.__name__
            if hasattr(dest, "collection_name"):
                final_error_context["collection_name"] = dest.collection_name

            # Fetch collection health for final error diagnostics
            if hasattr(dest, "get_collection_health_info"):
                try:
                    health_info = await dest.get_collection_health_info()
                    final_error_context["collection_health"] = health_info
                except Exception:
                    pass  # Don't fail on diagnostics

        return final_error_context

    # ------------------------------------------------------------------------------------
    # Retry Logic for Destination Operations - Main Method
    # ------------------------------------------------------------------------------------

    async def _retry_destination_operation(
        self,
        operation: Callable,
        operation_name: str,
        sync_context: SyncContext,
    ):
        """Retry a destination operation with exponential backoff for transient errors.

        Uses tenacity to retry specific exception types (timeouts, disconnections, rate limits).
        Permanent errors (auth, not found) fail immediately without retry.

        Args:
            operation: Async callable to retry
            operation_name: Human-readable operation name for logging
            sync_context: Sync context with logger

        Returns:
            Result of the operation

        Raises:
            SyncFailureError: After all retries exhausted or on permanent errors
        """
        # Get retryable exception types
        retry_exception_types = self._get_retryable_exception_types()

        # Track retry attempts and timing for detailed logging
        attempt_count = 0
        first_error_time = None

        @retry(
            retry=retry_if_exception_type(retry_exception_types),
            stop=stop_after_attempt(4),  # 1 initial + 3 retries = 4 total
            wait=wait_exponential(multiplier=2, min=2, max=60),  # 2s, 4s, 8s, 16s
            reraise=True,
        )
        async def _execute_with_retry():
            nonlocal attempt_count, first_error_time
            attempt_count += 1

            try:
                return await operation()
            except Exception as e:
                # Track first error time
                if first_error_time is None:
                    first_error_time = time.time()

                # Build error context using helper methods
                error_context = self._build_base_error_context(
                    e, operation_name, attempt_count, sync_context
                )
                await self._add_destination_details_to_error_context(
                    error_context, sync_context, attempt_count
                )
                self._extract_qdrant_error_details(e, error_context)
                self._extract_http_error_details(e, error_context)

                # Check for permanent errors and handle accordingly
                if self._is_permanent_error(e, operation_name, error_context, sync_context):
                    raise SyncFailureError(f"Destination {operation_name} failed: {e}")

                # Log retry attempt with full context
                if attempt_count < 4:
                    next_wait = 2 * (2 ** (attempt_count - 1))
                    sync_context.logger.warning(
                        f"⚠️  Destination '{operation_name}' retry {attempt_count}/4: "
                        f"{type(e).__name__} - retrying in {next_wait}s",
                        extra={"error_context": error_context},
                    )

                # Let other exceptions bubble up for tenacity to handle
                raise

        try:
            return await _execute_with_retry()
        except SyncFailureError:
            raise  # Already wrapped
        except Exception as e:
            # Retries exhausted - build final error context
            total_time = time.time() - first_error_time if first_error_time else 0
            final_error_context = await self._build_final_error_context(
                e, operation_name, attempt_count, total_time, sync_context
            )

            sync_context.logger.error(
                f"💥 Destination '{operation_name}' failed after {attempt_count} attempts "
                f"over {total_time:.1f}s: {type(e).__name__}",
                extra={"error_context": final_error_context},
                exc_info=True,
            )
            sync_context.logger.error(f"[Destination] Final error context: {final_error_context}")
            raise SyncFailureError(f"Destination {operation_name} failed: {e}")

    # ------------------------------------------------------------------------------------
    # File Cleanup
    # ------------------------------------------------------------------------------------

    async def _cleanup_processed_files(
        self,
        partitions: Dict[str, Any],
        sync_context: SyncContext,
    ) -> None:
        """Delete temporary files after batch processing (progressive cleanup).

        Called after entities are persisted to destinations and database.
        Raises SyncFailureError if deletion fails to prevent disk space issues.

        Args:
            partitions: Entity partitions from _determine_actions
            sync_context: Sync context with logger
        """
        entities_to_clean = partitions["inserts"] + partitions["updates"]
        cleaned_count = 0
        failed_deletions = []

        for entity in entities_to_clean:
            # Only clean up file entities (FileEntity includes EmailEntity and CodeFileEntity)
            if not isinstance(entity, FileEntity):
                continue

            # FileEntity without local_path is a programming error - should never reach here
            if not hasattr(entity, "local_path") or not entity.local_path:
                raise SyncFailureError(
                    f"FileEntity {entity.__class__.__name__}[{entity.entity_id}] "
                    f"has no local_path after processing. This indicates download/save failed "
                    f"but entity was not filtered out."
                )

            local_path = entity.local_path

            try:
                # Delete the file
                if os.path.exists(local_path):
                    os.remove(local_path)

                    # Verify deletion succeeded
                    if os.path.exists(local_path):
                        failed_deletions.append(local_path)
                        sync_context.logger.error(f"Failed to delete temp file: {local_path}")
                    else:
                        cleaned_count += 1
                        sync_context.logger.debug(f"Deleted temp file: {local_path}")

            except Exception as e:
                failed_deletions.append(local_path)
                sync_context.logger.error(f"Error deleting temp file {local_path}: {e}")

        # Report cleanup results
        if cleaned_count > 0:
            sync_context.logger.debug(f"Progressive cleanup: deleted {cleaned_count} temp files")

        # Fail the sync if any deletions failed (prevent disk space issues)
        if failed_deletions:
            raise SyncFailureError(
                f"Failed to delete {len(failed_deletions)} temp files. "
                f"This can cause pod eviction. Files: {failed_deletions[:5]}"
            )

    async def cleanup_temp_files(self, sync_context: SyncContext) -> None:
        """Remove entire sync_job_id directory (final cleanup safety net).

        Called in orchestrator's finally block to ensure cleanup happens even if
        pipeline fails. Removes entire /tmp/airweave/processing/{sync_job_id}/ directory.

        This catches any files missed by progressive cleanup if sync failed mid-batch.

        Args:
            sync_context: Sync context with source and logger

        Note:
            Some sources don't download files (e.g., Airtable, Jira without attachments).
            For these sources, file_downloader won't be set, which is expected.
        """
        try:
            # Check if source has file downloader
            # Note: Not all sources have file_downloader (e.g., API-only sources)
            if not hasattr(sync_context.source, "file_downloader"):
                sync_context.logger.debug(
                    "Source has no file downloader (API-only source), skipping temp cleanup"
                )
                return

            downloader = sync_context.source.file_downloader
            if downloader is None:
                sync_context.logger.debug("File downloader not initialized, skipping temp cleanup")
                return

            # Downloader knows its own sync_job_id from initialization
            # Stored as self.sync_job_id and used in self.base_temp_dir
            await downloader.cleanup_sync_directory(sync_context.logger)

        except Exception as e:
            # Log but don't raise - we're in a finally block
            # The original sync error (if any) should propagate, not be masked by cleanup errors
            sync_context.logger.warning(
                f"Final temp file cleanup failed (non-fatal): {e}", exc_info=True
            )
