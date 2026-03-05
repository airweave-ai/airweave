"""Snapshot source for replaying raw data captures.

This source reads entities from ARF (Airweave Raw Format) storage:
    {path}/
    ├── manifest.json           # Sync metadata
    ├── entities/
    │   └── {entity_id}.json    # One file per entity
    └── files/
        └── {entity_id}_{name}  # File attachments

Usage:
    Create a source connection with:
    - short_name: "snapshot"
    - config: {"path": "/local/path/to/raw/{sync_id}"} OR {"path": "raw/{sync_id}"}
    - credentials: {"placeholder": "snapshot"} (required for API)

The path can be:
- A local filesystem path (for evals): "/path/to/airweave/local_storage/raw/{sync_id}"
- A storage-relative path (for blob): "raw/{sync_id}"
- A full Azure blob URL: "https://{account}.blob.core.windows.net/{container}/{path}"

Note: This source is behind a feature flag (Internal label).
For automatic ARF replay during syncs, use execution_config.behavior.replay_from_arf=True instead.
"""

import importlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from airweave.platform.configs.auth import SnapshotAuthConfig
from airweave.platform.configs.config import SnapshotConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.storage import StorageBackend, StoragePaths
from airweave.schemas.source_connection import AuthenticationMethod

# Regex to parse Azure blob URLs
# Format: https://{account}.blob.core.windows.net/{container}/{path}
AZURE_BLOB_URL_PATTERN = re.compile(r"^https://([^.]+)\.blob\.core\.windows\.net/([^/]+)/(.+)$")


@source(
    name="Snapshot",
    short_name="snapshot",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class=SnapshotAuthConfig,
    config_class=SnapshotConfig,
    labels=["Internal", "Replay"],
    supports_continuous=False,
    internal=True,
)
class SnapshotSource(BaseSource):
    """Source that replays entities from raw data captures.

    Supports three modes:
    1. Local filesystem path (for evals): reads directly from disk
    2. Azure blob URL: reads directly from Azure using DefaultAzureCredential
    3. Storage-relative path (for blob): uses StorageBackend abstraction
    """

    def __init__(self):
        """Initialize snapshot source."""
        super().__init__()
        self.path: str = ""
        self.restore_files: bool = True
        self._storage: Optional[StorageBackend] = None
        self._temp_dir: Optional[Path] = None
        self._is_local_path: bool = False
        self._is_azure_url: bool = False
        self._azure_account: Optional[str] = None
        self._azure_container: Optional[str] = None
        self._azure_blob_prefix: Optional[str] = None
        self._azure_client: Optional[Any] = None  # BlobServiceClient

    @classmethod
    async def create(
        cls,
        credentials: Optional[Union[Dict[str, Any], SnapshotAuthConfig]] = None,
        config: Optional[Union[Dict[str, Any], SnapshotConfig]] = None,
    ) -> "SnapshotSource":
        """Create a new snapshot source instance.

        Args:
            credentials: Optional SnapshotAuthConfig (placeholder for API compatibility)
            config: SnapshotConfig with path to raw data directory

        Returns:
            Configured SnapshotSource instance
        """
        instance = cls()

        # Extract config
        if config is None:
            raise ValueError("config with 'path' is required for SnapshotSource")

        if isinstance(config, dict):
            instance.path = config.get("path", "")
            instance.restore_files = config.get("restore_files", True)
        else:
            instance.path = config.path
            instance.restore_files = config.restore_files

        if not instance.path:
            raise ValueError("path is required in config")

        # Check if this is a full Azure blob URL
        azure_match = AZURE_BLOB_URL_PATTERN.match(instance.path)
        if azure_match:
            instance._is_azure_url = True
            instance._azure_account = azure_match.group(1)
            instance._azure_container = azure_match.group(2)
            instance._azure_blob_prefix = azure_match.group(3)
            instance._is_local_path = False
        else:
            # Determine if this is a local filesystem path or storage-relative path
            # Local paths start with / or contain typical filesystem patterns
            instance._is_local_path = instance.path.startswith("/") or (
                os.name == "nt" and ":" in instance.path[:3]  # Windows drive letter
            )

        return instance

    @property
    def storage(self) -> StorageBackend:
        """Get storage backend (lazy to avoid circular import)."""
        if self._storage is None:
            from airweave.platform.storage import storage_backend

            self._storage = storage_backend
        return self._storage

    # =========================================================================
    # Local filesystem methods (for evals)
    # =========================================================================

    def _local_path(self, relative: str = "") -> Path:
        """Get local filesystem path."""
        base = Path(self.path)
        return base / relative if relative else base

    async def _read_json_local(self, relative_path: str) -> Dict[str, Any]:
        """Read JSON from local filesystem."""
        file_path = self._local_path(relative_path)
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def _list_entity_files_local(self) -> List[str]:
        """List entity files from local filesystem."""
        entities_dir = self._local_path("entities")
        if not entities_dir.exists():
            return []
        return [
            f"entities/{f.name}"
            for f in entities_dir.iterdir()
            if f.is_file() and f.suffix == ".json"
        ]

    async def _restore_file_local(self, stored_file_path: str) -> Optional[str]:
        """Restore file from local filesystem to temp directory."""
        if not self.restore_files:
            return None

        try:
            # Strip full storage path if present
            # (ARF may store full paths like raw/{sync_id}/files/...)
            # Extract just the relative path within the snapshot directory
            if "/" in stored_file_path and "files/" in stored_file_path:
                # Extract everything from 'files/' onward
                files_idx = stored_file_path.find("files/")
                if files_idx != -1:
                    stored_file_path = stored_file_path[files_idx:]

            # Ensure stored_file_path includes 'files/' prefix
            if not stored_file_path.startswith("files/"):
                stored_file_path = f"files/{stored_file_path}"

            # Validate path to prevent traversal attacks
            if ".." in stored_file_path:
                self.logger.warning(f"Rejected path with '..' component: {stored_file_path}")
                return None

            source_path = self._local_path(stored_file_path)

            # Verify resolved path is still within snapshot directory (additional safety check)
            base_path = self._local_path().resolve()
            try:
                resolved_path = source_path.resolve()
                resolved_path.relative_to(base_path)
            except ValueError:
                self.logger.warning(f"Path traversal attempt detected: {stored_file_path}")
                return None

            if not source_path.exists():
                self.logger.debug(f"File not found at {source_path}")
                return None

            # Create temp directory if needed
            if self._temp_dir is None:
                self._temp_dir = Path(
                    tempfile.mkdtemp(prefix="snapshot_", dir=StoragePaths.TEMP_BASE)
                )

            filename = source_path.name
            local_path = self._temp_dir / filename
            local_path.parent.mkdir(parents=True, exist_ok=True)

            with open(source_path, "rb") as src, open(local_path, "wb") as dst:
                dst.write(src.read())

            return str(local_path)

        except Exception as e:
            self.logger.warning(f"Failed to restore file {stored_file_path}: {e}")
            return None

    # =========================================================================
    # Azure blob URL methods (direct access to any Azure blob)
    # =========================================================================

    def _get_azure_client(self) -> Any:
        """Get or create Azure BlobServiceClient using DefaultAzureCredential."""
        if self._azure_client is None:
            from azure.identity.aio import DefaultAzureCredential
            from azure.storage.blob.aio import BlobServiceClient

            credential = DefaultAzureCredential()
            account_url = f"https://{self._azure_account}.blob.core.windows.net"
            self._azure_client = BlobServiceClient(account_url, credential=credential)
        return self._azure_client

    async def _read_json_azure(self, relative_path: str) -> Dict[str, Any]:
        """Read JSON from Azure blob storage using direct URL access."""
        blob_path = f"{self._azure_blob_prefix.rstrip('/')}/{relative_path}"
        client = self._get_azure_client()
        container_client = client.get_container_client(self._azure_container)
        blob_client = container_client.get_blob_client(blob_path)

        try:
            download = await blob_client.download_blob()
            content = await download.readall()
            return json.loads(content.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Failed to read {blob_path} from Azure: {e}")

    async def _list_entity_files_azure(self) -> List[str]:
        """List entity files from Azure blob storage."""
        client = self._get_azure_client()
        container_client = client.get_container_client(self._azure_container)
        entities_prefix = f"{self._azure_blob_prefix.rstrip('/')}/entities/"

        files = []
        async for blob in container_client.list_blobs(name_starts_with=entities_prefix):
            if blob.name.endswith(".json"):
                # Return relative to snapshot path
                rel_path = blob.name.replace(f"{self._azure_blob_prefix.rstrip('/')}/", "")
                files.append(rel_path)
        return files

    async def _restore_file_azure(self, stored_file_path: str) -> Optional[str]:
        """Restore file from Azure blob storage to temp directory."""
        if not self.restore_files:
            return None

        try:
            # Strip full storage path if present
            if "/" in stored_file_path and "files/" in stored_file_path:
                files_idx = stored_file_path.find("files/")
                if files_idx != -1:
                    stored_file_path = stored_file_path[files_idx:]

            # Ensure stored_file_path includes 'files/' prefix
            if not stored_file_path.startswith("files/"):
                stored_file_path = f"files/{stored_file_path}"

            # Validate path to prevent traversal attacks
            if ".." in stored_file_path:
                self.logger.warning(f"Rejected path with '..' component: {stored_file_path}")
                return None

            blob_path = f"{self._azure_blob_prefix.rstrip('/')}/{stored_file_path}"
            client = self._get_azure_client()
            container_client = client.get_container_client(self._azure_container)
            blob_client = container_client.get_blob_client(blob_path)

            download = await blob_client.download_blob()
            content = await download.readall()

            # Create temp directory if needed
            if self._temp_dir is None:
                self._temp_dir = Path(
                    tempfile.mkdtemp(prefix="snapshot_", dir=StoragePaths.TEMP_BASE)
                )

            filename = Path(stored_file_path).name
            local_path = self._temp_dir / filename
            local_path.parent.mkdir(parents=True, exist_ok=True)

            with open(local_path, "wb") as f:
                f.write(content)

            return str(local_path)

        except Exception as e:
            self.logger.warning(f"Failed to restore file {stored_file_path} from Azure: {e}")
            return None

    async def _azure_blob_exists(self, relative_path: str) -> bool:
        """Check if a blob exists in Azure storage."""
        blob_path = f"{self._azure_blob_prefix.rstrip('/')}/{relative_path}"
        client = self._get_azure_client()
        container_client = client.get_container_client(self._azure_container)
        blob_client = container_client.get_blob_client(blob_path)

        try:
            await blob_client.get_blob_properties()
            return True
        except Exception:
            return False

    # =========================================================================
    # Storage backend methods (for blob storage)
    # =========================================================================

    async def _read_json_storage(self, relative_path: str) -> Dict[str, Any]:
        """Read JSON from storage backend."""
        full_path = f"{self.path.rstrip('/')}/{relative_path}"
        return await self.storage.read_json(full_path)

    async def _list_entity_files_storage(self) -> List[str]:
        """List entity files from storage backend."""
        entities_prefix = f"{self.path.rstrip('/')}/entities"
        files = await self.storage.list_files(entities_prefix)
        # Return relative to snapshot path
        return [f.replace(f"{self.path.rstrip('/')}/", "") for f in files if f.endswith(".json")]

    async def _restore_file_storage(self, stored_file_path: str) -> Optional[str]:
        """Restore file from storage backend to temp directory."""
        if not self.restore_files:
            return None

        try:
            # Strip full storage path if present
            if "/" in stored_file_path and "files/" in stored_file_path:
                files_idx = stored_file_path.find("files/")
                if files_idx != -1:
                    stored_file_path = stored_file_path[files_idx:]

            # Ensure stored_file_path includes 'files/' prefix
            if not stored_file_path.startswith("files/"):
                stored_file_path = f"files/{stored_file_path}"

            # Validate path to prevent traversal attacks
            if ".." in stored_file_path:
                self.logger.warning(f"Rejected path with '..' component: {stored_file_path}")
                return None

            full_path = f"{self.path.rstrip('/')}/{stored_file_path}"
            content = await self.storage.read_file(full_path)

            # Create temp directory if needed
            if self._temp_dir is None:
                self._temp_dir = Path(
                    tempfile.mkdtemp(prefix="snapshot_", dir=StoragePaths.TEMP_BASE)
                )

            filename = Path(stored_file_path).name
            local_path = self._temp_dir / filename
            local_path.parent.mkdir(parents=True, exist_ok=True)

            with open(local_path, "wb") as f:
                f.write(content)

            return str(local_path)

        except Exception as e:
            self.logger.warning(f"Failed to restore file {stored_file_path}: {e}")
            return None

    # =========================================================================
    # Unified methods (route to local, Azure URL, or storage backend)
    # =========================================================================

    async def _read_json(self, relative_path: str) -> Dict[str, Any]:
        """Read JSON from appropriate backend."""
        if self._is_local_path:
            return await self._read_json_local(relative_path)
        if self._is_azure_url:
            return await self._read_json_azure(relative_path)
        return await self._read_json_storage(relative_path)

    async def _list_entity_files(self) -> List[str]:
        """List entity files from appropriate backend."""
        if self._is_local_path:
            return await self._list_entity_files_local()
        if self._is_azure_url:
            return await self._list_entity_files_azure()
        return await self._list_entity_files_storage()

    async def _restore_file(self, stored_file_path: str) -> Optional[str]:
        """Restore file from appropriate backend."""
        if self._is_local_path:
            return await self._restore_file_local(stored_file_path)
        if self._is_azure_url:
            return await self._restore_file_azure(stored_file_path)
        return await self._restore_file_storage(stored_file_path)

    # =========================================================================
    # Entity reconstruction
    # =========================================================================

    def _reconstruct_entity(
        self, entity_dict: Dict[str, Any], restored_file_path: Optional[str] = None
    ) -> BaseEntity:
        """Reconstruct a BaseEntity from stored dict."""
        # Make a copy to avoid mutating
        entity_dict = dict(entity_dict)

        # Extract metadata
        entity_class_name = entity_dict.pop("__entity_class__", None)
        entity_module = entity_dict.pop("__entity_module__", None)
        entity_dict.pop("__captured_at__", None)
        entity_dict.pop("__stored_file__", None)

        if not entity_class_name or not entity_module:
            raise ValueError("Entity dict missing __entity_class__ or __entity_module__")

        # Import entity class
        try:
            module = importlib.import_module(entity_module)
            entity_class = getattr(module, entity_class_name)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Cannot reconstruct {entity_module}.{entity_class_name}: {e}")

        # Update local_path if file was restored
        if restored_file_path:
            entity_dict["local_path"] = restored_file_path

        return entity_class(**entity_dict)

    # =========================================================================
    # Main interface
    # =========================================================================

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from raw data storage.

        Reads manifest and iterates over all entity JSON files,
        reconstructing BaseEntity objects and optionally restoring files.
        """
        if self._is_local_path:
            mode = "local filesystem"
        elif self._is_azure_url:
            mode = f"Azure blob ({self._azure_account}/{self._azure_container})"
        else:
            mode = "storage backend"
        self.logger.info(f"📂 Snapshot replay from {mode}: {self.path}")

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

        for file_path in entity_files:
            try:
                entity_dict = await self._read_json(file_path)

                # Check if file needs to be restored
                stored_file = entity_dict.get("__stored_file__")
                restored_path = None
                if stored_file and self.restore_files:
                    restored_path = await self._restore_file(stored_file)

                # Reconstruct entity
                entity = self._reconstruct_entity(entity_dict, restored_path)
                yield entity

            except Exception as e:
                self.logger.warning(f"Failed to reconstruct entity from {file_path}: {e}")
                continue

    async def validate(self) -> bool:
        """Validate that the snapshot path exists and is readable."""
        self.logger.info(f"Validating snapshot source with path: {self.path}")

        if not self.path:
            self.logger.error("Snapshot validation failed: path is empty")
            return False

        # Check path exists based on storage type
        if self._is_local_path:
            if not self._local_path().exists():
                self.logger.error(f"Snapshot validation failed: path does not exist: {self.path}")
                return False
        elif self._is_azure_url:
            # Direct Azure URL access
            if not await self._azure_blob_exists("manifest.json"):
                self.logger.error(f"Snapshot validation failed: manifest not found at {self.path}")
                return False
        else:
            # Storage-relative path
            if not await self.storage.exists(f"{self.path}/manifest.json"):
                self.logger.error(f"Snapshot validation failed: manifest not found at {self.path}")
                return False

        try:
            manifest = await self._read_json("manifest.json")
            return "sync_id" in manifest
        except Exception as e:
            self.logger.error(f"Snapshot validation failed: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up temp files and close Azure client."""
        if self._temp_dir and self._temp_dir.exists():
            import shutil

            try:
                shutil.rmtree(self._temp_dir)
            except Exception:
                pass
            self._temp_dir = None

        # Note: Azure client cleanup happens via garbage collection
        # The async close should be called if we want explicit cleanup
        self._azure_client = None
