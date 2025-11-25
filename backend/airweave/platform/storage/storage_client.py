"""Cloud-agnostic storage client using filesystem (local or PVC-mounted).

The storage client uses a simple filesystem backend that works everywhere:
- Local development: ./local_storage directory
- Kubernetes with PVC: /data/airweave-storage (mounted from PVC)
- Any environment: Configured via settings.STORAGE_PATH

No cloud-specific SDKs required - pure filesystem operations.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, List, Optional

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger, logger


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def list_containers(self, logger: ContextualLogger) -> List[str]:
        """List all containers/directories."""
        pass

    @abstractmethod
    async def upload_file(
        self, logger: ContextualLogger, container_name: str, blob_name: str, data: BinaryIO
    ) -> bool:
        """Upload a file to storage."""
        pass

    @abstractmethod
    async def download_file(
        self, logger: ContextualLogger, container_name: str, blob_name: str
    ) -> Optional[bytes]:
        """Download a file from storage."""
        pass

    @abstractmethod
    async def delete_file(
        self, logger: ContextualLogger, container_name: str, blob_name: str
    ) -> bool:
        """Delete a file from storage."""
        pass

    @abstractmethod
    async def file_exists(
        self, logger: ContextualLogger, container_name: str, blob_name: str
    ) -> bool:
        """Check if a file exists."""
        pass


class FilesystemStorageBackend(StorageBackend):
    """Filesystem storage backend (local disk or PVC-mounted).

    Works everywhere - local development, Kubernetes with PVC, any platform.
    """

    def __init__(self, base_path: Path):
        """Initialize filesystem storage backend.

        Args:
            base_path: Base directory for storage (from settings.STORAGE_PATH)
        """
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def list_containers(self, logger: ContextualLogger) -> List[str]:
        """List all directories in local storage.

        Returns:
            List of directory names
        """
        try:
            directories = [d.name for d in self.base_path.iterdir() if d.is_dir()]
            logger.with_context(
                directories=directories,
            ).info(f"Listed {len(directories)} local directories")
            return directories
        except Exception as e:
            logger.error(f"Failed to list local directories: {e}")
            raise

    async def upload_file(
        self, logger: ContextualLogger, container_name: str, blob_name: str, data: BinaryIO
    ) -> bool:
        """Save a file to local storage.

        Args:
            logger: The logger to use
            container_name: Name of the directory
            blob_name: Name of the file
            data: File data to save

        Returns:
            True if successful
        """
        try:
            container_path = self.base_path / container_name
            container_path.mkdir(parents=True, exist_ok=True)

            # Sanitize blob_name to create valid file path
            safe_blob_name = blob_name.replace(":", "_").replace("/", os.sep)
            file_path = container_path / safe_blob_name

            # Ensure parent directories exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "wb") as f:
                f.write(data.read())

            logger.with_context(
                container=container_name,
                file=blob_name,
                path=str(file_path),
            ).info("Saved file locally")
            return True
        except Exception as e:
            logger.with_context(
                container=container_name,
                file=blob_name,
            ).error(f"Failed to save file locally: {e}")
            raise

    async def download_file(
        self, logger: ContextualLogger, container_name: str, blob_name: str
    ) -> Optional[bytes]:
        """Read a file from local storage.

        Args:
            logger: The logger to use
            container_name: Name of the directory
            blob_name: Name of the file

        Returns:
            File content as bytes, or None if not found
        """
        try:
            # Sanitize blob_name to create valid file path
            safe_blob_name = blob_name.replace(":", "_").replace("/", os.sep)
            file_path = self.base_path / container_name / safe_blob_name

            if not file_path.exists():
                logger.with_context(container=container_name, file=blob_name).debug(
                    "File not found"
                )
                return None

            with open(file_path, "rb") as f:
                data = f.read()

            logger.with_context(
                container=container_name,
                file=blob_name,
                size=len(data),
            ).info("Read file from local storage")
            return data
        except Exception as e:
            logger.with_context(
                container=container_name,
                file=blob_name,
            ).error(f"Failed to read local file: {e}")
            raise

    async def delete_file(
        self, logger: ContextualLogger, container_name: str, blob_name: str
    ) -> bool:
        """Delete a file from local storage.

        Args:
            logger: The logger to use
            container_name: Name of the directory
            blob_name: Name of the file

        Returns:
            True if successful
        """
        try:
            # Sanitize blob_name to create valid file path
            safe_blob_name = blob_name.replace(":", "_").replace("/", os.sep)
            file_path = self.base_path / container_name / safe_blob_name

            if not file_path.exists():
                logger.with_context(container=container_name, file=blob_name).debug(
                    "File not found"
                )
                return False

            file_path.unlink()
            logger.with_context(
                container=container_name,
                file=blob_name,
            ).debug("Deleted file from local storage")
            return True
        except Exception as e:
            logger.with_context(
                container=container_name,
                file=blob_name,
            ).error(f"Failed to delete local file: {e}")
            raise

    async def file_exists(
        self, logger: ContextualLogger, container_name: str, blob_name: str
    ) -> bool:
        """Check if a file exists in local storage.

        Args:
            logger: The logger to use
            container_name: Name of the directory
            blob_name: Name of the file

        Returns:
            True if the file exists
        """
        # Sanitize blob_name to create valid file path
        safe_blob_name = blob_name.replace(":", "_").replace("/", os.sep)
        file_path = self.base_path / container_name / safe_blob_name
        return file_path.exists()


class StorageClient:
    """Environment-aware storage client."""

    def __init__(self, backend: Optional[StorageBackend] = None):
        """Initialize storage client with auto-configuration.

        Args:
            backend: Optional storage backend. If not provided, will be auto-configured.
        """
        self.backend = backend or self._configure_backend()
        self._log_configuration()

    def _configure_backend(self) -> StorageBackend:
        """Configure filesystem storage backend.

        Uses settings.STORAGE_PATH for the storage location:
        - Local dev: ./local_storage (default)
        - Kubernetes: /data/airweave-storage (PVC mount)

        Returns:
            Configured filesystem storage backend
        """
        storage_path = Path(settings.STORAGE_PATH)

        logger.info(f"Configuring filesystem storage", extra={"storage_path": str(storage_path)})

        # Ensure base directory exists
        storage_path.mkdir(parents=True, exist_ok=True)

        # Create default containers (subdirectories)
        self._ensure_default_containers(storage_path)

        logger.info(
            "Filesystem storage configured successfully", extra={"storage_path": str(storage_path)}
        )

        return FilesystemStorageBackend(storage_path)

    def _ensure_default_containers(self, base_path: Path) -> None:
        """Ensure default storage containers (subdirectories) exist.

        Args:
            base_path: Base directory for storage
        """
        default_containers = ["sync-data", "sync-metadata", "processed-files", "backup"]
        for container in default_containers:
            (base_path / container).mkdir(parents=True, exist_ok=True)

        logger.debug(
            f"Ensured {len(default_containers)} storage containers exist",
            extra={"containers": default_containers},
        )

    def _log_configuration(self) -> None:
        """Log the current storage configuration."""
        backend_type = type(self.backend).__name__
        logger.with_context(
            storage_path=settings.STORAGE_PATH,
            backend_type=backend_type,
        ).info("Storage client configured")

    # Delegate all storage operations to the backend
    async def list_containers(self, logger: ContextualLogger) -> List[str]:
        """List all containers/directories."""
        return await self.backend.list_containers(logger)

    async def upload_file(
        self, logger: ContextualLogger, container_name: str, blob_name: str, data: BinaryIO
    ) -> bool:
        """Upload a file to storage."""
        return await self.backend.upload_file(logger, container_name, blob_name, data)

    async def download_file(
        self, logger: ContextualLogger, container_name: str, blob_name: str
    ) -> Optional[bytes]:
        """Download a file from storage."""
        return await self.backend.download_file(logger, container_name, blob_name)

    async def delete_file(
        self, logger: ContextualLogger, container_name: str, blob_name: str
    ) -> bool:
        """Delete a file from storage."""
        return await self.backend.delete_file(logger, container_name, blob_name)

    async def file_exists(
        self, logger: ContextualLogger, container_name: str, blob_name: str
    ) -> bool:
        """Check if a file exists."""
        return await self.backend.file_exists(logger, container_name, blob_name)
