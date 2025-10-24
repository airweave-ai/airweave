"""Linear entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base_legacy import ChunkEntity, FileEntity


class LinearIssueEntity(ChunkEntity):
    """Schema for Linear issue entities.

    This entity represents an issue from Linear, containing all relevant
    metadata and content from the Linear API.
    """

    # Core identification fields
    identifier: str = AirweaveField(
        ..., description="The unique identifier of the issue (e.g., 'ENG-123')", embeddable=True
    )
    title: str = AirweaveField(..., description="The title of the issue", embeddable=True)

    # Content fields
    description: Optional[str] = AirweaveField(
        None, description="The description/content of the issue", embeddable=True
    )

    # Status and priority fields
    priority: Optional[int] = AirweaveField(None, description="The priority level of the issue")
    state: Optional[str] = AirweaveField(
        None, description="The current state/status name of the issue", embeddable=True
    )

    # Temporal information
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the issue was created", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the issue was last updated", is_updated_at=True
    )
    completed_at: Optional[datetime] = AirweaveField(
        None, description="When the issue was completed, if applicable"
    )
    due_date: Optional[str] = AirweaveField(
        None, description="The due date for the issue, if set", embeddable=True
    )

    # Organizational information
    team_id: Optional[str] = AirweaveField(None, description="ID of the team this issue belongs to")
    team_name: Optional[str] = AirweaveField(
        None, description="Name of the team this issue belongs to", embeddable=True
    )
    project_id: Optional[str] = AirweaveField(
        None, description="ID of the project this issue belongs to, if any"
    )
    project_name: Optional[str] = AirweaveField(
        None, description="Name of the project this issue belongs to, if any", embeddable=True
    )

    # Assignment information
    assignee: Optional[str] = AirweaveField(
        None, description="Name of the user assigned to this issue, if any", embeddable=True
    )


class LinearAttachmentEntity(FileEntity):
    """Schema for Linear attachment entities.

    Attachments in Linear allow linking external resources to issues.
    """

    issue_id: str = AirweaveField(..., description="ID of the issue this attachment belongs to")
    issue_identifier: str = AirweaveField(
        ..., description="Identifier of the issue (e.g., 'ENG-123')"
    )

    # Attachment specific fields
    title: Optional[str] = AirweaveField(None, description="Title of the attachment")
    subtitle: Optional[str] = AirweaveField(None, description="Subtitle of the attachment")

    # Source metadata
    source: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Source information about the attachment"
    )

    # Temporal information
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the attachment was created", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the attachment was last updated", is_updated_at=True
    )

    # Additional metadata
    metadata: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Key-value metadata for the attachment"
    )


class LinearProjectEntity(ChunkEntity):
    """Schema for Linear project entities.

    This entity represents a project from Linear, containing all relevant
    metadata and content from the Linear API.
    """

    # Core identification fields
    name: str = AirweaveField(..., description="The name of the project", embeddable=True)
    slug_id: str = AirweaveField(..., description="The project's unique URL slug", embeddable=True)

    # Content fields
    description: Optional[str] = AirweaveField(
        None, description="The project's description", embeddable=True
    )

    # Status and priority fields
    priority: Optional[int] = AirweaveField(None, description="The priority level of the project")
    state: Optional[str] = AirweaveField(
        None, description="The current state/status name of the project", embeddable=True
    )

    # Temporal information
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the project was created", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the project was last updated", is_updated_at=True
    )
    completed_at: Optional[datetime] = AirweaveField(
        None, description="When the project was completed, if applicable"
    )
    started_at: Optional[datetime] = AirweaveField(
        None, description="When the project was started, if applicable"
    )
    target_date: Optional[str] = AirweaveField(
        None, description="The estimated completion date of the project", embeddable=True
    )
    start_date: Optional[str] = AirweaveField(
        None, description="The estimated start date of the project", embeddable=True
    )

    # Organizational information
    team_ids: Optional[List[str]] = AirweaveField(
        None, description="IDs of the teams this project belongs to"
    )
    team_names: Optional[List[str]] = AirweaveField(
        None, description="Names of the teams this project belongs to", embeddable=True
    )

    # Progress information
    progress: Optional[float] = AirweaveField(
        None, description="The overall progress of the project"
    )

    # Leader information
    lead: Optional[str] = AirweaveField(
        None, description="Name of the project lead, if any", embeddable=True
    )


class LinearTeamEntity(ChunkEntity):
    """Schema for Linear team entities.

    This entity represents a team from Linear, containing all relevant
    metadata and content from the Linear API.
    """

    # Core identification fields
    name: str = AirweaveField(..., description="The team's name", embeddable=True)
    key: str = AirweaveField(..., description="The team's unique key used in URLs", embeddable=True)

    # Content fields
    description: Optional[str] = AirweaveField(
        None, description="The team's description", embeddable=True
    )

    # Display fields
    color: Optional[str] = AirweaveField(None, description="The team's color")
    icon: Optional[str] = AirweaveField(None, description="The icon of the team")

    # Team properties
    private: Optional[bool] = AirweaveField(None, description="Whether the team is private or not")
    timezone: Optional[str] = AirweaveField(None, description="The timezone of the team")

    # Organizational information
    parent_id: Optional[str] = AirweaveField(
        None, description="ID of the parent team, if this is a sub-team"
    )
    parent_name: Optional[str] = AirweaveField(
        None, description="Name of the parent team, if this is a sub-team", embeddable=True
    )

    # Temporal information
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the team was created", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the team was last updated", is_updated_at=True
    )

    # Member information
    member_count: Optional[int] = AirweaveField(None, description="Number of members in the team")


class LinearCommentEntity(ChunkEntity):
    """Schema for Linear comment entities.

    This entity represents a comment on a Linear issue, containing all relevant
    metadata and content from the Linear API.
    """

    # Core identification fields
    issue_id: str = AirweaveField(..., description="ID of the issue this comment belongs to")
    issue_identifier: str = AirweaveField(
        ..., description="Identifier of the issue (e.g., 'ENG-123')", embeddable=True
    )

    # Content fields
    body: str = AirweaveField(..., description="The content/body of the comment", embeddable=True)

    # Author information
    user_id: Optional[str] = AirweaveField(
        None, description="ID of the user who created the comment"
    )
    user_name: Optional[str] = AirweaveField(
        None, description="Name of the user who created the comment", embeddable=True
    )

    # Temporal information
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the comment was created", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the comment was last updated", is_updated_at=True
    )

    # Organizational information
    team_id: Optional[str] = AirweaveField(
        None, description="ID of the team this comment belongs to"
    )
    team_name: Optional[str] = AirweaveField(
        None, description="Name of the team this comment belongs to", embeddable=True
    )
    project_id: Optional[str] = AirweaveField(
        None, description="ID of the project this comment belongs to, if any"
    )
    project_name: Optional[str] = AirweaveField(
        None, description="Name of the project this comment belongs to, if any", embeddable=True
    )


class LinearUserEntity(ChunkEntity):
    """Schema for Linear user entities.

    This entity represents a user from Linear, containing all relevant
    metadata and content from the Linear API.
    """

    # Core identification fields
    name: str = AirweaveField(..., description="The user's full name", embeddable=True)
    display_name: str = AirweaveField(
        ..., description="The user's display name, unique within the organization", embeddable=True
    )
    email: str = AirweaveField(..., description="The user's email address", embeddable=True)

    # Profile information
    avatar_url: Optional[str] = AirweaveField(None, description="URL to the user's avatar image")
    description: Optional[str] = AirweaveField(
        None, description="A short description of the user", embeddable=True
    )
    timezone: Optional[str] = AirweaveField(None, description="The local timezone of the user")

    # Status information
    active: Optional[bool] = AirweaveField(
        None, description="Whether the user account is active or disabled"
    )
    admin: Optional[bool] = AirweaveField(
        None, description="Whether the user is an organization administrator"
    )
    guest: Optional[bool] = AirweaveField(
        None, description="Whether the user is a guest with limited access"
    )
    last_seen: Optional[datetime] = AirweaveField(
        None, description="The last time the user was seen online"
    )

    # Current status
    status_emoji: Optional[str] = AirweaveField(
        None, description="The emoji to represent the user's current status"
    )
    status_label: Optional[str] = AirweaveField(
        None, description="The label of the user's current status", embeddable=True
    )
    status_until_at: Optional[datetime] = AirweaveField(
        None, description="Date at which the user's status should be cleared"
    )

    # Activity metrics
    created_issue_count: Optional[int] = AirweaveField(
        None, description="Number of issues created by the user"
    )

    # Team information
    team_ids: Optional[List[str]] = AirweaveField(
        None, description="IDs of the teams this user belongs to"
    )
    team_names: Optional[List[str]] = AirweaveField(
        None, description="Names of the teams this user belongs to", embeddable=True
    )

    # Temporal information
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the user was created", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the user was last updated", is_updated_at=True
    )
