"""AWS S3 source integration for Airweave.

Retrieves data from an S3 bucket via SigV4-signed API calls:
  - The bucket itself (as a top-level entity)
  - Objects within the bucket

Entity schemas are defined in entities/aws_s3.py.
"""

from typing import AsyncGenerator, Dict, Optional

import aioboto3

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs.sigv4 import SigV4AuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity
from airweave.platform.entities.aws_s3 import S3BucketEntity, S3ObjectEntity
from airweave.platform.sources._base import BaseSource


@source(
    "AWS S3",
    "aws_s3",
    AuthType.sigv4,
    "SigV4AuthConfig",
    labels=["File Storage"],
)
class S3Source(BaseSource):
    """AWS S3 source implementation.

    Yields:
      - S3BucketEntity for the configured bucket
      - S3ObjectEntity for each object in the bucket
    """

    @classmethod
    async def create(
        cls,
        *args,
        # access_key_id: str,
        # secret_access_key: str,
        # session_token: Optional[str],
        # region: str,
        # bucket: str,
    ) -> "S3Source":
        """Initialize the boto3 client with provided credentials and settings."""
        if len(args) == 1 and isinstance(args[0], SigV4AuthConfig):
            cfg: SigV4AuthConfig = args[0]
            access_key_id = cfg.access_key_id
            secret_access_key = cfg.secret_access_key
            session_token = cfg.session_token
            region = cfg.region
            bucket = cfg.bucket
        else:
            access_key_id, secret_access_key, session_token, region, bucket = args
        logger.info(f"AWS S3: \n {access_key_id} \n {secret_access_key} \n {region} \n {bucket}")
        bucket_name = bucket.removeprefix("s3://")
        if session_token and session_token == "":
            session = aioboto3.Session(
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name=region,
            )
        else:
            session = aioboto3.Session(
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name=region,
            )
        client = session.client("s3")
        instance = cls()
        instance.client = client
        instance.session = session
        instance.bucket = bucket_name
        return instance

    async def _generate_bucket_entity(self) -> S3BucketEntity:
        """Yield the bucket-level entity."""
        async with self.session.client("s3") as client:
            response = await client.get_bucket_location(Bucket=self.bucket)
        return S3BucketEntity(
            entity_id=self.bucket,
            bucket_name=self.bucket,
            location=response.get("LocationConstraint"),
        )

    async def _list_objects(self) -> AsyncGenerator[Dict, None]:
        """List all objects in the bucket with pagination."""
        continuation_token: Optional[str] = None
        while True:
            params = {"Bucket": self.bucket, "MaxKeys": 1000}
            if continuation_token:
                params["ContinuationToken"] = continuation_token

            async with self.session.client("s3") as client:
                data = await client.list_objects_v2(**params)

            for obj in data.get("Contents", []):
                logger.info(f"Found object: {obj['Key']}")
                yield obj

            if not data.get("IsTruncated"):
                break
            continuation_token = data.get("NextContinuationToken")

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all S3 entities: bucket + objects."""
        yield await self._generate_bucket_entity()

        async for obj in self._list_objects():
            try:
                entity = S3ObjectEntity(
                    entity_id=obj["Key"],
                    bucket_name=self.bucket,
                    key=obj["Key"],
                    size=obj.get("Size", 0),
                    last_modified=obj.get("LastModified"),
                    etag=obj.get("ETag"),
                    storage_class=obj.get("StorageClass"),
                )
                yield entity
            except Exception as e:
                logger.error(f"Failed to process object {obj.get('Key')}: {e}")
                continue
