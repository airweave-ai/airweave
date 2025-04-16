"""Service for managing temporary files."""

import hashlib
import os
from typing import AsyncGenerator, AsyncIterator, Dict, Optional
from uuid import uuid4

import aiofiles
import httpx

from airweave.core.logging import logger
from airweave.platform.entities._base import FileEntity


class FileManager:
    """Manages temporary file operations."""

    def __init__(self):
        """Initialize the file manager."""
        self.base_temp_dir = "/tmp/airweave"
        self._ensure_base_dir()

    def _ensure_base_dir(self):
        """Ensure the base temporary directory exists."""
        os.makedirs(self.base_temp_dir, exist_ok=True)

    async def handle_file_entity(
        self,
        stream: AsyncIterator[bytes],
        entity: FileEntity,
        chunk_size: int = 8192,
    ) -> FileEntity | None:
        """Process a file entity by saving its stream and enriching the entity.

        Args:
            stream: An async iterator yielding file chunks
            entity: The file entity to process
            chunk_size: Size of chunks to process

        Returns:
            The enriched file entity
        """
        if not entity.download_url:
            return entity

        file_uuid = uuid4()
        safe_filename = self._safe_filename(entity.name)
        temp_path = os.path.join(self.base_temp_dir, f"{file_uuid}-{safe_filename}")

        try:
            downloaded_size = 0
            async with aiofiles.open(temp_path, "wb") as f:
                async for chunk in stream:
                    await f.write(chunk)
                    downloaded_size += len(chunk)
                    # TODO: Implement safety check that skips file if size exceeds 1 GB

                    # Log progress for large files
                    if entity.total_size and entity.total_size > 10 * 1024 * 1024:  # 10MB
                        progress = (downloaded_size / entity.total_size) * 100
                        logger.info(
                            f"Saving {entity.name}: {progress:.1f}% "
                            f"({downloaded_size}/{entity.total_size} bytes)"
                        )

            # Calculate checksum and update entity
            with open(temp_path, "rb") as f:
                content = f.read()
                entity.checksum = hashlib.sha256(content).hexdigest()
                entity.local_path = temp_path
                logger.info(f"\nlocal_path: {entity.local_path}\n")
                entity.file_uuid = file_uuid
                entity.total_size = downloaded_size  # Update with actual size

        except Exception as e:
            logger.error(f"Error saving file {entity.name}: {str(e)}")
            # Clean up partial file if it exists
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e

        return entity

    @staticmethod
    def _safe_filename(filename: str) -> str:
        """Create a safe version of a filename."""
        # Replace potentially problematic characters
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
        return safe_name.strip()

    async def stream_file_from_url(
        self,
        url: str,
        access_token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[bytes, None]:
        """Stream file content from a URL with optional authentication.

        Args:
            url: The file download URL
            access_token: Optional OAuth token
            headers: Optional additional headers

        Yields:
            Chunks of file content
        """
        request_headers = headers or {}
        if access_token:
            request_headers["Authorization"] = f"Bearer {access_token}"

        # The file is downloaded in chunks
        # Google Drive API might take longer than default 5 second timeout prepare chunks
        timeout = httpx.Timeout(10.0, read=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Simple streaming without retry
            try:
                async with client.stream(
                    "GET", url, headers=request_headers, follow_redirects=True
                ) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except Exception as e:
                logger.error(f"Error streaming file from URL {url}: {str(e)}")
                logger.exception("Full error details:")  # This logs the stack trace
                raise  # This will propagate through the generator


# Global instance
file_manager = FileManager()


async def handle_file_entity(file_entity: FileEntity, stream: AsyncIterator[bytes]) -> FileEntity:
    """Utility function to handle a file entity with its stream.

    This is a convenience function that can be used directly in source implementations.

    Args:
        file_entity: The file entity
        stream: The file stream

    Returns:
        The processed entity
    """
    return await file_manager.handle_file_entity(stream, file_entity)
