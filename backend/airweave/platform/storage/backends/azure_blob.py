"""Azure Blob Storage backend.

Implements StorageBackend protocol for Azure Blob Storage.
Uses DefaultAzureCredential for authentication (managed identity, CLI, env vars).
"""

import fnmatch
import json
from typing import Any, Dict, List

from airweave.core.logging import logger
from airweave.platform.storage.exceptions import (
    StorageException,
    StorageNotFoundError,
)
from airweave.platform.storage.protocol import StorageBackend


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
        """Delete blob or all blobs under prefix.

        Handles both flat blob storage and hierarchical namespace (ADLS Gen2).
        For hierarchical namespace, deletes all blobs under the prefix first.
        """
        blob_path = self._resolve(path)

        deleted_count = 0
        try:
            container_client = await self._get_container_client()

            # First, try to list and delete all blobs under this prefix
            # This handles both single files and directories
            prefix = blob_path
            if not prefix.endswith("/"):
                # Check if it's a file first
                blob_client = container_client.get_blob_client(blob_path)
                try:
                    props = await blob_client.get_blob_properties()
                    # It's a blob (not a directory), delete it directly
                    if props.get("metadata", {}).get("hdi_isfolder") != "true":
                        await blob_client.delete_blob()
                        return True
                except Exception:
                    pass  # Not a blob, try as prefix

                prefix = blob_path + "/"

            # List and delete all blobs under the prefix
            async for blob in container_client.list_blobs(name_starts_with=prefix):
                # Skip directory markers in hierarchical namespace
                if blob.get("metadata", {}).get("hdi_isfolder") == "true":
                    continue
                blob_to_delete = container_client.get_blob_client(blob.name)
                try:
                    await blob_to_delete.delete_blob()
                    deleted_count += 1
                except Exception:
                    pass  # May fail for directories, continue

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
