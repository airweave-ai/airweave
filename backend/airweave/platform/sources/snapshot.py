"""Snapshot source for replaying raw data captures.

This source reads entities from the raw data storage (via StorageBackend):
    raw/{sync_id}/
    ├── manifest.json           # Sync metadata
    ├── entities/
    │   └── {entity_id}.json    # One file per entity
    └── files/
        └── {entity_id}_{name}  # File attachments

Usage:
    Create a source connection with:
    - short_name: "snapshot"
    - config: {"sync_id": "7dd989e8-0634-447e-9406-5dba481569cd"}
    - credentials: {"placeholder": "snapshot"} (required for API)
"""

import importlib
import tempfile
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from airweave.platform.configs.auth import SnapshotAuthConfig
from airweave.platform.configs.config import SnapshotConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.storage.backend import StorageBackend
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="Snapshot",
    short_name="snapshot",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class="SnapshotAuthConfig",
    config_class="SnapshotConfig",
    labels=["Internal", "Replay"],
    supports_continuous=False,
)
class SnapshotSource(BaseSource):
    """Source that replays entities from raw data captures.

    Uses StorageBackend to read entities and files.
    Supports file restoration for FileEntity types.
    """

    def __init__(self):
        """Initialize snapshot source."""
        super().__init__()
        self.sync_id: str = ""
        self.restore_files: bool = True
        self._temp_dir: Optional[Path] = None
        self._storage: Optional[StorageBackend] = None

    @classmethod
    async def create(
        cls,
        credentials: Optional[Union[Dict[str, Any], SnapshotAuthConfig]] = None,
        config: Optional[Union[Dict[str, Any], SnapshotConfig]] = None,
    ) -> "SnapshotSource":
        """Create a new snapshot source instance.

        Args:
            credentials: Optional SnapshotAuthConfig (placeholder for API compatibility)
            config: SnapshotConfig with sync_id

        Returns:
            Configured SnapshotSource instance
        """
        instance = cls()

        # Extract config
        if config is None:
            raise ValueError("config with 'sync_id' is required for SnapshotSource")

        if isinstance(config, dict):
            instance.sync_id = config.get("sync_id", "")
            instance.restore_files = config.get("restore_files", True)
        else:
            instance.sync_id = config.sync_id
            instance.restore_files = config.restore_files

        if not instance.sync_id:
            raise ValueError("sync_id is required in config")

        return instance

    @property
    def storage(self) -> StorageBackend:
        """Get storage backend (lazy to avoid circular import)."""
        if self._storage is None:
            from airweave.platform.storage import storage_backend

            self._storage = storage_backend
        return self._storage

    def _storage_path(self, relative_path: str) -> str:
        """Get full storage path for a file."""
        return f"raw/{self.sync_id}/{relative_path}"

    async def _read_json(self, relative_path: str) -> Dict[str, Any]:
        """Read a JSON file from storage."""
        storage_path = self._storage_path(relative_path)
        return await self.storage.read_json(storage_path)

    async def _list_entity_files(self) -> List[str]:
        """List all entity JSON files."""
        entities_dir = self._storage_path("entities")
        try:
            files = await self.storage.list_files(entities_dir)
            # Filter for .json files and return storage paths
            return [f for f in files if f.endswith(".json")]
        except Exception:
            return []

    async def _restore_file(self, stored_file_path: str) -> Optional[str]:
        """Restore a file attachment to temp directory.

        Args:
            stored_file_path: Storage path to file (e.g., "raw/{sync_id}/files/...")

        Returns:
            Local path to restored file, or None if restoration failed
        """
        if not self.restore_files:
            return None

        try:
            # Read file content from storage
            content = await self.storage.read_file(stored_file_path)

            # Create temp directory if needed
            if self._temp_dir is None:
                self._temp_dir = Path(tempfile.mkdtemp(prefix="snapshot_files_"))

            # Extract filename from storage path
            filename = Path(stored_file_path).name
            local_path = self._temp_dir / filename
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to local temp file
            with open(local_path, "wb") as f:
                f.write(content)

            return str(local_path)

        except Exception as e:
            self.logger.warning(f"Failed to restore file {stored_file_path}: {e}")
            return None

    def _reconstruct_entity(
        self, entity_dict: Dict[str, Any], restored_file_path: Optional[str] = None
    ) -> BaseEntity:
        """Reconstruct a BaseEntity from stored dict.

        Args:
            entity_dict: Dict with entity data and __entity_class__/__entity_module__
            restored_file_path: Optional local path to restored file

        Returns:
            Reconstructed entity instance
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

        # Handle file restoration for FileEntities
        if stored_file:
            # Remove stale local_path from original sync (points to non-existent temp dir)
            entity_dict.pop("local_path", None)
            # Set new local_path only if file was successfully restored
            if restored_file_path:
                entity_dict["local_path"] = restored_file_path

        return entity_class(**entity_dict)

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from raw data storage.

        Reads manifest and iterates over all entity JSON files,
        reconstructing BaseEntity objects and optionally restoring files.
        """
        # Read manifest for logging
        try:
            manifest = await self._read_json("manifest.json")
            self.logger.info(
                f"Replaying snapshot: {manifest.get('entity_count', '?')} entities "
                f"from {manifest.get('source_short_name', 'unknown')} source"
            )
        except Exception as e:
            self.logger.warning(f"Could not read manifest: {e}")

        # List and process entity files
        entity_files = await self._list_entity_files()
        self.logger.info(f"Found {len(entity_files)} entity files to replay")

        for storage_path in entity_files:
            try:
                # Read entity JSON from storage
                entity_dict = await self.storage.read_json(storage_path)

                # Check if file needs to be restored
                stored_file = entity_dict.get("__stored_file__")
                restored_path = None
                if stored_file and self.restore_files:
                    restored_path = await self._restore_file(stored_file)

                # Reconstruct entity
                entity = self._reconstruct_entity(entity_dict, restored_path)
                yield entity

            except Exception as e:
                self.logger.warning(f"Failed to reconstruct entity from {storage_path}: {e}")
                continue

    async def validate(self) -> bool:
        """Validate that the snapshot exists in storage and is readable."""
        self.logger.info(f"Validating snapshot source with sync_id: {self.sync_id}")
        if not self.sync_id:
            self.logger.error("Snapshot validation failed: sync_id is empty")
            return False

        try:
            manifest = await self._read_json("manifest.json")
            return "sync_id" in manifest
        except Exception as e:
            self.logger.error(f"Snapshot validation failed: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up temp files."""
        if self._temp_dir and self._temp_dir.exists():
            import shutil

            shutil.rmtree(self._temp_dir)
            self._temp_dir = None
