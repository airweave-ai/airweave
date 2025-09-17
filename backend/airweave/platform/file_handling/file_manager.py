"""Service for managing temporary files."""

import hashlib
import os
from typing import AsyncGenerator, AsyncIterator, Dict, Optional
from uuid import uuid4

import aiofiles
import httpx

from airweave.core.logging import ContextualLogger
from airweave.platform.entities._base import FileEntity
from airweave.platform.storage import storage_manager


class FileManager:
    """Manages temporary file operations with storage integration."""

    def __init__(self):
        """Initialize the file manager."""
        self.base_temp_dir = "/tmp/airweave/processing"
        self._ensure_base_dir()

    def _ensure_base_dir(self):
        """Ensure the base temporary directory exists."""
        os.makedirs(self.base_temp_dir, exist_ok=True)

    async def handle_file_entity(
        self,
        stream: AsyncIterator[bytes],
        entity: FileEntity,
        logger: ContextualLogger,
        max_size: int = 1024 * 1024 * 1024,  # 1GB limit
    ) -> FileEntity:
        """Process a file entity by saving its stream and enriching the entity.

        This method handles the following:
        1. Check if file exists in storage (download from storage to temp)
        2. If not, download new file from source to temp
        3. Store in persistent storage for future use
        4. Keep temp file for processing (chunker will clean up)

        NOTE: We always process entities even if they exist in storage,
        because each collection needs its own copy in the vector database.

        Args:
            stream: An async iterator yielding file chunks
            entity: The file entity to process
            logger: The logger to use
            max_size: Maximum allowed file size in bytes (default: 1GB)

        Returns:
            The enriched file entity
        """
        if not entity.download_url:
            return entity

        entity.airweave_system_metadata.should_skip = False

        # Check if this is a CTTI entity for special handling
        is_ctti = storage_manager._is_ctti_entity(entity)

        if is_ctti:
            logger.debug(
                f"🏥 FILE_CTTI Detected CTTI entity, using global deduplication "
                f"(entity_id: {entity.entity_id})"
            )

        # Check if file exists in storage (but still process it)
        cached_entity = await self._get_cached_entity(entity, is_ctti, logger)
        if cached_entity:
            return cached_entity

        # File not in cache, download from source
        return await self._download_and_store_entity(entity, stream, max_size, is_ctti, logger)

    async def _get_cached_entity(
        self, entity: FileEntity, is_ctti: bool, logger: ContextualLogger
    ) -> Optional[FileEntity]:
        """Get cached entity if it exists in storage."""
        # Check if file exists in storage (but not fully processed)
        # Note: CTTI files are handled differently by web_fetcher,
        # so this mainly applies to non-CTTI files
        if (
            not is_ctti
            and entity.airweave_system_metadata
            and entity.airweave_system_metadata.sync_id
        ):
            cached_path = await storage_manager.get_cached_file_path(
                logger, entity.airweave_system_metadata.sync_id, entity.entity_id, entity.name
            )

            if cached_path:
                logger.debug(
                    f"File found in storage cache, using cached version "
                    f"(entity_id: {entity.entity_id}, "
                    f"sync_id: {entity.airweave_system_metadata.sync_id}, "
                    f"cached_path: {cached_path})"
                )

                # Update entity with cached file info
                entity.airweave_system_metadata.local_path = cached_path
                entity.airweave_system_metadata.storage_blob_name = storage_manager._get_blob_name(
                    entity.airweave_system_metadata.sync_id, entity.entity_id
                )
                entity.airweave_system_metadata.is_cached = True

                # Calculate checksum from cached file
                with open(cached_path, "rb") as f:
                    content = f.read()
                    entity.airweave_system_metadata.checksum = hashlib.sha256(content).hexdigest()
                    entity.airweave_system_metadata.total_size = len(content)

                return entity
        return None

    async def _download_and_store_entity(
        self,
        entity: FileEntity,
        stream: AsyncIterator[bytes],
        max_size: int,
        is_ctti: bool,
        logger: ContextualLogger,
    ) -> FileEntity:
        """Download entity from source and store in persistent storage."""
        file_uuid = uuid4()
        safe_filename = self._safe_filename(entity.name)
        temp_path = os.path.join(self.base_temp_dir, f"{file_uuid}-{safe_filename}")

        try:
            downloaded_size = await self._download_file_stream(
                entity, stream, temp_path, max_size, logger
            )

            if entity.airweave_system_metadata.should_skip:
                return entity

            # Calculate checksum and update entity
            await self._update_entity_metadata(
                entity, temp_path, file_uuid, downloaded_size, logger
            )

            # Store in persistent storage for future use
            await self._store_entity_in_storage(entity, temp_path, is_ctti, logger)

            # IMPORTANT: Keep temp file for processing - chunker will clean it up

        except Exception as e:
            logger.error(
                f"[Entity({entity.entity_id})] Error processing file {entity.name}: {str(e)}"
            )
            # Clean up partial file if it exists
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e

        return entity

    async def _download_file_stream(
        self,
        entity: FileEntity,
        stream: AsyncIterator[bytes],
        temp_path: str,
        max_size: int,
        logger: ContextualLogger,
    ) -> int:
        """Download file stream to temporary path."""
        downloaded_size = 0
        # Truncate long URLs for logging
        url_display = (
            entity.download_url[:100] + "..."
            if len(entity.download_url) > 100
            else entity.download_url
        )
        logger.debug(
            f"Downloading file from source (entity_id: {entity.entity_id}, "
            f"name: {entity.name}, url: {url_display})"
        )

        # Ensure the directory exists before writing
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)

        async with aiofiles.open(temp_path, "wb") as f:
            async for chunk in stream:
                downloaded_size += len(chunk)

                # Safety check to skip files exceeding max size
                if downloaded_size > max_size:
                    await self._handle_oversized_file(
                        entity, f, temp_path, max_size, downloaded_size, logger
                    )
                    return downloaded_size

                await f.write(chunk)

                # Log progress for large files
                if (
                    entity.airweave_system_metadata
                    and entity.airweave_system_metadata.total_size
                    and entity.airweave_system_metadata.total_size > 10 * 1024 * 1024
                ):  # 10MB
                    progress = (downloaded_size / entity.airweave_system_metadata.total_size) * 100
                    logger.debug(
                        f"Download progress for {entity.name}: {progress:.1f}% "
                        f"({downloaded_size}/{entity.airweave_system_metadata.total_size} bytes)"
                    )

        return downloaded_size

    async def _handle_oversized_file(
        self,
        entity: FileEntity,
        file_handle,
        temp_path: str,
        max_size: int,
        downloaded_size: int,
        logger: ContextualLogger,
    ) -> None:
        """Handle files that exceed the maximum size limit."""
        max_size_gb = max_size / (1024 * 1024 * 1024)
        downloaded_size_mb = downloaded_size / (1024 * 1024)

        logger.warning(
            f"File {entity.name} exceeded maximum size "
            f"limit of {max_size_gb:.1f}GB. "
            f"Download aborted at {downloaded_size_mb:.1f}MB."
        )

        # Clean up the partial file
        await file_handle.close()
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Add warning to entity metadata
        if not entity.metadata:
            entity.metadata = {}
        entity.metadata["error"] = f"File too large (exceeded {max_size_gb:.1f}GB limit)"
        entity.metadata["size_exceeded"] = downloaded_size

        # Set the skip flag
        entity.airweave_system_metadata.should_skip = True

    async def _update_entity_metadata(
        self,
        entity: FileEntity,
        temp_path: str,
        file_uuid,
        downloaded_size: int,
        logger: ContextualLogger,
    ) -> None:
        """Update entity with file metadata."""
        with open(temp_path, "rb") as f:
            content = f.read()
            entity.airweave_system_metadata.checksum = hashlib.sha256(content).hexdigest()
            entity.airweave_system_metadata.local_path = temp_path
            entity.airweave_system_metadata.file_uuid = file_uuid
            entity.airweave_system_metadata.total_size = downloaded_size

        logger.debug(
            f"File downloaded successfully (entity_id: {entity.entity_id}, "
            f"local_path: {temp_path}, size: {downloaded_size}, "
            f"checksum: {entity.airweave_system_metadata.checksum[:8]}...)"
        )

    async def _store_entity_in_storage(
        self, entity: FileEntity, temp_path: str, is_ctti: bool, logger: ContextualLogger
    ) -> None:
        """Store entity in persistent storage."""
        # Note: CTTI files are handled by web_fetcher, not here
        if (
            not is_ctti
            and entity.airweave_system_metadata
            and entity.airweave_system_metadata.sync_id
            and not entity.airweave_system_metadata.should_skip
        ):
            with open(temp_path, "rb") as f:
                entity = await storage_manager.store_file_entity(logger, entity, f)

            logger.debug(
                f"File stored in persistent storage (entity_id: {entity.entity_id}, "
                f"sync_id: {entity.airweave_system_metadata.sync_id}, "
                f"storage_blob_name: {entity.airweave_system_metadata.storage_blob_name})"
            )
        elif is_ctti:
            logger.debug(
                f"🏥 FILE_CTTI_SKIP_STORE Skipping storage for CTTI file "
                f"(handled by web_fetcher) (entity_id: {entity.entity_id})"
            )

    @staticmethod
    def _safe_filename(filename: str) -> str:
        """Create a safe version of a filename."""
        # Replace potentially problematic characters
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
        safe_name = safe_name.strip()
        
        # Limit filename length to prevent "File name too long" errors
        # Account for UUID (36) + dash (1) + extension, leaving room for filesystem limits
        # Using conservative limit for UTF-8 multibyte characters (like Cyrillic)
        max_filename_length = 80
        if len(safe_name) > max_filename_length:
            # Keep the file extension if present
            if "." in safe_name:
                name, ext = safe_name.rsplit(".", 1)
                max_name_length = max_filename_length - len(ext) - 1  # -1 for the dot
                safe_name = name[:max_name_length] + "." + ext
            else:
                safe_name = safe_name[:max_filename_length]
        
        return safe_name

    async def stream_file_from_url(
        self,
        url: str,
        logger: ContextualLogger,
        access_token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[bytes, None]:
        """Stream file content from a URL with optional authentication."""
        request_headers = headers or {}

        # Only add Authorization header if URL doesn't already have S3 auth
        if access_token and "X-Amz-Algorithm" not in url:
            request_headers["Authorization"] = f"Bearer {access_token}"

        # The file is downloaded in chunks
        timeout = httpx.Timeout(180.0, read=540.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream(
                    "GET", url, headers=request_headers, follow_redirects=True
                ) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except httpx.HTTPStatusError as e:
                # Log the specific HTTP error with more details
                status_code = e.response.status_code if hasattr(e, "response") else "Unknown"
                logger.error(
                    f"HTTP {status_code} error streaming file from {url[:100]}...: {str(e)}"
                )
                raise
            except Exception as e:
                logger.error(f"Error streaming file: {str(e)}")
                raise


# Global instance
file_manager = FileManager()


async def handle_file_entity(
    file_entity: FileEntity, stream: AsyncIterator[bytes], logger: ContextualLogger
) -> FileEntity:
    """Utility function to handle a file entity with its stream.

    This is a convenience function that can be used directly in source implementations.

    Args:
        file_entity: The file entity
        stream: The file stream
        logger: The logger to use

    Returns:
        The processed entity
    """
    return await file_manager.handle_file_entity(stream, file_entity, logger)
