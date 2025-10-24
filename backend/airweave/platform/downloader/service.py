"""File download service for downloading files to local disk."""

import os
from typing import Callable
from uuid import uuid4

import httpx

from airweave.core.logging import ContextualLogger
from airweave.platform.entities._base import FileEntity


class FileDownloadService:
    """Simple file download service that writes files to local disk.

    Responsibilities:
    - Download file from URL to local temp path
    - Save in-memory bytes to local temp path
    - Nothing else (no cache, no persistent storage)
    """

    def __init__(self, base_temp_dir: str = "/tmp/airweave/processing"):
        """Initialize file download service.

        Args:
            base_temp_dir: Base directory for temporary file storage
        """
        self.base_temp_dir = base_temp_dir
        self._ensure_base_dir()

    def _ensure_base_dir(self) -> None:
        """Ensure base temporary directory exists."""
        os.makedirs(self.base_temp_dir, exist_ok=True)

    async def download_from_url(
        self,
        entity: FileEntity,
        http_client_factory: Callable,
        access_token_provider: Callable,
        logger: ContextualLogger,
    ) -> FileEntity:
        """Download file from URL to local disk.

        Args:
            entity: FileEntity with url to fetch
            http_client_factory: Factory that returns async HTTP client context manager
            access_token_provider: Async callable that returns access token or None
            logger: Logger for diagnostics

        Returns:
            FileEntity with local_path set (or raises exception)

        Raises:
            ValueError: If url is missing or access token unavailable
            httpx.HTTPStatusError: On HTTP errors
            IOError: On file write errors
        """
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
