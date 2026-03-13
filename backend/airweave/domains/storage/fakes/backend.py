"""In-memory fake for StorageBackend protocol."""

from typing import Any, Dict, List

from airweave.domains.storage.exceptions import StorageNotFoundError


class FakeStorageBackend:
    """In-memory storage backend for testing.

    Stores JSON and binary data in dicts keyed by path.
    Supports prefix-based listing and directory-style deletion.
    """

    def __init__(self) -> None:
        self._json_store: Dict[str, Dict[str, Any]] = {}
        self._file_store: Dict[str, bytes] = {}

    # -- Test helpers ----------------------------------------------------------

    def seed_json(self, path: str, data: Dict[str, Any]) -> None:
        """Pre-populate a JSON object."""
        self._json_store[path] = data

    def seed_file(self, path: str, content: bytes) -> None:
        """Pre-populate a binary file."""
        self._file_store[path] = content

    def reset(self) -> None:
        """Clear all stored data."""
        self._json_store.clear()
        self._file_store.clear()

    # -- Protocol implementation -----------------------------------------------

    async def write_json(self, path: str, data: Dict[str, Any]) -> None:
        self._json_store[path] = data

    async def read_json(self, path: str) -> Dict[str, Any]:
        if path not in self._json_store:
            raise StorageNotFoundError(path)
        return self._json_store[path]

    async def write_file(self, path: str, content: bytes) -> None:
        self._file_store[path] = content

    async def read_file(self, path: str) -> bytes:
        if path not in self._file_store:
            raise StorageNotFoundError(path)
        return self._file_store[path]

    async def exists(self, path: str) -> bool:
        return path in self._json_store or path in self._file_store

    async def delete(self, path: str) -> bool:
        if path in self._json_store or path in self._file_store:
            self._json_store.pop(path, None)
            self._file_store.pop(path, None)
            return True
        prefix = path.rstrip("/") + "/"
        json_keys = [k for k in self._json_store if k.startswith(prefix)]
        file_keys = [k for k in self._file_store if k.startswith(prefix)]
        for k in json_keys:
            del self._json_store[k]
        for k in file_keys:
            del self._file_store[k]
        return len(json_keys) > 0 or len(file_keys) > 0

    async def list_files(self, prefix: str = "") -> List[str]:
        return [k for k in self._json_store if k.startswith(prefix)]

    async def list_dirs(self, prefix: str = "") -> List[str]:
        dirs: set[str] = set()
        for k in self._json_store:
            if k.startswith(prefix):
                rest = k[len(prefix):].lstrip("/")
                parts = rest.split("/")
                if len(parts) > 1:
                    dirs.add(f"{prefix}/{parts[0]}")
        return sorted(dirs)

    async def count_files(self, prefix: str = "", pattern: str = "*") -> int:
        files = await self.list_files(prefix)
        if pattern == "*.json":
            files = [f for f in files if f.endswith(".json")]
        return len(files)
