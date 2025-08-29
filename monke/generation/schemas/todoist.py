"""Todoist-specific generation schema."""

from datetime import datetime
from pydantic import BaseModel, Field


class TodoistArtifact(BaseModel):
    """Schema for Todoist task generation."""

    content: str = Field(description="Task content/title")
    description: str = Field(description="Task description")
    priority: int = Field(description="Task priority (1-4, where 4 is highest)", default=1)
    created_at: datetime = Field(default_factory=datetime.now)
