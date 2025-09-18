"""ClickUp entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import ChunkEntity


class ClickUpWorkspaceEntity(ChunkEntity):
    """Schema for ClickUp workspace (team) entities."""

    name: str = AirweaveField(..., description="The name of the workspace", embeddable=True)
    clickup_id: str = Field(..., description="ClickUp's unique identifier for the workspace")
    color: Optional[str] = Field(None, description="Color theme of the workspace")
    avatar: Optional[str] = Field(None, description="URL of the workspace avatar image")
    
    # Member information
    members: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="List of workspace members",
        embeddable=True
    )


class ClickUpSpaceEntity(ChunkEntity):
    """Schema for ClickUp space entities."""

    name: str = AirweaveField(..., description="The name of the space", embeddable=True)
    clickup_id: str = Field(..., description="ClickUp's unique identifier for the space")
    workspace_id: str = Field(..., description="ID of the workspace this space belongs to")
    workspace_name: str = AirweaveField(
        ..., description="Name of the workspace this space belongs to", embeddable=True
    )
    
    color: Optional[str] = Field(None, description="Color theme of the space")
    private: bool = Field(False, description="Whether the space is private")
    avatar: Optional[str] = Field(None, description="URL of the space avatar image")
    
    # Feature settings
    multiple_assignees: bool = Field(False, description="Whether multiple assignees are enabled")
    features: Dict[str, Any] = Field(
        default_factory=dict, description="Feature settings for the space"
    )
    
    # Member information
    members: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="List of space members",
        embeddable=True
    )


class ClickUpFolderEntity(ChunkEntity):
    """Schema for ClickUp folder entities."""

    name: str = AirweaveField(..., description="The name of the folder", embeddable=True)
    clickup_id: str = Field(..., description="ClickUp's unique identifier for the folder")
    space_id: str = Field(..., description="ID of the space this folder belongs to")
    space_name: str = AirweaveField(
        ..., description="Name of the space this folder belongs to", embeddable=True
    )
    workspace_id: str = Field(..., description="ID of the workspace this folder belongs to")
    
    orderindex: int = Field(0, description="Order index of the folder")
    override_statuses: bool = Field(False, description="Whether folder overrides space statuses")
    hidden: bool = Field(False, description="Whether the folder is hidden")
    
    # Status configuration
    statuses: List[Dict[str, Any]] = Field(
        default_factory=list, description="Status configurations for the folder"
    )


class ClickUpListEntity(ChunkEntity):
    """Schema for ClickUp list entities."""

    name: str = AirweaveField(..., description="The name of the list", embeddable=True)
    clickup_id: str = Field(..., description="ClickUp's unique identifier for the list")
    folder_id: Optional[str] = Field(None, description="ID of the folder this list belongs to")
    folder_name: Optional[str] = AirweaveField(
        None, description="Name of the folder this list belongs to", embeddable=True
    )
    space_id: str = Field(..., description="ID of the space this list belongs to")
    space_name: str = AirweaveField(
        ..., description="Name of the space this list belongs to", embeddable=True
    )
    workspace_id: str = Field(..., description="ID of the workspace this list belongs to")
    
    content: Optional[str] = AirweaveField(
        None, description="Description content of the list", embeddable=True
    )
    orderindex: int = Field(0, description="Order index of the list")
    priority: Optional[Dict[str, Any]] = Field(None, description="Priority settings for the list")
    assignee: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Default assignee for tasks in this list", embeddable=True
    )
    task_count: Optional[int] = Field(None, description="Number of tasks in the list")
    due_date: Optional[str] = AirweaveField(
        None, description="Due date for the list", embeddable=True
    )
    due_date_time: bool = Field(False, description="Whether due date includes time")
    start_date: Optional[str] = AirweaveField(
        None, description="Start date for the list", embeddable=True
    )
    start_date_time: bool = Field(False, description="Whether start date includes time")
    archived: bool = Field(False, description="Whether the list is archived")
    
    # Status configuration
    statuses: List[Dict[str, Any]] = Field(
        default_factory=list, description="Status configurations for the list"
    )


class ClickUpTaskEntity(ChunkEntity):
    """Schema for ClickUp task entities."""

    name: str = AirweaveField(..., description="The name of the task", embeddable=True)
    clickup_id: str = Field(..., description="ClickUp's unique identifier for the task")
    custom_id: Optional[str] = AirweaveField(
        None, description="Custom ID for the task", embeddable=True
    )
    
    # Hierarchy information
    list_id: str = Field(..., description="ID of the list this task belongs to")
    list_name: str = AirweaveField(
        ..., description="Name of the list this task belongs to", embeddable=True
    )
    folder_id: Optional[str] = Field(None, description="ID of the folder this task belongs to")
    folder_name: Optional[str] = AirweaveField(
        None, description="Name of the folder this task belongs to", embeddable=True
    )
    space_id: str = Field(..., description="ID of the space this task belongs to")
    space_name: str = AirweaveField(
        ..., description="Name of the space this task belongs to", embeddable=True
    )
    workspace_id: str = Field(..., description="ID of the workspace this task belongs to")
    
    # Content and description
    description: Optional[str] = AirweaveField(
        None, description="Description content of the task", embeddable=True
    )
    text_content: Optional[str] = AirweaveField(
        None, description="Plain text content of the task description", embeddable=True
    )
    
    # Status and progress
    status: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Current status of the task", embeddable=True
    )
    priority: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Priority level of the task", embeddable=True
    )
    
    # Assignment and collaboration
    assignees: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Users assigned to this task",
        embeddable=True
    )
    watchers: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Users watching this task",
        embeddable=True
    )
    creator: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who created the task", embeddable=True
    )
    
    # Temporal information
    date_created: Optional[datetime] = AirweaveField(
        None, description="When the task was created", is_created_at=True
    )
    date_updated: Optional[datetime] = AirweaveField(
        None, description="When the task was last updated", is_updated_at=True
    )
    date_closed: Optional[datetime] = AirweaveField(
        None, description="When the task was closed"
    )
    due_date: Optional[str] = AirweaveField(
        None, description="Due date for the task", embeddable=True
    )
    start_date: Optional[str] = AirweaveField(
        None, description="Start date for the task", embeddable=True
    )
    
    # Time tracking
    time_estimate: Optional[int] = Field(None, description="Estimated time in milliseconds")
    time_spent: Optional[int] = Field(None, description="Time spent in milliseconds")
    
    # Organization
    orderindex: str = Field("", description="Order index for sorting")
    archived: bool = Field(False, description="Whether the task is archived")
    
    # Custom fields and tags
    custom_fields: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Custom field values for the task",
        embeddable=True
    )
    tags: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Tags applied to the task",
        embeddable=True
    )
    
    # Relationships
    parent: Optional[str] = Field(None, description="ID of parent task if this is a subtask")
    dependencies: List[Dict[str, Any]] = Field(
        default_factory=list, description="Task dependencies"
    )
    linked_tasks: List[Dict[str, Any]] = Field(
        default_factory=list, description="Tasks linked to this task"
    )
    
    # Additional metadata
    url: Optional[str] = Field(None, description="URL to view the task in ClickUp")


class ClickUpCommentEntity(ChunkEntity):
    """Schema for ClickUp comment entities."""

    comment_text: str = AirweaveField(
        ..., description="The text content of the comment", embeddable=True
    )
    clickup_id: str = Field(..., description="ClickUp's unique identifier for the comment")
    
    # Parent task information
    task_id: str = Field(..., description="ID of the task this comment belongs to")
    task_name: str = AirweaveField(
        ..., description="Name of the task this comment belongs to", embeddable=True
    )
    
    # Hierarchy context for better search
    list_id: str = Field(..., description="ID of the list the parent task belongs to")
    list_name: str = AirweaveField(
        ..., description="Name of the list the parent task belongs to", embeddable=True
    )
    space_id: str = Field(..., description="ID of the space the parent task belongs to")
    space_name: str = AirweaveField(
        ..., description="Name of the space the parent task belongs to", embeddable=True
    )
    workspace_id: str = Field(..., description="ID of the workspace the parent task belongs to")
    
    # Author information
    user: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who created the comment", embeddable=True
    )
    
    # Temporal information
    date: Optional[datetime] = AirweaveField(
        None, description="When the comment was created", is_created_at=True
    )
    
    # Comment metadata
    comment_type: Optional[str] = Field(None, description="Type of comment")
    resolved: bool = Field(False, description="Whether the comment thread is resolved")
    
    # Threading
    parent_comment_id: Optional[str] = Field(
        None, description="ID of parent comment if this is a reply"
    )
    replies: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Replies to this comment",
        embeddable=True
    )