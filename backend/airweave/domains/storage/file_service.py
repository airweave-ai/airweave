"""File download and restoration service for Airweave.

Handles:
- Downloading files from URLs to temp directory
- Restoring files from ARF storage to temp directory
- File validation (extension, size)
- Temp directory cleanup

Does NOT handle domain exception translation — that's the source's job.
Raw httpx errors propagate to the caller.
"""

import os
import shutil
from typing import Optional
from uuid import UUID, uuid4

import aiofiles
import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.domains.sources.token_providers.protocol import SourceAuthProvider
from airweave.domains.storage.exceptions import FileSkippedException
from airweave.domains.storage.paths import paths
from airweave.domains.storage.protocols import StorageBackend
from airweave.domains.sync_pipeline.file_types import SUPPORTED_FILE_EXTENSIONS
from airweave.platform.entities._base import FileEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.utils.ssrf import validate_url


class FileService:
    """Unified file service for downloading and restoring files."""

    MAX_FILE_SIZE_BYTES = 209715200

    def __init__(
        self,
        sync_job_id: UUID,
        storage_backend: StorageBackend,
    ) -> None:
        """Initialize file service."""
        self.sync_job_id = sync_job_id
        self.storage = storage_backend
        self.base_temp_dir = paths.temp_sync_dir(sync_job_id)
        self._ensure_base_dir()

    def _ensure_base_dir(self) -> None:
        """Ensure temp directory exists."""
        os.makedirs(self.base_temp_dir, exist_ok=True)

    # =========================================================================
    # Auth helpers
    # =========================================================================

    @staticmethod
    async def _resolve_headers(auth: SourceAuthProvider, url: str) -> dict:
        """Build auth headers. Pre-signed URLs skip the bearer token."""
        if "X-Amz-Algorithm" in url or "tempauth=" in url:
            return {}
        token = await auth.get_token() if hasattr(auth, "get_token") else None
        if not token:
            raise ValueError(f"No access token available for downloading {url}")
        return {"Authorization": f"Bearer {token}"}

    # =========================================================================
    # URL Download
    # =========================================================================

    async def _check_file_size_via_head(
        self,
        client: AirweaveHttpClient,
        url: str,
        headers: dict,
        logger: ContextualLogger,
    ) -> Optional[str]:
        """HEAD request to check file size. Returns skip reason or None."""
        try:
            response = await client.head(url, headers=headers, follow_redirects=True, timeout=10.0)
            response.raise_for_status()
            content_length = response.headers.get("Content-Length")
            if content_length:
                size_bytes = int(content_length)
                if size_bytes > self.MAX_FILE_SIZE_BYTES:
                    size_mb = size_bytes / (1024 * 1024)
                    return f"File too large: {size_mb:.1f}MB (max 200MB)"
        except (httpx.HTTPError, ValueError) as e:
            logger.debug(f"HEAD request failed for size check: {e}, will attempt download")
        return None

    @staticmethod
    def _validate_extension(filename: str) -> Optional[str]:
        """Check if the file extension is supported. Returns skip reason or None."""
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        if ext not in SUPPORTED_FILE_EXTENSIONS:
            return f"Unsupported file extension: {ext}"
        return None

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _stream_download(
        self,
        client: AirweaveHttpClient,
        url: str,
        headers: dict,
        temp_path: str,
        logger: ContextualLogger,
    ) -> None:
        """Stream-download a file to disk with retry on 429/5xx/timeout."""
        async with client.stream(
            "GET",
            url,
            headers=headers,
            follow_redirects=True,
            timeout=httpx.Timeout(180.0, read=540.0),
        ) as response:
            response.raise_for_status()

            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > self.MAX_FILE_SIZE_BYTES:
                size_mb = int(content_length) / (1024 * 1024)
                max_mb = self.MAX_FILE_SIZE_BYTES // (1024 * 1024)
                raise FileSkippedException(
                    reason=f"File too large: {size_mb:.1f}MB (max {max_mb}MB)",
                    filename=temp_path,
                )

            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            bytes_written = 0
            async with aiofiles.open(temp_path, "wb") as f:
                async for chunk in response.aiter_bytes():
                    bytes_written += len(chunk)
                    if bytes_written > self.MAX_FILE_SIZE_BYTES:
                        max_mb = self.MAX_FILE_SIZE_BYTES // (1024 * 1024)
                        raise FileSkippedException(
                            reason=f"File exceeded {max_mb}MB during download",
                            filename=temp_path,
                        )
                    await f.write(chunk)

    async def download_from_url(
        self,
        entity: FileEntity,
        client: AirweaveHttpClient,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
    ) -> FileEntity:
        """Download file from URL to temp directory.

        Raises httpx errors on HTTP failures — the source handles
        domain exception translation.
        """
        if not entity.url:
            raise ValueError(f"No download URL for file {entity.name}")
        validate_url(entity.url)

        ext_skip = self._validate_extension(entity.name)
        if ext_skip:
            raise FileSkippedException(reason=ext_skip, filename=entity.name)

        headers = await self._resolve_headers(auth, entity.url)

        size_skip = await self._check_file_size_via_head(client, entity.url, headers, logger)
        if size_skip:
            raise FileSkippedException(reason=size_skip, filename=entity.name)

        file_uuid = str(uuid4())
        safe_filename = self._safe_filename(entity.name)
        temp_path = f"{self.base_temp_dir}/{file_uuid}-{safe_filename}"

        logger.debug(
            f"Downloading file: {entity.name} (pre-signed: {'X-Amz-Algorithm' in entity.url})"
        )

        try:
            await self._stream_download(client, entity.url, headers, temp_path, logger)
        except FileSkippedException:
            self._cleanup_temp(temp_path)
            raise
        except httpx.HTTPStatusError as first_error:
            if first_error.response.status_code == 401 and auth.supports_refresh:
                logger.info("Download got 401, refreshing token and retrying")
                new_token = await auth.force_refresh()
                headers = {"Authorization": f"Bearer {new_token}"}
                try:
                    await self._stream_download(client, entity.url, headers, temp_path, logger)
                except Exception:
                    self._cleanup_temp(temp_path)
                    raise
            else:
                self._cleanup_temp(temp_path)
                raise

        logger.debug(f"Downloaded file to: {temp_path}")
        entity.local_path = temp_path
        return entity

    def _cleanup_temp(self, temp_path: str) -> None:
        """Remove a partially-downloaded temp file."""
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    # =========================================================================
    # ARF Restoration
    # =========================================================================

    async def restore_from_arf(
        self,
        arf_file_path: str,
        filename: str,
        logger: ContextualLogger,
    ) -> str:
        """Restore file from ARF storage to temp directory."""
        content = await self.storage.read_file(arf_file_path)

        file_uuid = str(uuid4())
        safe_filename = self._safe_filename(filename)
        temp_path = f"{self.base_temp_dir}/{file_uuid}-{safe_filename}"

        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(content)

        logger.debug(f"Restored file from ARF to {temp_path}")
        return temp_path

    # =========================================================================
    # In-memory bytes
    # =========================================================================

    async def save_bytes(
        self,
        entity: FileEntity,
        content: bytes,
        filename_with_extension: str,
        logger: ContextualLogger,
    ) -> FileEntity:
        """Save in-memory bytes to temp directory."""
        _, ext = os.path.splitext(filename_with_extension)
        if not ext:
            raise ValueError(
                f"filename_with_extension must include file extension. "
                f"Got: '{filename_with_extension}'."
            )

        ext = ext.lower()
        if ext not in SUPPORTED_FILE_EXTENSIONS:
            skip_reason = f"Unsupported file extension: {ext}"
            logger.info(f"Skipping file {filename_with_extension}: {skip_reason}")
            raise FileSkippedException(reason=skip_reason, filename=filename_with_extension)

        content_size = len(content)
        if content_size > self.MAX_FILE_SIZE_BYTES:
            size_mb = content_size / (1024 * 1024)
            skip_reason = f"File too large: {size_mb:.1f}MB (max 200MB)"
            logger.info(f"Skipping file {filename_with_extension}: {skip_reason}")
            raise FileSkippedException(reason=skip_reason, filename=filename_with_extension)

        file_uuid = str(uuid4())
        safe_filename = self._safe_filename(filename_with_extension)
        temp_path = f"{self.base_temp_dir}/{file_uuid}-{safe_filename}"

        logger.debug(f"Saving in-memory bytes to disk: {entity.name} ({content_size} bytes)")

        try:
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(content)
            entity.local_path = temp_path
            return entity
        except Exception as e:
            self._cleanup_temp(temp_path)
            raise IOError(f"Failed to save bytes for {entity.name}: {e}") from e

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def cleanup_sync_directory(self, logger: ContextualLogger) -> None:
        """Remove entire temp directory for this sync job."""
        try:
            if not os.path.exists(self.base_temp_dir):
                return

            file_count = sum(len(files) for _, _, files in os.walk(self.base_temp_dir))
            shutil.rmtree(self.base_temp_dir)

            if os.path.exists(self.base_temp_dir):
                logger.warning(f"Failed to delete temp directory: {self.base_temp_dir}")
            else:
                logger.info(f"Cleaned up temp directory {self.base_temp_dir} ({file_count} files)")
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


FileDownloadService = FileService
