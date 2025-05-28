"""Todoist entity schemas.

Based on the Todoist REST API reference, we define entity schemas for
Todoist objects, Projects, Sections, Tasks, and Comments.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity


class TodoistProjectEntity(ChunkEntity):
    """Schema for Todoist project entities."""

    name: str = Field(..., description="The name of the project")
    color: Optional[str] = Field(None, description="Color of the project (e.g., 'grey', 'blue')")
    comment_count: int = Field(0, description="Number of comments in the project")
    order: int = Field(0, description="Project order in the project list")
    is_shared: bool = Field(False, description="Whether the project is shared with others")
    is_favorite: bool = Field(False, description="Whether the project is marked as a favorite")
    is_inbox_project: bool = Field(False, description="Whether this is the Inbox project")
    is_team_inbox: bool = Field(False, description="Whether this is the team Inbox project")
    view_style: Optional[str] = Field(None, description="Project view style ('list' or 'board')")
    url: Optional[str] = Field(None, description="URL to access the project")
    parent_id: Optional[str] = Field(None, description="ID of the parent project if nested")


class TodoistSectionEntity(ChunkEntity):
    """Schema for Todoist section entities."""

    name: str = Field(..., description="The name of the section")
    project_id: str = Field(..., description="ID of the project this section belongs to")
    order: int = Field(0, description="Section order in the project")


class TodoistTaskEntity(ChunkEntity):
    """Schema for Todoist task entities."""

    content: str = Field(..., description="The task content/title")
    description: Optional[str] = Field(
        None, description="Optional detailed description of the task"
    )
    comment_count: int = Field(0, description="Number of comments on the task")
    is_completed: bool = Field(False, description="Whether the task is completed")
    labels: List[str] = Field(
        default_factory=list, description="List of label names attached to the task"
    )
    order: int = Field(0, description="Task order in the project or section")
    priority: int = Field(1, description="Task priority (1-4, 4 is highest)", ge=1, le=4)
    project_id: Optional[str] = Field(None, description="ID of the project this task belongs to")
    section_id: Optional[str] = Field(None, description="ID of the section this task belongs to")
    parent_id: Optional[str] = Field(None, description="ID of the parent task if subtask")
    creator_id: Optional[str] = Field(None, description="ID of the user who created the task")
    created_at: Optional[datetime] = Field(None, description="When the task was created")
    assignee_id: Optional[str] = Field(None, description="ID of the user assigned to the task")
    assigner_id: Optional[str] = Field(None, description="ID of the user who assigned the task")

    # Flatten out the 'due' object from the Todoist API
    due_date: Optional[str] = Field(None, description="Due date in YYYY-MM-DD format")
    due_datetime: Optional[datetime] = Field(None, description="Due date and time")
    due_string: Optional[str] = Field(
        None, description="Original due date string (e.g., 'tomorrow')"
    )
    due_is_recurring: bool = Field(False, description="Whether the task is recurring")
    due_timezone: Optional[str] = Field(None, description="Timezone for the due date")

    # Deadline information
    deadline_date: Optional[str] = Field(None, description="Deadline date in YYYY-MM-DD format")

    # Duration information
    duration_amount: Optional[int] = Field(None, description="Duration amount")
    duration_unit: Optional[str] = Field(None, description="Duration unit ('minute' or 'day')")

    url: Optional[str] = Field(None, description="URL to access the task")


class TodoistCommentEntity(ChunkEntity):
    """Schema for Todoist comment entities."""

    task_id: str = Field(..., description="ID of the task this comment belongs to")
    content: Optional[str] = Field(None, description="The comment content")
    posted_at: datetime = Field(..., description="When the comment was posted")
