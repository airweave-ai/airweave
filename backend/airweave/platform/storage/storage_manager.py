"""Storage manager for file handling."""

import io
import json
import os
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple
from uuid import UUID

from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import ContextualLogger
from airweave.platform.entities._base import FileEntity
from airweave.platform.storage.storage_client import StorageClient


class StorageManager:
    """Manages file storage with sync-aware folder structure and caching."""

    def __init__(self, client: Optional[StorageClient] = None):
        """Initialize storage manager.

        Args:
            client: Optional storage client. If not provided, will be auto-configured.
        """
        self.client = client or StorageClient()
        self.container_name = "sync-data"
        self.metadata_container = "sync-metadata"
        self._ensure_containers()

        # Local cache directory for temporary files during processing
        self.temp_cache_dir = Path("/tmp/airweave/cache")
        self.temp_cache_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_containers(self) -> None:
        """Ensure required containers exist."""
        # This would need to be implemented based on storage backend
        pass

    def _get_blob_name(self, sync_id: UUID, entity_id: str) -> str:
        """Get standardized blob name for a file.

        Format: sync_id/entity_id/original_filename
        """
        return f"{sync_id}/{entity_id}"

    def _get_metadata_blob_name(self, sync_id: UUID, entity_id: str) -> str:
        """Get blob name for metadata."""
        return f"{sync_id}/{entity_id}.metadata.json"

    async def check_file_exists(
        self, logger: ContextualLogger, sync_id: UUID, entity_id: str
    ) -> bool:
        """Check if a file exists in storage.

        Args:
            logger: The logger to use
            sync_id: Sync ID
            entity_id: Entity ID

        Returns:
            True if file exists in storage
        """
        blob_name = self._get_blob_name(sync_id, entity_id)
        exists = await self.client.file_exists(logger, self.container_name, blob_name)

        if exists:
            logger.info(
                "File exists in storage",
                extra={"sync_id": str(sync_id), "entity_id": entity_id, "blob_name": blob_name},
            )

        return exists

    async def is_entity_fully_processed(self, logger: ContextualLogger, cache_key: str) -> bool:
        """Check if an entity has been fully processed (including chunking).

        Args:
            logger: The logger to use
            cache_key: Format "sync_id/entity_id"

        Returns:
            True if entity was fully processed
        """
        try:
            # Check metadata to see if processing was completed
            parts = cache_key.split("/")
            if len(parts) != 2:
                return False

            sync_id, entity_id = parts[0], parts[1]
            metadata_blob = self._get_metadata_blob_name(UUID(sync_id), entity_id)

            metadata_bytes = await self.client.download_file(
                logger, self.metadata_container, metadata_blob
            )

            if metadata_bytes:
                metadata = json.loads(metadata_bytes.decode("utf-8"))
                return metadata.get("fully_processed", False)

        except Exception as e:
            logger.debug(f"Error checking if entity is fully processed: {e}")

        return False

    async def store_file_entity(
        self, logger: ContextualLogger, entity: FileEntity, content: BinaryIO
    ) -> Any:
        """Store a file entity in persistent storage.

        Args:
            logger: The logger to use
            entity: FileEntity to store
            content: File content as binary stream

        Returns:
            Updated entity with storage information
        """
        if not entity.airweave_system_metadata or not entity.airweave_system_metadata.sync_id:
            logger.warning(
                "Cannot store file without sync_id", extra={"entity_id": entity.entity_id}
            )
            return entity

        sync_id = entity.airweave_system_metadata.sync_id
        blob_name = self._get_blob_name(sync_id, entity.entity_id)

        # Store the file
        logger.info(
            "Storing file in persistent storage",
            extra={
                "sync_id": str(sync_id),
                "entity_id": entity.entity_id,
                "blob_name": blob_name,
                "size": (
                    entity.airweave_system_metadata.total_size
                    if entity.airweave_system_metadata
                    else None
                ),
            },
        )

        success = await self.client.upload_file(logger, self.container_name, blob_name, content)

        if success:
            # Set storage blob name in system metadata (always exists for FileEntity)
            entity.airweave_system_metadata.storage_blob_name = blob_name

            # Store metadata
            metadata = {
                "entity_id": entity.entity_id,
                "sync_id": str(sync_id),
                "file_name": entity.name,
                "size": (
                    entity.airweave_system_metadata.total_size
                    if entity.airweave_system_metadata
                    else None
                ),
                "checksum": (
                    entity.airweave_system_metadata.checksum
                    if entity.airweave_system_metadata
                    else None
                ),
                "mime_type": getattr(entity, "mime_type", None),
                "stored_at": utc_now_naive().isoformat(),
                "fully_processed": False,  # Will be updated after chunking
            }

            await self._store_metadata(logger, sync_id, entity.entity_id, metadata)

            logger.info(
                "File stored successfully",
                extra={"sync_id": str(sync_id), "entity_id": entity.entity_id},
            )
        else:
            logger.error(
                "Failed to store file",
                extra={"sync_id": str(sync_id), "entity_id": entity.entity_id},
            )

        return entity

    async def _store_metadata(
        self, logger: ContextualLogger, sync_id: UUID, entity_id: str, metadata: Dict[str, Any]
    ) -> None:
        """Store metadata for a file."""
        metadata_blob = self._get_metadata_blob_name(sync_id, entity_id)
        metadata_bytes = json.dumps(metadata).encode("utf-8")

        await self.client.upload_file(
            logger, self.metadata_container, metadata_blob, io.BytesIO(metadata_bytes)
        )

    async def mark_entity_processed(
        self, logger: ContextualLogger, sync_id: UUID, entity_id: str, chunk_count: int
    ) -> None:
        """Mark an entity as fully processed after chunking.

        Args:
            logger: The logger to use
            sync_id: Sync ID
            entity_id: Entity ID
            chunk_count: Number of chunks created
        """
        metadata_blob = self._get_metadata_blob_name(sync_id, entity_id)

        # Get existing metadata
        metadata_bytes = await self.client.download_file(
            logger, self.metadata_container, metadata_blob
        )

        if metadata_bytes:
            metadata = json.loads(metadata_bytes.decode("utf-8"))
            metadata.update(
                {
                    "fully_processed": True,
                    "chunk_count": chunk_count,
                    "processed_at": utc_now_naive().isoformat(),
                }
            )

            # Update metadata
            await self._store_metadata(logger, sync_id, entity_id, metadata)

            logger.info(
                "Marked entity as processed",
                extra={"sync_id": str(sync_id), "entity_id": entity_id, "chunk_count": chunk_count},
            )

    async def get_cached_file_path(
        self, logger: ContextualLogger, sync_id: UUID, entity_id: str, file_name: str
    ) -> Optional[str]:
        """Get or create a local cache path for a file.

        This method checks if the file exists in storage and downloads it
        to a local cache if needed for processing.

        Args:
            logger: The logger to use
            sync_id: Sync ID
            entity_id: Entity ID
            file_name: Original file name

        Returns:
            Local file path if available, None otherwise
        """
        # Check if file exists in storage
        blob_name = self._get_blob_name(sync_id, entity_id)
        if not await self.client.file_exists(logger, self.container_name, blob_name):
            return None

        # Create local cache path
        cache_path = self.temp_cache_dir / str(sync_id) / entity_id / file_name
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # If already in local cache, return it
        if cache_path.exists():
            logger.info(
                "File found in local cache",
                extra={
                    "sync_id": str(sync_id),
                    "entity_id": entity_id,
                    "cache_path": str(cache_path),
                },
            )
            return str(cache_path)

        # Download from storage to cache
        logger.info(
            "Downloading file from storage to cache",
            extra={"sync_id": str(sync_id), "entity_id": entity_id, "blob_name": blob_name},
        )

        content = await self.client.download_file(logger, self.container_name, blob_name)
        if content:
            with open(cache_path, "wb") as f:
                f.write(content)
            return str(cache_path)

        return None

    async def cleanup_temp_file(self, logger: ContextualLogger, file_path: str) -> None:
        """Clean up a temporary file after processing.

        Args:
            logger: The logger to use
            file_path: Path to the temporary file
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up temp file: {file_path}")

                # Also try to clean up empty parent directories
                parent = Path(file_path).parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()

        except Exception as e:
            logger.warning(f"Failed to clean up temp file {file_path}: {e}")

    # ===== CTTI-SPECIFIC STORAGE METHODS =====
    # Special handling for CTTI clinical trials data that uses global deduplication

    def _is_ctti_entity(self, entity: Any) -> bool:
        """Check if an entity is from CTTI source.

        Args:
            entity: Entity to check

        Returns:
            True if entity is from CTTI source
        """
        # Check multiple indicators for CTTI source
        if (
            entity.airweave_system_metadata
            and entity.airweave_system_metadata.source_name == "CTTI AACT"
        ):
            return True

        # Check entity type
        entity_type = getattr(entity, "__class__", None)
        if entity_type and entity_type.__name__ in ["CTTIWebEntity", "WebFileEntity"]:
            # For WebFileEntity, check if it came from CTTI based on entity_id
            if hasattr(entity, "entity_id") and entity.entity_id.startswith("CTTI:"):
                return True

        # Check metadata for CTTI indicators
        if hasattr(entity, "metadata") and isinstance(entity.metadata, dict):
            if entity.metadata.get("source") == "CTTI":
                return True

        return False

    async def check_ctti_file_exists(self, logger: ContextualLogger, entity_id: str) -> bool:
        """Check if a CTTI file exists in the global aactmarkdowns container.

        Args:
            logger: The logger to use
            entity_id: Entity ID (will be used as filename)

        Returns:
            True if file exists
        """
        # Clean entity_id to create safe filename
        safe_filename = entity_id.replace(":", "_").replace("/", "_") + ".md"

        exists = await self.client.file_exists(logger, "aactmarkdowns", safe_filename)

        if exists:
            logger.info(
                "CTTI file exists in global storage",
                extra={
                    "entity_id": entity_id,
                    "blob_name": safe_filename,
                    "container": "aactmarkdowns",
                },
            )

        return exists

    async def store_ctti_file(
        self, logger: ContextualLogger, entity: FileEntity, content: BinaryIO
    ) -> Any:
        """Store a CTTI file in the global aactmarkdowns container.

        This method stores files without sync_id organization for global deduplication.

        Args:
            logger: The logger to use
            entity: FileEntity to store (must be from CTTI source)
            content: File content as binary stream

        Returns:
            Updated entity with storage information
        """
        if not self._is_ctti_entity(entity):
            raise ValueError(f"Entity {entity.entity_id} is not from CTTI source")

        # Clean entity_id to create safe filename
        safe_filename = entity.entity_id.replace(":", "_").replace("/", "_") + ".md"

        logger.info(
            "Storing CTTI file in global container",
            extra={
                "entity_id": entity.entity_id,
                "blob_name": safe_filename,
                "container": "aactmarkdowns",
            },
        )

        # Store the file
        success = await self.client.upload_file(logger, "aactmarkdowns", safe_filename, content)

        if success:
            # Update entity with storage information
            # Set storage blob name in system metadata (always exists for FileEntity)
            entity.airweave_system_metadata.storage_blob_name = safe_filename

            # Add CTTI-specific metadata to the entity
            if not hasattr(entity, "metadata") or entity.metadata is None:
                entity.metadata = {}
            entity.metadata["ctti_container"] = "aactmarkdowns"
            entity.metadata["ctti_blob_name"] = safe_filename
            entity.metadata["ctti_global_storage"] = True

            # Store minimal metadata (no sync-specific info)
            metadata = {
                "entity_id": entity.entity_id,
                "filename": safe_filename,
                "size": getattr(entity, "total_size", 0),
                "checksum": getattr(entity, "checksum", None),
                "stored_at": utc_now_naive().isoformat(),
                "source": "CTTI",
                "global_dedupe": True,
            }

            # Store metadata in the same container with .meta suffix
            metadata_blob = safe_filename + ".meta"
            metadata_bytes = json.dumps(metadata).encode("utf-8")

            await self.client.upload_file(
                "aactmarkdowns", metadata_blob, io.BytesIO(metadata_bytes)
            )

            logger.info(
                "CTTI file stored successfully in global container",
                extra={"entity_id": entity.entity_id, "blob_name": safe_filename},
            )
        else:
            logger.error(
                "Failed to store CTTI file",
                extra={"entity_id": entity.entity_id, "blob_name": safe_filename},
            )

        return entity

    async def is_ctti_entity_processed(self, logger: ContextualLogger, entity_id: str) -> bool:
        """Check if a CTTI entity has been fully processed (globally).

        Args:
            logger: The logger to use
            entity_id: Entity ID to check

        Returns:
            True if entity was fully processed by any sync
        """
        # For CTTI, just check if the file exists in the global container
        return await self.check_ctti_file_exists(logger, entity_id)

    async def get_ctti_file_content(
        self, logger: ContextualLogger, entity_id: str
    ) -> Optional[str]:
        """Retrieve CTTI file content from global storage.

        Args:
            logger: The logger to use
            entity_id: Entity ID to retrieve

        Returns:
            The markdown content as string if found, None otherwise
        """
        # Clean entity_id to create safe filename
        safe_filename = entity_id.replace(":", "_").replace("/", "_") + ".md"

        logger.info(
            "Retrieving CTTI file from global storage",
            extra={
                "entity_id": entity_id,
                "blob_name": safe_filename,
                "container": "aactmarkdowns",
            },
        )

        # Download the file content
        content_bytes = await self.client.download_file(logger, "aactmarkdowns", safe_filename)

        if content_bytes:
            # Decode markdown content
            content = content_bytes.decode("utf-8")
            logger.info(
                "CTTI file retrieved successfully",
                extra={
                    "entity_id": entity_id,
                    "content_length": len(content),
                },
            )
            return content
        else:
            logger.warning(
                "CTTI file not found in global storage",
                extra={
                    "entity_id": entity_id,
                    "blob_name": safe_filename,
                },
            )
            return None

    async def download_ctti_file(
        self,
        logger: ContextualLogger,
        entity_id: str,
        output_path: Optional[str] = None,
        create_dirs: bool = True,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Download a CTTI file from Azure storage based on entity ID.

        This method retrieves CTTI clinical trial markdown files from the global
        'aactmarkdowns' container in Azure storage.

        Args:
            logger: The logger to use
            entity_id: The CTTI entity ID (e.g., "CTTI:study:NCT00000001")
            output_path: Optional path to save the file. If not provided, returns content only.
                        Can be a directory (file will be named after entity) or full file path.
            create_dirs: Whether to create parent directories if they don't exist (default: True)

        Returns:
            A tuple of (content, file_path):
            - content: The markdown content as a string, or None if not found
            - file_path: The path where the file was saved, or None if output_path not provided

        Raises:
            ValueError: If the entity_id is not a valid CTTI entity ID
            OSError: If there are file system errors when saving
        """
        # Validate entity ID format
        if not entity_id or not entity_id.startswith("CTTI:"):
            raise ValueError(
                f"Invalid CTTI entity ID: '{entity_id}'. "
                "Expected format: 'CTTI:study:NCT...' or similar"
            )

        logger.info(f"Downloading CTTI file for entity: {entity_id}")

        try:
            # Check if file exists first
            if not await self.check_ctti_file_exists(logger, entity_id):
                logger.warning(
                    "CTTI file not found in storage",
                    extra={
                        "entity_id": entity_id,
                        "container": "aactmarkdowns",
                    },
                )
                return None, None

            # Retrieve content from storage
            content = await self.get_ctti_file_content(logger, entity_id)

            if content is None:
                logger.error("Failed to retrieve CTTI file content", extra={"entity_id": entity_id})
                return None, None

            # If no output path specified, just return content
            if not output_path:
                logger.info(
                    "CTTI file retrieved successfully",
                    extra={
                        "entity_id": entity_id,
                        "content_length": len(content),
                        "output": "memory_only",
                    },
                )
                return content, None

            # Determine output file path
            output_file_path = self._determine_ctti_output_path(entity_id, output_path)

            # Create parent directories if needed
            if create_dirs:
                Path(output_file_path).parent.mkdir(parents=True, exist_ok=True)

            # Save content to file
            with open(output_file_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(
                "CTTI file saved successfully",
                extra={
                    "entity_id": entity_id,
                    "content_length": len(content),
                    "output_path": output_file_path,
                },
            )

            return content, output_file_path

        except Exception as e:
            logger.error(
                "Error downloading CTTI file",
                extra={
                    "entity_id": entity_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise

    async def download_ctti_files_batch(
        self,
        logger: ContextualLogger,
        entity_ids: List[str],
        output_dir: Optional[str] = None,
        create_dirs: bool = True,
        continue_on_error: bool = True,
    ) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
        """Download multiple CTTI files in batch.

        Args:
            logger: The logger to use
            entity_ids: List of CTTI entity IDs to download
            output_dir: Optional directory to save files. If not provided, returns content only.
            create_dirs: Whether to create the output directory if it doesn't exist
            continue_on_error: Whether to continue downloading if one file fails

        Returns:
            Dictionary mapping entity_id to (content, file_path) tuples.
            Failed downloads will have (None, None) values.
        """
        results = {}

        logger.info(
            f"Starting batch download of {len(entity_ids)} CTTI files",
            extra={"output_dir": output_dir or "memory_only"},
        )

        for entity_id in entity_ids:
            try:
                content, file_path = await self.download_ctti_file(
                    logger, entity_id, output_dir, create_dirs=create_dirs
                )
                results[entity_id] = (content, file_path)

            except Exception as e:
                logger.error(
                    "Failed to download CTTI file in batch",
                    extra={
                        "entity_id": entity_id,
                        "error": str(e),
                    },
                )
                results[entity_id] = (None, None)

                if not continue_on_error:
                    raise

        # Log summary
        successful = sum(1 for content, _ in results.values() if content is not None)
        logger.info(
            "Batch download completed",
            extra={
                "total": len(entity_ids),
                "successful": successful,
                "failed": len(entity_ids) - successful,
            },
        )

        return results

    def _determine_ctti_output_path(self, entity_id: str, output_path: str) -> str:
        """Determine the actual output file path for CTTI files.

        Args:
            entity_id: The CTTI entity ID
            output_path: The provided output path (file or directory)

        Returns:
            The full file path where the content should be saved
        """
        path = Path(output_path)

        # If output_path is a directory or ends with /, generate filename
        if path.is_dir() or output_path.endswith(os.sep):
            # Generate safe filename from entity_id
            safe_filename = entity_id.replace(":", "_").replace("/", "_") + ".md"
            return os.path.join(output_path, safe_filename)

        # Otherwise use the provided path as-is
        return output_path

    async def get_file_path(
        self, entity_id: str, sync_id: UUID, filename: str, logger: ContextualLogger
    ) -> Optional[str]:
        """Get file path for an entity (from cache or temp directory).

        Args:
            entity_id: The entity ID
            sync_id: The sync ID
            filename: The filename
            logger: Logger for diagnostics

        Returns:
            Path to the file, or None if not found
        """
        # First check if file exists in storage cache
        cached_path = await self.get_cached_file_path(logger, sync_id, entity_id, filename)

        if cached_path and os.path.exists(cached_path):
            logger.debug(f"File found in storage cache: {cached_path}")
            return cached_path

        # Check temp directory as fallback
        temp_base_dir = "/tmp/airweave/processing"
        if not os.path.exists(temp_base_dir):
            return None

        # Search for files matching the safe filename pattern
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
        temp_files = []
        for file in os.listdir(temp_base_dir):
            if file.endswith(safe_filename):
                temp_path = os.path.join(temp_base_dir, file)
                if os.path.exists(temp_path):
                    temp_files.append(temp_path)

        if temp_files:
            # Return most recently modified
            latest_file = max(temp_files, key=os.path.getmtime)
            logger.debug(f"File found in temp directory: {latest_file}")
            return latest_file

        logger.debug(f"File not found for entity {entity_id}")
        return None

    async def get_file_content(
        self, entity_id: str, sync_id: UUID, filename: str, logger: ContextualLogger
    ) -> Optional[bytes]:
        """Get file content as bytes.

        Args:
            entity_id: The entity ID
            sync_id: The sync ID
            filename: The filename
            logger: Logger for diagnostics

        Returns:
            File content as bytes, or None if not found
        """
        file_path = await self.get_file_path(entity_id, sync_id, filename, logger)

        if not file_path:
            return None

        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return None


# Global instance
storage_manager = StorageManager()
