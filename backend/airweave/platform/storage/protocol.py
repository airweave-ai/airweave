"""Storage backend protocol definition.

Defines the interface that all storage backends must implement.
Uses Python's Protocol for structural subtyping (duck typing with type hints).
"""

from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol defining the storage backend interface.

    All paths are relative strings (e.g., "raw/sync123/manifest.json").
    Implementations handle the actual storage location (local filesystem,
    cloud bucket, etc.).

    Implementations:
        - FilesystemBackend: Local filesystem or K8s PVC
        - AzureBlobBackend: Azure Blob Storage
        - S3Backend: AWS S3
        - GCSBackend: Google Cloud Storage
    """

    async def write_json(self, path: str, data: Dict[str, Any]) -> None:
        """Write JSON data to storage.

        Args:
            path: Relative path (e.g., "raw/sync123/manifest.json")
            data: Dict to serialize as JSON
        """
        ...

    async def read_json(self, path: str) -> Dict[str, Any]:
        """Read JSON data from storage.

        Args:
            path: Relative path

        Returns:
            Deserialized dict

        Raises:
            StorageNotFoundError: If path doesn't exist
        """
        ...

    async def write_file(self, path: str, content: bytes) -> None:
        """Write binary content to storage.

        Args:
            path: Relative path
            content: Binary content
        """
        ...

    async def read_file(self, path: str) -> bytes:
        """Read binary content from storage.

        Args:
            path: Relative path

        Returns:
            Binary content

        Raises:
            StorageNotFoundError: If path doesn't exist
        """
        ...

    async def exists(self, path: str) -> bool:
        """Check if a path exists.

        Args:
            path: Relative path

        Returns:
            True if exists
        """
        ...

    async def delete(self, path: str) -> bool:
        """Delete a file or directory.

        Args:
            path: Relative path

        Returns:
            True if deleted, False if didn't exist
        """
        ...

    async def list_files(self, prefix: str = "") -> List[str]:
        """List files under a prefix (recursive).

        Args:
            prefix: Path prefix to filter by

        Returns:
            List of relative paths
        """
        ...

    async def list_dirs(self, prefix: str = "") -> List[str]:
        """List immediate subdirectories under a prefix.

        Args:
            prefix: Path prefix

        Returns:
            List of directory paths
        """
        ...

    async def count_files(self, prefix: str = "", pattern: str = "*") -> int:
        """Count files under a prefix without building a full list.

        Much faster than len(await list_files()) for large directories.

        Args:
            prefix: Path prefix to filter by
            pattern: File pattern to match (e.g., "*.json")

        Returns:
            Number of matching files
        """
        ...
