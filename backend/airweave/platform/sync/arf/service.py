"""Entity ARF service for audit and replay.

Stores raw entities during sync with entity-level granularity.
Supports both full syncs and incremental syncs with proper delete handling.

Storage structure (entity_id as filename - no index needed):
    raw/{sync_id}/
    ├── manifest.json           # Sync metadata
    ├── entities/
    │   └── {entity_id}.json    # One file per entity
    └── files/
        └── {entity_id}_{name}.{ext}  # File with name and extension

Operations:
- upsert_entity: Write/overwrite entity by ID
- delete_entity: Remove entity and associated files
- get_entity: Read entity by ID
- iter_entities: Stream all entities

Usage:
    from airweave.platform.sync.arf import arf_service

    # During sync - capture as entities are processed
    await arf_service.upsert_entity(entity, sync_context)
    await arf_service.delete_entity(entity_id, sync_context)

    # Replay later
    async for entity_dict in arf_service.iter_entities(sync_id):
        entity = arf_service.reconstruct_entity(entity_dict)
        # Process with different config...
"""

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

import aiofiles

from airweave.platform.storage.exceptions import StorageNotFoundError
from airweave.platform.storage.protocol import StorageBackend
from airweave.platform.sync.arf.schema import SyncManifest

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.entities._base import BaseEntity


class ArfService:
    """Service for capturing and retrieving raw entity data.

    Handles:
    - Entity-level storage (one file per entity_id)
    - File attachments for FileEntities
    - Full sync support (delete stale entities using tracker)
    - Incremental sync support (upsert/delete as events come)
    - Entity reconstruction for replay
    """

    def __init__(self, storage: Optional[StorageBackend] = None):
        """Initialize ARF service.

        Args:
            storage: Storage backend. Uses singleton if not provided.
        """
        self._storage = storage

    @property
    def storage(self) -> StorageBackend:
        """Get storage backend (lazy to avoid circular import)."""
        if self._storage is None:
            from airweave.platform.storage import storage_backend

            self._storage = storage_backend
        return self._storage

    # =========================================================================
    # Path helpers
    # =========================================================================

    def _sync_path(self, sync_id: str) -> str:
        """Get base path for a sync's ARF data."""
        return f"raw/{sync_id}"

    def _manifest_path(self, sync_id: str) -> str:
        """Get manifest path."""
        return f"{self._sync_path(sync_id)}/manifest.json"

    def _entity_path(self, sync_id: str, entity_id: str) -> str:
        """Get path for an entity file."""
        safe_id = self._safe_filename(entity_id)
        return f"{self._sync_path(sync_id)}/entities/{safe_id}.json"

    def _file_path(self, sync_id: str, entity_id: str, filename: str = "") -> str:
        """Get path for an entity's attached file.

        Format: files/{entity_id}_{name}.{ext} for readability.
        """
        safe_id = self._safe_filename(entity_id)
        if filename:
            safe_name = self._safe_filename(Path(filename).stem)
            ext = Path(filename).suffix or ""
            return f"{self._sync_path(sync_id)}/files/{safe_id}_{safe_name}{ext}"
        return f"{self._sync_path(sync_id)}/files/{safe_id}"

    def _safe_filename(self, value: str, max_length: int = 200) -> str:
        """Convert entity_id or filename to safe storage path.

        Uses hash suffix for long/complex IDs to ensure uniqueness.
        """
        # Basic sanitization
        safe = re.sub(r'[/\\:*?"<>|]', "_", str(value))
        safe = re.sub(r"_+", "_", safe).strip("_")

        # If too long or contains special chars, use hash-based name
        if len(safe) > max_length or safe != value:
            # Include original start for readability + hash for uniqueness
            prefix = safe[:50] if len(safe) > 50 else safe
            hash_suffix = hashlib.md5(value.encode()).hexdigest()[:12]
            safe = f"{prefix}_{hash_suffix}"

        return safe[:max_length]

    # =========================================================================
    # Entity serialization
    # =========================================================================

    def _get_source_short_name(self, sync_context: "SyncContext") -> str:
        """Extract short name from source class."""
        source = sync_context.source
        if hasattr(source.__class__, "_short_name"):
            return source.__class__._short_name
        return source.__class__.__name__.lower().replace("source", "")

    def _is_file_entity(self, entity: "BaseEntity") -> bool:
        """Check if entity is a FileEntity or subclass."""
        for cls in entity.__class__.__mro__:
            if cls.__name__ == "FileEntity":
                return True
        return False

    def _serialize_entity(self, entity: "BaseEntity") -> Dict[str, Any]:
        """Serialize entity with class info for reconstruction."""
        entity_dict = entity.model_dump(mode="json")
        entity_dict["__entity_class__"] = entity.__class__.__name__
        entity_dict["__entity_module__"] = entity.__class__.__module__
        entity_dict["__captured_at__"] = datetime.now(timezone.utc).isoformat()
        return entity_dict

    # =========================================================================
    # Core operations
    # =========================================================================

    async def upsert_entity(
        self,
        entity: "BaseEntity",
        sync_context: "SyncContext",
    ) -> None:
        """Store or update an entity.

        Args:
            entity: Entity to store
            sync_context: Sync context for metadata
        """
        sync_id = str(sync_context.sync.id)
        entity_id = str(entity.entity_id)

        # Check if this is an update (entity already exists)
        entity_path = self._entity_path(sync_id, entity_id)
        is_update = await self.storage.exists(entity_path)

        # For updates, check if we need to delete old file
        if is_update:
            try:
                old_entity = await self.storage.read_json(entity_path)
                old_file = old_entity.get("__stored_file__")
                if old_file:
                    # Delete old file - will be replaced with new one
                    await self.storage.delete(old_file)
            except Exception:
                pass

        # Serialize entity
        entity_dict = self._serialize_entity(entity)

        # Handle file entities
        stored_files = []
        if self._is_file_entity(entity) and hasattr(entity, "local_path"):
            local_path = getattr(entity, "local_path", None)
            if local_path and Path(local_path).exists():
                filename = Path(local_path).name
                file_path = self._file_path(sync_id, entity_id, filename)

                try:
                    async with aiofiles.open(local_path, "rb") as f:
                        content = await f.read()
                    await self.storage.write_file(file_path, content)
                    entity_dict["__stored_file__"] = file_path
                    stored_files.append(entity_id)
                except Exception as e:
                    sync_context.logger.warning(f"Could not store file for {entity_id}: {e}")

        await self.storage.write_json(entity_path, entity_dict)

    async def upsert_entities(
        self,
        entities: List["BaseEntity"],
        sync_context: "SyncContext",
    ) -> int:
        """Store or update multiple entities (batch operation).

        Args:
            entities: Entities to store
            sync_context: Sync context

        Returns:
            Number of entities stored
        """
        for entity in entities:
            await self.upsert_entity(entity, sync_context)
        return len(entities)

    async def delete_entity(
        self,
        entity_id: str,
        sync_context: "SyncContext",
    ) -> bool:
        """Delete an entity and its associated files.

        Args:
            entity_id: Entity ID to delete
            sync_context: Sync context

        Returns:
            True if entity was deleted
        """
        sync_id = str(sync_context.sync.id)
        entity_path = self._entity_path(sync_id, entity_id)

        # Check if entity exists
        if not await self.storage.exists(entity_path):
            return False

        # Read entity to find associated files
        try:
            entity_dict = await self.storage.read_json(entity_path)
            stored_file = entity_dict.get("__stored_file__")
            if stored_file:
                await self.storage.delete(stored_file)
        except Exception:
            pass

        # Delete entity file
        deleted = await self.storage.delete(entity_path)

        if deleted:
            sync_context.logger.debug(f"Deleted ARF entity: {entity_id}")

        return deleted

    async def delete_entities(
        self,
        entity_ids: List[str],
        sync_context: "SyncContext",
    ) -> int:
        """Delete multiple entities (batch operation).

        Args:
            entity_ids: Entity IDs to delete
            sync_context: Sync context

        Returns:
            Number of entities deleted
        """
        deleted_count = 0
        for entity_id in entity_ids:
            if await self.delete_entity(entity_id, sync_context):
                deleted_count += 1
        return deleted_count

    async def get_entity(self, sync_id: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get a single entity by ID.

        Args:
            sync_id: Sync ID
            entity_id: Entity ID

        Returns:
            Entity dict or None if not found
        """
        entity_path = self._entity_path(sync_id, entity_id)
        try:
            return await self.storage.read_json(entity_path)
        except StorageNotFoundError:
            return None

    async def iter_entities(
        self, sync_id: str, batch_size: int = 50
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Iterate over all entities in a sync's ARF store with batched concurrent reads.

        Reads entities in concurrent batches to dramatically improve performance
        when reading from cloud storage (Azure Blob, S3, etc).

        For 2000 entities:
        - Sequential: ~100-200s (50-100ms per file)
        - Batched (50 concurrent): ~5-10s (40 batches × 100ms)

        Args:
            sync_id: Sync ID
            batch_size: Number of files to read concurrently (default: 50)

        Yields:
            Entity dicts
        """
        import asyncio

        entities_dir = f"{self._sync_path(sync_id)}/entities"
        try:
            files = await self.storage.list_files(entities_dir)
        except Exception:
            return

        # Filter to .json files only
        json_files = [f for f in files if f.endswith(".json")]

        # Read files in concurrent batches
        for i in range(0, len(json_files), batch_size):
            batch = json_files[i : i + batch_size]

            # Read batch concurrently
            results = await asyncio.gather(
                *[self.storage.read_json(file_path) for file_path in batch],
                return_exceptions=True,
            )

            # Yield successful results, skip exceptions
            for result in results:
                if not isinstance(result, Exception):
                    yield result

    async def get_all_entities(self, sync_id: str) -> List[Dict[str, Any]]:
        """Load all entities into memory.

        Args:
            sync_id: Sync ID

        Returns:
            List of entity dicts
        """
        entities = []
        async for entity in self.iter_entities(sync_id):
            entities.append(entity)
        return entities

    async def list_entity_ids(self, sync_id: str) -> List[str]:
        """List all entity IDs in a sync's ARF store.

        Args:
            sync_id: Sync ID

        Returns:
            List of entity IDs
        """
        entities_dir = f"{self._sync_path(sync_id)}/entities"
        try:
            files = await self.storage.list_files(entities_dir)
        except Exception:
            return []

        entity_ids = []
        for file_path in files:
            if file_path.endswith(".json"):
                # Extract entity_id from filename (reverse of _safe_filename)
                # We store the original entity_id in the JSON, so read it
                try:
                    entity_dict = await self.storage.read_json(file_path)
                    entity_id = entity_dict.get("entity_id")
                    if entity_id:
                        entity_ids.append(str(entity_id))
                except Exception:
                    continue

        return entity_ids

    # =========================================================================
    # Full sync support
    # =========================================================================

    async def cleanup_stale_entities(self, sync_context: "SyncContext") -> int:
        """Delete entities not seen during the current sync.

        Call at the end of a full sync to remove entities that no longer exist
        in the source.

        Args:
            sync_context: Sync context with EntityTracker

        Returns:
            Number of stale entities deleted
        """
        sync_id = str(sync_context.sync.id)

        # Get set of all encountered entity IDs
        seen_ids = sync_context.entity_tracker.get_all_encountered_ids_flat()

        current_ids = await self.list_entity_ids(sync_id)
        stale_ids = [eid for eid in current_ids if eid not in seen_ids]

        if stale_ids:
            sync_context.logger.info(f"Cleaning up {len(stale_ids)} stale entities from ARF store")
            deleted = await self.delete_entities(stale_ids, sync_context)
            return deleted

        return 0

    # =========================================================================
    # Manifest management
    # =========================================================================

    async def get_manifest(self, sync_id: str) -> Optional[SyncManifest]:
        """Get manifest for a sync."""
        manifest_path = self._manifest_path(sync_id)
        try:
            data = await self.storage.read_json(manifest_path)
            return SyncManifest.model_validate(data)
        except StorageNotFoundError:
            return None

    async def upsert_manifest(self, sync_context: "SyncContext") -> None:
        """Create or update manifest for a sync job.

        Args:
            sync_context: Sync context with job info
        """
        sync_id = str(sync_context.sync.id)
        manifest_path = self._manifest_path(sync_id)
        now = datetime.now(timezone.utc).isoformat()
        job_id = str(sync_context.sync_job.id)

        # Read existing manifest if it exists
        existing_manifest = await self.get_manifest(sync_id)

        if existing_manifest:
            # Update existing: add job ID, update timestamp
            if job_id not in existing_manifest.sync_jobs:
                existing_manifest.sync_jobs.append(job_id)
            existing_manifest.updated_at = now
            await self.storage.write_json(manifest_path, existing_manifest.model_dump())
        else:
            # Create new manifest
            manifest = SyncManifest(
                sync_id=sync_id,
                source_short_name=self._get_source_short_name(sync_context),
                collection_id=str(sync_context.collection.id),
                collection_readable_id=sync_context.collection.readable_id,
                organization_id=str(sync_context.collection.organization_id),
                created_at=now,
                updated_at=now,
                sync_jobs=[job_id],
                vector_size=sync_context.collection.vector_size,
                embedding_model_name=sync_context.collection.embedding_model_name,
            )
            await self.storage.write_json(manifest_path, manifest.model_dump())

    # =========================================================================
    # Entity reconstruction
    # =========================================================================

    async def reconstruct_entity(
        self,
        entity_dict: Dict[str, Any],
        restore_files_to: Optional[Path] = None,
    ) -> "BaseEntity":
        """Reconstruct a BaseEntity from stored dict.

        Args:
            entity_dict: Dict from get_entity() or iter_entities()
            restore_files_to: Optional directory to restore files to

        Returns:
            Reconstructed entity instance
        """
        import importlib

        # Make a copy to avoid mutating
        entity_dict = dict(entity_dict)

        # Extract metadata
        entity_class_name = entity_dict.pop("__entity_class__", None)
        entity_module = entity_dict.pop("__entity_module__", None)
        entity_dict.pop("__captured_at__", None)
        stored_file = entity_dict.pop("__stored_file__", None)

        if not entity_class_name or not entity_module:
            raise ValueError("Entity dict missing __entity_class__ or __entity_module__")

        # Import entity class
        try:
            module = importlib.import_module(entity_module)
            entity_class = getattr(module, entity_class_name)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Cannot reconstruct {entity_module}.{entity_class_name}: {e}")

        # Restore file if requested
        if restore_files_to and stored_file:
            try:
                content = await self.storage.read_file(stored_file)
                filename = Path(stored_file).name
                restored_path = restore_files_to / filename
                restored_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(restored_path, "wb") as f:
                    await f.write(content)
                entity_dict["local_path"] = str(restored_path)
            except Exception:
                pass

        return entity_class(**entity_dict)

    # =========================================================================
    # Store management
    # =========================================================================

    async def list_syncs(self) -> List[str]:
        """List all sync IDs with ARF stores."""
        try:
            dirs = await self.storage.list_dirs("raw")
            return [d.split("/")[-1] for d in dirs]
        except Exception:
            return []

    async def sync_exists(self, sync_id: str) -> bool:
        """Check if a ARF store exists for a sync."""
        return await self.storage.exists(self._manifest_path(sync_id))

    async def delete_sync(self, sync_id: str) -> bool:
        """Delete entire ARF store for a sync."""
        return await self.storage.delete(self._sync_path(sync_id))

    async def get_entity_count(self, sync_id: str) -> int:
        """Get count of entities in store (fast - counts without listing all files)."""
        entities_dir = f"{self._sync_path(sync_id)}/entities"
        try:
            return await self.storage.count_files(entities_dir, pattern="*.json")
        except Exception:
            return 0

    # =========================================================================
    # Replay / Resync support
    # =========================================================================

    async def iter_entities_for_replay(
        self,
        sync_id: str,
        restore_files_to: Optional[Path] = None,
    ) -> AsyncGenerator["BaseEntity", None]:
        """Iterate over entities as reconstructed BaseEntity objects for replay.

        This is the main method for re-processing ARF data through a pipeline
        with different configurations.

        Args:
            sync_id: Sync ID to replay
            restore_files_to: Optional directory to restore file attachments to

        Yields:
            Reconstructed BaseEntity instances ready for processing
        """
        async for entity_dict in self.iter_entities(sync_id):
            try:
                entity = await self.reconstruct_entity(entity_dict, restore_files_to)
                yield entity
            except Exception as e:
                # Log but continue - don't fail entire replay for one entity
                from airweave.core.logging import logger

                logger.warning(f"Failed to reconstruct entity: {e}")
                continue

    async def get_replay_stats(self, sync_id: str) -> Dict[str, Any]:
        """Get stats for a potential replay operation.

        Args:
            sync_id: Sync ID

        Returns:
            Dict with entity count, file count, last updated, etc.
        """
        manifest = await self.get_manifest(sync_id)
        if not manifest:
            return {"exists": False}

        # Compute entity count on-demand
        entity_count = await self.get_entity_count(sync_id)

        return {
            "exists": True,
            "sync_id": manifest.sync_id,
            "source": manifest.source_short_name,
            "entity_count": entity_count,
            "created_at": manifest.created_at,
            "updated_at": manifest.updated_at,
            "sync_jobs": manifest.sync_jobs,
        }


# Singleton instance
arf_service = ArfService()
