"""S3 destination using IAM role assumption for cross-account access.

Writes entities in ARF-compatible format to customer S3 buckets using
temporary credentials obtained via STS AssumeRole.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional
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

if TYPE_CHECKING:
    from airweave.platform.entities._base import BaseEntity


@destination("S3", "s3", auth_config_class=S3AuthConfig, supports_vector=False)
class S3Destination(BaseDestination):
    """S3 destination writing ARF-compatible format via cross-account IAM role assumption.

    Uses STS AssumeRole to obtain temporary credentials for writing to customer
    S3 buckets without requiring long-lived access keys.

    Data Organization (ARF-compatible):
        {bucket}/{prefix}/raw/{sync_id}/
        ├── manifest.json                    # Sync metadata
        ├── entities/
        │   └── {safe_entity_id}.json        # Entity with class metadata
        └── files/
            └── {entity_id}_{name}.{ext}     # File attachments

    Entity JSON structure (matching ArfService._serialize_entity):
        {
            "__entity_class__": "SlackMessageEntity",
            "__entity_module__": "airweave.platform.entities.slack",
            "__captured_at__": "2026-01-12T...",
            "entity_id": "...",
            ... entity fields
        }
    """

    from airweave.platform.sync.pipeline import ProcessingRequirement

    processing_requirement = ProcessingRequirement.RAW

    def __init__(self):
        """Initialize S3 destination."""
        super().__init__()
        self.collection_id: UUID | None = None
        self.organization_id: UUID | None = None
        self.collection_readable_id: str | None = None
        self.sync_id: UUID | None = None
        self.bucket_name: str | None = None
        self.bucket_prefix: str = "airweave/"
        self._region: str = "us-east-1"
        self._role_arn: str | None = None
        self._external_id: str | None = None
        # IAM user credentials (from Key Vault)
        self._iam_access_key_id: str | None = None
        self._iam_secret_access_key: str | None = None
        # Cached temporary credentials (from AssumeRole)
        self._temp_credentials: Dict[str, Any] | None = None
        self._credentials_expiry: datetime | None = None
        # Track entities
        self.entities_inserted_count: int = 0
        self._manifest_written: bool = False

    @classmethod
    async def create(
        cls,
        credentials: S3AuthConfig,
        config: Optional[dict],
        collection_id: UUID,
        organization_id: Optional[UUID] = None,
        logger: Optional[ContextualLogger] = None,
        collection_readable_id: Optional[str] = None,
        sync_id: Optional[UUID] = None,
    ) -> "S3Destination":
        """Create and configure S3 destination.

        Args:
            credentials: S3AuthConfig with role ARN and bucket configuration
            config: Unused (kept for interface consistency)
            collection_id: Collection UUID
            organization_id: Organization UUID
            logger: Logger instance
            collection_readable_id: Human-readable collection ID
            sync_id: Sync ID for ARF paths

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

        # Store configuration
        instance.bucket_name = credentials.bucket_name
        # Normalize bucket_prefix to ensure trailing slash
        prefix = credentials.bucket_prefix or ""
        instance.bucket_prefix = f"{prefix.rstrip('/')}/" if prefix else ""
        instance._region = credentials.aws_region
        instance._role_arn = credentials.role_arn
        instance._external_id = credentials.external_id

        # Load IAM user credentials from Key Vault
        await instance._load_iam_credentials()

        # Validate connection by assuming role and checking bucket
        await instance._test_connection()

        return instance

    # =========================================================================
    # Credential Management
    # =========================================================================

    async def _load_iam_credentials(self) -> None:
        """Load IAM user credentials from Azure Key Vault."""
        try:
            from airweave.core.secrets import secret_client

            if secret_client is None:
                raise ImportError("Azure Key Vault secret client not available")

            # Load credentials from Key Vault
            # TODO: Move this to DestinationFactory
            access_key_id = await secret_client.get_secret("aws-s3-destination-access-key-id")
            secret_access_key = await secret_client.get_secret(
                "aws-s3-destination-secret-access-key"
            )

            if not access_key_id or not secret_access_key:
                raise ValueError(
                    "AWS S3 destination credentials not found in Key Vault. "
                    "Ensure 'aws-s3-destination-access-key-id' and "
                    "'aws-s3-destination-secret-access-key' are set."
                )

            self._iam_access_key_id = access_key_id.value
            self._iam_secret_access_key = secret_access_key.value

            self.logger.debug("Loaded IAM user credentials from Key Vault")
        except Exception as e:
            raise ConnectionError(f"Failed to load AWS credentials from Key Vault: {e}") from e

    async def _assume_role(self) -> Dict[str, Any]:
        """Assume customer IAM role using IAM user credentials.

        Returns:
            Dict with AccessKeyId, SecretAccessKey, SessionToken
        """
        if not self._iam_access_key_id or not self._iam_secret_access_key:
            raise ValueError("IAM user credentials not loaded")

        # Create STS client with IAM user credentials
        session = aioboto3.Session(
            aws_access_key_id=self._iam_access_key_id,
            aws_secret_access_key=self._iam_secret_access_key,
        )
        async with session.client("sts", region_name=self._region) as sts:
            response = await sts.assume_role(
                RoleArn=self._role_arn,
                ExternalId=self._external_id,
                RoleSessionName=f"airweave-sync-{self.sync_id or 'test'}",
                DurationSeconds=3600,  # 1 hour
            )

        creds = response["Credentials"]
        self._temp_credentials = {
            "aws_access_key_id": creds["AccessKeyId"],
            "aws_secret_access_key": creds["SecretAccessKey"],
            "aws_session_token": creds["SessionToken"],
        }
        self._credentials_expiry = creds["Expiration"]

        self.logger.debug(
            f"Assumed role {self._role_arn}, credentials expire at {self._credentials_expiry}"
        )
        return self._temp_credentials

    async def _get_credentials(self) -> Dict[str, Any]:
        """Get temporary credentials, refreshing if needed.

        Returns:
            Dict with temporary credential parameters for boto3 client.
        """
        # Check if we need to refresh (5 min buffer before expiry)
        if self._temp_credentials and self._credentials_expiry:
            buffer = datetime.now(timezone.utc).timestamp() + 300
            if self._credentials_expiry.timestamp() > buffer:
                return self._temp_credentials

        return await self._assume_role()

    async def _get_s3_client(self):
        """Get S3 client with temporary credentials.

        Returns:
            Async context manager for S3 client.
        """
        creds = await self._get_credentials()
        session = aioboto3.Session()
        return session.client(
            "s3",
            region_name=self._region,
            aws_access_key_id=creds["aws_access_key_id"],
            aws_secret_access_key=creds["aws_secret_access_key"],
            aws_session_token=creds["aws_session_token"],
        )

    async def _test_connection(self) -> None:
        """Test S3 connection by assuming role and checking bucket access."""
        try:
            async with await self._get_s3_client() as s3:
                await s3.head_bucket(Bucket=self.bucket_name)

            self.logger.info(
                f"Connected to S3 bucket: {self.bucket_name} via role {self._role_arn}"
            )
        except NoCredentialsError as e:
            raise ConnectionError(f"Failed to assume role {self._role_arn}: {e}") from e
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                raise ConnectionError(f"S3 bucket '{self.bucket_name}' does not exist") from e
            elif error_code == "403":
                raise ConnectionError(
                    f"Access denied to S3 bucket '{self.bucket_name}'. "
                    f"Check IAM role permissions for {self._role_arn}"
                ) from e
            elif error_code == "AccessDenied":
                raise ConnectionError(
                    f"Cannot assume role {self._role_arn}. Check trust policy and external ID."
                ) from e
            raise ConnectionError(f"Failed to connect to S3: {e}") from e

    async def setup_collection(self, vector_size: int | None = None) -> None:
        """No-op for S3 - paths created on write."""
        pass

    # =========================================================================
    # ARF-Compatible Path Helpers
    # =========================================================================

    def _sync_path(self) -> str:
        """Get base path for sync's ARF data."""
        return f"{self.bucket_prefix}raw/{self.sync_id}"

    def _manifest_path(self) -> str:
        """Get manifest path."""
        return f"{self._sync_path()}/manifest.json"

    def _entity_path(self, entity_id: str) -> str:
        """Get path for an entity file."""
        safe_id = self._safe_filename(entity_id)
        return f"{self._sync_path()}/entities/{safe_id}.json"

    def _file_path(self, entity_id: str, filename: str = "") -> str:
        """Get path for an entity's attached file."""
        safe_id = self._safe_filename(entity_id)
        if filename:
            safe_name = self._safe_filename(Path(filename).stem)
            ext = Path(filename).suffix or ""
            return f"{self._sync_path()}/files/{safe_id}_{safe_name}{ext}"
        return f"{self._sync_path()}/files/{safe_id}"

    def _safe_filename(self, value: str, max_length: int = 200) -> str:
        """Convert entity_id or filename to safe storage path.

        Uses hash suffix for long/complex IDs to ensure uniqueness.
        """
        safe = re.sub(r'[/\\:*?"<>|]', "_", str(value))
        safe = re.sub(r"_+", "_", safe).strip("_")

        if len(safe) > max_length or safe != value:
            prefix = safe[:50] if len(safe) > 50 else safe
            hash_suffix = hashlib.md5(value.encode()).hexdigest()[:12]
            safe = f"{prefix}_{hash_suffix}"

        return safe[:max_length]

    # =========================================================================
    # ARF-Compatible Entity Serialization
    # =========================================================================

    def _serialize_entity(self, entity: "BaseEntity") -> Dict[str, Any]:
        """Serialize entity with class info for reconstruction (ARF format)."""
        entity_dict = entity.model_dump(mode="json")
        entity_dict["__entity_class__"] = entity.__class__.__name__
        entity_dict["__entity_module__"] = entity.__class__.__module__
        entity_dict["__captured_at__"] = datetime.now(timezone.utc).isoformat()
        return entity_dict

    def _is_file_entity(self, entity: "BaseEntity") -> bool:
        """Check if entity is a FileEntity or subclass."""
        for cls in entity.__class__.__mro__:
            if cls.__name__ == "FileEntity":
                return True
        return False

    # =========================================================================
    # Manifest Management
    # =========================================================================

    async def _ensure_manifest(self, s3) -> None:
        """Ensure manifest exists for this sync (called once per sync)."""
        if self._manifest_written:
            return

        manifest_path = self._manifest_path()
        now = datetime.now(timezone.utc).isoformat()

        manifest = {
            "sync_id": str(self.sync_id),
            "collection_id": str(self.collection_id),
            "collection_readable_id": self.collection_readable_id,
            "organization_id": str(self.organization_id) if self.organization_id else None,
            "created_at": now,
            "updated_at": now,
            "format": "arf",
            "format_version": "1.0",
        }

        await s3.put_object(
            Bucket=self.bucket_name,
            Key=manifest_path,
            Body=json.dumps(manifest, indent=2).encode("utf-8"),
            ContentType="application/json",
        )

        self._manifest_written = True
        self.logger.debug(f"Wrote manifest to {manifest_path}")

    # =========================================================================
    # Core Operations
    # =========================================================================

    async def bulk_insert(self, entities: list) -> None:
        """Write entities in ARF-compatible format to S3.

        Args:
            entities: List of entities to write
        """
        if not entities:
            return

        try:
            async with await self._get_s3_client() as s3:
                # Ensure manifest exists
                await self._ensure_manifest(s3)

                for entity in entities:
                    entity_id = str(entity.entity_id)

                    # Handle file entities (with attached files)
                    if self._is_file_entity(entity) and hasattr(entity, "local_path"):
                        await self._write_file_entity(s3, entity, entity_id)
                    else:
                        await self._write_entity(s3, entity, entity_id)

            self.entities_inserted_count += len(entities)
            self.logger.info(
                f"Wrote {len(entities)} entities to S3 (total: {self.entities_inserted_count})"
            )
        except Exception as e:
            self.logger.error(f"Failed to write entities to S3: {e}", exc_info=True)
            raise

    async def _write_entity(self, s3, entity: "BaseEntity", entity_id: str) -> None:
        """Write a single entity in ARF format."""
        entity_path = self._entity_path(entity_id)
        entity_data = self._serialize_entity(entity)

        await s3.put_object(
            Bucket=self.bucket_name,
            Key=entity_path,
            Body=json.dumps(entity_data, indent=2, default=str).encode("utf-8"),
            ContentType="application/json",
        )

    async def _write_file_entity(self, s3, entity: "BaseEntity", entity_id: str) -> None:
        """Write file entity: file attachment + entity JSON."""
        local_path = getattr(entity, "local_path", None)
        filename = getattr(entity, "name", None) or Path(local_path).name if local_path else None

        stored_file_path = None

        # Upload file if it exists
        if local_path and Path(local_path).exists() and filename:
            try:
                file_path = self._file_path(entity_id, filename)
                with open(local_path, "rb") as f:
                    file_content = f.read()

                mime_type = getattr(entity, "mime_type", "application/octet-stream")
                await s3.put_object(
                    Bucket=self.bucket_name,
                    Key=file_path,
                    Body=file_content,
                    ContentType=mime_type,
                )
                stored_file_path = file_path
                self.logger.debug(f"Uploaded file for entity {entity_id}: {file_path}")
            except Exception as e:
                self.logger.warning(f"Could not store file for {entity_id}: {e}")

        # Also try sync_file_manager if local_path didn't work
        if not stored_file_path and self.sync_id and filename:
            try:
                file_content = await sync_file_manager.get_file_content(
                    entity_id=entity_id,
                    sync_id=self.sync_id,
                    filename=filename,
                    logger=self.logger,
                )
                if file_content is not None:
                    file_path = self._file_path(entity_id, filename)
                    mime_type = getattr(entity, "mime_type", "application/octet-stream")
                    await s3.put_object(
                        Bucket=self.bucket_name,
                        Key=file_path,
                        Body=file_content,
                        ContentType=mime_type,
                    )
                    stored_file_path = file_path
            except Exception as e:
                self.logger.warning(
                    f"Failed to upload file via sync_file_manager for {entity_id}: {e}"
                )

        # Write entity JSON with file reference
        entity_path = self._entity_path(entity_id)
        entity_data = self._serialize_entity(entity)
        if stored_file_path:
            entity_data["__stored_file__"] = stored_file_path

        await s3.put_object(
            Bucket=self.bucket_name,
            Key=entity_path,
            Body=json.dumps(entity_data, indent=2, default=str).encode("utf-8"),
            ContentType="application/json",
        )

    async def bulk_delete_by_parent_ids(self, parent_ids: list[str], sync_id: UUID) -> None:
        """Delete entities by parent IDs.

        Args:
            parent_ids: List of parent entity IDs to delete
            sync_id: Sync ID (for path construction)
        """
        if not parent_ids:
            return

        try:
            async with await self._get_s3_client() as s3:
                total_deleted = 0

                for parent_id in parent_ids:
                    # Delete entity JSON
                    entity_path = self._entity_path(parent_id)
                    try:
                        await s3.delete_object(Bucket=self.bucket_name, Key=entity_path)
                        total_deleted += 1
                    except Exception:
                        pass

                    # Delete any associated files with parent_id prefix
                    file_prefix = f"{self._sync_path()}/files/{self._safe_filename(parent_id)}"
                    paginator = s3.get_paginator("list_objects_v2")
                    async for page in paginator.paginate(
                        Bucket=self.bucket_name, Prefix=file_prefix
                    ):
                        if "Contents" not in page:
                            continue
                        objects_to_delete = [{"Key": obj["Key"]} for obj in page["Contents"]]
                        if objects_to_delete:
                            await s3.delete_objects(
                                Bucket=self.bucket_name, Delete={"Objects": objects_to_delete}
                            )
                            total_deleted += len(objects_to_delete)

            if total_deleted > 0:
                self.logger.info(
                    f"Deleted {total_deleted} objects for {len(parent_ids)} parents from S3"
                )
        except Exception as e:
            self.logger.error(
                f"Failed to delete entities by parent_ids from S3: {e}", exc_info=True
            )
            raise

    async def delete_by_sync_id(self, sync_id: UUID) -> None:
        """Delete all entities for a given sync."""
        self.logger.warning(
            f"delete_by_sync_id called for sync {sync_id}. "
            "Use delete entire sync directory instead."
        )

    async def search(self, query_vector: list[float]) -> None:
        """S3 doesn't support search."""
        raise NotImplementedError("S3 destination doesn't support search")
