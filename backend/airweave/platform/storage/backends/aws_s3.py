"""AWS S3 storage backend.

Implements StorageBackend protocol for AWS S3 and S3-compatible storage
(MinIO, LocalStack, etc.).
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


class S3Backend(StorageBackend):
    """AWS S3 storage backend.

    Uses aiobotocore for async S3 operations. Supports standard AWS
    credential chain (env vars, IAM roles, credential files).

    Also works with S3-compatible storage (MinIO, LocalStack) via endpoint_url.
    """

    def __init__(
        self,
        bucket: str,
        region: str,
        prefix: str = "",
        endpoint_url: Optional[str] = None,
    ):
        """Initialize S3 backend.

        Args:
            bucket: S3 bucket name
            region: AWS region (e.g., "us-east-1")
            prefix: Optional prefix for all paths
            endpoint_url: Optional custom endpoint for S3-compatible storage
        """
        self.bucket = bucket
        self.region = region
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        self.endpoint_url = endpoint_url
        self._session = None
        self._client = None

        logger.debug(
            f"S3Backend initialized: s3://{bucket}"
            f"{f'/{prefix}' if prefix else ''}"
            f" (region={region})"
            f"{f', endpoint={endpoint_url}' if endpoint_url else ''}"
        )

    async def _get_client(self):
        """Lazy-load async S3 client."""
        if self._client is None:
            try:
                from aiobotocore.session import get_session

                self._session = get_session()
                self._client = await self._session.create_client(
                    "s3",
                    region_name=self.region,
                    endpoint_url=self.endpoint_url,
                ).__aenter__()
            except ImportError as e:
                raise StorageException(
                    "aiobotocore not installed. Install with: pip install aiobotocore"
                ) from e
        return self._client

    def _resolve(self, path: str) -> str:
        """Resolve path with prefix."""
        return f"{self.prefix}{path}"

    async def close(self) -> None:
        """Close async client and release resources."""
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None
            self._session = None

    async def write_json(self, path: str, data: Dict[str, Any]) -> None:
        """Write JSON to S3."""
        key = self._resolve(path)
        try:
            content = json.dumps(data, indent=2, default=str)
            client = await self._get_client()
            await client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as e:
            raise StorageException(f"Failed to write JSON to {path}: {e}")

    async def read_json(self, path: str) -> Dict[str, Any]:
        """Read JSON from S3."""
        key = self._resolve(path)
        try:
            client = await self._get_client()
            response = await client.get_object(Bucket=self.bucket, Key=key)
            async with response["Body"] as stream:
                content = await stream.read()
            return json.loads(content.decode("utf-8"))
        except client.exceptions.NoSuchKey:
            raise StorageNotFoundError(f"Path not found: {path}")
        except Exception as e:
            if "NoSuchKey" in str(e) or "404" in str(e):
                raise StorageNotFoundError(f"Path not found: {path}")
            raise StorageException(f"Failed to read JSON from {path}: {e}")

    async def write_file(self, path: str, content: bytes) -> None:
        """Write binary content to S3."""
        key = self._resolve(path)
        try:
            client = await self._get_client()
            await client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
            )
        except Exception as e:
            raise StorageException(f"Failed to write file to {path}: {e}")

    async def read_file(self, path: str) -> bytes:
        """Read binary content from S3."""
        key = self._resolve(path)
        try:
            client = await self._get_client()
            response = await client.get_object(Bucket=self.bucket, Key=key)
            async with response["Body"] as stream:
                return await stream.read()
        except Exception as e:
            if "NoSuchKey" in str(e) or "404" in str(e):
                raise StorageNotFoundError(f"Path not found: {path}")
            raise StorageException(f"Failed to read file from {path}: {e}")

    async def exists(self, path: str) -> bool:
        """Check if object exists in S3."""
        key = self._resolve(path)
        try:
            client = await self._get_client()
            await client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    async def delete(self, path: str) -> bool:
        """Delete object or all objects under prefix."""
        key = self._resolve(path)
        deleted_count = 0

        try:
            client = await self._get_client()

            # Try direct object delete first
            try:
                await client.head_object(Bucket=self.bucket, Key=key)
                await client.delete_object(Bucket=self.bucket, Key=key)
                return True
            except Exception:
                pass

            # If not a single object, try as prefix
            prefix = key if key.endswith("/") else key + "/"
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    await client.delete_object(Bucket=self.bucket, Key=obj["Key"])
                    deleted_count += 1

            return deleted_count > 0

        except Exception as e:
            logger.error(f"Failed to delete {path}: {e}")
            return False

    async def list_files(self, prefix: str = "") -> List[str]:
        """List all objects under prefix."""
        full_prefix = self._resolve(prefix)
        if prefix and not full_prefix.endswith("/"):
            full_prefix += "/"

        files = []
        try:
            client = await self._get_client()
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
                for obj in page.get("Contents", []):
                    # Return path relative to our prefix
                    rel_path = obj["Key"]
                    if self.prefix and rel_path.startswith(self.prefix):
                        rel_path = rel_path[len(self.prefix) :]
                    files.append(rel_path)
        except Exception as e:
            logger.error(f"Failed to list files in {prefix}: {e}")

        return sorted(files)

    async def list_dirs(self, prefix: str = "") -> List[str]:
        """List 'directories' under prefix (common prefixes)."""
        full_prefix = self._resolve(prefix)
        if not full_prefix.endswith("/"):
            full_prefix += "/"

        dirs = set()
        try:
            client = await self._get_client()
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(
                Bucket=self.bucket, Prefix=full_prefix, Delimiter="/"
            ):
                for common_prefix in page.get("CommonPrefixes", []):
                    # Extract directory name from prefix
                    dir_path = common_prefix["Prefix"].rstrip("/")
                    if self.prefix and dir_path.startswith(self.prefix):
                        dir_path = dir_path[len(self.prefix) :]
                    dirs.add(dir_path)
        except Exception as e:
            logger.error(f"Failed to list dirs in {prefix}: {e}")

        return sorted(dirs)

    async def count_files(self, prefix: str = "", pattern: str = "*") -> int:
        """Count objects under prefix without building full list."""
        full_prefix = self._resolve(prefix)
        if prefix and not full_prefix.endswith("/"):
            full_prefix += "/"

        count = 0
        try:
            client = await self._get_client()
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
                for obj in page.get("Contents", []):
                    rel_path = obj["Key"][len(full_prefix) :]
                    if pattern == "*" or fnmatch.fnmatch(rel_path, pattern):
                        count += 1
        except Exception as e:
            logger.error(f"Failed to count files in {prefix}: {e}")

        return count
