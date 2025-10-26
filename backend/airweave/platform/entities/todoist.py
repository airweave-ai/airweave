"""Todoist entity schemas.

Based on the Todoist REST API reference, we define entity schemas for
Todoist objects, Projects, Sections, Tasks, and Comments.
"""

from datetime import datetime
from typing import List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import 


class TodoistProjectEntity(BaseEntity):
    """Schema for Todoist project entities."""

    name: str = AirweaveField(..., description="The name of the project", embeddable=True)
    color: Optional[str] = AirweaveField(
        None, description="Color of the project (e.g., 'grey', 'blue')"
    )
    comment_count: int = AirweaveField(0, description="Number of comments in the project")
    order: int = AirweaveField(0, description="Project order in the project list")
    is_shared: bool = AirweaveField(False, description="Whether the project is shared with others")
    is_favorite: bool = AirweaveField(
        False, description="Whether the project is marked as a favorite"
    )
    is_inbox_project: bool = AirweaveField(False, description="Whether this is the Inbox project")
    is_team_inbox: bool = AirweaveField(False, description="Whether this is the team Inbox project")
    view_style: Optional[str] = AirweaveField(
        None, description="Project view style ('list' or 'board')"
    )
    url: Optional[str] = AirweaveField(None, description="URL to access the project")
    parent_id: Optional[str] = AirweaveField(None, description="ID of the parent project if nested")


class TodoistSectionEntity(BaseEntity):
    """Schema for Todoist section entities."""

    name: str = AirweaveField(..., description="The name of the section", embeddable=True)
    project_id: str = AirweaveField(..., description="ID of the project this section belongs to")
    order: int = AirweaveField(0, description="Section order in the project")


class TodoistTaskEntity(BaseEntity):
    """Schema for Todoist task entities."""

    content: str = AirweaveField(..., description="The task content/title", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Optional detailed description of the task", embeddable=True
    )
    comment_count: int = AirweaveField(0, description="Number of comments on the task")
    is_completed: bool = AirweaveField(False, description="Whether the task is completed")
    labels: List[str] = AirweaveField(
        default_factory=list,
        description="List of label names attached to the task",
        embeddable=True,
    )
    order: int = AirweaveField(0, description="Task order in the project or section")
    priority: int = AirweaveField(1, description="Task priority (1-4, 4 is highest)", ge=1, le=4)
    project_id: Optional[str] = AirweaveField(
        None, description="ID of the project this task belongs to"
    )
    section_id: Optional[str] = AirweaveField(
        None, description="ID of the section this task belongs to"
    )
    parent_id: Optional[str] = AirweaveField(None, description="ID of the parent task if subtask")
    creator_id: Optional[str] = AirweaveField(
        None, description="ID of the user who created the task"
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the task was created", is_created_at=True
    )
    assignee_id: Optional[str] = AirweaveField(
        None, description="ID of the user assigned to the task"
    )
    assigner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who assigned the task"
    )

    # Flatten out the 'due' object from the Todoist API
    due_date: Optional[str] = AirweaveField(
        None, description="Due date in YYYY-MM-DD format", embeddable=True
    )
    due_datetime: Optional[datetime] = AirweaveField(
        None, description="Due date and time", embeddable=True
    )
    due_string: Optional[str] = AirweaveField(
        None, description="Original due date string (e.g., 'tomorrow')", embeddable=True
    )
    due_is_recurring: bool = AirweaveField(False, description="Whether the task is recurring")
    due_timezone: Optional[str] = AirweaveField(None, description="Timezone for the due date")

    # Deadline information
    deadline_date: Optional[str] = AirweaveField(
        None, description="Deadline date in YYYY-MM-DD format"
    )

    # Duration information
    duration_amount: Optional[int] = AirweaveField(None, description="Duration amount")
    duration_unit: Optional[str] = AirweaveField(
        None, description="Duration unit ('minute' or 'day')"
    )

    url: Optional[str] = AirweaveField(None, description="URL to access the task")


class TodoistCommentEntity(BaseEntity):
    """Schema for Todoist comment entities."""

    task_id: str = AirweaveField(..., description="ID of the task this comment belongs to")
    content: Optional[str] = AirweaveField(None, description="The comment content", embeddable=True)
    posted_at: datetime = AirweaveField(
        ..., description="When the comment was posted", is_created_at=True
    )
