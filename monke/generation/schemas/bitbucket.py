"""Bitbucket-specific generation schema."""

from datetime import datetime
from pydantic import BaseModel, Field


class BitbucketArtifact(BaseModel):
    """Schema for Bitbucket file generation."""

    filename: str = Field(description="File name without extension")
    content: str = Field(description="File content (code)")
    file_type: str = Field(description="File extension (py, js, md)", default="py")
    created_at: datetime = Field(default_factory=datetime.now)
