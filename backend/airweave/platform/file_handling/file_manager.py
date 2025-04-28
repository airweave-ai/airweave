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
        max_size: int = 1024 * 1024 * 1024,  # 1GB limit
    ) -> FileEntity:
        """Process a file entity by saving its stream and enriching the entity.

        Args:
            stream: An async iterator yielding file chunks
            entity: The file entity to process
            max_size: Maximum allowed file size in bytes (default: 1GB)

        Returns:
            The enriched file entity with should_skip flag set if too large
        """
        if not entity.download_url:
            return entity

        # Initialize a flag to indicate if this entity should be skipped
        entity.should_skip = False

        file_uuid = uuid4()
        safe_filename = self._safe_filename(entity.name)
        temp_path = os.path.join(self.base_temp_dir, f"{file_uuid}-{safe_filename}")

        try:
            downloaded_size = 0
            async with aiofiles.open(temp_path, "wb") as f:
                async for chunk in stream:
                    downloaded_size += len(chunk)

                    # Safety check to skip files exceeding max size
                    if downloaded_size > max_size:
                        logger.warning(
                            f"File {entity.name} exceeded maximum size"
                            f"limit of {max_size / (1024 * 1024 * 1024):.1f}GB. "
                            f"Download aborted at {downloaded_size / (1024 * 1024):.1f}MB."
                        )
                        # Clean up the partial file
                        await f.close()
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                        # Add warning to entity metadata
                        if not entity.metadata:
                            entity.metadata = {}
                        entity.metadata["error"] = (
                            f"File too large (exceeded "
                            f"{max_size / (1024 * 1024 * 1024):.1f}GB limit)"
                        )
                        entity.metadata["size_exceeded"] = downloaded_size

                        # Set the skip flag
                        entity.should_skip = True
                        return entity

                    await f.write(chunk)

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
            except Exception as e:
                logger.error(f"Error streaming file: {str(e)}")
                raise


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
