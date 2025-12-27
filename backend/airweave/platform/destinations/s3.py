"""S3-compatible storage destination for state mirroring.

Supports AWS S3, MinIO, LocalStack, Cloudflare R2, or any S3 API-compatible service.
Mirrors the current state of entities (one file per entity) with insert/update/delete operations.
Event streaming is built on top using S3 event notifications (SNS/SQS).
"""

import json
from typing import Optional
from uuid import UUID

try:
    import aioboto3  # type: ignore
    from botocore.exceptions import ClientError, NoCredentialsError  # type: ignore
except ImportError:
    aioboto3 = None  # type: ignore
    ClientError = Exception  # type: ignore
    NoCredentialsError = Exception  # type: ignore

from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.configs.auth import S3AuthConfig
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.storage import sync_file_manager


@destination("S3", "s3", auth_config_class=S3AuthConfig, supports_vector=False)
class S3Destination(BaseDestination):
    """S3-compatible storage destination for state mirroring with blob support.

    Data Organization:
        {bucket}/{prefix}/collections/{readable_id}/
            ├── entities/
            │   └── {entity_id}.json        ← Entity metadata (all entities)
            └── blobs/
                └── {entity_id}.{ext}       ← Actual file content (FileEntity only)

    Entity Types:
        1. Regular entities: JSON metadata only in entities/
        2. File entities (class name contains "File" + has download_url):
           JSON metadata + actual file in blobs/

        Note: File entities are detected at runtime by:
        - Class name contains "File" (e.g., AsanaFileUnifiedChunk)
        - Has download_url attribute with value

    For file entities, the download_url in the JSON is rewritten to point to the blob:
        "download_url": "s3://{bucket}/{prefix}/collections/{readable_id}/blobs/{entity_id}.pdf"

    Operations:
        - INSERT/UPDATE: Write/overwrite entity JSON (and blob for files)
        - DELETE: Delete entity JSON (and blob for files)

    Event streaming is provided via S3 event notifications (s3:ObjectCreated:*, s3:ObjectRemoved:*).
    """

    def __init__(self):
        """Initialize S3 destination."""
        super().__init__()
        self.collection_id: UUID | None = None
        self.organization_id: UUID | None = None
        self.collection_readable_id: str | None = None  # For human-readable S3 paths
        self.sync_id: UUID | None = None  # For file retrieval from storage
        self.bucket_name: str | None = None
        self.bucket_prefix: str = "airweave-outbound/"
        self.session: aioboto3.Session | None = None
        # Store connection config for creating clients
        self._endpoint_url: str | None = None
        self._access_key_id: str | None = None
        self._secret_access_key: str | None = None
        self._region: str = "us-east-1"
        self._use_ssl: bool = True
        # Track total entities inserted
        self.entities_inserted_count: int = 0

    @classmethod
    async def create(
        cls,
        credentials: S3AuthConfig,
        config: Optional[dict],
        collection_id: UUID,
        organization_id: Optional[UUID] = None,
        logger: Optional[ContextualLogger] = None,
        collection_readable_id: Optional[str] = None,
        sync_id: Optional[UUID] = None,  # For file retrieval from storage
    ) -> "S3Destination":
        """Create and configure S3 destination (matches source pattern).

        Args:
            credentials: S3AuthConfig with all S3 configuration (auth + parameters)
            config: Unused (kept for interface consistency with sources)
            collection_id: Collection UUID
            organization_id: Organization UUID
            logger: Logger instance
            collection_readable_id: Human-readable collection ID for S3 paths
            sync_id: Sync ID for file retrieval from storage

        Returns:
            Configured S3Destination instance
        """
        if aioboto3 is None:
            raise ImportError("aioboto3 is required for S3 destination")

        instance = cls()
        instance.set_logger(logger or default_logger)
        instance.collection_id = collection_id
        instance.organization_id = organization_id
        instance.collection_readable_id = collection_readable_id or str(collection_id)
        instance.sync_id = sync_id

        # Extract all fields from credentials (contains both auth and config)
        instance.bucket_name = credentials.bucket_name
        instance.bucket_prefix = credentials.bucket_prefix
        instance._region = credentials.aws_region
        instance._endpoint_url = credentials.endpoint_url
        instance._use_ssl = credentials.use_ssl
        instance._access_key_id = credentials.aws_access_key_id
        instance._secret_access_key = credentials.aws_secret_access_key

        # Initialize session
        instance.session = aioboto3.Session()
        await instance._test_connection()

        return instance

    async def _test_connection(self) -> None:
        """Test S3 connection by checking if bucket exists."""
        try:
            async with self.session.client(
                "s3",
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                region_name=self._region,
                use_ssl=self._use_ssl,
            ) as s3:
                await s3.head_bucket(Bucket=self.bucket_name)

            self.logger.info(
                f"Connected to S3 bucket: {self.bucket_name} "
                f"(endpoint: {self._endpoint_url or 'AWS S3'})"
            )
        except NoCredentialsError as e:
            raise ConnectionError(f"S3 credentials not configured: {e}") from e
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                raise ConnectionError(f"S3 bucket '{self.bucket_name}' does not exist") from e
            elif error_code == "403":
                raise ConnectionError(f"Access denied to S3 bucket '{self.bucket_name}'") from e
            raise ConnectionError(f"Failed to connect to S3: {e}") from e

    async def setup_collection(self, vector_size: int | None = None) -> None:
        """No-op for S3 - paths created on write."""
        pass

    def _get_file_extension(self, mime_type: Optional[str], filename: Optional[str] = None) -> str:
        """Get file extension from mime_type or filename.

        Args:
            mime_type: MIME type of the file
            filename: Optional filename to extract extension from

        Returns:
            File extension with leading dot (e.g., ".pdf", ".png")
        """
        # Try to get extension from filename first
        if filename:
            import os

            _, ext = os.path.splitext(filename)
            if ext:
                return ext

        # Common MIME type mappings
        mime_to_ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/svg+xml": ".svg",
            "application/pdf": ".pdf",
            "application/json": ".json",
            "application/xml": ".xml",
            "text/plain": ".txt",
            "text/html": ".html",
            "text/csv": ".csv",
            "application/zip": ".zip",
            "application/x-zip-compressed": ".zip",
            "application/vnd.ms-excel": ".xls",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        }

        if mime_type:
            return mime_to_ext.get(mime_type, ".bin")

        return ".bin"

    async def insert(self, entity) -> None:
        """Single entity insert - delegates to bulk_insert."""
        await self.bulk_insert([entity])

    async def bulk_insert(self, entities: list) -> None:
        """Write entities as individual JSON files to S3.

        Handles two types:
        1. Regular entities: JSON metadata only
        2. File entities: JSON metadata + actual blob file

        INSERT and UPDATE both use PUT (overwrite).
        """
        if not entities:
            return

        try:
            async with self.session.client(
                "s3",
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                region_name=self._region,
                use_ssl=self._use_ssl,
            ) as s3:
                for entity in entities:
                    entity_id = entity.entity_id
                    collection_path = self.collection_readable_id
                    base_path = f"{self.bucket_prefix}collections/{collection_path}"

                    # Check if this is a file entity (runtime unified chunks)
                    # File entities have "File" in class name and have download_url
                    entity_class_name = entity.__class__.__name__
                    has_download_url = hasattr(entity, "download_url") and entity.download_url
                    is_file_entity = "File" in entity_class_name and has_download_url

                    if is_file_entity:
                        # Handle file entity: upload blob + metadata
                        await self._write_file_entity(s3, entity, base_path, entity_id)
                    else:
                        # Handle regular entity: JSON only
                        await self._write_regular_entity(s3, entity, base_path, entity_id)

            # Update counter
            self.entities_inserted_count += len(entities)

            self.logger.info(
                f"Wrote {len(entities)} entities to S3 (total: {self.entities_inserted_count})"
            )
        except Exception as e:
            self.logger.error(f"Failed to write entities to S3: {e}", exc_info=True)
            raise

    async def _write_regular_entity(self, s3, entity, base_path: str, entity_id: str) -> None:
        """Write regular entity as JSON file."""
        # Get entity data as dict (UUIDs->strings, datetimes->ISO)
        entity_data = entity.model_dump(mode="json", exclude_none=True)
        key = f"{base_path}/entities/{entity_id}.json"

        await s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(entity_data, default=self._json_serializer).encode("utf-8"),
            ContentType="application/json",
            Metadata={
                "collection_id": str(self.collection_id),
                "entity_id": str(entity_id),
                "entity_type": entity.__class__.__name__,
            },
        )

    async def _write_file_entity(self, s3, entity, base_path: str, entity_id: str) -> None:
        """Write file entity: blob + metadata JSON.

        Uploads the actual file content to /blobs/ and metadata to /entities/.
        Rewrites download_url to point to the blob in S3.

        Works with file entities that have:
        - local_path field
        - mime_type and name attributes
        """
        # Get file metadata
        mime_type = getattr(entity, "mime_type", None)
        filename = getattr(entity, "name", None)

        # Determine file extension
        extension = self._get_file_extension(mime_type, filename)

        # Upload blob if we have sync_id and file info
        blob_key = None
        if self.sync_id and filename:
            try:
                # Use sync_file_manager to get file content
                file_content = await sync_file_manager.get_file_content(
                    entity_id=entity_id,
                    sync_id=self.sync_id,
                    filename=filename,
                    logger=self.logger,
                )

                if file_content is not None:
                    # Upload actual file content
                    blob_key = f"{base_path}/blobs/{entity_id}{extension}"

                    await s3.put_object(
                        Bucket=self.bucket_name,
                        Key=blob_key,
                        Body=file_content,
                        ContentType=mime_type or "application/octet-stream",
                        Metadata={
                            "collection_id": str(self.collection_id),
                            "entity_id": str(entity_id),
                            "entity_type": entity.__class__.__name__,
                        },
                        # Use S3 tags for easier querying/deletion
                        Tagging=f"entity_id={entity_id}&sync_id={self.sync_id}",
                    )

                    self.logger.debug(f"Uploaded blob for entity {entity_id}: {blob_key}")
                else:
                    self.logger.debug(f"No file content available for {entity_id}")
            except Exception as e:
                self.logger.warning(f"Failed to upload blob for {entity_id}: {e}")
                blob_key = None

        # Prepare entity metadata
        # Get entity data as dict (UUIDs->strings, datetimes->ISO)
        entity_data = entity.model_dump(mode="json", exclude_none=True)

        # Rewrite download_url to point to blob if we uploaded it
        if blob_key:
            s3_url = f"s3://{self.bucket_name}/{blob_key}"
            entity_data["download_url"] = s3_url
            self.logger.debug(f"Rewrote download_url for {entity_id} to {s3_url}")

        # Upload metadata JSON
        metadata_key = f"{base_path}/entities/{entity_id}.json"
        await s3.put_object(
            Bucket=self.bucket_name,
            Key=metadata_key,
            Body=json.dumps(entity_data, default=self._json_serializer).encode("utf-8"),
            ContentType="application/json",
            Metadata={
                "collection_id": str(self.collection_id),
                "entity_id": str(entity_id),
                "entity_type": entity.__class__.__name__,
                "has_blob": "true" if blob_key else "false",
            },
        )

    async def delete(self, db_entity_id: UUID) -> None:
        """Delete entity file from S3.

        Note: db_entity_id is our internal UUID, but we need the source entity_id
        for the S3 key. This method has limitations - use bulk_delete when possible.
        """
        # We can't construct the S3 key from db_entity_id alone
        # Log warning but don't fail - bulk_delete is the primary delete path
        self.logger.warning(
            f"Single entity delete called with db_entity_id {db_entity_id}. "
            "Cannot delete from S3 without source entity_id. Use bulk_delete instead."
        )

    async def bulk_delete(self, entity_ids: list[str], sync_id: UUID) -> None:
        """Delete entity files from S3.

        Deletes both entity JSON and associated blobs (if they exist).

        Args:
            entity_ids: List of source entity IDs (used as S3 keys)
            sync_id: Sync ID (unused for S3)
        """
        if not entity_ids:
            return

        try:
            async with self.session.client(
                "s3",
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                region_name=self._region,
                use_ssl=self._use_ssl,
            ) as s3:
                collection_path = self.collection_readable_id
                base_path = f"{self.bucket_prefix}collections/{collection_path}"

                for entity_id in entity_ids:
                    # Delete entity JSON
                    entity_key = f"{base_path}/entities/{entity_id}.json"
                    await s3.delete_object(Bucket=self.bucket_name, Key=entity_key)

                    # Try to delete associated blob (if it exists)
                    # List all blobs with this entity_id prefix to handle any extension
                    blob_prefix = f"{base_path}/blobs/{entity_id}"

                    try:
                        response = await s3.list_objects_v2(
                            Bucket=self.bucket_name,
                            Prefix=blob_prefix,
                            MaxKeys=10,  # Should only be 1, but be safe
                        )

                        if "Contents" in response:
                            for obj in response["Contents"]:
                                await s3.delete_object(Bucket=self.bucket_name, Key=obj["Key"])
                                self.logger.debug(f"Deleted blob: {obj['Key']}")
                    except Exception as e:
                        # Non-fatal: blob might not exist
                        self.logger.debug(f"No blob found for entity {entity_id}: {e}")

            self.logger.info(f"Deleted {len(entity_ids)} entities from S3")
        except Exception as e:
            self.logger.error(f"Failed to delete entities from S3: {e}", exc_info=True)
            raise

    async def bulk_delete_by_parent_id(self, parent_id: str, sync_id: UUID) -> None:
        """Delete entities by parent using S3 prefix listing.

        Lists all objects with parent_id prefix and deletes them (entities + blobs).
        This is less efficient but necessary for hierarchical deletions.
        """
        try:
            async with self.session.client(
                "s3",
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                region_name=self._region,
                use_ssl=self._use_ssl,
            ) as s3:
                collection_path = self.collection_readable_id
                base_path = f"{self.bucket_prefix}collections/{collection_path}"

                total_deleted = 0

                # Delete from both entities/ and blobs/ with parent_id prefix
                for folder in ["entities", "blobs"]:
                    prefix = f"{base_path}/{folder}/{parent_id}"

                    paginator = s3.get_paginator("list_objects_v2")
                    folder_deleted = 0

                    async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                        if "Contents" not in page:
                            continue

                        # Batch delete (up to 1000 objects per request)
                        objects_to_delete = [{"Key": obj["Key"]} for obj in page["Contents"]]

                        if objects_to_delete:
                            await s3.delete_objects(
                                Bucket=self.bucket_name, Delete={"Objects": objects_to_delete}
                            )
                            folder_deleted += len(objects_to_delete)

                    if folder_deleted > 0:
                        self.logger.debug(f"Deleted {folder_deleted} objects from {folder}/")
                    total_deleted += folder_deleted

            msg = f"Deleted {total_deleted} objects with parent_id '{parent_id}' from S3"
            self.logger.info(msg)
        except Exception as e:
            self.logger.error(f"Failed to delete entities by parent_id from S3: {e}", exc_info=True)
            raise

    async def delete_by_sync_id(self, sync_id: UUID) -> None:
        """Delete all entities for a given sync.

        Note: S3 doesn't store sync_id metadata on individual files.
        This would require listing all files and checking metadata or using a separate index.
        For now, this is a no-op. Consider using collection-level deletion instead.
        """
        self.logger.warning(
            f"delete_by_sync_id called for sync {sync_id}. "
            "S3 state mirroring doesn't support deletion by sync_id. "
            "Use delete entire collection instead."
        )
        pass

    async def search(self, query_vector: list[float]) -> None:
        """S3 doesn't support search."""
        raise NotImplementedError("S3 destination doesn't support search")

    async def has_keyword_index(self) -> bool:
        """S3 doesn't have keyword index."""
        return False

    @staticmethod
    def _json_serializer(obj):
        """JSON serializer for special types."""
        from datetime import datetime

        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        return str(obj)
