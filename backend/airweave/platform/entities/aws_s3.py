"""AWS S3 entity schemas.

Defines:
 - S3BucketEntity
 - S3ObjectEntity
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity


class S3BucketEntity(ChunkEntity):
    """Schema for an S3 bucket resource."""

    bucket_name: str = Field(..., description="Name of the S3 bucket.")
    location: Optional[str] = Field(
        None,
        description="Region or location constraint of the bucket.",
    )


class S3ObjectEntity(FileEntity):
    """Schema for an S3 object resource."""

    bucket_name: str = Field(..., description="Name of the containing bucket.")
    key: str = Field(..., description="Object key within the bucket.")
    size: Optional[int] = Field(None, description="Size of the object in bytes.")
    last_modified: Optional[datetime] = Field(
        None,
        description="Timestamp when the object was last modified.",
    )
    etag: Optional[str] = Field(None, description="ETag hash of the object.")
    storage_class: Optional[str] = Field(
        None,
        description="Storage class (e.g., STANDARD, GLACIER).",
    )

    def model_dump(self, *args, **kwargs) -> dict[str, Any]:
        """Override model_dump to stringify size."""
        data = super().model_dump(*args, **kwargs)
        if data.get("size") is not None:
            data["size"] = str(data["size"])
        return data
