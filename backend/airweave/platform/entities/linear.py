"""Linear entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity


class LinearIssueEntity(ChunkEntity):
    """Schema for Linear issue entities.

    This entity represents an issue from Linear, containing all relevant
    metadata and content from the Linear API.
    """

    # Core identification fields
    identifier: str = Field(..., description="The unique identifier of the issue (e.g., 'ENG-123')")
    title: str = Field(..., description="The title of the issue")

    # Content fields
    description: Optional[str] = Field(None, description="The description/content of the issue")

    # Status and priority fields
    priority: Optional[int] = Field(None, description="The priority level of the issue")
    state: Optional[str] = Field(None, description="The current state/status name of the issue")

    # Temporal information
    created_at: Optional[datetime] = Field(None, description="When the issue was created")
    updated_at: Optional[datetime] = Field(None, description="When the issue was last updated")
    completed_at: Optional[datetime] = Field(
        None, description="When the issue was completed, if applicable"
    )
    due_date: Optional[str] = Field(None, description="The due date for the issue, if set")

    # Organizational information
    team_id: Optional[str] = Field(None, description="ID of the team this issue belongs to")
    team_name: Optional[str] = Field(None, description="Name of the team this issue belongs to")
    project_id: Optional[str] = Field(
        None, description="ID of the project this issue belongs to, if any"
    )
    project_name: Optional[str] = Field(
        None, description="Name of the project this issue belongs to, if any"
    )

    # Assignment information
    assignee: Optional[str] = Field(
        None, description="Name of the user assigned to this issue, if any"
    )


class LinearAttachmentEntity(FileEntity):
    """Schema for Linear attachment entities.

    Attachments in Linear allow linking external resources to issues.
    """

    issue_id: str = Field(..., description="ID of the issue this attachment belongs to")
    issue_identifier: str = Field(..., description="Identifier of the issue (e.g., 'ENG-123')")

    # Attachment specific fields
    title: Optional[str] = Field(None, description="Title of the attachment")
    subtitle: Optional[str] = Field(None, description="Subtitle of the attachment")

    # Source metadata
    source: Optional[Dict[str, Any]] = Field(
        None, description="Source information about the attachment"
    )

    # Temporal information
    created_at: Optional[datetime] = Field(None, description="When the attachment was created")
    updated_at: Optional[datetime] = Field(None, description="When the attachment was last updated")

    # Additional metadata
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Key-value metadata for the attachment"
    )


class LinearProjectEntity(ChunkEntity):
    """Schema for Linear project entities.

    This entity represents a project from Linear, containing all relevant
    metadata and content from the Linear API.
    """

    # Core identification fields
    name: str = Field(..., description="The name of the project")
    slug_id: str = Field(..., description="The project's unique URL slug")

    # Content fields
    description: Optional[str] = Field(None, description="The project's description")

    # Status and priority fields
    priority: Optional[int] = Field(None, description="The priority level of the project")
    state: Optional[str] = Field(None, description="The current state/status name of the project")

    # Temporal information
    created_at: Optional[datetime] = Field(None, description="When the project was created")
    updated_at: Optional[datetime] = Field(None, description="When the project was last updated")
    completed_at: Optional[datetime] = Field(
        None, description="When the project was completed, if applicable"
    )
    started_at: Optional[datetime] = Field(
        None, description="When the project was started, if applicable"
    )
    target_date: Optional[str] = Field(
        None, description="The estimated completion date of the project"
    )
    start_date: Optional[str] = Field(None, description="The estimated start date of the project")

    # Organizational information
    team_ids: Optional[List[str]] = Field(
        None, description="IDs of the teams this project belongs to"
    )
    team_names: Optional[List[str]] = Field(
        None, description="Names of the teams this project belongs to"
    )

    # Progress information
    progress: Optional[float] = Field(None, description="The overall progress of the project")

    # Leader information
    lead: Optional[str] = Field(None, description="Name of the project lead, if any")


class LinearTeamEntity(ChunkEntity):
    """Schema for Linear team entities.

    This entity represents a team from Linear, containing all relevant
    metadata and content from the Linear API.
    """

    # Core identification fields
    name: str = Field(..., description="The team's name")
    key: str = Field(..., description="The team's unique key used in URLs")

    # Content fields
    description: Optional[str] = Field(None, description="The team's description")

    # Display fields
    color: Optional[str] = Field(None, description="The team's color")
    icon: Optional[str] = Field(None, description="The icon of the team")

    # Team properties
    private: Optional[bool] = Field(None, description="Whether the team is private or not")
    timezone: Optional[str] = Field(None, description="The timezone of the team")

    # Organizational information
    parent_id: Optional[str] = Field(
        None, description="ID of the parent team, if this is a sub-team"
    )
    parent_name: Optional[str] = Field(
        None, description="Name of the parent team, if this is a sub-team"
    )

    # Temporal information
    created_at: Optional[datetime] = Field(None, description="When the team was created")
    updated_at: Optional[datetime] = Field(None, description="When the team was last updated")

    # Member information
    member_count: Optional[int] = Field(None, description="Number of members in the team")


class LinearUserEntity(ChunkEntity):
    """Schema for Linear user entities.

    This entity represents a user from Linear, containing all relevant
    metadata and content from the Linear API.
    """

    # Core identification fields
    name: str = Field(..., description="The user's full name")
    display_name: str = Field(
        ..., description="The user's display name, unique within the organization"
    )
    email: str = Field(..., description="The user's email address")

    # Profile information
    avatar_url: Optional[str] = Field(None, description="URL to the user's avatar image")
    description: Optional[str] = Field(None, description="A short description of the user")
    timezone: Optional[str] = Field(None, description="The local timezone of the user")

    # Status information
    active: Optional[bool] = Field(
        None, description="Whether the user account is active or disabled"
    )
    admin: Optional[bool] = Field(
        None, description="Whether the user is an organization administrator"
    )
    guest: Optional[bool] = Field(
        None, description="Whether the user is a guest with limited access"
    )
    last_seen: Optional[datetime] = Field(
        None, description="The last time the user was seen online"
    )

    # Current status
    status_emoji: Optional[str] = Field(
        None, description="The emoji to represent the user's current status"
    )
    status_label: Optional[str] = Field(None, description="The label of the user's current status")
    status_until_at: Optional[datetime] = Field(
        None, description="Date at which the user's status should be cleared"
    )

    # Activity metrics
    created_issue_count: Optional[int] = Field(
        None, description="Number of issues created by the user"
    )

    # Team information
    team_ids: Optional[List[str]] = Field(None, description="IDs of the teams this user belongs to")
    team_names: Optional[List[str]] = Field(
        None, description="Names of the teams this user belongs to"
    )

    # Temporal information
    created_at: Optional[datetime] = Field(None, description="When the user was created")
    updated_at: Optional[datetime] = Field(None, description="When the user was last updated")
