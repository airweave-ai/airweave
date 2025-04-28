"""Jira entity schemas.

Simplified entity schemas for Jira Projects and Issues to demonstrate
Airweave's capabilities with minimal complexity.
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity


class JiraProjectEntity(ChunkEntity):
    """Schema for a Jira Project."""

    project_key: str = Field(..., description="Unique key of the project (e.g., 'PROJ').")
    name: Optional[str] = Field(None, description="Name of the project.")
    description: Optional[str] = Field(None, description="Description of the project.")


class JiraIssueEntity(ChunkEntity):
    """Schema for a Jira Issue."""

    issue_key: str = Field(..., description="Jira key for the issue (e.g. 'PROJ-123').")
    summary: Optional[str] = Field(None, description="Short summary field of the issue.")
    description: Optional[str] = Field(None, description="Detailed description of the issue.")
    status: Optional[str] = Field(None, description="Current workflow status of the issue.")
    issue_type: Optional[str] = Field(
        None, description="Type of the issue (bug, task, story, etc.)."
    )
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when the issue was created."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when the issue was last updated."
    )
