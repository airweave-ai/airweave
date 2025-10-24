"""Asana entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


class AsanaWorkspaceEntity(BaseEntity):
    """Schema for Asana workspace entities."""

    # API fields
    is_organization: bool = Field(False, description="Whether the workspace is an organization")
    email_domains: List[str] = Field(
        default_factory=list, description="List of email domains that can access this workspace"
    )
    permalink_url: Optional[str] = Field(
        None, description="URL to access the workspace in the Asana application"
    )


class AsanaProjectEntity(BaseEntity):
    """Schema for Asana project entities."""

    workspace_gid: str = Field(
        ..., description="Globally unique identifier of the workspace the project belongs to"
    )
    workspace_name: str = AirweaveField(
        ..., description="The name of the workspace the project belongs to", embeddable=True
    )
    color: Optional[str] = Field(
        None, description="Color of the project (e.g. 'dark-pink', 'light-blue')"
    )
    archived: bool = Field(False, description="Whether the project is archived")
    current_status: Optional[Dict] = AirweaveField(
        None, description="The current status update for this project", embeddable=True
    )
    default_view: Optional[str] = Field(
        None, description="The default view of the project (list, board, calendar, timeline)"
    )
    due_date: Optional[str] = AirweaveField(
        None,
        description="The day on which this project is due (YYYY-MM-DD format)",
        embeddable=True,
    )
    due_on: Optional[str] = AirweaveField(
        None,
        description="The day on which this project is due (YYYY-MM-DD format)",
        embeddable=True,
    )
    html_notes: Optional[str] = AirweaveField(
        None,
        description="HTML formatted note content of the project",
        embeddable=True,
    )
    notes: Optional[str] = AirweaveField(
        None,
        description="Free-form textual information associated with the project",
        embeddable=True,
    )
    is_public: bool = Field(False, description="Whether the project is public to its team")
    start_on: Optional[str] = AirweaveField(
        None,
        description="The day on which this project starts (YYYY-MM-DD format)",
        embeddable=True,
    )
    owner: Optional[Dict] = AirweaveField(
        None, description="The owner of this project", embeddable=True
    )
    team: Optional[Dict] = AirweaveField(
        None,
        description="The team that this project is associated with",
        embeddable=True,
    )
    members: List[Dict] = AirweaveField(
        default_factory=list,
        description="Array of users who are members of this project",
        embeddable=True,
    )
    followers: List[Dict] = AirweaveField(
        default_factory=list,
        description="Array of users following this project",
        embeddable=True,
    )
    custom_fields: List[Dict] = Field(
        default_factory=list, description="Array of custom field values applied to the project"
    )
    custom_field_settings: List[Dict] = Field(
        default_factory=list, description="Array of custom field settings for this project"
    )
    default_access_level: Optional[str] = Field(
        None, description="Default access level for the project (editor, commenter, viewer)"
    )
    icon: Optional[str] = Field(None, description="The icon for a project")
    permalink_url: Optional[str] = Field(
        None, description="URL to access the project in the Asana application"
    )


class AsanaSectionEntity(BaseEntity):
    """Schema for Asana section entities."""

    project_gid: str = Field(
        ..., description="Globally unique identifier of the project this section belongs to"
    )
    projects: List[Dict] = AirweaveField(
        default_factory=list,
        description="Deprecated. Array of projects this section is associated with",
        embeddable=True,
    )


class AsanaTaskEntity(BaseEntity):
    """Schema for Asana task entities."""

    project_gid: str = Field(
        ..., description="Globally unique identifier of the project this task belongs to"
    )
    section_gid: Optional[str] = Field(
        None, description="Globally unique identifier of the section this task belongs to"
    )
    actual_time_minutes: Optional[int] = Field(
        None, description="The actual time spent on this task in minutes"
    )
    approval_status: Optional[str] = AirweaveField(
        None, description="The status of the task's approval, if applicable", embeddable=True
    )
    assignee: Optional[Dict] = AirweaveField(
        None, description="User to which this task is assigned", embeddable=True
    )
    assignee_status: Optional[str] = AirweaveField(
        None,
        description="The scheduling status of this task for the user it's assigned to",
        embeddable=True,
    )
    completed: bool = AirweaveField(
        False, description="Whether the task is marked complete", embeddable=True
    )
    completed_at: Optional[datetime] = AirweaveField(
        None, description="The time at which this task was completed", embeddable=True
    )
    completed_by: Optional[Dict] = AirweaveField(
        None, description="The user who completed this task", embeddable=True
    )
    dependencies: List[Dict] = AirweaveField(
        default_factory=list,
        description="Array of tasks that this task depends on",
        embeddable=True,
    )
    dependents: List[Dict] = AirweaveField(
        default_factory=list,
        description="Array of tasks that depend on this task",
        embeddable=True,
    )
    due_at: Optional[datetime] = AirweaveField(
        None,
        description="The time at which this task is due with a time component",
        embeddable=True,
    )
    due_on: Optional[str] = AirweaveField(
        None, description="The date on which this task is due (YYYY-MM-DD format)", embeddable=True
    )
    external: Optional[Dict] = AirweaveField(
        None,
        description="Information about the external application syncing with this task",
        embeddable=True,
    )
    html_notes: Optional[str] = AirweaveField(
        None, description="HTML formatted note content of the task", embeddable=True
    )
    notes: Optional[str] = AirweaveField(
        None,
        description="Free-form textual information associated with the task",
        embeddable=True,
    )
    is_rendered_as_separator: bool = Field(
        False, description="Whether the task is rendered as a separator in list view"
    )
    liked: bool = Field(False, description="Whether the task is liked by the authorized user")
    memberships: List[Dict] = Field(
        default_factory=list, description="Array of projects and sections this task is in"
    )
    num_likes: int = Field(0, description="The number of users who have liked this task")
    num_subtasks: int = Field(0, description="The number of subtasks on this task")
    parent: Optional[Dict] = AirweaveField(
        None, description="The parent of this task, if applicable", embeddable=True
    )
    permalink_url: Optional[str] = Field(
        None, description="URL to access the task in the Asana application"
    )
    resource_subtype: str = Field(
        "default_task", description="The subtype of the task (default_task, milestone, approval)"
    )
    start_at: Optional[datetime] = AirweaveField(
        None,
        description="The time at which this task starts with a time component",
        embeddable=True,
    )
    start_on: Optional[str] = AirweaveField(
        None,
        description="The date on which this task starts (YYYY-MM-DD format)",
        embeddable=True,
    )
    tags: List[Dict] = AirweaveField(
        default_factory=list, description="Array of tags associated with this task", embeddable=True
    )
    custom_fields: List[Dict] = AirweaveField(
        default_factory=list,
        description="Array of custom field values applied to the task",
        embeddable=True,
    )
    followers: List[Dict] = AirweaveField(
        default_factory=list, description="Array of users following this task", embeddable=True
    )
    workspace: Optional[Dict] = AirweaveField(
        None, description="The workspace this task is associated with", embeddable=True
    )


class AsanaCommentEntity(BaseEntity):
    """Schema for Asana comment/story entities."""

    task_gid: str = Field(
        ..., description="Globally unique identifier of the task this comment belongs to"
    )
    author: Dict = AirweaveField(
        ..., description="The user who created this comment", embeddable=True
    )
    resource_subtype: str = Field(
        "comment_added", description="The subtype of the comment resource"
    )
    text: Optional[str] = AirweaveField(
        None, description="The plain text content of the comment", embeddable=True
    )
    html_text: Optional[str] = AirweaveField(
        None, description="HTML formatted content of the comment", embeddable=True
    )
    is_pinned: bool = Field(False, description="Whether the comment is pinned to the task")
    is_edited: bool = Field(False, description="Whether the comment has been edited")
    sticker_name: Optional[str] = Field(
        None, description="The name of the sticker (for sticker comments)"
    )
    num_likes: int = Field(0, description="The number of users who have liked this comment")
    liked: bool = Field(False, description="Whether the comment is liked by the authorized user")
    type: str = Field("comment", description="The type of the comment (comment or system)")
    previews: List[Dict] = Field(
        default_factory=list, description="Previews of attachments referenced in the comment"
    )


class AsanaFileEntity(FileEntity):
    """Schema for Asana file attachments.

    Reference:
        https://developers.asana.com/reference/getattachment
    """

    task_gid: str = Field(..., description="GID of the task this file is attached to")
    task_name: str = Field(..., description="Name of the task this file is attached to")
    resource_type: str = Field(..., description="Type of the attachment resource")
    host: Optional[str] = Field(None, description="Service hosting the attachment")
    parent: Optional[Dict[str, Any]] = Field(
        None, description="Parent resource the attachment is on"
    )
    view_url: Optional[str] = Field(None, description="URL to view the attachment")
    permanent: bool = Field(False, description="Whether this is a permanent attachment")
