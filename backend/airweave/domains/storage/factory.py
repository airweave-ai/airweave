"""Storage backend factory.

Creates the appropriate storage backend based on configuration.
Uses settings from core.config for all configuration values.

The Container (core.container) calls this once at startup and owns the
singleton. Standalone scripts may still call get_storage_backend() directly.
"""

from typing import TYPE_CHECKING

from airweave.core.config import StorageBackendType, settings
from airweave.core.logging import logger

if TYPE_CHECKING:
    from airweave.domains.storage.protocols import StorageBackend


def get_storage_backend() -> "StorageBackend":
    """Create a storage backend from the current settings.

    Returns:
        StorageBackend: Configured storage backend instance

    Raises:
        ValueError: If required configuration is missing for the selected backend
    """
    backend_type = settings.STORAGE_BACKEND

    logger.info(f"Initializing storage backend: {backend_type}")

    if backend_type == StorageBackendType.FILESYSTEM:
        from airweave.domains.storage.backends.filesystem import FilesystemBackend

        return FilesystemBackend(base_path=settings.STORAGE_PATH)

    elif backend_type == StorageBackendType.AZURE:
        if not settings.STORAGE_AZURE_ACCOUNT:
            raise ValueError("STORAGE_AZURE_ACCOUNT required for azure backend")
        from airweave.domains.storage.backends.azure_blob import AzureBlobBackend

        return AzureBlobBackend(
            storage_account=settings.STORAGE_AZURE_ACCOUNT,
            container=settings.STORAGE_AZURE_CONTAINER,
            prefix=settings.STORAGE_AZURE_PREFIX,
        )

    elif backend_type == StorageBackendType.AWS:
        if not settings.STORAGE_AWS_BUCKET:
            raise ValueError("STORAGE_AWS_BUCKET required for aws backend")
        if not settings.STORAGE_AWS_REGION:
            raise ValueError("STORAGE_AWS_REGION required for aws backend")
        from airweave.domains.storage.backends.aws_s3 import S3Backend

        return S3Backend(
            bucket=settings.STORAGE_AWS_BUCKET,
            region=settings.STORAGE_AWS_REGION,
            prefix=settings.STORAGE_AWS_PREFIX,
            endpoint_url=settings.STORAGE_AWS_ENDPOINT_URL,
        )

    elif backend_type == StorageBackendType.GCP:
        if not settings.STORAGE_GCP_BUCKET:
            raise ValueError("STORAGE_GCP_BUCKET required for gcp backend")
        from airweave.domains.storage.backends.gcp_gcs import GCSBackend

        return GCSBackend(
            bucket=settings.STORAGE_GCP_BUCKET,
            project=settings.STORAGE_GCP_PROJECT,
            prefix=settings.STORAGE_GCP_PREFIX,
        )

    else:
        valid_options = ", ".join(t.value for t in StorageBackendType)
        raise ValueError(f"Unknown STORAGE_BACKEND: {backend_type}. Valid options: {valid_options}")
