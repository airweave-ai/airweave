"""SigV4 Auth config."""

from typing import Optional

from pydantic import Field

from airweave.platform.configs._base import BaseConfig


class SigV4AuthConfig(BaseConfig):
    """Base SigV4 authentication configuration."""

    access_key_id: str = Field(
        ...,
        title="Access Key ID",
        description="The SigV4 access key ID (e.g. AWS_ACCESS_KEY_ID).",
    )
    secret_access_key: str = Field(
        ...,
        title="Secret Access Key",
        description="The SigV4 secret access key (e.g. AWS_SECRET_ACCESS_KEY).",
    )
    session_token: Optional[str] = Field(
        None,
        title="Session Token",
        description="Optional session token (e.g. AWS_SESSION_TOKEN).",
    )
    region: Optional[str] = Field(
        None,
        title="Region",
        description="The AWS region (e.g. us-east-1).",
    )
    endpoint_url: Optional[str] = Field(
        None,
        title="Endpoint URL",
        description="Custom endpoint for S3-compatible services.",
    )
    bucket: Optional[str] = Field(
        None,
        title="Bucket",
        description="The name of the bucket to access.",
    )
