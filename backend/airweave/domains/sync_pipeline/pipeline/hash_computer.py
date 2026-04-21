"""Hash computation for entity change detection."""

import asyncio
import hashlib
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from airweave.domains.sync_pipeline.async_helpers import run_in_thread_pool
from airweave.domains.sync_pipeline.exceptions import EntityProcessingError, SyncFailureError
from airweave.domains.sync_pipeline.pipeline.entity_hasher import (
    compute_dict_hash,
    exclude_volatile_fields,
    stable_serialize,
)
from airweave.platform.entities._base import BaseEntity, CodeFileEntity, FileEntity

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.contexts import SyncContext
    from airweave.domains.sync_pipeline.contexts.runtime import SyncRuntime


class HashComputer:
    """Computes stable content hashes for entities to detect changes.

    Handles:
    - Stable serialization of entity data
    - File content hashing for FileEntity/CodeFileEntity
    - Batch hash computation with semaphore-controlled concurrency
    """

    # ------------------------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------------------------

    async def compute_for_batch(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
        stored_data: Optional[Dict[str, str]] = None,
    ) -> None:
        """Compute hashes for entire batch and set on entity.airweave_system_metadata.hash.

        Args:
            entities: List of entities to compute hashes for
            sync_context: Sync context with logger
            runtime: Sync runtime with live services
            stored_data: Mapping of entity_id -> stored content_hash for entities
                whose source_hash matched. Allows skipping file reads.

        Note:
            Modifies entities in-place, setting airweave_system_metadata.hash.
            Failed entities are removed from the list and counted as skipped.

        Raises:
            SyncFailureError: If any entity has no hash after computation (programming error)
        """
        if not entities:
            return

        # Compute all hashes concurrently with semaphore control
        results = await self._compute_hashes_concurrently(
            entities, sync_context, stored_data=stored_data
        )

        # Process results and handle failures
        await self._process_hash_results(entities, results, sync_context, runtime)

        # Validate all remaining entities have hash set
        self._validate_hashes(entities)

    async def compute_for_entity(
        self,
        entity: BaseEntity,
        stored_content_hash: Optional[str] = None,
    ) -> Optional[str]:
        """Compute stable content hash for a single entity.

        Args:
            entity: Entity to compute hash for
            stored_content_hash: If provided, reuse this content hash instead of reading
                the file. Used when source_hash matched the stored value.

        Returns:
            SHA256 hash hex digest, or None on failure

        Raises:
            EntityProcessingError: If file entity is missing local_path or file read fails
        """
        try:
            # Step 1: Get entity dict
            entity_dict = entity.model_dump(mode="python", exclude_none=True)

            # Step 2: For file entities, compute and add content hash
            if isinstance(entity, (FileEntity, CodeFileEntity)):
                if stored_content_hash is not None:
                    content_hash = stored_content_hash
                else:
                    content_hash = await self._compute_file_content_hash(entity)
                entity_dict["_content_hash"] = content_hash
                # Store on entity metadata for persistence
                if entity.airweave_system_metadata is not None:
                    entity.airweave_system_metadata._computed_content_hash = content_hash

            # Step 3: Exclude volatile fields
            content_dict = self._exclude_volatile_fields(entity, entity_dict)

            # Step 4: Stable serialize and hash
            return self._compute_dict_hash(content_dict)

        except EntityProcessingError:
            raise
        except Exception:
            raise

    # ------------------------------------------------------------------------------------
    # Batch Processing
    # ------------------------------------------------------------------------------------

    async def _compute_hashes_concurrently(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
        stored_data: Optional[Dict[str, str]] = None,
    ) -> List[Tuple[Tuple[str, str], Optional[str]]]:
        """Compute hashes for all entities concurrently with semaphore control.

        Args:
            entities: Entities to hash
            sync_context: Sync context with logger
            stored_data: Mapping of entity_id -> stored content_hash

        Returns:
            List of ((entity_type, entity_id), hash_value) tuples
        """
        # Limit concurrent file reads
        semaphore = asyncio.Semaphore(10)

        async def compute_with_semaphore(
            entity: BaseEntity,
        ) -> Tuple[Tuple[str, str], Optional[str]]:
            async with semaphore:
                entity_key = (entity.__class__.__name__, entity.entity_id)
                # Look up stored content_hash for source-hash-matched entities
                reuse_content_hash: Optional[str] = None
                if stored_data and entity.entity_id:
                    reuse_content_hash = stored_data.get(entity.entity_id)
                try:
                    hash_value = await self.compute_for_entity(
                        entity, stored_content_hash=reuse_content_hash
                    )
                    return entity_key, hash_value
                except EntityProcessingError as e:
                    sync_context.logger.warning(
                        f"Hash computation failed for {entity.__class__.__name__}"
                        f"[{entity.entity_id}]: {e}"
                    )
                    return entity_key, None
                except Exception as e:
                    sync_context.logger.warning(
                        f"Unexpected error computing hash for {entity.__class__.__name__}"
                        f"[{entity.entity_id}]: {e}"
                    )
                    return entity_key, None

        return await asyncio.gather(*[compute_with_semaphore(e) for e in entities])

    async def _process_hash_results(
        self,
        entities: List[BaseEntity],
        results: List[Tuple[Tuple[str, str], Optional[str]]],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Process hash computation results, handling failures.

        Args:
            entities: Original entity list (modified in-place)
            results: List of ((entity_type, entity_id), hash_value) tuples
            sync_context: Sync context for logging and progress tracking
            runtime: Sync runtime with live services
        """
        failed_entities = []
        file_count = 0
        regular_count = 0

        for entity, (_, hash_value) in zip(entities, results, strict=True):
            if hash_value is not None:
                entity.airweave_system_metadata.hash = hash_value

                if isinstance(entity, (FileEntity, CodeFileEntity)):
                    file_count += 1
                else:
                    regular_count += 1
            else:
                failed_entities.append(entity)

        # Remove failed entities and mark as skipped
        for entity in failed_entities:
            entities.remove(entity)

        if failed_entities:
            # TODO: Record this through exception handling instead
            await runtime.entity_tracker.record_skipped(len(failed_entities))

            sync_context.logger.warning(
                f"Skipped {len(failed_entities)} entities with hash computation failures"
            )

        sync_context.logger.debug(
            f"Computed {file_count + regular_count} hashes: "
            f"{file_count} files, {regular_count} regular entities"
        )

    def _validate_hashes(self, entities: List[BaseEntity]) -> None:
        """Validate all entities have hash set.

        Args:
            entities: Entities to validate

        Raises:
            SyncFailureError: If any entity is missing a hash
        """
        for entity in entities:
            if not entity.airweave_system_metadata.hash:
                raise SyncFailureError(
                    f"PROGRAMMING ERROR: Hash not set for entity "
                    f"{entity.entity_id} after computation"
                )

    # ------------------------------------------------------------------------------------
    # File Content Hashing
    # ------------------------------------------------------------------------------------

    async def _compute_file_content_hash(self, entity: BaseEntity) -> str:
        """Compute SHA256 hash of file content.

        Args:
            entity: FileEntity or CodeFileEntity with local_path

        Returns:
            Hex digest of file content hash

        Raises:
            EntityProcessingError: If local_path missing or file read fails
        """
        local_path = getattr(entity, "local_path", None)
        if not local_path:
            raise EntityProcessingError(
                f"FileEntity {entity.__class__.__name__}[{entity.entity_id}] "
                f"missing local_path - cannot compute hash"
            )

        try:
            return await run_in_thread_pool(self._sync_hash_file, str(local_path))
        except Exception as e:
            raise EntityProcessingError(
                f"Failed to read file for {entity.__class__.__name__}[{entity.entity_id}] "
                f"at {local_path}: {e}"
            ) from e

    @staticmethod
    def _sync_hash_file(path: str) -> str:
        """Hash file content synchronously in a single thread-pool dispatch."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):  # 64KB chunks
                h.update(chunk)
        return h.hexdigest()

    # ------------------------------------------------------------------------------------
    # Serialization and Hashing (delegated to entity_hasher)
    # ------------------------------------------------------------------------------------

    @staticmethod
    def _exclude_volatile_fields(entity: BaseEntity, entity_dict: dict) -> dict:
        return exclude_volatile_fields(entity, entity_dict)

    @staticmethod
    def _compute_dict_hash(content_dict: dict) -> str:
        return compute_dict_hash(content_dict)

    @staticmethod
    def _stable_serialize(obj: Any) -> Any:
        return stable_serialize(obj)


# Singleton instance
hash_computer = HashComputer()
