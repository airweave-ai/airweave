"""Jira-specific generation schema."""

from datetime import datetime
from pydantic import BaseModel, Field


class JiraArtifact(BaseModel):
    """Schema for Jira issue generation."""

    summary: str = Field(description="Issue summary/title")
    description: str = Field(description="Issue description")
    issue_type: str = Field(description="Issue type (Task, Bug, Story)", default="Task")
    created_at: datetime = Field(default_factory=datetime.now)
