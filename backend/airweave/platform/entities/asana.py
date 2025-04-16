"""Asana entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity


class AsanaWorkspaceEntity(ChunkEntity):
    """Schema for Asana workspace entities."""

    name: str
    asana_gid: str
    is_organization: bool = False
    email_domains: List[str] = Field(default_factory=list)
    permalink_url: Optional[str] = None


class AsanaProjectEntity(ChunkEntity):
    """Schema for Asana project entities."""

    name: str
    workspace_gid: str
    workspace_name: str
    color: Optional[str] = None  # e.g. 'dark-pink', 'light-blue', etc.
    archived: bool = False
    created_at: Optional[datetime] = None
    current_status: Optional[Dict] = None
    default_view: Optional[str] = None  # 'list', 'board', 'calendar', 'timeline'
    due_date: Optional[str] = None
    due_on: Optional[str] = None
    html_notes: Optional[str] = None
    notes: Optional[str] = None
    is_public: bool = False
    start_on: Optional[str] = None
    modified_at: Optional[datetime] = None
    owner: Optional[Dict] = None
    team: Optional[Dict] = None
    members: List[Dict] = Field(default_factory=list)
    followers: List[Dict] = Field(default_factory=list)
    custom_fields: List[Dict] = Field(default_factory=list)
    custom_field_settings: List[Dict] = Field(default_factory=list)
    default_access_level: Optional[str] = None
    icon: Optional[str] = None
    permalink_url: Optional[str] = None


class AsanaSectionEntity(ChunkEntity):
    """Schema for Asana section entities."""

    name: str
    project_gid: str
    created_at: Optional[datetime] = None
    projects: List[Dict] = Field(default_factory=list)  # Deprecated but included for compatibility


class AsanaTaskEntity(ChunkEntity):
    """Schema for Asana task entities."""

    name: str
    gid: str
    project_gid: str
    section_gid: Optional[str] = None
    actual_time_minutes: Optional[int] = None
    approval_status: Optional[str] = None
    assignee: Optional[Dict] = None
    assignee_status: Optional[str] = None
    completed: bool = False
    completed_at: Optional[datetime] = None
    completed_by: Optional[Dict] = None
    created_at: Optional[datetime] = None
    dependencies: List[Dict] = Field(default_factory=list)
    dependents: List[Dict] = Field(default_factory=list)
    due_at: Optional[datetime] = None
    due_on: Optional[str] = None
    external: Optional[Dict] = None
    html_notes: Optional[str] = None
    notes: Optional[str] = None
    is_rendered_as_separator: bool = False
    liked: bool = False
    memberships: List[Dict] = Field(default_factory=list)
    modified_at: Optional[datetime] = None
    num_likes: int = 0
    num_subtasks: int = 0
    parent: Optional[Dict] = None
    permalink_url: Optional[str] = None
    privacy_setting: Optional[str] = None
    resource_subtype: str = "default_task"  # 'default_task', 'milestone', 'approval'
    start_at: Optional[datetime] = None
    start_on: Optional[str] = None
    tags: List[Dict] = Field(default_factory=list)
    custom_fields: List[Dict] = Field(default_factory=list)
    followers: List[Dict] = Field(default_factory=list)
    workspace: Optional[Dict] = None


class AsanaCommentEntity(ChunkEntity):
    """Schema for Asana comment/story entities."""

    task_gid: str
    name: str  # Adding name field for breadcrumb compatibility
    author: Dict
    created_at: datetime
    resource_subtype: str = "comment_added"
    text: Optional[str] = None
    html_text: Optional[str] = None
    is_pinned: bool = False
    is_edited: bool = False
    sticker_name: Optional[str] = None
    num_likes: int = 0
    liked: bool = False
    type: str = "comment"  # 'comment' or 'system'
    previews: List[Dict] = Field(default_factory=list)


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
