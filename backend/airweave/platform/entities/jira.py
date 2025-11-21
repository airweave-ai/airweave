"""Jira entity schemas.

Simplified entity schemas for Jira Projects and Issues to demonstrate
Airweave's capabilities with minimal complexity.
"""

from datetime import datetime
from typing import Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class JiraProjectEntity(BaseEntity):
    """Schema for a Jira Project.

    Reference:
        https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-projects/
    """

    project_id: str = AirweaveField(
        ..., description="Unique numeric identifier for the project.", is_entity_id=True
    )
    project_name: str = AirweaveField(
        ..., description="Display name of the project.", embeddable=True, is_name=True
    )
    project_key: str = AirweaveField(
        ..., description="Unique key of the project (e.g., 'PROJ').", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Description of the project.", embeddable=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="Link to the project in Jira.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """UI link for the Jira project."""
        return self.web_url_value or ""


class JiraIssueEntity(BaseEntity):
    """Schema for a Jira Issue.

    Reference:
        https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/
    """

    issue_id: str = AirweaveField(
        ..., description="Unique identifier for the issue.", is_entity_id=True
    )
    issue_key: str = AirweaveField(
        ..., description="Jira key for the issue (e.g. 'PROJ-123').", embeddable=True
    )
    summary: str = AirweaveField(
        ..., description="Short summary field of the issue.", embeddable=True, is_name=True
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
    project_key: str = AirweaveField(
        ..., description="Key of the project that owns this issue.", embeddable=True
    )
    created_time: datetime = AirweaveField(
        ..., description="Timestamp when the issue was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="Timestamp when the issue was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="Link to the issue in Jira.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """UI link for the Jira issue."""
        return self.web_url_value or ""
