"""Jira entity schemas.

Simplified entity schemas for Jira Projects and Issues to demonstrate
Airweave's capabilities with minimal complexity.
"""

from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class JiraProjectEntity(BaseEntity):
    """Schema for a Jira Project.

    Reference:
        https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-projects/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (project-{id})
    # - breadcrumbs (empty - projects are top-level)
    # - name (from project name)
    # - created_at (None - projects don't have creation timestamp in API)
    # - updated_at (None - projects don't have update timestamp in API)

    # API fields
    project_key: str = AirweaveField(
        ..., description="Unique key of the project (e.g., 'PROJ').", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Description of the project.", embeddable=True
    )


class JiraIssueEntity(BaseEntity):
    """Schema for a Jira Issue.

    Reference:
        https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (issue-{id})
    # - breadcrumbs (project breadcrumb)
    # - name (from summary)
    # - created_at (from created timestamp)
    # - updated_at (from updated timestamp)

    # API fields
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
