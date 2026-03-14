"""ARF reader for entity replay.

Reads and reconstructs entities from ARF storage. Used by ArfReplaySource
for automatic replay when execution_config.behavior.replay_from_arf=True.

Storage layout:
    raw/{sync_id}/
    ├── manifest.json
    ├── entities/{entity_id}.json
    └── files/{entity_id}_{name}.{ext}
"""

import asyncio
import importlib
import shutil
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

import aiofiles

from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.domains.arf.protocols import ArfReaderProtocol
from airweave.platform.entities._base import BaseEntity
from airweave.domains.storage.exceptions import StorageNotFoundError
from airweave.domains.storage.paths import StoragePaths
from airweave.domains.storage.protocols import StorageBackend


class ArfReader(ArfReaderProtocol):
    """Reader for ARF storage.

    Implements ArfReaderProtocol.
    Handles reading entities and files using the injected StorageBackend.
    """

    def __init__(  # noqa: D107
        self,
        sync_id: UUID,
        storage: StorageBackend,
        logger: Optional[ContextualLogger] = None,
        restore_files: bool = True,
    ) -> None:
        self.sync_id = sync_id
        self._storage = storage
        self.logger = logger or default_logger
        self.restore_files = restore_files
        self._temp_dir: Optional[Path] = None

    # =========================================================================
    # Path helpers
    # =========================================================================

    def _sync_path(self) -> str:
        return StoragePaths.arf_sync_path(self.sync_id)

    def _manifest_path(self) -> str:
        return StoragePaths.arf_manifest_path(self.sync_id)

    def _entities_dir(self) -> str:
        return StoragePaths.arf_entities_dir(self.sync_id)

    # =========================================================================
    # Reading operations
    # =========================================================================

    async def read_manifest(self) -> Dict[str, Any]:
        """Read and return the manifest.

        Raises:
            StorageNotFoundError: If manifest doesn't exist.
        """
        return await self._storage.read_json(self._manifest_path())

    async def validate(self) -> bool:
        """Validate that ARF data exists and is readable."""
        try:
            manifest = await self.read_manifest()
            return "sync_id" in manifest
        except StorageNotFoundError:
            return False
        except Exception as e:
            self.logger.error(f"ARF validation failed for sync {self.sync_id}: {e}")
            return False

    async def list_entity_files(self) -> List[str]:
        """List all entity JSON file paths."""
        entities_dir = self._entities_dir()
        try:
            files = await self._storage.list_files(entities_dir)
            return [f for f in files if f.endswith(".json")]
        except Exception:
            return []

    async def get_entity_count(self) -> int:
        """Count entities in ARF storage."""
        entities_dir = self._entities_dir()
        try:
            return await self._storage.count_files(entities_dir, pattern="*.json")
        except Exception:
            return 0

    async def iter_entity_dicts(self, batch_size: int = 50) -> AsyncGenerator[Dict[str, Any], None]:
        """Iterate over raw entity dicts with batched concurrent reads."""
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")

        entity_files = await self.list_entity_files()
        total_batches = (len(entity_files) + batch_size - 1) // batch_size
        self.logger.info(
            f"Reading {len(entity_files)} entity files in {total_batches} concurrent batches "
            f"(batch_size={batch_size})"
        )

        for i in range(0, len(entity_files), batch_size):
            batch = entity_files[i : i + batch_size]
            results = await asyncio.gather(
                *[self._storage.read_json(file_path) for file_path in batch],
                return_exceptions=True,
            )
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.warning(f"Failed to read entity from {batch[idx]}: {result}")
                else:
                    yield result

    # =========================================================================
    # Entity reconstruction
    # =========================================================================

    async def reconstruct_entity(self, entity_dict: Dict[str, Any]) -> BaseEntity:
        """Reconstruct a BaseEntity from stored dict.

        Raises:
            ValueError: If entity cannot be reconstructed.
        """
        entity_dict = dict(entity_dict)

        entity_class_name = entity_dict.pop("__entity_class__", None)
        entity_module = entity_dict.pop("__entity_module__", None)
        entity_dict.pop("__captured_at__", None)
        stored_file = entity_dict.pop("__stored_file__", None)

        if not entity_class_name or not entity_module:
            raise ValueError("Entity dict missing __entity_class__ or __entity_module__")

        try:
            module = importlib.import_module(entity_module)
            entity_class = getattr(module, entity_class_name)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Cannot reconstruct {entity_module}.{entity_class_name}: {e}")

        if self.restore_files and stored_file:
            restored_path = await self._restore_file(stored_file)
            if restored_path:
                entity_dict["local_path"] = restored_path

        return entity_class(**entity_dict)

    async def _restore_file(self, stored_file_path: str) -> Optional[str]:
        """Restore a file attachment to temp directory."""
        try:
            content = await self._storage.read_file(stored_file_path)

            if self._temp_dir is None:
                self._temp_dir = Path(StoragePaths.TEMP_BASE) / "arf_replay" / str(self.sync_id)
                self._temp_dir.mkdir(parents=True, exist_ok=True)

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

    async def iter_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Iterate over reconstructed entities for replay."""
        try:
            manifest = await self.read_manifest()
            self.logger.info(
                f"Replaying ARF: {manifest.get('entity_count', '?')} entities "
                f"from {manifest.get('source_short_name', 'unknown')} source"
            )
        except Exception as e:
            self.logger.warning(f"Could not read manifest: {e}")

        entity_count = await self.get_entity_count()
        self.logger.info(f"Found {entity_count} entity files to replay")

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
            try:
                shutil.rmtree(self._temp_dir)
                self._temp_dir = None
            except Exception as e:
                self.logger.warning(f"Failed to cleanup temp dir: {e}")
