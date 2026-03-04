"""Sync-aware file manager for Airweave.

Provides high-level file operations with sync context awareness:
- Sync-scoped file storage (sync_id/entity_id pattern)
- Metadata tracking for processing state
- Local caching for file processing
- CTTI-specific global storage (legacy)

Uses the unified StorageBackend under the hood.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Dict, List, Optional, Tuple
from uuid import UUID

import aiofiles

from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import ContextualLogger
from airweave.platform.storage.exceptions import StorageNotFoundError
from airweave.platform.storage.protocol import StorageBackend

if TYPE_CHECKING:
    from airweave.platform.entities._base import FileEntity


class SyncFileManager:
    """Manages file storage with sync-aware folder structure and caching.

    Storage layout (unified with raw_data.py):
        raw/{sync_id}/files/{entity_id}_{name}.{ext} # File with name and extension
        raw/{sync_id}/metadata/{entity_id}.json      # File metadata
        aactmarkdowns/{entity_id}.md                 # CTTI global storage (legacy)
    """

    # Container/directory names - unified with raw_data.py
    RAW_DIR = "raw"
    CTTI_GLOBAL_DIR = "aactmarkdowns"

    def __init__(self, backend: Optional[StorageBackend] = None):
        """Initialize sync file manager.

        Args:
            backend: Storage backend. Uses singleton if not provided.
        """
        self._backend = backend

        # Local cache directory for temporary files during processing
        self.temp_cache_dir = Path("/tmp/airweave/cache")
        self.temp_cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def backend(self) -> StorageBackend:
        """Get storage backend (lazy to avoid circular import at module load)."""
        if self._backend is None:
            from airweave.platform.storage import storage_backend

            self._backend = storage_backend
        return self._backend

    def _get_file_path(self, sync_id: UUID, entity_id: str, filename: str = "") -> str:
        """Get storage path for a file: raw/{sync_id}/files/{entity_id}_{name}.{ext}."""
        safe_id = self._safe_entity_id(entity_id)
        if filename:
            safe_name = self._safe_entity_id(Path(filename).stem)
            ext = Path(filename).suffix or ""
            return f"{self.RAW_DIR}/{sync_id}/files/{safe_id}_{safe_name}{ext}"
        return f"{self.RAW_DIR}/{sync_id}/files/{safe_id}"

    def _get_metadata_path(self, sync_id: UUID, entity_id: str) -> str:
        """Get storage path for metadata: raw/{sync_id}/metadata/{entity_id}.json."""
        safe_id = self._safe_entity_id(entity_id)
        return f"{self.RAW_DIR}/{sync_id}/metadata/{safe_id}.json"

    def _safe_entity_id(self, value: str, max_length: int = 200) -> str:
        """Convert entity_id or filename to safe storage path."""
        import hashlib
        import re

        safe = re.sub(r'[/\\:*?"<>|]', "_", str(value))
        safe = re.sub(r"_+", "_", safe).strip("_")

        if len(safe) > max_length or safe != value:
            prefix = safe[:50] if len(safe) > 50 else safe
            hash_suffix = hashlib.md5(value.encode()).hexdigest()[:12]
            safe = f"{prefix}_{hash_suffix}"

        return safe[:max_length]

    def _get_ctti_path(self, entity_id: str) -> str:
        """Get CTTI global storage path."""
        safe_filename = entity_id.replace(":", "_").replace("/", "_") + ".md"
        return f"{self.CTTI_GLOBAL_DIR}/{safe_filename}"

    # =========================================================================
    # Sync-scoped file operations
    # =========================================================================

    async def check_file_exists(
        self, logger: ContextualLogger, sync_id: UUID, entity_id: str
    ) -> bool:
        """Check if a file exists in storage."""
        path = self._get_file_path(sync_id, entity_id)
        exists = await self.backend.exists(path)

        if exists:
            logger.debug(
                "File exists in storage",
                extra={"sync_id": str(sync_id), "entity_id": entity_id},
            )

        return exists

    async def store_file_entity(
        self, logger: ContextualLogger, entity: "FileEntity", content: BinaryIO
    ) -> Any:
        """Store a file entity in persistent storage.

        Args:
            logger: Logger for operations
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
        # Use entity name for file extension
        filename = entity.name or ""
        file_path = self._get_file_path(sync_id, entity.entity_id, filename)

        logger.info(
            "Storing file in persistent storage",
            extra={
                "sync_id": str(sync_id),
                "entity_id": entity.entity_id,
                "path": file_path,
            },
        )

        # Read content and store
        file_bytes = content.read()
        await self.backend.write_file(file_path, file_bytes)

        # Update entity metadata
        entity.airweave_system_metadata.storage_blob_name = file_path

        # Store metadata
        metadata = {
            "entity_id": entity.entity_id,
            "sync_id": str(sync_id),
            "file_name": entity.name,
            "size": entity.airweave_system_metadata.total_size
            if entity.airweave_system_metadata
            else len(file_bytes),
            "checksum": entity.airweave_system_metadata.checksum
            if entity.airweave_system_metadata
            else None,
            "mime_type": getattr(entity, "mime_type", None),
            "stored_at": utc_now_naive().isoformat(),
            "fully_processed": False,
        }

        await self._store_metadata(sync_id, entity.entity_id, metadata)

        logger.info(
            "File stored successfully",
            extra={"sync_id": str(sync_id), "entity_id": entity.entity_id},
        )

        return entity

    async def _store_metadata(
        self, sync_id: UUID, entity_id: str, metadata: Dict[str, Any]
    ) -> None:
        """Store metadata for a file."""
        path = self._get_metadata_path(sync_id, entity_id)
        await self.backend.write_json(path, metadata)

    async def is_entity_fully_processed(self, logger: ContextualLogger, cache_key: str) -> bool:
        """Check if an entity has been fully processed.

        Args:
            logger: Logger for operations
            cache_key: Format "sync_id/entity_id"

        Returns:
            True if entity was fully processed
        """
        try:
            parts = cache_key.split("/")
            if len(parts) != 2:
                return False

            sync_id, entity_id = parts[0], parts[1]
            path = self._get_metadata_path(UUID(sync_id), entity_id)

            try:
                metadata = await self.backend.read_json(path)
                return metadata.get("fully_processed", False)
            except StorageNotFoundError:
                return False

        except Exception as e:
            logger.debug(f"Error checking if entity is fully processed: {e}")
            return False

    async def mark_entity_processed(
        self, logger: ContextualLogger, sync_id: UUID, entity_id: str, chunk_count: int
    ) -> None:
        """Mark an entity as fully processed after chunking."""
        path = self._get_metadata_path(sync_id, entity_id)

        try:
            metadata = await self.backend.read_json(path)
        except StorageNotFoundError:
            metadata = {"entity_id": entity_id, "sync_id": str(sync_id)}

        metadata.update(
            {
                "fully_processed": True,
                "chunk_count": chunk_count,
                "processed_at": utc_now_naive().isoformat(),
            }
        )

        await self.backend.write_json(path, metadata)

        logger.info(
            "Marked entity as processed",
            extra={"sync_id": str(sync_id), "entity_id": entity_id, "chunk_count": chunk_count},
        )

    async def get_cached_file_path(
        self, logger: ContextualLogger, sync_id: UUID, entity_id: str, file_name: str
    ) -> Optional[str]:
        """Get or create a local cache path for a file.

        Downloads from storage to local cache if needed.
        """
        path = self._get_file_path(sync_id, entity_id)

        if not await self.backend.exists(path):
            return None

        # Create local cache path
        cache_path = self.temp_cache_dir / str(sync_id) / entity_id / file_name
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Return if already cached
        if cache_path.exists():
            logger.debug(f"File found in local cache: {cache_path}")
            return str(cache_path)

        # Download from storage to cache
        logger.debug(f"Downloading file from storage to cache: {path}")
        content = await self.backend.read_file(path)
        async with aiofiles.open(cache_path, "wb") as f:
            await f.write(content)

        return str(cache_path)

    async def cleanup_temp_file(self, logger: ContextualLogger, file_path: str) -> None:
        """Clean up a temporary file after processing."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up temp file: {file_path}")

                # Clean up empty parent directories
                parent = Path(file_path).parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()

        except Exception as e:
            logger.warning(f"Failed to clean up temp file {file_path}: {e}")

    async def get_file_path(
        self, entity_id: str, sync_id: UUID, filename: str, logger: ContextualLogger
    ) -> Optional[str]:
        """Get file path for an entity (from cache or temp directory)."""
        # Check storage cache first
        cached_path = await self.get_cached_file_path(logger, sync_id, entity_id, filename)
        if cached_path and os.path.exists(cached_path):
            return cached_path

        # Check temp directory as fallback
        temp_base_dir = "/tmp/airweave/processing"
        if not os.path.exists(temp_base_dir):
            return None

        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
        temp_files = []
        for file in os.listdir(temp_base_dir):
            if file.endswith(safe_filename):
                temp_path = os.path.join(temp_base_dir, file)
                if os.path.exists(temp_path):
                    temp_files.append(temp_path)

        if temp_files:
            return max(temp_files, key=os.path.getmtime)

        logger.debug(f"File not found for entity {entity_id}")
        return None

    async def get_file_content(
        self, entity_id: str, sync_id: UUID, filename: str, logger: ContextualLogger
    ) -> Optional[bytes]:
        """Get file content as bytes."""
        file_path = await self.get_file_path(entity_id, sync_id, filename, logger)
        if not file_path:
            return None

        try:
            async with aiofiles.open(file_path, "rb") as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return None

    # =========================================================================
    # CTTI-specific global storage (legacy)
    # =========================================================================

    def _is_ctti_entity(self, entity: Any) -> bool:
        """Check if an entity is from CTTI source."""
        if hasattr(entity, "airweave_system_metadata") and entity.airweave_system_metadata:
            if entity.airweave_system_metadata.source_name == "CTTI AACT":
                return True

        entity_type = getattr(entity, "__class__", None)
        if entity_type and entity_type.__name__ in ["CTTIWebEntity", "WebFileEntity"]:
            if hasattr(entity, "entity_id") and str(entity.entity_id).startswith("CTTI:"):
                return True

        if hasattr(entity, "metadata") and isinstance(entity.metadata, dict):
            if entity.metadata.get("source") == "CTTI":
                return True

        return False

    async def check_ctti_file_exists(self, logger: ContextualLogger, entity_id: str) -> bool:
        """Check if a CTTI file exists in global storage."""
        path = self._get_ctti_path(entity_id)
        exists = await self.backend.exists(path)

        if exists:
            logger.debug(
                "CTTI file exists in global storage",
                extra={"entity_id": entity_id, "path": path},
            )

        return exists

    async def store_ctti_file(
        self, logger: ContextualLogger, entity: "FileEntity", content: BinaryIO
    ) -> Any:
        """Store a CTTI file in global storage."""
        if not self._is_ctti_entity(entity):
            raise ValueError(f"Entity {entity.entity_id} is not from CTTI source")

        path = self._get_ctti_path(entity.entity_id)

        logger.info(
            "Storing CTTI file in global storage",
            extra={"entity_id": entity.entity_id, "path": path},
        )

        file_bytes = content.read()
        await self.backend.write_file(path, file_bytes)

        # Update entity metadata
        entity.airweave_system_metadata.storage_blob_name = path

        if not hasattr(entity, "metadata") or entity.metadata is None:
            entity.metadata = {}
        entity.metadata["ctti_container"] = self.CTTI_GLOBAL_DIR
        entity.metadata["ctti_global_storage"] = True

        # Store metadata alongside
        metadata_path = path + ".meta"
        metadata = {
            "entity_id": entity.entity_id,
            "size": len(file_bytes),
            "checksum": entity.airweave_system_metadata.checksum
            if entity.airweave_system_metadata
            else None,
            "stored_at": utc_now_naive().isoformat(),
            "source": "CTTI",
            "global_dedupe": True,
        }
        await self.backend.write_json(metadata_path, metadata)

        logger.info(
            "CTTI file stored successfully",
            extra={"entity_id": entity.entity_id, "path": path},
        )

        return entity

    async def is_ctti_entity_processed(self, logger: ContextualLogger, entity_id: str) -> bool:
        """Check if a CTTI entity has been fully processed."""
        return await self.check_ctti_file_exists(logger, entity_id)

    async def get_ctti_file_content(
        self, logger: ContextualLogger, entity_id: str
    ) -> Optional[str]:
        """Retrieve CTTI file content from global storage."""
        path = self._get_ctti_path(entity_id)

        try:
            content_bytes = await self.backend.read_file(path)
            content = content_bytes.decode("utf-8")
            logger.debug(
                "CTTI file retrieved",
                extra={"entity_id": entity_id, "content_length": len(content)},
            )
            return content
        except StorageNotFoundError:
            logger.warning(
                "CTTI file not found",
                extra={"entity_id": entity_id, "path": path},
            )
            return None
        except Exception as e:
            logger.error(f"Failed to get CTTI file content: {e}")
            return None

    async def download_ctti_file(
        self,
        logger: ContextualLogger,
        entity_id: str,
        output_path: Optional[str] = None,
        create_dirs: bool = True,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Download a CTTI file by entity ID.

        Args:
            logger: Logger instance
            entity_id: The CTTI entity ID (e.g., "CTTI:study:NCT00000001")
            output_path: Optional path to save the file
            create_dirs: Whether to create parent directories

        Returns:
            Tuple of (content, file_path)
        """
        if not entity_id or not entity_id.startswith("CTTI:"):
            raise ValueError(
                f"Invalid CTTI entity ID: '{entity_id}'. "
                "Expected format: 'CTTI:study:NCT...' or similar"
            )

        logger.debug(f"Downloading CTTI file for entity: {entity_id}")

        try:
            if not await self.check_ctti_file_exists(logger, entity_id):
                return None, None

            content = await self.get_ctti_file_content(logger, entity_id)
            if content is None:
                return None, None

            if not output_path:
                return content, None

            # Determine output file path
            path = Path(output_path)
            if path.is_dir() or output_path.endswith(os.sep):
                safe_filename = entity_id.replace(":", "_").replace("/", "_") + ".md"
                output_file_path = os.path.join(output_path, safe_filename)
            else:
                output_file_path = output_path

            if create_dirs:
                Path(output_file_path).parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(output_file_path, "w", encoding="utf-8") as f:
                await f.write(content)

            logger.info(
                "CTTI file saved",
                extra={"entity_id": entity_id, "output_path": output_file_path},
            )

            return content, output_file_path

        except Exception as e:
            logger.error(f"Error downloading CTTI file: {e}")
            raise

    async def download_ctti_files_batch(
        self,
        logger: ContextualLogger,
        entity_ids: List[str],
        output_dir: Optional[str] = None,
        create_dirs: bool = True,
        continue_on_error: bool = True,
    ) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
        """Download multiple CTTI files in batch."""
        results = {}

        logger.info(f"Starting batch download of {len(entity_ids)} CTTI files")

        for entity_id in entity_ids:
            try:
                content, file_path = await self.download_ctti_file(
                    logger, entity_id, output_dir, create_dirs=create_dirs
                )
                results[entity_id] = (content, file_path)

            except Exception as e:
                logger.error(f"Failed to download CTTI file {entity_id}: {e}")
                results[entity_id] = (None, None)

                if not continue_on_error:
                    raise

        successful = sum(1 for content, _ in results.values() if content is not None)
        logger.info(f"Batch download completed: {successful}/{len(entity_ids)} successful")

        return results


# Global instance for convenience
sync_file_manager = SyncFileManager()
