"""Centralized path constants for Airweave storage operations.

All temp and persistent storage paths should be defined here for consistency.
"""

import hashlib
import re
from pathlib import Path
from typing import Optional
from uuid import UUID


class StoragePaths:
    """Centralized storage path constants and builders."""

    # =========================================================================
    # Base directories
    # =========================================================================

    # Temp processing directory (ephemeral, cleaned after sync)
    TEMP_BASE = "/tmp/airweave"
    TEMP_PROCESSING = f"{TEMP_BASE}/processing"
    TEMP_CACHE = f"{TEMP_BASE}/cache"

    # ARF (Airweave Raw Format) storage prefix
    ARF_PREFIX = "raw"

    # Legacy directories
    CTTI_GLOBAL_DIR = "aactmarkdowns"

    # =========================================================================
    # ARF path builders
    # =========================================================================

    @classmethod
    def arf_sync_path(cls, sync_id: UUID) -> str:
        """Base path for a sync's ARF data: raw/{sync_id}/."""
        return f"{cls.ARF_PREFIX}/{sync_id}"

    @classmethod
    def arf_manifest_path(cls, sync_id: UUID) -> str:
        """Manifest path: raw/{sync_id}/manifest.json."""
        return f"{cls.arf_sync_path(sync_id)}/manifest.json"

    @classmethod
    def arf_entity_path(cls, sync_id: UUID, entity_id: str) -> str:
        """Entity path: raw/{sync_id}/entities/{safe_entity_id}.json."""
        safe_id = cls._safe_filename(entity_id)
        return f"{cls.arf_sync_path(sync_id)}/entities/{safe_id}.json"

    @classmethod
    def arf_file_path(cls, sync_id: UUID, entity_id: str, filename: Optional[str] = None) -> str:
        """File path: raw/{sync_id}/files/{entity_id}_{name}.{ext}."""
        safe_id = cls._safe_filename(entity_id)
        if filename:
            name = Path(filename).stem
            ext = Path(filename).suffix or ""
            safe_name = cls._safe_filename(name)
            return f"{cls.arf_sync_path(sync_id)}/files/{safe_id}_{safe_name}{ext}"
        return f"{cls.arf_sync_path(sync_id)}/files/{safe_id}"

    @classmethod
    def arf_entities_dir(cls, sync_id: UUID) -> str:
        """Entities directory: raw/{sync_id}/entities/."""
        return f"{cls.arf_sync_path(sync_id)}/entities"

    @classmethod
    def arf_files_dir(cls, sync_id: UUID) -> str:
        """Files directory: raw/{sync_id}/files/."""
        return f"{cls.arf_sync_path(sync_id)}/files"

    # =========================================================================
    # Temp path builders
    # =========================================================================

    @classmethod
    def temp_sync_dir(cls, sync_job_id: UUID) -> str:
        """Temp directory for a sync job: /tmp/airweave/processing/{sync_job_id}/."""
        return f"{cls.TEMP_PROCESSING}/{sync_job_id}"

    @classmethod
    def temp_file_path(cls, sync_job_id: UUID, file_uuid: str, filename: str) -> str:
        """Temp file path: /tmp/airweave/processing/{sync_job_id}/{uuid}-{name}."""
        safe_name = cls._safe_filename(filename)
        return f"{cls.temp_sync_dir(sync_job_id)}/{file_uuid}-{safe_name}"

    @classmethod
    def temp_cache_dir(cls) -> str:
        """Cache directory for downloaded files."""
        return cls.TEMP_CACHE

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _safe_filename(value: str, max_length: int = 200) -> str:
        """Convert value to safe storage path.

        Uses hash suffix for long/complex values to ensure uniqueness.
        """
        safe = re.sub(r'[/\\:*?"<>|]', "_", str(value))
        safe = re.sub(r"_+", "_", safe).strip("_")

        if len(safe) > max_length or safe != value:
            prefix = safe[:50] if len(safe) > 50 else safe
            hash_suffix = hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()[:12]
            safe = f"{prefix}_{hash_suffix}"

        return safe[:max_length]


# Convenience alias
paths = StoragePaths
