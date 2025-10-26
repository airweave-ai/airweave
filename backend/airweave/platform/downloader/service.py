"""File download service for downloading files to local disk."""

import os
import shutil
from typing import Callable, Optional, Tuple
from uuid import uuid4

import httpx

from airweave.core.logging import ContextualLogger
from airweave.platform.entities._base import FileEntity
from airweave.platform.sync.file_types import SUPPORTED_FILE_EXTENSIONS


class FileDownloadService:
    """Simple file download service that writes files to local disk.

    Responsibilities:
    - Validate files before download (extension, size)
    - Download file from URL to local temp path (sync_job_id scoped)
    - Save in-memory bytes to local temp path
    - Cleanup temp directory after sync completes
    """

    # Maximum file size we'll download (1GB)
    MAX_FILE_SIZE_BYTES = 1073741824

    def __init__(self, sync_job_id: str):
        """Initialize file download service with sync-scoped temp directory.

        Args:
            sync_job_id: Sync job ID for organizing temp files
        """
        self.sync_job_id = sync_job_id
        self.base_temp_dir = f"/tmp/airweave/processing/{sync_job_id}"
        self._ensure_base_dir()

    def _ensure_base_dir(self) -> None:
        """Ensure base temporary directory exists."""
        os.makedirs(self.base_temp_dir, exist_ok=True)

    async def _validate_file_before_download(
        self,
        entity: FileEntity,
        http_client_factory: Callable,
        access_token_provider: Callable,
        logger: ContextualLogger,
    ) -> Tuple[bool, Optional[str]]:
        """Validate file before download (extension and size check).

        Args:
            entity: FileEntity to validate
            http_client_factory: Factory that returns async HTTP client context manager
            access_token_provider: Async callable that returns access token or None
            logger: Logger for diagnostics

        Returns:
            Tuple of (should_download, skip_reason)
            - should_download: True if file should be downloaded
            - skip_reason: Reason for skipping (if should_download is False)
        """
        # Check file extension against supported types
        _, ext = os.path.splitext(entity.name)
        ext = ext.lower()

        if ext not in SUPPORTED_FILE_EXTENSIONS:
            return False, f"Unsupported file extension: {ext}"

        # Check file size via HEAD request
        if not entity.url:
            return False, "No download URL"

        # Check if pre-signed URL (no auth header needed)
        is_presigned_url = "X-Amz-Algorithm" in entity.url

        try:
            # Get access token
            token = await access_token_provider()
            if not token and not is_presigned_url:
                return False, "No access token available"

            # Send HEAD request to get file size
            async with http_client_factory(timeout=httpx.Timeout(30.0)) as client:
                headers = {}
                if token and not is_presigned_url:
                    headers["Authorization"] = f"Bearer {token}"

                try:
                    response = await client.head(
                        entity.url, headers=headers, follow_redirects=True, timeout=10.0
                    )
                    response.raise_for_status()

                    # Check Content-Length header
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        size_bytes = int(content_length)
                        if size_bytes > self.MAX_FILE_SIZE_BYTES:
                            size_mb = size_bytes / (1024 * 1024)
                            return False, f"File too large: {size_mb:.1f}MB (max 1GB)"

                except (httpx.HTTPError, ValueError) as e:
                    # HEAD request failed - log but allow download attempt
                    # Some servers don't support HEAD or return incorrect size
                    logger.debug(
                        f"HEAD request failed for {entity.name}: {e}, will attempt download"
                    )

        except Exception as e:
            # Validation error - log but allow download attempt
            logger.debug(f"File validation error for {entity.name}: {e}, will attempt download")

        return True, None

    async def download_from_url(
        self,
        entity: FileEntity,
        http_client_factory: Callable,
        access_token_provider: Callable,
        logger: ContextualLogger,
    ) -> Optional[FileEntity]:
        """Download file from URL to local disk with pre-download validation.

        Validates file extension and size before downloading. Returns None if file
        should be skipped (unsupported type or too large).

        Args:
            entity: FileEntity with url to fetch
            http_client_factory: Factory that returns async HTTP client context manager
            access_token_provider: Async callable that returns access token or None
            logger: Logger for diagnostics

        Returns:
            FileEntity with local_path set, or None if file should be skipped

        Raises:
            ValueError: If url is missing or access token unavailable
            httpx.HTTPStatusError: On HTTP errors
            IOError: On file write errors
        """
        # Validate file before downloading
        should_download, skip_reason = await self._validate_file_before_download(
            entity, http_client_factory, access_token_provider, logger
        )

        if not should_download:
            logger.info(f"Skipping download of {entity.name}: {skip_reason}")
            return None

        if not entity.url:
            raise ValueError(f"No download URL for file {entity.name}")

        # Generate temp path
        file_uuid = uuid4()
        safe_filename = self._safe_filename(entity.name)
        temp_path = os.path.join(self.base_temp_dir, f"{file_uuid}-{safe_filename}")

        # Check if pre-signed URL
        is_presigned_url = "X-Amz-Algorithm" in entity.url

        # Get access token
        token = await access_token_provider()
        if not token and not is_presigned_url:
            raise ValueError(f"No access token available for downloading {entity.name}")

        logger.debug(
            f"Downloading file from URL: {entity.name} "
            f"(pre-signed: {is_presigned_url}, has_token: {bool(token)})"
        )

        try:
            # Stream download to disk
            async with http_client_factory(timeout=httpx.Timeout(180.0, read=540.0)) as client:
                headers = {}
                if token and not is_presigned_url:
                    headers["Authorization"] = f"Bearer {token}"

                async with client.stream(
                    "GET", entity.url, headers=headers, follow_redirects=True
                ) as response:
                    response.raise_for_status()

                    # Ensure directory exists
                    os.makedirs(os.path.dirname(temp_path), exist_ok=True)

                    # Write to disk
                    with open(temp_path, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)

            logger.debug(f"Downloaded file to: {temp_path}")

            # Set local path on entity
            entity.local_path = temp_path

            return entity

        except Exception:
            # Clean up partial file
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise

    async def save_bytes(
        self, entity: FileEntity, content: bytes, logger: ContextualLogger
    ) -> FileEntity:
        """Save in-memory bytes directly to local disk.

        Args:
            entity: FileEntity to save
            content: File content as bytes
            logger: Logger for diagnostics

        Returns:
            FileEntity with local_path set (or raises exception)

        Raises:
            IOError: On file write errors
        """
        # Generate temp path
        file_uuid = uuid4()
        safe_filename = self._safe_filename(entity.name)
        temp_path = os.path.join(self.base_temp_dir, f"{file_uuid}-{safe_filename}")

        logger.debug(f"Saving in-memory bytes to disk: {entity.name} ({len(content)} bytes)")

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)

            # Write bytes to disk
            with open(temp_path, "wb") as f:
                f.write(content)

            logger.debug(f"Saved file to: {temp_path}")

            # Set local path on entity
            entity.local_path = temp_path

            return entity

        except Exception as e:
            # Clean up partial file
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise IOError(f"Failed to save bytes for {entity.name}: {e}") from e

    async def cleanup_sync_directory(self, logger: ContextualLogger) -> None:
        """Remove entire sync_job_id temp directory.

        Called in orchestrator's finally block as safety net to ensure all temp files
        are cleaned up, even if progressive cleanup failed or sync failed mid-batch.

        Args:
            logger: Logger for diagnostics
        """
        try:
            if not os.path.exists(self.base_temp_dir):
                logger.debug(f"Temp directory already cleaned: {self.base_temp_dir}")
                return

            # Count files before deletion for logging
            file_count = 0
            try:
                for _, _, files in os.walk(self.base_temp_dir):
                    file_count += len(files)
            except Exception:
                pass

            # Remove entire directory tree
            shutil.rmtree(self.base_temp_dir)

            # Verify deletion succeeded
            if os.path.exists(self.base_temp_dir):
                logger.warning(
                    f"Failed to delete temp directory: {self.base_temp_dir} "
                    f"(may cause disk space issues)"
                )
            else:
                logger.info(
                    f"Final cleanup: removed temp directory {self.base_temp_dir} "
                    f"({file_count} files)"
                )

        except Exception as e:
            # Never raise from cleanup - we're likely in a finally block
            logger.warning(f"Temp directory cleanup error: {e}", exc_info=True)

    @staticmethod
    def _safe_filename(filename: str) -> str:
        """Create a safe version of a filename.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for filesystem
        """
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
        return safe_name.strip()
