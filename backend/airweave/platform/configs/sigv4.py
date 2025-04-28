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
        description="Optional session token. In case you cannot continue, write '' in this field.",
    )
    region: str = Field(
        ...,
        title="Region",
        description="The AWS region (e.g. us-east-1).",
    )
    bucket: str = Field(
        ...,
        title="Bucket",
        description="The name of the bucket to access.",
    )
