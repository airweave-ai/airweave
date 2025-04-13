"""ClickUp entity definitions for Airweave.

This module defines schemas for ClickUp entities including:
- Workspaces
- Spaces
- Folders
- Lists
- Tasks
- Comments
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity


class ClickUpWorkspaceEntity(ChunkEntity):
    """ClickUp workspace entity."""

    entity_id: str = Field(..., description="Unique Entity ID")
    workspace_id: str = Field(..., description="Workspace ID")
    name: str = Field(..., description="Workspace name")
    color: Optional[str] = Field(None, description="Workspace color")
    avatar: Optional[str] = Field(None, description="Workspace avatar URL")
    members: List[dict] = Field(default_factory=list, description="List of workspace members")


class ClickUpSpaceEntity(ChunkEntity):
    """ClickUp space entity."""

    space_id: str = Field(..., description="Space ID")
    name: str = Field(..., description="Space name")
    private: bool = Field(False, description="Whether the space is private")
    status: Dict[str, Any] = Field(default_factory=dict, description="Space status configuration")
    multiple_assignees: bool = Field(False, description="Whether multiple assignees are allowed")
    features: Dict[str, Any] = Field(
        default_factory=dict, description="Space features configuration"
    )


class ClickUpFolderEntity(ChunkEntity):
    """ClickUp folder entity."""

    folder_id: str = Field(..., description="Folder ID")
    name: str = Field(..., description="Folder name")
    hidden: bool = Field(False, description="Whether the folder is hidden")
    space_id: str = Field(..., description="Parent space ID")
    task_count: Optional[int] = Field(None, description="Number of tasks in the folder")


class ClickUpListEntity(ChunkEntity):
    """ClickUp list entity."""

    list_id: str = Field(..., description="List ID")
    name: str = Field(..., description="List name")
    folder_id: str = Field(..., description="Parent folder ID")
    space_id: str = Field(..., description="Parent space ID")
    content: Optional[str] = Field("", description="List content/description")
    status: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="List status configuration"
    )
    priority: Optional[Dict[str, Any]] = Field(None, description="List priority configuration")
    assignee: Optional[str] = Field(None, description="List assignee username")
    task_count: Optional[int] = Field(None, description="Number of tasks in the list")
    due_date: Optional[Any] = Field(None, description="List due date")
    start_date: Optional[Any] = Field(None, description="List start date")
    folder_name: str = Field(..., description="Parent folder name")
    space_name: str = Field(..., description="Parent space name")


class ClickUpTaskEntity(ChunkEntity):
    """ClickUp task entity."""

    task_id: str = Field(..., description="Task ID")
    name: str = Field(..., description="Task name")
    status: Dict[str, Any] = Field(default_factory=dict, description="Task status configuration")
    priority: Optional[Dict[str, Any]] = Field(None, description="Task priority configuration")
    assignees: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of task assignees"
    )
    tags: List[str] = Field(default_factory=list, description="List of task tags")
    due_date: Optional[datetime] = Field(None, description="Task due date")
    start_date: Optional[datetime] = Field(None, description="Task start date")
    time_estimate: Optional[int] = Field(None, description="Estimated time in milliseconds")
    time_spent: Optional[int] = Field(None, description="Time spent in milliseconds")
    custom_fields: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of custom fields"
    )
    list_id: str = Field(..., description="Parent list ID")
    folder_id: str = Field(..., description="Parent folder ID")
    space_id: str = Field(..., description="Parent space ID")
    url: str = Field("", description="Task URL")
    description: str = Field("", description="Task description")
    parent: Optional[str] = Field(None, description="Parent task ID if this is a subtask")


class ClickUpCommentEntity(ChunkEntity):
    """ClickUp comment entity."""

    comment_id: str = Field(..., description="Comment ID")
    task_id: str = Field(..., description="Parent task ID")
    user: Dict[str, Any] = Field(default_factory=dict, description="Comment author information")
    text_content: str = Field("", description="Comment text content")
    resolved: bool = Field(False, description="Whether the comment is resolved")
    assignee: Optional[Dict[str, Any]] = Field(None, description="Comment assignee information")
    assigned_by: Optional[Dict[str, Any]] = Field(None, description="User who assigned the comment")
    reactions: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of reactions to the comment"
    )
    date: datetime = Field(..., description="Comment creation date")
