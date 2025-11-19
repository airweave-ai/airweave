"""File download service for downloading files to local disk."""

import os
import shutil
from typing import Callable, Optional, Tuple
from uuid import uuid4

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.platform.entities._base import FileEntity
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.sync.file_types import SUPPORTED_FILE_EXTENSIONS


class FileSkippedException(Exception):
    """Exception raised when a file is intentionally skipped (not an error).

    This is raised when files are skipped for valid reasons like:
    - Unsupported file extension
    - File too large
    - No download URL available

    This is NOT an error condition - it's expected behavior during normal sync operations.
    """

    def __init__(self, reason: str, filename: str):
        """Initialize file skipped exception.

        Args:
            reason: Human-readable reason why file was skipped
            filename: Name of the file that was skipped
        """
        self.reason = reason
        self.filename = filename
        super().__init__(f"File '{filename}' skipped: {reason}")


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

    @retry(
        stop=stop_after_attempt(5),  # Increased for aggressive rate limits
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _head_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict,
        logger: ContextualLogger,
    ) -> httpx.Response:
        """Make HEAD request with retry logic for rate limits and timeouts.

        Args:
            client: HTTP client
            url: URL to request
            headers: Request headers
            logger: Logger for diagnostics

        Returns:
            HTTP response

        Raises:
            httpx.HTTPStatusError: On HTTP errors (after retries)
        """
        try:
            response = await client.head(url, headers=headers, follow_redirects=True, timeout=10.0)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            # Log rate limits (will be retried)
            if e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After", "unknown")
                logger.warning(
                    f"Rate limit hit (429) during HEAD request for file validation "
                    f"(will retry after {retry_after}s)"
                )
            raise

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

        Raises:
            ValueError: If URL or access token is unavailable (actual errors, not intentional skips)
        """
        # Check for missing URL (actual error, not intentional skip)
        if not entity.url:
            raise ValueError(f"No download URL for file {entity.name}")

        # Check file extension against supported types
        _, ext = os.path.splitext(entity.name)
        ext = ext.lower()

        if ext not in SUPPORTED_FILE_EXTENSIONS:
            return False, f"Unsupported file extension: {ext}"

        # Check if pre-signed URL (no auth header needed)
        is_presigned_url = "X-Amz-Algorithm" in entity.url

        try:
            # Get access token (raise ValueError if missing - this is an actual error)
            token = await access_token_provider()
            if not token and not is_presigned_url:
                raise ValueError(f"No access token available for downloading {entity.name}")

            # Send HEAD request to get file size (with retry logic)
            async with http_client_factory(timeout=httpx.Timeout(30.0)) as client:
                headers = {}
                if token and not is_presigned_url:
                    headers["Authorization"] = f"Bearer {token}"

                try:
                    response = await self._head_with_retry(client, entity.url, headers, logger)

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

    @retry(
        stop=stop_after_attempt(5),  # Increased for aggressive rate limits
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _download_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict,
        temp_path: str,
        logger: ContextualLogger,
    ) -> None:
        """Download file with retry logic for rate limits and timeouts.

        Args:
            client: HTTP client
            url: URL to download from
            headers: Request headers
            temp_path: Path to save file to
            logger: Logger for diagnostics

        Raises:
            httpx.HTTPStatusError: On HTTP errors (after retries)
        """
        try:
            async with client.stream(
                "GET", url, headers=headers, follow_redirects=True
            ) as response:
                response.raise_for_status()

                # Ensure directory exists
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)

                # Write to disk
                with open(temp_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
        except httpx.HTTPStatusError as e:
            # Log rate limits (will be retried)
            if e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After", "unknown")
                logger.warning(
                    f"Rate limit hit (429) during file download (will retry after {retry_after}s)"
                )
            raise

    async def download_from_url(
        self,
        entity: FileEntity,
        http_client_factory: Callable,
        access_token_provider: Callable,
        logger: ContextualLogger,
    ) -> FileEntity:
        """Download file from URL to local disk with pre-download validation.

        Validates file extension and size before downloading.

        Args:
            entity: FileEntity with url to fetch
            http_client_factory: Factory that returns async HTTP client context manager
            access_token_provider: Async callable that returns access token or None
            logger: Logger for diagnostics

        Returns:
            FileEntity with local_path set

        Raises:
            FileSkippedException: If file should be skipped (unsupported type, too large)
            ValueError: If url is missing or access token unavailable (actual errors)
            httpx.HTTPStatusError: On HTTP errors (after retries)
            IOError: On file write errors
        """
        # Validate file before downloading (raises ValueError for actual errors)
        should_download, skip_reason = await self._validate_file_before_download(
            entity, http_client_factory, access_token_provider, logger
        )

        if not should_download:
            logger.info(f"Skipping download of {entity.name}: {skip_reason}")
            raise FileSkippedException(reason=skip_reason, filename=entity.name)

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
            # Stream download to disk with retry logic
            async with http_client_factory(timeout=httpx.Timeout(180.0, read=540.0)) as client:
                headers = {}
                if token and not is_presigned_url:
                    headers["Authorization"] = f"Bearer {token}"

                await self._download_with_retry(client, entity.url, headers, temp_path, logger)

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
        self,
        entity: FileEntity,
        content: bytes,
        filename_with_extension: str,
        logger: ContextualLogger,
    ) -> FileEntity:
        """Save in-memory bytes directly to local disk with EXPLICIT validation.

        EXPLICIT validation - raises exceptions for validation failures:
        - Missing extension (programming error) → ValueError
        - Unsupported extension (file will be skipped) → FileSkippedException
        - File too large (file will be skipped) → FileSkippedException

        This makes failures immediately visible and distinguishes intentional skips from errors.

        Args:
            entity: FileEntity to save
            content: File content as bytes
            filename_with_extension: Filename WITH extension (e.g., "report.pdf", "email.html")
                                    For emails: append ".html" to subject
                                    For code files: use the file path (already has extension)
                                    For attachments: use the attachment name from API
            logger: Logger for diagnostics

        Returns:
            FileEntity with local_path set

        Raises:
            FileSkippedException: If file should be skipped (unsupported extension or too large)
            ValueError: If filename missing extension (programming error)
            IOError: On file write errors
        """
        # EXPLICIT validation: filename MUST have extension
        _, ext = os.path.splitext(filename_with_extension)
        if not ext:
            raise ValueError(
                f"filename_with_extension must include file extension. "
                f"Got: '{filename_with_extension}'. "
                f"Examples: 'report.pdf', 'email.html', 'code.py'. "
                f"For emails: append '.html' to subject before calling save_bytes()."
            )

        ext = ext.lower()

        # Validate extension is supported - raise FileSkippedException (not an error)
        if ext not in SUPPORTED_FILE_EXTENSIONS:
            skip_reason = f"Unsupported file extension: {ext}"
            logger.info(f"Skipping file {filename_with_extension}: {skip_reason}")
            raise FileSkippedException(reason=skip_reason, filename=filename_with_extension)

        # Validate file size - raise FileSkippedException (not an error)
        content_size = len(content)
        if content_size > self.MAX_FILE_SIZE_BYTES:
            size_mb = content_size / (1024 * 1024)
            skip_reason = f"File too large: {size_mb:.1f}MB (max 1GB)"
            logger.info(f"Skipping file {filename_with_extension}: {skip_reason}")
            raise FileSkippedException(reason=skip_reason, filename=filename_with_extension)

        # Generate temp path using explicit filename
        file_uuid = uuid4()
        safe_filename = self._safe_filename(filename_with_extension)
        temp_path = os.path.join(self.base_temp_dir, f"{file_uuid}-{safe_filename}")

        logger.debug(f"Saving in-memory bytes to disk: {entity.name} ({content_size} bytes)")

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
