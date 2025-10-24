"""Jira entity schemas.

Simplified entity schemas for Jira Projects and Issues to demonstrate
Airweave's capabilities with minimal complexity.
"""

from datetime import datetime
from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base_legacy import ChunkEntity


class JiraProjectEntity(ChunkEntity):
    """Schema for a Jira Project."""

    project_key: str = AirweaveField(
        ..., description="Unique key of the project (e.g., 'PROJ').", embeddable=True
    )
    name: Optional[str] = AirweaveField(None, description="Name of the project.", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Description of the project.", embeddable=True
    )


class JiraIssueEntity(ChunkEntity):
    """Schema for a Jira Issue."""

    issue_key: str = AirweaveField(
        ..., description="Jira key for the issue (e.g. 'PROJ-123').", embeddable=True
    )
    summary: Optional[str] = AirweaveField(
        None, description="Short summary field of the issue.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Detailed description of the issue.", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Current workflow status of the issue.", embeddable=True
    )
    issue_type: Optional[str] = AirweaveField(
        None, description="Type of the issue (bug, task, story, etc.).", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the issue was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the issue was last updated.", is_updated_at=True
    )
