"""File download and restoration service for Airweave.

Handles:
- Downloading files from URLs to temp directory
- Restoring files from ARF storage to temp directory
- File validation (extension, size)
- Temp directory cleanup
"""

import os
import re
import shutil
from typing import TYPE_CHECKING, Callable, Optional, Tuple
from uuid import UUID, uuid4

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.platform.entities._base import FileEntity
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage.exceptions import FileSkippedException
from airweave.platform.storage.paths import paths
from airweave.platform.sync.file_types import SUPPORTED_FILE_EXTENSIONS

if TYPE_CHECKING:
    from airweave.platform.storage.protocol import StorageBackend


class FileService:
    """Unified file service for downloading and restoring files.

    Responsibilities:
    - Download files from URLs to temp (for live sources)
    - Restore files from ARF storage to temp (for replay)
    - Validate files before download (extension, size)
    - Save in-memory bytes to temp
    - Cleanup temp directory after sync
    """

    # Maximum file size we'll download (1GB)
    MAX_FILE_SIZE_BYTES = 1073741824

    def __init__(
        self,
        sync_job_id: UUID,
        storage_backend: Optional["StorageBackend"] = None,
    ):
        """Initialize file service.

        Args:
            sync_job_id: Sync job ID for organizing temp files
            storage_backend: Storage backend for ARF operations (lazy loaded if None)
        """
        self.sync_job_id = sync_job_id
        self._storage = storage_backend
        self.base_temp_dir = paths.temp_sync_dir(sync_job_id)
        self._ensure_base_dir()

    @property
    def storage(self) -> "StorageBackend":
        """Lazy-load storage backend."""
        if self._storage is None:
            from airweave.platform.storage import storage_backend

            self._storage = storage_backend
        return self._storage

    def _ensure_base_dir(self) -> None:
        """Ensure temp directory exists."""
        os.makedirs(self.base_temp_dir, exist_ok=True)

    # =========================================================================
    # URL Download (for live sources)
    # =========================================================================

    @retry(
        stop=stop_after_attempt(5),
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
        """Make HEAD request with retry logic for rate limits and timeouts."""
        try:
            response = await client.head(url, headers=headers, follow_redirects=True, timeout=10.0)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
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

        Returns:
            Tuple of (should_download, skip_reason)

        Raises:
            ValueError: If URL or access token is unavailable
        """
        if not entity.url:
            raise ValueError(f"No download URL for file {entity.name}")

        _, ext = os.path.splitext(entity.name)
        ext = ext.lower()

        if ext not in SUPPORTED_FILE_EXTENSIONS:
            return False, f"Unsupported file extension: {ext}"

        is_presigned_url = "X-Amz-Algorithm" in entity.url

        try:
            token = await access_token_provider()
            if not token and not is_presigned_url:
                raise ValueError(f"No access token available for downloading {entity.name}")

            async with http_client_factory(timeout=httpx.Timeout(30.0)) as client:
                headers = {}
                if token and not is_presigned_url:
                    headers["Authorization"] = f"Bearer {token}"

                try:
                    response = await self._head_with_retry(client, entity.url, headers, logger)

                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        size_bytes = int(content_length)
                        if size_bytes > self.MAX_FILE_SIZE_BYTES:
                            size_mb = size_bytes / (1024 * 1024)
                            return False, f"File too large: {size_mb:.1f}MB (max 1GB)"

                except (httpx.HTTPError, ValueError) as e:
                    logger.debug(
                        f"HEAD request failed for {entity.name}: {e}, will attempt download"
                    )

        except Exception as e:
            logger.debug(f"File validation error for {entity.name}: {e}, will attempt download")

        return True, None

    @staticmethod
    def _extract_filename_from_content_disposition(content_disposition: str) -> Optional[str]:
        """Extract filename from Content-Disposition header.

        Handles formats like:
        - attachment; filename="file.pdf"
        - attachment; filename*=UTF-8''file%20name.pdf

        Args:
            content_disposition: Content-Disposition header value

        Returns:
            Extracted filename or None if not found
        """
        if not content_disposition:
            return None

        # Try quoted filename first: filename="file.pdf"
        match = re.search(r'filename="([^"]+)"', content_disposition)
        if match:
            return match.group(1)

        # Try unquoted filename: filename=file.pdf
        match = re.search(r"filename=([^;\s]+)", content_disposition)
        if match:
            return match.group(1)

        return None

    @retry(
        stop=stop_after_attempt(5),
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
    ) -> Optional[str]:
        """Download file with retry logic for rate limits and timeouts.

        Returns:
            Extracted filename from Content-Disposition header, or None if not available.
        """
        extracted_filename = None
        try:
            async with client.stream(
                "GET", url, headers=headers, follow_redirects=True
            ) as response:
                response.raise_for_status()

                # Extract filename from Content-Disposition header if present
                content_disp = response.headers.get("Content-Disposition", "")
                if content_disp:
                    extracted_filename = self._extract_filename_from_content_disposition(
                        content_disp
                    )

                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                with open(temp_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After", "unknown")
                logger.warning(
                    f"Rate limit hit (429) during file download (will retry after {retry_after}s)"
                )
            raise

        return extracted_filename

    async def download_from_url(
        self,
        entity: FileEntity,
        http_client_factory: Callable,
        access_token_provider: Callable,
        logger: ContextualLogger,
    ) -> FileEntity:
        """Download file from URL to temp directory.

        If entity.name is not set, the filename will be extracted from the
        Content-Disposition header during download.

        Args:
            entity: FileEntity with url to fetch (name can be None for redirect URLs)
            http_client_factory: Factory for HTTP client
            access_token_provider: Async callable returning access token
            logger: Logger for diagnostics

        Returns:
            FileEntity with local_path and name set

        Raises:
            FileSkippedException: If file should be skipped
            ValueError: If url is missing or filename cannot be determined
        """
        # If name is set, validate before download (existing behavior)
        # If name is not set, we'll extract it from Content-Disposition after download
        filename_known_upfront = bool(entity.name)

        if filename_known_upfront:
            should_download, skip_reason = await self._validate_file_before_download(
                entity, http_client_factory, access_token_provider, logger
            )

            if not should_download:
                logger.info(f"Skipping download of {entity.name}: {skip_reason}")
                raise FileSkippedException(reason=skip_reason, filename=entity.name)

        file_uuid = str(uuid4())

        # Use placeholder filename if name not known upfront
        initial_filename = entity.name if entity.name else f"download_{file_uuid[:8]}"
        safe_filename = self._safe_filename(initial_filename)
        temp_path = f"{self.base_temp_dir}/{file_uuid}-{safe_filename}"

        is_presigned_url = "X-Amz-Algorithm" in entity.url
        token = await access_token_provider()
        if not token and not is_presigned_url:
            raise ValueError(f"No access token available for downloading {entity.name or 'file'}")

        logger.debug(
            f"Downloading file from URL: {entity.name or '(filename from response)'} "
            f"(pre-signed: {is_presigned_url}, has_token: {bool(token)})"
        )

        try:
            async with http_client_factory(timeout=httpx.Timeout(180.0, read=540.0)) as client:
                headers = {}
                if token and not is_presigned_url:
                    headers["Authorization"] = f"Bearer {token}"

                extracted_filename = await self._download_with_retry(
                    client, entity.url, headers, temp_path, logger
                )

            # If filename wasn't known upfront, use extracted filename
            if not filename_known_upfront:
                if extracted_filename:
                    entity.name = extracted_filename

                    # Validate the extracted filename's extension
                    _, ext = os.path.splitext(extracted_filename)
                    ext = ext.lower()
                    if ext not in SUPPORTED_FILE_EXTENSIONS:
                        # Clean up downloaded file
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        skip_reason = f"Unsupported file extension: {ext}"
                        logger.info(f"Skipping download of {extracted_filename}: {skip_reason}")
                        raise FileSkippedException(reason=skip_reason, filename=extracted_filename)

                    # Rename temp file to use correct filename
                    new_safe_filename = self._safe_filename(extracted_filename)
                    new_temp_path = f"{self.base_temp_dir}/{file_uuid}-{new_safe_filename}"
                    os.rename(temp_path, new_temp_path)
                    temp_path = new_temp_path

                    logger.debug(f"Extracted filename from response: {extracted_filename}")
                else:
                    # No filename in response - clean up and fail
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    raise ValueError(
                        "Could not determine filename: entity.name not set and "
                        "no Content-Disposition header in response"
                    )

            logger.debug(f"Downloaded file to: {temp_path}")
            entity.local_path = temp_path
            return entity

        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise

    # =========================================================================
    # ARF Restoration (for replay sources)
    # =========================================================================

    async def restore_from_arf(
        self,
        arf_file_path: str,
        filename: str,
        logger: ContextualLogger,
    ) -> str:
        """Restore file from ARF storage to temp directory.

        Args:
            arf_file_path: Path in ARF storage (e.g., "raw/{sync_id}/files/...")
            filename: Original filename for temp path
            logger: Logger for diagnostics

        Returns:
            Local path to restored file

        Raises:
            StorageNotFoundError: If file not found in ARF
        """
        content = await self.storage.read_file(arf_file_path)

        file_uuid = str(uuid4())
        safe_filename = self._safe_filename(filename)
        temp_path = f"{self.base_temp_dir}/{file_uuid}-{safe_filename}"

        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "wb") as f:
            f.write(content)

        logger.debug(f"Restored file from ARF to {temp_path}")
        return temp_path

    # =========================================================================
    # In-memory bytes (for sources that fetch content directly)
    # =========================================================================

    async def save_bytes(
        self,
        entity: FileEntity,
        content: bytes,
        filename_with_extension: str,
        logger: ContextualLogger,
    ) -> FileEntity:
        """Save in-memory bytes to temp directory.

        Args:
            entity: FileEntity to save
            content: File content as bytes
            filename_with_extension: Filename WITH extension
            logger: Logger for diagnostics

        Returns:
            FileEntity with local_path set

        Raises:
            FileSkippedException: If file should be skipped
            ValueError: If filename missing extension
        """
        _, ext = os.path.splitext(filename_with_extension)
        if not ext:
            raise ValueError(
                f"filename_with_extension must include file extension. "
                f"Got: '{filename_with_extension}'. "
                f"Examples: 'report.pdf', 'email.html', 'code.py'. "
                f"For emails: append '.html' to subject before calling save_bytes()."
            )

        ext = ext.lower()

        if ext not in SUPPORTED_FILE_EXTENSIONS:
            skip_reason = f"Unsupported file extension: {ext}"
            logger.info(f"Skipping file {filename_with_extension}: {skip_reason}")
            raise FileSkippedException(reason=skip_reason, filename=filename_with_extension)

        content_size = len(content)
        if content_size > self.MAX_FILE_SIZE_BYTES:
            size_mb = content_size / (1024 * 1024)
            skip_reason = f"File too large: {size_mb:.1f}MB (max 1GB)"
            logger.info(f"Skipping file {filename_with_extension}: {skip_reason}")
            raise FileSkippedException(reason=skip_reason, filename=filename_with_extension)

        file_uuid = str(uuid4())
        safe_filename = self._safe_filename(filename_with_extension)
        temp_path = f"{self.base_temp_dir}/{file_uuid}-{safe_filename}"

        logger.debug(f"Saving in-memory bytes to disk: {entity.name} ({content_size} bytes)")

        try:
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            with open(temp_path, "wb") as f:
                f.write(content)

            logger.debug(f"Saved file to: {temp_path}")
            entity.local_path = temp_path
            return entity

        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise IOError(f"Failed to save bytes for {entity.name}: {e}") from e

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def cleanup_sync_directory(self, logger: ContextualLogger) -> None:
        """Remove entire temp directory for this sync job."""
        try:
            if not os.path.exists(self.base_temp_dir):
                logger.debug(f"Temp directory already cleaned: {self.base_temp_dir}")
                return

            file_count = 0
            try:
                for _, _, files in os.walk(self.base_temp_dir):
                    file_count += len(files)
            except Exception:
                pass

            shutil.rmtree(self.base_temp_dir)

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
            logger.warning(f"Temp directory cleanup error: {e}", exc_info=True)

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _safe_filename(filename: str) -> str:
        """Create a safe version of a filename."""
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
        return safe_name.strip()


# Backwards compatibility alias
FileDownloadService = FileService
