"""Jira-specific generation schema."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class JiraCommentArtifact(BaseModel):
    """Schema for Jira comment generation."""

    body: str = Field(description="Comment body text")
    author_name: str = Field(description="Comment author display name", default="Test User")


class JiraIssueArtifact(BaseModel):
    """Schema for Jira issue generation with rich metadata."""

    summary: str = Field(description="Issue summary/title")
    description: str = Field(description="Issue description")
    issue_type: str = Field(
        description="Issue type (Task, Bug, Story, Epic)",
        default="Task"
    )

    # User assignments (will be set to actual users later)
    assignee_needed: bool = Field(
        description="Whether this issue should have an assignee",
        default=False
    )

    # Labels for categorization
    labels: List[str] = Field(
        description="Labels for issue categorization (2-4 labels)",
        default_factory=list
    )

    # Priority
    priority: str = Field(
        description="Issue priority (Highest, High, Medium, Low, Lowest)",
        default="Medium"
    )

    # Comments
    should_have_comments: bool = Field(
        description="Whether this issue should have comments",
        default=False
    )
    num_comments: int = Field(
        description="Number of comments to generate (if should_have_comments=True)",
        default=0
    )

    # Parent-child relationships
    is_subtask: bool = Field(
        description="Whether this should be a subtask of another issue",
        default=False
    )

    created_at: datetime = Field(default_factory=datetime.now)


class JiraEpicArtifact(BaseModel):
    """Schema for Jira epic generation."""

    summary: str = Field(description="Epic summary/title")
    description: str = Field(description="Epic description")
    labels: List[str] = Field(
        description="Epic labels",
        default_factory=list
    )


# Legacy alias for backwards compatibility
JiraArtifact = JiraIssueArtifact
