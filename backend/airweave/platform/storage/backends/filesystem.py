"""Filesystem storage backend.

Implements StorageBackend protocol for local filesystem storage.
Works with local development directories and Kubernetes PVC mounts.
"""

import asyncio
import json
import logging
import os
import shutil
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Union

import aiofiles
import aiofiles.os

from airweave.platform.storage.exceptions import (
    StorageException,
    StorageNotFoundError,
)
from airweave.platform.storage.protocol import StorageBackend

logger = logging.getLogger(__name__)


class FilesystemBackend(StorageBackend):
    """Filesystem-based storage backend.

    Works with:
    - Local development: local_storage/ (at repo root, mounted to /app/local_storage)
    - Kubernetes: PVC-mounted path (e.g., /data/airweave-storage)

    Uses aiofiles for non-blocking file I/O operations.
    """

    def __init__(self, base_path: Union[str, Path]):
        """Initialize filesystem backend.

        Args:
            base_path: Root directory for all storage operations
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"FilesystemBackend initialized at {self.base_path}")

    def _resolve(self, path: str) -> Path:
        """Resolve relative path to absolute."""
        normalized = path.replace("/", os.sep)
        return self.base_path / normalized

    async def _ensure_parent_dir(self, full_path: Path) -> None:
        """Ensure parent directory exists (async-friendly)."""
        parent = full_path.parent
        if not parent.exists():
            await asyncio.to_thread(parent.mkdir, parents=True, exist_ok=True)

    async def write_json(self, path: str, data: Dict[str, Any]) -> None:
        """Write JSON to filesystem."""
        full_path = self._resolve(path)
        await self._ensure_parent_dir(full_path)

        try:
            content = json.dumps(data, indent=2, default=str)
            async with aiofiles.open(full_path, "w", encoding="utf-8") as f:
                await f.write(content)
        except Exception as e:
            raise StorageException(f"Failed to write JSON to {path}: {e}")

    async def read_json(self, path: str) -> Dict[str, Any]:
        """Read JSON from filesystem."""
        full_path = self._resolve(path)

        if not full_path.exists():
            raise StorageNotFoundError(f"Path not found: {path}")

        try:
            async with aiofiles.open(full_path, "r", encoding="utf-8") as f:
                content = await f.read()
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise StorageException(f"Invalid JSON at {path}: {e}")
        except Exception as e:
            raise StorageException(f"Failed to read JSON from {path}: {e}")

    async def write_file(self, path: str, content: bytes) -> None:
        """Write binary content to filesystem."""
        full_path = self._resolve(path)
        await self._ensure_parent_dir(full_path)

        try:
            async with aiofiles.open(full_path, "wb") as f:
                await f.write(content)
        except Exception as e:
            raise StorageException(f"Failed to write file to {path}: {e}")

    async def read_file(self, path: str) -> bytes:
        """Read binary content from filesystem."""
        full_path = self._resolve(path)

        if not full_path.exists():
            raise StorageNotFoundError(f"Path not found: {path}")

        try:
            async with aiofiles.open(full_path, "rb") as f:
                return await f.read()
        except Exception as e:
            raise StorageException(f"Failed to read file from {path}: {e}")

    async def exists(self, path: str) -> bool:
        """Check if path exists on filesystem."""
        full_path = self._resolve(path)
        return await aiofiles.os.path.exists(full_path)

    async def delete(self, path: str) -> bool:
        """Delete file or directory from filesystem."""
        full_path = self._resolve(path)

        if not full_path.exists():
            return False

        try:
            if full_path.is_dir():
                await asyncio.to_thread(shutil.rmtree, full_path)
            else:
                await aiofiles.os.remove(full_path)
            return True
        except Exception as e:
            logger.error(f"Failed to delete {path}: {e}")
            return False

    async def list_files(self, prefix: str = "") -> List[str]:
        """List all files under prefix (recursive)."""

        def _list_files_sync() -> List[str]:
            base = self._resolve(prefix) if prefix else self.base_path
            if not base.exists():
                return []

            files = []
            for item in base.rglob("*"):
                if item.is_file():
                    rel_path = str(item.relative_to(self.base_path))
                    files.append(rel_path.replace(os.sep, "/"))

            return sorted(files)

        return await asyncio.to_thread(_list_files_sync)

    async def list_dirs(self, prefix: str = "") -> List[str]:
        """List immediate subdirectories under prefix."""

        def _list_dirs_sync() -> List[str]:
            base = self._resolve(prefix) if prefix else self.base_path
            if not base.exists():
                return []

            dirs = []
            for item in base.iterdir():
                if item.is_dir():
                    rel_path = str(item.relative_to(self.base_path))
                    dirs.append(rel_path.replace(os.sep, "/"))

            return sorted(dirs)

        return await asyncio.to_thread(_list_dirs_sync)

    async def count_files(self, prefix: str = "", pattern: str = "*") -> int:
        """Count files under prefix matching pattern."""

        def _count_files_sync() -> int:
            base = self._resolve(prefix) if prefix else self.base_path
            if not base.exists():
                return 0

            count = 0
            for item in base.rglob("*"):
                if item.is_file() and fnmatch(item.name, pattern):
                    count += 1

            return count

        return await asyncio.to_thread(_count_files_sync)
