"""Gmail-specific generation schema."""

from datetime import datetime
from pydantic import BaseModel, Field


class GmailArtifact(BaseModel):
    """Schema for Gmail email generation."""

    subject: str = Field(description="Email subject line")
    body: str = Field(description="Email body content")
    created_at: datetime = Field(default_factory=datetime.now)
