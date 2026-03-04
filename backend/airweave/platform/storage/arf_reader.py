"""ARF (Airweave Raw Format) reader for entity replay.

Provides shared logic for reading and reconstructing entities from ARF storage.
Used by both SnapshotSource (manual replay) and ArfReplaySource (automatic replay).

Storage structure:
    raw/{sync_id}/
    ├── manifest.json           # Sync metadata
    ├── entities/
    │   └── {entity_id}.json    # One file per entity
    └── files/
        └── {entity_id}_{name}.{ext}  # File attachments
"""

import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

import aiofiles

from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.storage.exceptions import StorageNotFoundError
from airweave.platform.storage.paths import StoragePaths
from airweave.platform.storage.protocol import StorageBackend

if TYPE_CHECKING:
    from airweave.platform.entities._base import BaseEntity


class ArfReader:
    """Reader for ARF (Airweave Raw Format) storage.

    Handles reading entities and files from ARF storage using the StorageBackend
    abstraction, supporting both local filesystem and Azure Blob storage.
    """

    def __init__(
        self,
        sync_id: UUID,
        storage: Optional[StorageBackend] = None,
        logger: Optional[ContextualLogger] = None,
        restore_files: bool = True,
    ):
        """Initialize ARF reader.

        Args:
            sync_id: The sync ID to read ARF data from
            storage: Storage backend (uses singleton if not provided)
            logger: Logger instance
            restore_files: Whether to restore file attachments to temp directory
        """
        self.sync_id = sync_id
        self._storage = storage
        self.logger = logger or default_logger
        self.restore_files = restore_files
        self._temp_dir: Optional[Path] = None

    @property
    def storage(self) -> StorageBackend:
        """Get storage backend (lazy to avoid circular import)."""
        if self._storage is None:
            from airweave.platform.storage import storage_backend

            self._storage = storage_backend
        return self._storage

    # =========================================================================
    # Path helpers (using StoragePaths)
    # =========================================================================

    def _sync_path(self) -> str:
        """Base path for this sync's ARF data."""
        return StoragePaths.arf_sync_path(self.sync_id)

    def _manifest_path(self) -> str:
        """Manifest path."""
        return StoragePaths.arf_manifest_path(self.sync_id)

    def _entities_dir(self) -> str:
        """Entities directory path."""
        return StoragePaths.arf_entities_dir(self.sync_id)

    # =========================================================================
    # Reading operations
    # =========================================================================

    async def read_manifest(self) -> Dict[str, Any]:
        """Read and return the manifest.

        Returns:
            Manifest dict with sync metadata

        Raises:
            StorageNotFoundError: If manifest doesn't exist
        """
        return await self.storage.read_json(self._manifest_path())

    async def validate(self) -> bool:
        """Validate that ARF data exists and is readable.

        Returns:
            True if valid ARF data exists
        """
        try:
            manifest = await self.read_manifest()
            return "sync_id" in manifest
        except StorageNotFoundError:
            return False
        except Exception as e:
            self.logger.error(f"ARF validation failed for sync {self.sync_id}: {e}")
            return False

    async def list_entity_files(self) -> List[str]:
        """List all entity JSON file paths.

        Returns:
            List of entity file paths relative to storage root
        """
        entities_dir = self._entities_dir()
        try:
            files = await self.storage.list_files(entities_dir)
            return [f for f in files if f.endswith(".json")]
        except Exception:
            return []

    async def get_entity_count(self) -> int:
        """Get count of entities in ARF storage (optimized).

        Returns:
            Number of entity files
        """
        entities_dir = self._entities_dir()
        try:
            return await self.storage.count_files(entities_dir, pattern="*.json")
        except Exception:
            return 0

    async def iter_entity_dicts(self, batch_size: int = 50) -> AsyncGenerator[Dict[str, Any], None]:
        """Iterate over raw entity dicts from storage with batched concurrent reads.

        Reads entities in concurrent batches to dramatically improve performance
        when reading from cloud storage (Azure Blob, S3, etc).

        Args:
            batch_size: Number of files to read concurrently (default: 50)

        Yields:
            Entity dicts as stored (with metadata fields)
        """
        import asyncio

        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")

        entity_files = await self.list_entity_files()
        total_batches = (len(entity_files) + batch_size - 1) // batch_size
        self.logger.info(
            f"Reading {len(entity_files)} entity files in {total_batches} concurrent batches "
            f"(batch_size={batch_size})"
        )

        # Read files in concurrent batches
        for i in range(0, len(entity_files), batch_size):
            batch = entity_files[i : i + batch_size]

            # Read batch concurrently
            results = await asyncio.gather(
                *[self.storage.read_json(file_path) for file_path in batch],
                return_exceptions=True,
            )

            # Yield successful results, log errors
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.warning(f"Failed to read entity from {batch[idx]}: {result}")
                else:
                    yield result

    # =========================================================================
    # Entity reconstruction
    # =========================================================================

    async def reconstruct_entity(
        self,
        entity_dict: Dict[str, Any],
    ) -> "BaseEntity":
        """Reconstruct a BaseEntity from stored dict.

        Args:
            entity_dict: Dict with entity data and __entity_class__/__entity_module__

        Returns:
            Reconstructed entity instance

        Raises:
            ValueError: If entity cannot be reconstructed
        """
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

        # Restore file if needed
        if self.restore_files and stored_file:
            restored_path = await self._restore_file(stored_file)
            if restored_path:
                entity_dict["local_path"] = restored_path

        return entity_class(**entity_dict)

    async def _restore_file(self, stored_file_path: str) -> Optional[str]:
        """Restore a file attachment to temp directory.

        Args:
            stored_file_path: Path to file in ARF storage

        Returns:
            Local path to restored file, or None if restoration failed
        """
        try:
            # Read file content from storage
            content = await self.storage.read_file(stored_file_path)

            # Create temp directory if needed
            if self._temp_dir is None:
                self._temp_dir = Path(StoragePaths.TEMP_BASE) / "arf_replay" / str(self.sync_id)
                self._temp_dir.mkdir(parents=True, exist_ok=True)

            # Extract filename and write to temp
            filename = Path(stored_file_path).name
            local_path = self._temp_dir / filename
            local_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(local_path, "wb") as f:
                await f.write(content)

            return str(local_path)

        except StorageNotFoundError:
            self.logger.warning(f"File not found in ARF storage: {stored_file_path}")
            return None
        except Exception as e:
            self.logger.warning(f"Failed to restore file {stored_file_path}: {e}")
            return None

    # =========================================================================
    # High-level iteration
    # =========================================================================

    async def iter_entities(self) -> AsyncGenerator["BaseEntity", None]:
        """Iterate over reconstructed entities.

        This is the main method for replaying ARF data through a sync pipeline.

        Yields:
            Reconstructed BaseEntity instances ready for processing
        """
        # Log manifest info
        try:
            manifest = await self.read_manifest()
            self.logger.info(
                f"Replaying ARF: {manifest.get('entity_count', '?')} entities "
                f"from {manifest.get('source_short_name', 'unknown')} source"
            )
        except Exception as e:
            self.logger.warning(f"Could not read manifest: {e}")

        # Count for logging
        entity_count = await self.get_entity_count()
        self.logger.info(f"Found {entity_count} entity files to replay")

        # Iterate and reconstruct
        async for entity_dict in self.iter_entity_dicts():
            try:
                entity = await self.reconstruct_entity(entity_dict)
                yield entity
            except Exception as e:
                self.logger.warning(f"Failed to reconstruct entity: {e}")
                continue

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup(self) -> None:
        """Clean up temp files created during replay."""
        if self._temp_dir and self._temp_dir.exists():
            import shutil

            try:
                shutil.rmtree(self._temp_dir)
                self._temp_dir = None
            except Exception as e:
                self.logger.warning(f"Failed to cleanup temp dir: {e}")
