"""Unified storage backend for Airweave.

Provides a single abstract interface with Filesystem and Azure Blob implementations.
All methods are async-first to work well with FastAPI.

Usage:
    from airweave.platform.storage import get_storage_backend

    backend = get_storage_backend()  # Auto-resolves based on ENVIRONMENT
    await backend.write_json("snapshots/my_data/manifest.json", {"key": "value"})
    data = await backend.read_json("snapshots/my_data/manifest.json")
"""

import asyncio
import fnmatch
import json
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Union

from airweave.core.logging import logger
from airweave.platform.storage.exceptions import (
    StorageException,
    StorageNotFoundError,
)


class StorageBackend(ABC):
    """Abstract storage backend interface.

    Provides a simple, unified API for storing:
    - JSON data (serialized dicts)
    - Binary files (bytes)

    All paths are relative strings (e.g., "snapshots/gmail_abc123/manifest.json").
    Implementations handle the actual storage location.
    """

    @abstractmethod
    async def write_json(self, path: str, data: Dict[str, Any]) -> None:
        """Write JSON data to storage.

        Args:
            path: Relative path (e.g., "snapshots/data.json")
            data: Dict to serialize as JSON
        """
        pass

    @abstractmethod
    async def read_json(self, path: str) -> Dict[str, Any]:
        """Read JSON data from storage.

        Args:
            path: Relative path

        Returns:
            Deserialized dict

        Raises:
            StorageNotFoundError: If path doesn't exist
        """
        pass

    @abstractmethod
    async def write_file(self, path: str, content: bytes) -> None:
        """Write binary content to storage.

        Args:
            path: Relative path
            content: Binary content
        """
        pass

    @abstractmethod
    async def read_file(self, path: str) -> bytes:
        """Read binary content from storage.

        Args:
            path: Relative path

        Returns:
            Binary content

        Raises:
            StorageNotFoundError: If path doesn't exist
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a path exists.

        Args:
            path: Relative path

        Returns:
            True if exists
        """
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete a file or directory.

        Args:
            path: Relative path

        Returns:
            True if deleted, False if didn't exist
        """
        pass

    @abstractmethod
    async def list_files(self, prefix: str = "") -> List[str]:
        """List files under a prefix (recursive).

        Args:
            prefix: Path prefix to filter by

        Returns:
            List of relative paths
        """
        pass

    @abstractmethod
    async def list_dirs(self, prefix: str = "") -> List[str]:
        """List immediate subdirectories under a prefix.

        Args:
            prefix: Path prefix

        Returns:
            List of directory paths
        """
        pass

    @abstractmethod
    async def count_files(self, prefix: str = "", pattern: str = "*") -> int:
        """Count files under a prefix without building a full list.

        Much faster than len(await list_files()) for large directories.

        Args:
            prefix: Path prefix to filter by
            pattern: File pattern to match (e.g., "*.json")

        Returns:
            Number of matching files
        """
        pass


class FilesystemBackend(StorageBackend):
    """Filesystem-based storage backend.

    Works with:
    - Local development: local_storage/ (at repo root, mounted to /app/local_storage)
    - Kubernetes: PVC-mounted path (e.g., /data/airweave-storage)

    Thread-safe for basic operations (relies on OS-level file locking).
    """

    def __init__(self, base_path: Union[str, Path]):
        """Initialize filesystem backend.

        Args:
            base_path: Root directory for all storage operations
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"FilesystemBackend initialized at {self.base_path}")

    def _resolve(self, path: str) -> Path:
        """Resolve relative path to absolute."""
        # Normalize path separators
        normalized = path.replace("/", os.sep)
        return self.base_path / normalized

    async def write_json(self, path: str, data: Dict[str, Any]) -> None:
        """Write JSON to filesystem."""

        def _write_json_sync():
            full_path = self._resolve(path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

        try:
            await asyncio.to_thread(_write_json_sync)
        except Exception as e:
            raise StorageException(f"Failed to write JSON to {path}: {e}")

    async def read_json(self, path: str) -> Dict[str, Any]:
        """Read JSON from filesystem."""

        def _read_json_sync():
            full_path = self._resolve(path)
            if not full_path.exists():
                raise StorageNotFoundError(f"Path not found: {path}")
            with open(full_path, "r", encoding="utf-8") as f:
                return json.load(f)

        try:
            return await asyncio.to_thread(_read_json_sync)
        except StorageNotFoundError:
            raise
        except json.JSONDecodeError as e:
            raise StorageException(f"Invalid JSON at {path}: {e}")
        except Exception as e:
            raise StorageException(f"Failed to read JSON from {path}: {e}")

    async def write_file(self, path: str, content: bytes) -> None:
        """Write binary content to filesystem."""

        def _write_file_sync():
            full_path = self._resolve(path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, "wb") as f:
                f.write(content)

        try:
            await asyncio.to_thread(_write_file_sync)
        except Exception as e:
            raise StorageException(f"Failed to write file to {path}: {e}")

    async def read_file(self, path: str) -> bytes:
        """Read binary content from filesystem."""

        def _read_file_sync():
            full_path = self._resolve(path)
            if not full_path.exists():
                raise StorageNotFoundError(f"Path not found: {path}")
            with open(full_path, "rb") as f:
                return f.read()

        try:
            return await asyncio.to_thread(_read_file_sync)
        except StorageNotFoundError:
            raise
        except Exception as e:
            raise StorageException(f"Failed to read file from {path}: {e}")

    async def exists(self, path: str) -> bool:
        """Check if path exists on filesystem."""
        return self._resolve(path).exists()

    async def delete(self, path: str) -> bool:
        """Delete file or directory from filesystem."""

        def _delete_sync():
            full_path = self._resolve(path)
            if not full_path.exists():
                return False
            if full_path.is_dir():
                shutil.rmtree(full_path)
            else:
                full_path.unlink()
            return True

        try:
            return await asyncio.to_thread(_delete_sync)
        except Exception as e:
            logger.error(f"Failed to delete {path}: {e}")
            return False

    async def list_files(self, prefix: str = "") -> List[str]:
        """List all files under prefix (recursive)."""

        def _list_files_sync():
            base = self._resolve(prefix) if prefix else self.base_path
            if not base.exists():
                return []

            files = []
            for item in base.rglob("*"):
                if item.is_file():
                    rel_path = str(item.relative_to(self.base_path))
                    # Normalize to forward slashes for consistency
                    files.append(rel_path.replace(os.sep, "/"))

            return sorted(files)

        return await asyncio.to_thread(_list_files_sync)

    async def list_dirs(self, prefix: str = "") -> List[str]:
        """List immediate subdirectories under prefix."""

        def _list_dirs_sync():
            base = self._resolve(prefix) if prefix else self.base_path
            if not base.exists():
                return []

            dirs = []
            for item in base.iterdir():
                if item.is_dir():
                    rel_path = str(item.relative_to(self.base_path))
                    dirs.append(rel_path.replace(os.sep, "/"))

            return sorted(dirs)

        return await asyncio.to_thread(_list_dirs_sync)

    async def count_files(self, prefix: str = "", pattern: str = "*") -> int:
        """Count files under prefix without building full list (fast)."""

        def _count_files_sync():
            base = self._resolve(prefix) if prefix else self.base_path
            if not base.exists():
                return 0

            count = 0
            for item in base.rglob(pattern):
                if item.is_file():
                    count += 1

            return count

        return await asyncio.to_thread(_count_files_sync)


class AzureBlobBackend(StorageBackend):
    """Azure Blob Storage backend.

    Uses DefaultAzureCredential for authentication (works with Azure CLI,
    managed identity, service principal, etc.).

    Uses the async Azure SDK (azure.storage.blob.aio) for non-blocking operations.
    """

    def __init__(
        self,
        storage_account: str,
        container: str,
        prefix: str = "",
    ):
        """Initialize Azure Blob backend.

        Args:
            storage_account: Azure storage account name
            container: Container name
            prefix: Optional prefix for all paths
        """
        self.storage_account = storage_account
        self.container_name = container
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        self._blob_service_client = None
        self._container_client = None
        self._credential = None

        logger.debug(
            f"AzureBlobBackend initialized: {storage_account}/{container}"
            f"{f'/{prefix}' if prefix else ''}"
        )

    async def _get_blob_service_client(self):
        """Lazy-load async blob service client."""
        if self._blob_service_client is None:
            try:
                from azure.identity.aio import DefaultAzureCredential
                from azure.storage.blob.aio import BlobServiceClient

                account_url = f"https://{self.storage_account}.blob.core.windows.net"
                self._credential = DefaultAzureCredential()
                self._blob_service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=self._credential,
                )
            except ImportError as e:
                raise StorageException(
                    "Azure SDK not installed. Install with: "
                    "pip install azure-storage-blob azure-identity"
                ) from e
        return self._blob_service_client

    async def _get_container_client(self):
        """Lazy-load async container client."""
        if self._container_client is None:
            blob_service_client = await self._get_blob_service_client()
            self._container_client = blob_service_client.get_container_client(self.container_name)
        return self._container_client

    def _resolve(self, path: str) -> str:
        """Resolve path with prefix."""
        return f"{self.prefix}{path}"

    async def close(self) -> None:
        """Close async clients and release resources.

        Should be called when the backend is no longer needed.
        """
        if self._blob_service_client is not None:
            await self._blob_service_client.close()
            self._blob_service_client = None
            self._container_client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None

    async def write_json(self, path: str, data: Dict[str, Any]) -> None:
        """Write JSON to Azure Blob."""
        blob_path = self._resolve(path)
        try:
            content = json.dumps(data, indent=2, default=str)
            container_client = await self._get_container_client()
            blob_client = container_client.get_blob_client(blob_path)
            await blob_client.upload_blob(content, overwrite=True)
        except Exception as e:
            raise StorageException(f"Failed to write JSON to {path}: {e}")

    async def read_json(self, path: str) -> Dict[str, Any]:
        """Read JSON from Azure Blob."""
        blob_path = self._resolve(path)
        try:
            container_client = await self._get_container_client()
            blob_client = container_client.get_blob_client(blob_path)
            if not await blob_client.exists():
                raise StorageNotFoundError(f"Path not found: {path}")
            download_stream = await blob_client.download_blob()
            content = (await download_stream.readall()).decode("utf-8")
            return json.loads(content)
        except StorageNotFoundError:
            raise
        except json.JSONDecodeError as e:
            raise StorageException(f"Invalid JSON at {path}: {e}")
        except Exception as e:
            raise StorageException(f"Failed to read JSON from {path}: {e}")

    async def write_file(self, path: str, content: bytes) -> None:
        """Write binary content to Azure Blob."""
        blob_path = self._resolve(path)
        try:
            container_client = await self._get_container_client()
            blob_client = container_client.get_blob_client(blob_path)
            await blob_client.upload_blob(content, overwrite=True)
        except Exception as e:
            raise StorageException(f"Failed to write file to {path}: {e}")

    async def read_file(self, path: str) -> bytes:
        """Read binary content from Azure Blob."""
        blob_path = self._resolve(path)
        try:
            container_client = await self._get_container_client()
            blob_client = container_client.get_blob_client(blob_path)
            if not await blob_client.exists():
                raise StorageNotFoundError(f"Path not found: {path}")
            download_stream = await blob_client.download_blob()
            return await download_stream.readall()
        except StorageNotFoundError:
            raise
        except Exception as e:
            raise StorageException(f"Failed to read file from {path}: {e}")

    async def exists(self, path: str) -> bool:
        """Check if blob exists."""
        blob_path = self._resolve(path)
        try:
            container_client = await self._get_container_client()
            blob_client = container_client.get_blob_client(blob_path)
            return await blob_client.exists()
        except Exception:
            return False

    async def delete(self, path: str) -> bool:
        """Delete blob or all blobs under prefix."""
        blob_path = self._resolve(path)

        deleted_count = 0
        try:
            container_client = await self._get_container_client()

            # Try direct blob delete first
            blob_client = container_client.get_blob_client(blob_path)
            if await blob_client.exists():
                await blob_client.delete_blob()
                return True

            # If not a blob, try as prefix (directory-like)
            prefix = blob_path if blob_path.endswith("/") else blob_path + "/"
            async for blob in container_client.list_blobs(name_starts_with=prefix):
                blob_to_delete = container_client.get_blob_client(blob.name)
                await blob_to_delete.delete_blob()
                deleted_count += 1

            return deleted_count > 0

        except Exception as e:
            logger.error(f"Failed to delete {path}: {e}")
            return False

    async def list_files(self, prefix: str = "") -> List[str]:
        """List all blobs under prefix."""
        full_prefix = self._resolve(prefix)
        if prefix and not full_prefix.endswith("/"):
            full_prefix += "/"

        files = []
        try:
            container_client = await self._get_container_client()
            async for blob in container_client.list_blobs(name_starts_with=full_prefix):
                # Return path relative to our prefix
                rel_path = blob.name
                if self.prefix and rel_path.startswith(self.prefix):
                    rel_path = rel_path[len(self.prefix) :]
                files.append(rel_path)
        except Exception as e:
            logger.error(f"Failed to list files in {prefix}: {e}")

        return sorted(files)

    async def list_dirs(self, prefix: str = "") -> List[str]:
        """List 'directories' under prefix (unique path components)."""
        full_prefix = self._resolve(prefix)
        if not full_prefix.endswith("/"):
            full_prefix += "/"

        dirs = set()
        try:
            container_client = await self._get_container_client()
            async for blob in container_client.list_blobs(name_starts_with=full_prefix):
                # Extract first path component after prefix
                rel_path = blob.name[len(full_prefix) :]
                if "/" in rel_path:
                    dir_name = rel_path.split("/")[0]
                    full_dir = f"{prefix}/{dir_name}" if prefix else dir_name
                    dirs.add(full_dir)
        except Exception as e:
            logger.error(f"Failed to list dirs in {prefix}: {e}")

        return sorted(dirs)

    async def count_files(self, prefix: str = "", pattern: str = "*") -> int:
        """Count blobs under prefix without building full list (fast)."""
        full_prefix = self._resolve(prefix)
        if prefix and not full_prefix.endswith("/"):
            full_prefix += "/"

        count = 0
        try:
            container_client = await self._get_container_client()
            async for blob in container_client.list_blobs(name_starts_with=full_prefix):
                rel_path = blob.name[len(full_prefix) :]
                if pattern == "*" or fnmatch.fnmatch(rel_path, pattern):
                    count += 1
        except Exception as e:
            logger.error(f"Failed to count files in {prefix}: {e}")

        return count
