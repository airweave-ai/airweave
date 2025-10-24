"""Module for entity pipeline."""

import asyncio
import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

import aiofiles

from airweave import crud, models
from airweave.db.session import get_db_context
from airweave.platform.entities._base import BaseEntity, CodeFileEntity, FileEntity
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.exceptions import EntityProcessingError, SyncFailureError


class EntityPipeline:
    """Pipeline for processing entities with stateful tracking across sync lifecycle."""

    def __init__(self):
        """Initialize pipeline with empty entity tracking."""
        self._entity_ids_encountered_by_type: Dict[str, Set[str]] = {}
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
        async with get_db_context() as db:
            stored_entities = await crud.entity.get_by_sync_id(db=db, sync_id=sync_context.sync.id)

        if not stored_entities:
            return []

        encountered_ids = set().union(*self._entity_ids_encountered_by_type.values())
        return [e for e in stored_entities if e.entity_id not in encountered_ids]

    async def _remove_orphaned_entities(
        self, orphaned_entities: List[models.Entity], sync_context: SyncContext
    ) -> None:
        """Remove orphaned entities from destinations and database, update trackers."""
        entity_ids = [e.entity_id for e in orphaned_entities]
        db_ids = [e.id for e in orphaned_entities]

        for destination in sync_context.destinations:
            await destination.bulk_delete(entity_ids, sync_context.sync.id)

        async with get_db_context() as db:
            await crud.entity.bulk_remove(db=db, ids=db_ids, ctx=sync_context.ctx)

        await sync_context.progress.increment("deleted", len(orphaned_entities))
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
        """Process a list of entities.

        - pubsub
        - batching
        - config

        0. [X] Determine action
            0.1 [X] Compute hash
        1. [ ] Create embeddable text
            1.1 [ ] create MD from embeddable fields
            1.2 [ ] convert local file to MD
        2. [ ] Chunk
        3. [ ] Embed
            - keyword vector has to be on full entity
        4. [ ] AirweaveSystemMetadata
        5. [ ] Persist
        """
        unique_entities = await self._filter_duplicates(entities, sync_context)

        if not unique_entities:
            sync_context.logger.debug("All entities in batch were duplicates, skipping processing")
            return

        await self._enrich_early_metadata(unique_entities, sync_context)

        # Hash computation (sets hash field on each entity)
        await self.compute_hashes_for_batch(unique_entities, sync_context)

        # Determine actions (reads hash from entity field)
        partitions = await self._determine_actions(unique_entities, sync_context)

        # Early exit: If nothing needs to be processed (only KEEP entities)
        if not any(partitions[k] for k in ("inserts", "updates", "deletes")):
            if partitions["keeps"]:
                await sync_context.progress.increment("kept", len(partitions["keeps"]))
                sync_context.logger.info(
                    f"All {len(partitions['keeps'])} entities unchanged - skipping pipeline"
                )
            return

        # Build textual representations for inserts and updates
        entities_to_process = partitions["inserts"] + partitions["updates"]
        if not entities_to_process:
            sync_context.logger.debug("No entities to process after action determination")
            return

        sync_context.logger.info(
            f"Building textual representations for {len(entities_to_process)} entities"
        )
        await self._build_textual_representations(entities_to_process, sync_context)

        # Sanity check: All entities MUST have textual_representation after this step
        # If any don't, it's a programming error (not entity-level error)
        for entity in entities_to_process:
            if not hasattr(entity, "textual_representation") or not entity.textual_representation:
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: Entity {entity.__class__.__name__}[{entity.entity_id}] "
                    f"has no textual_representation after _build_textual_representations(). "
                    f"This should never happen - failed entities should be removed from the list."
                )

        # Print textual representations for verification
        print("\n" + "=" * 80)
        print("TEXTUAL REPRESENTATIONS:")
        print("=" * 80)

        for i, entity in enumerate(entities_to_process, 1):
            print(f"\n[{i}] {entity.__class__.__name__}[{entity.entity_id}]")
            print("-" * 80)
            # Print first 10000 characters
            print(entity.textual_representation[:10000])
            if len(entity.textual_representation) > 10000:
                print("...")
            print("-" * 80)

        # Chunk entities (entity multiplication: 1 entity → N chunk entities)
        # entities_to_process may be empty if all failed conversion (handled in method)
        if not entities_to_process:
            sync_context.logger.debug("No entities to chunk - all failed conversion")
            return

        chunk_entities = await self._chunk_entities(entities_to_process, sync_context)

        # Print chunks for verification (first 5 entities, first 3 chunks each)
        if chunk_entities:
            print("\n" + "=" * 80)
            print(f"CHUNK ENTITIES (showing first 10 of {len(chunk_entities)}):")
            print("=" * 80)

            displayed = 0
            current_entity_id = None
            entity_chunk_count = 0

            for chunk_entity in chunk_entities:
                if displayed >= 10:
                    break

                chunk_idx = chunk_entity.airweave_system_metadata.chunk_index
                token_count = len(chunk_entity.textual_representation.split())  # Approximate

                # Track when we move to a new entity
                if chunk_entity.entity_id != current_entity_id:
                    current_entity_id = chunk_entity.entity_id
                    entity_chunk_count = 1
                else:
                    entity_chunk_count += 1

                # Only show first 3 chunks per entity
                if entity_chunk_count <= 3:
                    print(
                        f"[{displayed + 1}] {chunk_entity.__class__.__name__}"
                        f"[{chunk_entity.entity_id}] chunk_index={chunk_idx}, ~{token_count} tokens"
                    )
                    preview = chunk_entity.textual_representation[:100].replace("\n", " ")
                    print(f"    Preview: {preview}...")
                    displayed += 1

            if len(chunk_entities) > 10:
                print(f"\n... and {len(chunk_entities) - 10} more chunk entities")

        # Replace entities_to_process with chunk entities for next stages
        entities_to_process = chunk_entities

        # FUTURE: Embed chunk entities (sets vectors field)
        # FUTURE: Persist chunk entities (sets db_entity_id, timestamps)

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
            self._entity_ids_encountered_by_type.setdefault(entity_type, set())

            # Check if we've already seen this entity ID for this type
            if entity.entity_id in self._entity_ids_encountered_by_type[entity_type]:
                skipped_count += 1
                sync_context.logger.debug(
                    f"Skipping duplicate entity: {entity_type}[{entity.entity_id}]"
                )
                continue

            # Mark as encountered and add to unique list
            self._entity_ids_encountered_by_type[entity_type].add(entity.entity_id)
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

    async def _enrich_early_metadata(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> None:
        """Set early metadata fields from sync_context.

        Sets: source_name, entity_type, sync_id, sync_job_id, sync_metadata

        These fields are available immediately and don't depend on processing stages.
        All entities MUST have airweave_system_metadata initialized after this.

        Args:
            entities: List of entities to enrich
            sync_context: Sync context containing metadata

        Raises:
            SyncFailureError: If metadata initialization or validation fails
        """
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
            entity.airweave_system_metadata.sync_metadata = sync_context.sync.sync_metadata

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

    async def compute_hashes_for_batch(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> None:
        """Compute hashes for entire batch and set on entity.airweave_system_metadata.hash.

        This method sets the hash field directly on each entity instead of returning
        a dictionary. Failed entities are removed from the list and marked as skipped.

        Args:
            entities: List of entities to compute hashes for (modified in-place)
            sync_context: Sync context for logging

        Raises:
            SyncFailureError: If validation fails after hash computation
        """
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
        """Partition entities by action (INSERT/UPDATE/DELETE/KEEP).

        Reads hash from entity.airweave_system_metadata.hash (set during hash computation).

        Args:
            entities: List of entities with hashes already set
            sync_context: Sync context

        Returns:
            Dict with partitions: inserts, updates, keeps, deletes, existing_map

        Raises:
            SyncFailureError: If entity is missing hash or other required fields
        """
        from airweave.platform.entities._base import DeletionEntity

        # Step 1: Separate deletions from non-deletions
        deletes = [
            e for e in entities if isinstance(e, DeletionEntity) and e.deletion_status == "removed"
        ]
        non_deletes = [e for e in entities if e not in deletes]

        # Step 2: Build entity requests with definition IDs
        entity_requests = []
        for entity in non_deletes:
            entity_definition_id = sync_context.entity_map.get(entity.__class__)
            if entity_definition_id is None:
                # Entity type not in map → fatal error
                sync_context.logger.error(
                    f"Entity type {entity.__class__.__name__} not found in entity_map"
                )
                raise SyncFailureError(
                    f"Entity type {entity.__class__.__name__} not in sync_context.entity_map"
                )
            entity_requests.append((entity.entity_id, entity_definition_id))

        # Step 3: Bulk fetch existing DB records with composite key lookup
        existing_map: Dict[tuple[str, UUID], models.Entity] = {}
        if entity_requests:
            try:
                async with get_db_context() as db:
                    existing_map = await crud.entity.bulk_get_by_entity_sync_and_definition(
                        db,
                        sync_id=sync_context.sync.id,
                        entity_requests=entity_requests,
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
            entity_definition_id = sync_context.entity_map[entity.__class__]

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
        for field_name, field_info in entity.model_fields.items():
            if field_info.json_schema_extra and isinstance(field_info.json_schema_extra, dict):
                if field_info.json_schema_extra.get("embeddable"):
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

        Args:
            entity: Entity to build metadata for
            source_name: Name of the source

        Returns:
            Markdown formatted metadata section
        """
        entity_type = entity.__class__.__name__
        lines = [
            "# Metadata",
            "",
            f"**Source**: {source_name}",
            f"**Type**: {entity_type}",
            f"**Name**: {entity.name}",
        ]

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
        }

        converter = converter_map.get(ext)
        if not converter:
            raise EntityProcessingError(f"Unsupported file type: {ext}")

        return converter

    async def _build_textual_representations(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> None:
        """Build textual_representation with batch-optimized conversion.

        Steps:
        1. Build metadata and write directly to entity.textual_representation
        2. Partition FileEntities by converter based on file extension
        3. Batch convert each partition
        4. Append content to entity.textual_representation

        Args:
            entities: List of entities to process (inserts/updates only)
            sync_context: Sync context for source metadata

        Raises:
            EntityProcessingError: If metadata is empty, local_path missing,
                                  file type unsupported, or conversion fails
        """
        source_name = sync_context.source._short_name

        # Step 1: Build metadata sections and write directly to entities
        async def _build_metadata(entity: BaseEntity):
            metadata = self._build_metadata_section(entity, source_name)
            if not metadata:
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

        for converter, file_entities in converter_groups.items():
            file_paths = [e.local_path for e in file_entities]

            try:
                # Batch convert returns Dict[file_path, text_content]
                results = await converter.convert_batch(file_paths)

                # Append content to each entity's textual_representation
                # Track entities that fail (None results)
                for entity in file_entities:
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

            except Exception as e:
                # Unexpected error - mark entire batch as failed but continue with other converters
                converter_name = converter.__class__.__name__
                sync_context.logger.error(
                    f"Batch conversion failed for {converter_name}: {e}", exc_info=True
                )
                # Mark all entities in this batch as failed
                failed_entities.extend(file_entities)
                # Log each entity being skipped
                for entity in file_entities:
                    sync_context.logger.warning(
                        f"Skipping {entity.__class__.__name__}[{entity.entity_id}] "
                        f"due to batch failure"
                    )
                # Don't raise - continue with other converters

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

    async def _chunk_entities(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> List[BaseEntity]:
        """Chunk entities and create new chunk entities (entity multiplication).

        Transforms 1 entity with full textual_representation into N chunk entities,
        each with unique chunk_index and chunk text in textual_representation.

        Example:
            Input:  [FileEntity(id="f1", textual_representation=20000 chars, chunk_index=None)]
            Output: [FileEntity(id="f1", chunk_index=0, textual_representation=chunk1_text),
                     FileEntity(id="f1", chunk_index=1, textual_representation=chunk2_text),
                     FileEntity(id="f1", chunk_index=2, textual_representation=chunk3_text)]

        Sets: airweave_system_metadata.chunk_index

        Args:
            entities: List of entities with textual_representation set
            sync_context: Sync context for logging

        Returns:
            List of chunk entities (length >= len(entities))

        Raises:
            SyncFailureError: If chunker initialization or critical errors occur
        """
        if not entities:
            # Can happen if all entities failed conversion
            sync_context.logger.debug(
                "No entities to chunk - all failed conversion (already marked as skipped)"
            )
            return []

        # Get singleton chunker (loads ~330MB model once per pod)
        from airweave.platform.chunkers.semantic import SemanticChunker

        chunker = SemanticChunker()

        # Extract textual representations (order preserved for matching)
        texts = [e.textual_representation for e in entities]

        sync_context.logger.info(
            f"Chunking {len(texts)} entities with SemanticChunker "
            f"(max {chunker.MAX_TOKENS_PER_CHUNK} tokens per chunk)"
        )

        # Chunk batch (local inference, no API calls, no rate limiting needed)
        try:
            chunk_lists = await chunker.chunk_batch(texts)
        except SyncFailureError:
            # Model loading or critical error - fail sync
            raise
        except Exception as e:
            # Unexpected error - also fail sync (chunking is critical)
            raise SyncFailureError(f"Chunking batch processing failed: {e}")

        # Create chunk entities (entity multiplication)
        chunk_entities = []
        failed_entities = []

        for entity, chunks in zip(entities, chunk_lists, strict=True):
            # Check if chunking produced valid results
            if not chunks:
                # No chunks produced - shouldn't happen but handle gracefully
                sync_context.logger.warning(
                    f"Chunking produced no chunks for "
                    f"{entity.__class__.__name__}[{entity.entity_id}] - skipping entity"
                )
                failed_entities.append(entity)
                continue

            # Create one new entity per chunk
            for chunk_idx, chunk in enumerate(chunks):
                # Validate chunk has text
                if not chunk["text"] or not chunk["text"].strip():
                    sync_context.logger.error(
                        f"Empty chunk produced for {entity.__class__.__name__}[{entity.entity_id}] "
                        f"- skipping entire entity"
                    )
                    failed_entities.append(entity)
                    break  # Skip entire entity if any chunk is empty

                # Clone entity with deep copy (preserves all parent metadata)
                chunk_entity = entity.model_copy(deep=True)

                # Set chunk-specific fields
                chunk_entity.textual_representation = chunk["text"]

                # Metadata must exist at this point (set during early enrichment)
                if chunk_entity.airweave_system_metadata is None:
                    raise SyncFailureError(
                        f"PROGRAMMING ERROR: No airweave_system_metadata for entity "
                        f"{entity.entity_id} after early enrichment"
                    )

                # Set chunk_index (direct field assignment, no mapping needed!)
                chunk_entity.airweave_system_metadata.chunk_index = chunk_idx

                chunk_entities.append(chunk_entity)

            # Log entity multiplication
            if failed_entities and entity in failed_entities:
                continue  # Don't log if entity failed

            sync_context.logger.debug(
                f"{entity.__class__.__name__}[{entity.entity_id}]: "
                f"multiplied into {len(chunks)} chunk entities"
            )

        # Mark failed entities as skipped
        if failed_entities:
            # Remove duplicates (entity may appear multiple times if multiple chunks failed)
            failed_entities = list(set(failed_entities))
            await sync_context.progress.increment("skipped", len(failed_entities))
            sync_context.logger.warning(
                f"Skipped {len(failed_entities)} entities that produced empty/invalid chunks"
            )

        # Validate all chunk entities have chunk_index set
        for chunk_entity in chunk_entities:
            if chunk_entity.airweave_system_metadata.chunk_index is None:
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: chunk_index not set for chunk entity "
                    f"{chunk_entity.entity_id} after chunking"
                )

        sync_context.logger.info(
            f"Entity multiplication: {len(entities)} entities → "
            f"{len(chunk_entities)} chunk entities"
        )

        # Calculate and log chunk statistics (using actual tiktoken token counts)
        if chunk_entities:
            import tiktoken

            tokenizer = tiktoken.get_encoding("cl100k_base")
            token_counts = [
                len(tokenizer.encode(chunk_entity.textual_representation))
                for chunk_entity in chunk_entities
            ]

            min_tokens = min(token_counts)
            max_tokens = max(token_counts)
            avg_tokens = sum(token_counts) / len(token_counts)

            sync_context.logger.info(
                f"Chunk token statistics: min={min_tokens}, max={max_tokens}, avg={avg_tokens:.1f}"
            )

        return chunk_entities
