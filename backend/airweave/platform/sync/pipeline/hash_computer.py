"""Hash computation for entity change detection."""

import asyncio
import hashlib
import json
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from airweave.core.shared_models import AirweaveFieldFlag
from airweave.platform.entities._base import BaseEntity, CodeFileEntity, FileEntity
from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.sync.exceptions import EntityProcessingError, SyncFailureError

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


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
    ) -> None:
        """Compute hashes for entire batch and set on entity.airweave_system_metadata.hash.

        Args:
            entities: List of entities to compute hashes for
            sync_context: Sync context with logger

        Note:
            Modifies entities in-place, setting airweave_system_metadata.hash.
            Failed entities are removed from the list and counted as skipped.

        Raises:
            SyncFailureError: If any entity has no hash after computation (programming error)
        """
        if not entities:
            return

        # Compute all hashes concurrently with semaphore control
        results = await self._compute_hashes_concurrently(entities, sync_context)

        # Process results and handle failures
        await self._process_hash_results(entities, results, sync_context)

        # Validate all remaining entities have hash set
        self._validate_hashes(entities)

    async def compute_for_entity(self, entity: BaseEntity) -> Optional[str]:
        """Compute stable content hash for a single entity.

        Args:
            entity: Entity to compute hash for

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
                content_hash = await self._compute_file_content_hash(entity)
                entity_dict["_content_hash"] = content_hash

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
    ) -> List[Tuple[Tuple[str, str], Optional[str]]]:
        """Compute hashes for all entities concurrently with semaphore control.

        Args:
            entities: Entities to hash
            sync_context: Sync context with logger

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
                try:
                    hash_value = await self.compute_for_entity(entity)
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
    ) -> None:
        """Process hash computation results, handling failures.

        Args:
            entities: Original entity list (modified in-place)
            results: List of ((entity_type, entity_id), hash_value) tuples
            sync_context: Sync context for logging and progress tracking
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
            await sync_context.entity_tracker.record_skipped(len(failed_entities))

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
    # Serialization and Hashing
    # ------------------------------------------------------------------------------------

    def _exclude_volatile_fields(self, entity: BaseEntity, entity_dict: dict) -> dict:
        """Exclude volatile fields from entity dict for hashing.

        Args:
            entity: Original entity (for field metadata inspection)
            entity_dict: Entity dict from model_dump

        Returns:
            Dict with volatile fields excluded
        """
        excluded_fields = {
            "airweave_system_metadata",  # Not initialized yet
            "breadcrumbs",  # Parent relationships are volatile
            "local_path",  # Temp path changes per run
            "url",  # Contains access tokens
        }

        # Add fields marked with unhashable=True
        for field_name, field_info in entity.__class__.model_fields.items():
            json_extra = field_info.json_schema_extra
            if json_extra and isinstance(json_extra, dict):
                flag_key = (
                    AirweaveFieldFlag.UNHASHABLE.value
                    if hasattr(AirweaveFieldFlag.UNHASHABLE, "value")
                    else AirweaveFieldFlag.UNHASHABLE
                )
                if json_extra.get(flag_key):
                    excluded_fields.add(field_name)

        return {k: v for k, v in entity_dict.items() if k not in excluded_fields}

    def _compute_dict_hash(self, content_dict: dict) -> str:
        """Compute SHA256 hash of a dictionary with stable serialization.

        Args:
            content_dict: Dictionary to hash

        Returns:
            Hex digest of SHA256 hash
        """
        stable_data = self._stable_serialize(content_dict)
        json_str = json.dumps(stable_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(json_str.encode()).hexdigest()

    @staticmethod
    def _stable_serialize(obj: Any) -> Any:
        """Recursively serialize object in a stable way for hashing.

        Args:
            obj: Object to serialize

        Returns:
            Serialized object with stable ordering
        """
        if isinstance(obj, dict):
            return {k: HashComputer._stable_serialize(v) for k, v in sorted(obj.items())}
        elif isinstance(obj, (list, tuple)):
            return [HashComputer._stable_serialize(x) for x in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            return str(obj)


# Singleton instance
hash_computer = HashComputer()
