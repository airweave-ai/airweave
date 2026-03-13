"""Storage domain protocol definitions.

Defines the interfaces that storage backends and services must implement.
Uses Python's Protocol for structural subtyping (duck typing with type hints).
"""

from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Dict,
    List,
    Optional,
    Protocol,
    Tuple,
    runtime_checkable,
)
from uuid import UUID

if TYPE_CHECKING:
    from airweave.core.logging import ContextualLogger


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


@runtime_checkable
class SyncFileManagerProtocol(Protocol):
    """Protocol for sync-aware file management.

    Covers sync-scoped file storage, CTTI global storage,
    metadata tracking, and local caching.
    """

    async def check_file_exists(
        self, logger: "ContextualLogger", sync_id: UUID, entity_id: str
    ) -> bool:
        """Check if a file exists in sync-scoped storage."""
        ...

    async def store_file_entity(
        self, logger: "ContextualLogger", entity: Any, content: BinaryIO
    ) -> Any:
        """Store a file entity in persistent storage."""
        ...

    async def is_entity_fully_processed(
        self, logger: "ContextualLogger", cache_key: str
    ) -> bool:
        """Check if an entity has been fully processed."""
        ...

    async def mark_entity_processed(
        self, logger: "ContextualLogger", sync_id: UUID, entity_id: str, chunk_count: int
    ) -> None:
        """Mark an entity as fully processed after chunking."""
        ...

    async def get_cached_file_path(
        self, logger: "ContextualLogger", sync_id: UUID, entity_id: str, file_name: str
    ) -> Optional[str]:
        """Get or create a local cache path for a file."""
        ...

    async def cleanup_temp_file(
        self, logger: "ContextualLogger", file_path: str
    ) -> None:
        """Clean up a temporary file after processing."""
        ...

    async def get_file_path(
        self, entity_id: str, sync_id: UUID, filename: str, logger: "ContextualLogger"
    ) -> Optional[str]:
        """Get file path for an entity (from cache or temp directory)."""
        ...

    async def get_file_content(
        self, entity_id: str, sync_id: UUID, filename: str, logger: "ContextualLogger"
    ) -> Optional[bytes]:
        """Get file content as bytes."""
        ...

    async def check_ctti_file_exists(
        self, logger: "ContextualLogger", entity_id: str
    ) -> bool:
        """Check if a CTTI file exists in global storage."""
        ...

    async def store_ctti_file(
        self, logger: "ContextualLogger", entity: Any, content: BinaryIO
    ) -> Any:
        """Store a CTTI file in global storage."""
        ...

    async def is_ctti_entity_processed(
        self, logger: "ContextualLogger", entity_id: str
    ) -> bool:
        """Check if a CTTI entity has been fully processed."""
        ...

    async def get_ctti_file_content(
        self, logger: "ContextualLogger", entity_id: str
    ) -> Optional[str]:
        """Retrieve CTTI file content from global storage."""
        ...

    async def download_ctti_file(
        self,
        logger: "ContextualLogger",
        entity_id: str,
        output_path: Optional[str] = None,
        create_dirs: bool = True,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Download a CTTI file by entity ID."""
        ...

    async def download_ctti_files_batch(
        self,
        logger: "ContextualLogger",
        entity_ids: List[str],
        output_dir: Optional[str] = None,
        create_dirs: bool = True,
        continue_on_error: bool = True,
    ) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
        """Download multiple CTTI files in batch."""
        ...
