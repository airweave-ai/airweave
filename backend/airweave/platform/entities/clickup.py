"""ClickUp entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import ChunkEntity, FileEntity


class ClickUpWorkspaceEntity(ChunkEntity):
    """Schema for ClickUp workspace entities."""

    workspace_id: str = Field(..., description="Workspace ID")
    name: str = AirweaveField(..., description="Workspace name", embeddable=True)
    color: Optional[str] = Field(None, description="Workspace color")
    avatar: Optional[str] = Field(None, description="Workspace avatar URL")
    members: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="List of workspace members", embeddable=True
    )


class ClickUpSpaceEntity(ChunkEntity):
    """Schema for ClickUp space entities."""

    space_id: str = Field(..., description="Space ID")
    name: str = AirweaveField(..., description="Space name", embeddable=True)
    private: bool = Field(False, description="Whether the space is private")
    status: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Space status configuration", embeddable=True
    )
    multiple_assignees: bool = Field(False, description="Whether multiple assignees are allowed")
    features: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Space features configuration", embeddable=True
    )


class ClickUpFolderEntity(ChunkEntity):
    """Schema for ClickUp folder entities."""

    folder_id: str = Field(..., description="Folder ID")
    name: str = AirweaveField(..., description="Folder name", embeddable=True)
    hidden: bool = Field(False, description="Whether the folder is hidden")
    space_id: str = Field(..., description="Parent space ID")
    task_count: Optional[int] = Field(None, description="Number of tasks in the folder")


class ClickUpListEntity(ChunkEntity):
    """Schema for ClickUp list entities."""

    list_id: str = Field(..., description="List ID")
    name: str = AirweaveField(..., description="List name", embeddable=True)
    folder_id: Optional[str] = Field(None, description="Parent folder ID (optional)")
    space_id: str = Field(..., description="Parent space ID")
    content: Optional[str] = AirweaveField(
        None, description="List content/description", embeddable=True
    )
    status: Optional[Dict[str, Any]] = AirweaveField(
        None, description="List status configuration", embeddable=True
    )
    priority: Optional[Dict[str, Any]] = AirweaveField(
        None, description="List priority configuration", embeddable=True
    )
    assignee: Optional[str] = Field(None, description="List assignee username")
    task_count: Optional[int] = Field(None, description="Number of tasks in the list")
    due_date: Optional[Any] = Field(None, description="List due date")
    start_date: Optional[Any] = Field(None, description="List start date")
    folder_name: Optional[str] = AirweaveField(
        None, description="Parent folder name", embeddable=True
    )
    space_name: str = AirweaveField(..., description="Parent space name", embeddable=True)


class ClickUpTaskEntity(ChunkEntity):
    """Schema for ClickUp task entities."""

    task_id: str = Field(..., description="Task ID")
    name: str = AirweaveField(..., description="Task name", embeddable=True)
    status: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Task status configuration", embeddable=True
    )
    priority: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Task priority configuration", embeddable=True
    )
    assignees: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="List of task assignees", embeddable=True
    )
    tags: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="List of task tags", embeddable=True
    )
    due_date: Optional[datetime] = AirweaveField(None, description="Task due date", embeddable=True)
    start_date: Optional[datetime] = AirweaveField(
        None, description="Task start date", embeddable=True
    )
    time_estimate: Optional[int] = Field(None, description="Estimated time in milliseconds")
    time_spent: Optional[int] = Field(None, description="Time spent in milliseconds")
    custom_fields: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="List of custom fields", embeddable=True
    )
    list_id: str = Field(..., description="Parent list ID")
    folder_id: str = Field(..., description="Parent folder ID")
    space_id: str = Field(..., description="Parent space ID")
    url: str = Field(..., description="Task URL")
    description: Optional[str] = AirweaveField(
        None, description="Task description", embeddable=True
    )
    parent: Optional[str] = Field(None, description="Parent task ID if this is a subtask")


class ClickUpCommentEntity(ChunkEntity):
    """Schema for ClickUp comment entities."""

    comment_id: str = Field(..., description="Comment ID")
    task_id: str = Field(..., description="Parent task ID")
    user: Dict[str, Any] = AirweaveField(
        ..., description="Comment author information", embeddable=True
    )
    text_content: Optional[str] = AirweaveField(
        None, description="Comment text content", embeddable=True
    )
    resolved: bool = Field(False, description="Whether the comment is resolved")
    assignee: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Comment assignee information", embeddable=True
    )
    assigned_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who assigned the comment", embeddable=True
    )
    reactions: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="List of reactions to the comment", embeddable=True
    )
    date: Optional[datetime] = AirweaveField(
        None, description="Comment creation date", embeddable=True, is_created_at=True
    )


class ClickUpSubtaskEntity(ChunkEntity):
    """Schema for ClickUp subtask entities.

    Supports nested subtasks where subtasks can have their own subtasks.
    The parent_task_id points to the immediate parent (task or subtask).
    """

    subtask_id: str = Field(..., description="Subtask ID")
    name: str = AirweaveField(..., description="Subtask name", embeddable=True)
    parent_task_id: str = Field(..., description="Immediate parent task/subtask ID")
    status: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Subtask status configuration", embeddable=True
    )
    assignees: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="List of subtask assignees", embeddable=True
    )
    due_date: Optional[datetime] = AirweaveField(
        None, description="Subtask due date", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Subtask description", embeddable=True
    )
    nesting_level: Optional[int] = Field(
        None, description="Nesting level (1 = direct subtask, 2 = nested subtask, etc.)"
    )


class ClickUpFileEntity(FileEntity):
    """Schema for ClickUp file attachments.

    Represents files attached to ClickUp tasks.
    Reference: https://api.clickup.com/api/v2/task/{task_id}
    """

    task_id: str = Field(..., description="ID of the task this file is attached to")
    task_name: str = AirweaveField(
        ..., description="Name of the task this file is attached to", embeddable=True
    )
    attachment_id: str = Field(..., description="ClickUp attachment ID")
    version: Optional[int] = Field(None, description="Version number of the attachment")
    date: Optional[datetime] = AirweaveField(
        None, description="Date when the attachment was added", embeddable=True, is_created_at=True
    )
    title: Optional[str] = AirweaveField(
        None, description="Original title/name of the attachment", embeddable=True
    )
    extension: Optional[str] = Field(None, description="File extension")
    hidden: bool = Field(False, description="Whether the attachment is hidden")
    parent: Optional[str] = Field(None, description="Parent attachment ID if applicable")
    thumbnail_small: Optional[str] = Field(None, description="URL for small thumbnail")
    thumbnail_medium: Optional[str] = Field(None, description="URL for medium thumbnail")
    thumbnail_large: Optional[str] = Field(None, description="URL for large thumbnail")
    is_folder: Optional[bool] = Field(None, description="Whether this is a folder attachment")
    mimetype: Optional[str] = Field(None, description="MIME type of the file")
    total_comments: Optional[int] = Field(None, description="Number of comments on this attachment")
    # Additional ClickUp-specific fields
    url: Optional[str] = Field(None, description="Direct URL to download the attachment")
    url_w_query: Optional[str] = Field(None, description="URL with query parameters")
    url_w_host: Optional[str] = Field(None, description="URL with host parameters")
    email_data: Optional[Dict[str, Any]] = Field(
        None, description="Email data if attachment is from email"
    )
    user: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who uploaded the attachment", embeddable=True
    )
    resolved: Optional[bool] = Field(None, description="Whether the attachment is resolved")
    resolved_comments: Optional[int] = Field(None, description="Number of resolved comments")
    source: Optional[int] = Field(None, description="Source type of the attachment (numeric)")
    attachment_type: Optional[int] = Field(None, description="Type of the attachment (numeric)")
    orientation: Optional[str] = Field(None, description="Image orientation if applicable")
    parent_id: Optional[str] = Field(None, description="Parent task ID")
    deleted: Optional[bool] = Field(None, description="Whether the attachment is deleted")
    workspace_id: Optional[str] = Field(None, description="Workspace ID")
