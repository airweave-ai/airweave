"""Linear entity schemas."""

from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


class LinearIssueEntity(BaseEntity):
    """Schema for Linear issue entities.

    This entity represents an issue from Linear, containing all relevant
    metadata and content from the Linear API.

    Reference:
        https://developers.linear.app/docs/graphql/working-with-the-graphql-api
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the Linear issue ID)
    # - breadcrumbs (team and optionally project breadcrumbs)
    # - name (from title)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    identifier: str = AirweaveField(
        ..., description="The unique identifier of the issue (e.g., 'ENG-123')", embeddable=True
    )
    title: str = AirweaveField(..., description="The title of the issue", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="The description/content of the issue", embeddable=True
    )
    priority: Optional[int] = AirweaveField(
        None, description="The priority level of the issue", embeddable=False
    )
    state: Optional[str] = AirweaveField(
        None, description="The current state/status name of the issue", embeddable=True
    )
    completed_at: Optional[Any] = AirweaveField(
        None, description="When the issue was completed, if applicable", embeddable=False
    )
    due_date: Optional[str] = AirweaveField(
        None, description="The due date for the issue, if set", embeddable=True
    )
    team_id: Optional[str] = AirweaveField(
        None, description="ID of the team this issue belongs to", embeddable=False
    )
    team_name: Optional[str] = AirweaveField(
        None, description="Name of the team this issue belongs to", embeddable=True
    )
    project_id: Optional[str] = AirweaveField(
        None, description="ID of the project this issue belongs to, if any", embeddable=False
    )
    project_name: Optional[str] = AirweaveField(
        None, description="Name of the project this issue belongs to, if any", embeddable=True
    )
    assignee: Optional[str] = AirweaveField(
        None, description="Name of the user assigned to this issue, if any", embeddable=True
    )
    url: Optional[str] = AirweaveField(
        None, description="URL to view the issue in Linear", embeddable=False
    )


class LinearAttachmentEntity(FileEntity):
    """Schema for Linear attachment entities.

    Attachments in Linear allow linking external resources to issues.

    Reference:
        https://developers.linear.app/docs/graphql/working-with-the-graphql-api
    """

    # Base fields are inherited from BaseEntity:
    # - entity_id (the attachment ID)
    # - breadcrumbs (team, project, and issue breadcrumbs)
    # - name (from title or filename)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # File fields are inherited from FileEntity:
    # - url (download URL)
    # - size (file size in bytes, if available)
    # - file_type (determined from name/mime_type)
    # - mime_type
    # - local_path (set after download)

    # API fields (Linear-specific)
    issue_id: str = AirweaveField(
        ..., description="ID of the issue this attachment belongs to", embeddable=False
    )
    issue_identifier: str = AirweaveField(
        ..., description="Identifier of the issue (e.g., 'ENG-123')", embeddable=True
    )
    title: Optional[str] = AirweaveField(
        None, description="Title of the attachment", embeddable=True
    )
    subtitle: Optional[str] = AirweaveField(
        None, description="Subtitle of the attachment", embeddable=True
    )
    source: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Source information about the attachment", embeddable=False
    )


class LinearProjectEntity(BaseEntity):
    """Schema for Linear project entities.

    This entity represents a project from Linear, containing all relevant
    metadata and content from the Linear API.

    Reference:
        https://developers.linear.app/docs/graphql/working-with-the-graphql-api
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the Linear project ID)
    # - breadcrumbs (team breadcrumbs)
    # - name (from project name)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    slug_id: str = AirweaveField(..., description="The project's unique URL slug", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="The project's description", embeddable=True
    )
    priority: Optional[int] = AirweaveField(
        None, description="The priority level of the project", embeddable=False
    )
    state: Optional[str] = AirweaveField(
        None, description="The current state/status name of the project", embeddable=True
    )
    completed_at: Optional[Any] = AirweaveField(
        None, description="When the project was completed, if applicable", embeddable=False
    )
    started_at: Optional[Any] = AirweaveField(
        None, description="When the project was started, if applicable", embeddable=False
    )
    target_date: Optional[str] = AirweaveField(
        None, description="The estimated completion date of the project", embeddable=True
    )
    start_date: Optional[str] = AirweaveField(
        None, description="The estimated start date of the project", embeddable=True
    )
    team_ids: Optional[List[str]] = AirweaveField(
        None, description="IDs of the teams this project belongs to", embeddable=False
    )
    team_names: Optional[List[str]] = AirweaveField(
        None, description="Names of the teams this project belongs to", embeddable=True
    )
    progress: Optional[float] = AirweaveField(
        None, description="The overall progress of the project", embeddable=False
    )
    lead: Optional[str] = AirweaveField(
        None, description="Name of the project lead, if any", embeddable=True
    )
    url: Optional[str] = AirweaveField(
        None, description="URL to view the project in Linear", embeddable=False
    )


class LinearTeamEntity(BaseEntity):
    """Schema for Linear team entities.

    This entity represents a team from Linear, containing all relevant
    metadata and content from the Linear API.

    Reference:
        https://developers.linear.app/docs/graphql/working-with-the-graphql-api
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the Linear team ID)
    # - breadcrumbs (team breadcrumb - self-reference for consistency)
    # - name (from team name)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    key: str = AirweaveField(..., description="The team's unique key used in URLs", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="The team's description", embeddable=True
    )
    color: Optional[str] = AirweaveField(None, description="The team's color", embeddable=False)
    icon: Optional[str] = AirweaveField(None, description="The icon of the team", embeddable=False)
    private: Optional[bool] = AirweaveField(
        None, description="Whether the team is private or not", embeddable=False
    )
    timezone: Optional[str] = AirweaveField(
        None, description="The timezone of the team", embeddable=False
    )
    parent_id: Optional[str] = AirweaveField(
        None, description="ID of the parent team, if this is a sub-team", embeddable=False
    )
    parent_name: Optional[str] = AirweaveField(
        None, description="Name of the parent team, if this is a sub-team", embeddable=True
    )
    issue_count: Optional[int] = AirweaveField(
        None, description="Number of issues in the team", embeddable=False
    )
    url: Optional[str] = AirweaveField(
        None, description="URL to view the team in Linear", embeddable=False
    )


class LinearCommentEntity(BaseEntity):
    """Schema for Linear comment entities.

    This entity represents a comment on a Linear issue, containing all relevant
    metadata and content from the Linear API.

    Reference:
        https://developers.linear.app/docs/graphql/working-with-the-graphql-api
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the Linear comment ID)
    # - breadcrumbs (team, project, and issue breadcrumbs)
    # - name (from body preview)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    issue_id: str = AirweaveField(
        ..., description="ID of the issue this comment belongs to", embeddable=False
    )
    issue_identifier: str = AirweaveField(
        ..., description="Identifier of the issue (e.g., 'ENG-123')", embeddable=True
    )
    body: str = AirweaveField(..., description="The content/body of the comment", embeddable=True)
    user_id: Optional[str] = AirweaveField(
        None, description="ID of the user who created the comment", embeddable=False
    )
    user_name: Optional[str] = AirweaveField(
        None, description="Name of the user who created the comment", embeddable=True
    )
    team_id: Optional[str] = AirweaveField(
        None, description="ID of the team this comment belongs to", embeddable=False
    )
    team_name: Optional[str] = AirweaveField(
        None, description="Name of the team this comment belongs to", embeddable=True
    )
    project_id: Optional[str] = AirweaveField(
        None, description="ID of the project this comment belongs to, if any", embeddable=False
    )
    project_name: Optional[str] = AirweaveField(
        None, description="Name of the project this comment belongs to, if any", embeddable=True
    )
    url: Optional[str] = AirweaveField(
        None, description="URL to view the comment in Linear", embeddable=False
    )


class LinearUserEntity(BaseEntity):
    """Schema for Linear user entities.

    This entity represents a user from Linear, containing all relevant
    metadata and content from the Linear API.

    Reference:
        https://developers.linear.app/docs/graphql/working-with-the-graphql-api
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the Linear user ID)
    # - breadcrumbs (team breadcrumbs)
    # - name (from user's full name)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    display_name: str = AirweaveField(
        ..., description="The user's display name, unique within the organization", embeddable=True
    )
    email: str = AirweaveField(..., description="The user's email address", embeddable=True)
    avatar_url: Optional[str] = AirweaveField(
        None, description="URL to the user's avatar image", embeddable=False
    )
    description: Optional[str] = AirweaveField(
        None, description="A short description of the user", embeddable=True
    )
    timezone: Optional[str] = AirweaveField(
        None, description="The local timezone of the user", embeddable=False
    )
    active: Optional[bool] = AirweaveField(
        None, description="Whether the user account is active or disabled", embeddable=False
    )
    admin: Optional[bool] = AirweaveField(
        None, description="Whether the user is an organization administrator", embeddable=False
    )
    guest: Optional[bool] = AirweaveField(
        None, description="Whether the user is a guest with limited access", embeddable=False
    )
    last_seen: Optional[Any] = AirweaveField(
        None, description="The last time the user was seen online", embeddable=False
    )
    status_emoji: Optional[str] = AirweaveField(
        None, description="The emoji to represent the user's current status", embeddable=False
    )
    status_label: Optional[str] = AirweaveField(
        None, description="The label of the user's current status", embeddable=True
    )
    status_until_at: Optional[Any] = AirweaveField(
        None, description="Date at which the user's status should be cleared", embeddable=False
    )
    created_issue_count: Optional[int] = AirweaveField(
        None, description="Number of issues created by the user", embeddable=False
    )
    team_ids: Optional[List[str]] = AirweaveField(
        None, description="IDs of the teams this user belongs to", embeddable=False
    )
    team_names: Optional[List[str]] = AirweaveField(
        None, description="Names of the teams this user belongs to", embeddable=True
    )
    url: Optional[str] = AirweaveField(
        None, description="URL to view the user in Linear", embeddable=False
    )
