"""Google Cloud Storage backend.

Implements StorageBackend protocol for Google Cloud Storage (GCS).
Uses Application Default Credentials for authentication.
"""

import fnmatch
import json
from typing import Any, Dict, List, Optional

from airweave.core.logging import logger
from airweave.platform.storage.exceptions import (
    StorageException,
    StorageNotFoundError,
)
from airweave.platform.storage.protocol import StorageBackend


class GCSBackend(StorageBackend):
    """Google Cloud Storage backend.

    Uses google-cloud-storage library with Application Default Credentials
    (ADC). Authentication works via:
    - GOOGLE_APPLICATION_CREDENTIALS env var (service account JSON)
    - Workload Identity (GKE)
    - gcloud CLI default credentials

    Note: google-cloud-storage uses sync operations internally, so we wrap
    them in asyncio.to_thread for non-blocking behavior.
    """

    def __init__(
        self,
        bucket: str,
        project: Optional[str] = None,
        prefix: str = "",
    ):
        """Initialize GCS backend.

        Args:
            bucket: GCS bucket name
            project: Optional GCP project ID (usually auto-detected)
            prefix: Optional prefix for all paths
        """
        self.bucket_name = bucket
        self.project = project
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        self._client = None
        self._bucket = None

        logger.debug(
            f"GCSBackend initialized: gs://{bucket}"
            f"{f'/{prefix}' if prefix else ''}"
            f"{f' (project={project})' if project else ''}"
        )

    def _get_client(self):
        """Lazy-load GCS client (sync)."""
        if self._client is None:
            try:
                from google.cloud import storage

                self._client = storage.Client(project=self.project)
                self._bucket = self._client.bucket(self.bucket_name)
            except ImportError as e:
                raise StorageException(
                    "google-cloud-storage not installed. Install with: "
                    "pip install google-cloud-storage"
                ) from e
        return self._client

    def _get_bucket(self):
        """Get bucket object."""
        self._get_client()
        return self._bucket

    def _resolve(self, path: str) -> str:
        """Resolve path with prefix."""
        return f"{self.prefix}{path}"

    async def close(self) -> None:
        """Close client (GCS client doesn't require explicit closing)."""
        self._client = None
        self._bucket = None

    async def write_json(self, path: str, data: Dict[str, Any]) -> None:
        """Write JSON to GCS."""
        import asyncio

        blob_name = self._resolve(path)

        def _write():
            bucket = self._get_bucket()
            blob = bucket.blob(blob_name)
            content = json.dumps(data, indent=2, default=str)
            blob.upload_from_string(content, content_type="application/json")

        try:
            await asyncio.to_thread(_write)
        except Exception as e:
            raise StorageException(f"Failed to write JSON to {path}: {e}")

    async def read_json(self, path: str) -> Dict[str, Any]:
        """Read JSON from GCS."""
        import asyncio

        blob_name = self._resolve(path)

        def _read():
            from google.cloud.exceptions import NotFound

            bucket = self._get_bucket()
            blob = bucket.blob(blob_name)
            try:
                content = blob.download_as_text()
                return json.loads(content)
            except NotFound:
                raise StorageNotFoundError(f"Path not found: {path}")

        try:
            return await asyncio.to_thread(_read)
        except StorageNotFoundError:
            raise
        except json.JSONDecodeError as e:
            raise StorageException(f"Invalid JSON at {path}: {e}")
        except Exception as e:
            raise StorageException(f"Failed to read JSON from {path}: {e}")

    async def write_file(self, path: str, content: bytes) -> None:
        """Write binary content to GCS."""
        import asyncio

        blob_name = self._resolve(path)

        def _write():
            bucket = self._get_bucket()
            blob = bucket.blob(blob_name)
            blob.upload_from_string(content)

        try:
            await asyncio.to_thread(_write)
        except Exception as e:
            raise StorageException(f"Failed to write file to {path}: {e}")

    async def read_file(self, path: str) -> bytes:
        """Read binary content from GCS."""
        import asyncio

        blob_name = self._resolve(path)

        def _read():
            from google.cloud.exceptions import NotFound

            bucket = self._get_bucket()
            blob = bucket.blob(blob_name)
            try:
                return blob.download_as_bytes()
            except NotFound:
                raise StorageNotFoundError(f"Path not found: {path}")

        try:
            return await asyncio.to_thread(_read)
        except StorageNotFoundError:
            raise
        except Exception as e:
            raise StorageException(f"Failed to read file from {path}: {e}")

    async def exists(self, path: str) -> bool:
        """Check if blob exists in GCS."""
        import asyncio

        blob_name = self._resolve(path)

        def _exists():
            bucket = self._get_bucket()
            blob = bucket.blob(blob_name)
            return blob.exists()

        try:
            return await asyncio.to_thread(_exists)
        except Exception:
            return False

    async def delete(self, path: str) -> bool:
        """Delete blob or all blobs under prefix."""
        import asyncio

        blob_name = self._resolve(path)

        def _delete():
            from google.cloud.exceptions import NotFound

            bucket = self._get_bucket()
            deleted_count = 0

            # Try direct blob delete first
            blob = bucket.blob(blob_name)
            try:
                blob.delete()
                return True
            except NotFound:
                pass

            # If not a blob, try as prefix
            prefix = blob_name if blob_name.endswith("/") else blob_name + "/"
            blobs = list(bucket.list_blobs(prefix=prefix))
            for blob in blobs:
                blob.delete()
                deleted_count += 1

            return deleted_count > 0

        try:
            return await asyncio.to_thread(_delete)
        except Exception as e:
            logger.error(f"Failed to delete {path}: {e}")
            return False

    async def list_files(self, prefix: str = "") -> List[str]:
        """List all blobs under prefix."""
        import asyncio

        full_prefix = self._resolve(prefix)
        if prefix and not full_prefix.endswith("/"):
            full_prefix += "/"

        def _list():
            bucket = self._get_bucket()
            files = []
            for blob in bucket.list_blobs(prefix=full_prefix):
                # Return path relative to our prefix
                rel_path = blob.name
                if self.prefix and rel_path.startswith(self.prefix):
                    rel_path = rel_path[len(self.prefix) :]
                files.append(rel_path)
            return sorted(files)

        try:
            return await asyncio.to_thread(_list)
        except Exception as e:
            logger.error(f"Failed to list files in {prefix}: {e}")
            return []

    async def list_dirs(self, prefix: str = "") -> List[str]:
        """List 'directories' under prefix."""
        import asyncio

        full_prefix = self._resolve(prefix)
        if not full_prefix.endswith("/"):
            full_prefix += "/"

        def _list_dirs():
            bucket = self._get_bucket()
            dirs = set()

            # Use delimiter to get "directories"
            iterator = bucket.list_blobs(prefix=full_prefix, delimiter="/")
            # Force iteration to populate prefixes
            list(iterator)

            for prefix_path in iterator.prefixes:
                dir_path = prefix_path.rstrip("/")
                if self.prefix and dir_path.startswith(self.prefix):
                    dir_path = dir_path[len(self.prefix) :]
                dirs.add(dir_path)

            return sorted(dirs)

        try:
            return await asyncio.to_thread(_list_dirs)
        except Exception as e:
            logger.error(f"Failed to list dirs in {prefix}: {e}")
            return []

    async def count_files(self, prefix: str = "", pattern: str = "*") -> int:
        """Count blobs under prefix without building full list."""
        import asyncio

        full_prefix = self._resolve(prefix)
        if prefix and not full_prefix.endswith("/"):
            full_prefix += "/"

        def _count():
            bucket = self._get_bucket()
            count = 0
            for blob in bucket.list_blobs(prefix=full_prefix):
                rel_path = blob.name[len(full_prefix) :]
                if pattern == "*" or fnmatch.fnmatch(rel_path, pattern):
                    count += 1
            return count

        try:
            return await asyncio.to_thread(_count)
        except Exception as e:
            logger.error(f"Failed to count files in {prefix}: {e}")
            return 0
