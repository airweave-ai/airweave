"""Todoist entity schemas.

Based on the Todoist REST API reference, we define entity schemas for
Todoist objects, Projects, Sections, Tasks, and Comments.
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class TodoistProjectEntity(BaseEntity):
    """Schema for Todoist project entities.

    Reference:
        https://developer.todoist.com/api/v1/#tag/Projects
    """

    project_id: str = AirweaveField(..., description="Todoist project ID.", is_entity_id=True)
    project_name: str = AirweaveField(
        ..., description="Display name of the project.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the project snapshot was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the project snapshot was updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to open the project in Todoist.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    color: Optional[str] = AirweaveField(
        None, description="Color of the project (e.g., 'grey', 'blue')", embeddable=False
    )
    order: int = AirweaveField(0, description="Project order in the project list", embeddable=False)
    is_shared: bool = AirweaveField(
        False, description="Whether the project is shared with others", embeddable=False
    )
    is_favorite: bool = AirweaveField(
        False, description="Whether the project is marked as a favorite", embeddable=False
    )
    is_inbox_project: bool = AirweaveField(
        False, description="Whether this is the Inbox project", embeddable=False
    )
    is_team_inbox: bool = AirweaveField(
        False, description="Whether this is the team Inbox project", embeddable=False
    )
    view_style: Optional[str] = AirweaveField(
        None, description="Project view style ('list' or 'board')", embeddable=False
    )
    url: Optional[str] = AirweaveField(
        None, description="URL to access the project", embeddable=False, unhashable=True
    )
    parent_id: Optional[str] = AirweaveField(
        None, description="ID of the parent project if nested", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Todoist project URL."""
        return self.web_url_value or self.url or ""


class TodoistSectionEntity(BaseEntity):
    """Schema for Todoist section entities.

    Reference:
        https://developer.todoist.com/api/v1/#tag/Sections
    """

    section_id: str = AirweaveField(..., description="Todoist section ID.", is_entity_id=True)
    section_name: str = AirweaveField(
        ..., description="Display name of the section.", embeddable=True, is_name=True
    )
    project_id: str = AirweaveField(
        ..., description="ID of the project this section belongs to", embeddable=False
    )
    order: int = AirweaveField(0, description="Section order in the project", embeddable=False)


class TodoistTaskEntity(BaseEntity):
    """Schema for Todoist task entities.

    Reference:
        https://developer.todoist.com/api/v1/#tag/Tasks
    """

    task_id: str = AirweaveField(..., description="Todoist task ID.", is_entity_id=True)
    content: str = AirweaveField(
        ..., description="The task content/title", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the task was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="Last update timestamp for the task.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to open the task in Todoist.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    description: Optional[str] = AirweaveField(
        None, description="Optional detailed description of the task", embeddable=True
    )
    is_completed: bool = AirweaveField(
        False, description="Whether the task is completed", embeddable=True
    )
    completed_at: Optional[str] = AirweaveField(
        None, description="Timestamp when the task was completed (ISO 8601)", embeddable=False
    )
    labels: List[str] = AirweaveField(
        default_factory=list,
        description="List of label names attached to the task",
        embeddable=True,
    )
    order: int = AirweaveField(
        0, description="Task order in the project or section", embeddable=False
    )
    priority: int = AirweaveField(
        1, description="Task priority (1-4, 4 is highest)", ge=1, le=4, embeddable=True
    )
    project_id: Optional[str] = AirweaveField(
        None, description="ID of the project this task belongs to", embeddable=False
    )
    section_id: Optional[str] = AirweaveField(
        None, description="ID of the section this task belongs to", embeddable=False
    )
    parent_id: Optional[str] = AirweaveField(
        None, description="ID of the parent task if subtask", embeddable=False
    )
    creator_id: Optional[str] = AirweaveField(
        None, description="ID of the user who created the task", embeddable=False
    )
    assignee_id: Optional[str] = AirweaveField(
        None, description="ID of the user assigned to the task", embeddable=False
    )
    assigner_id: Optional[str] = AirweaveField(
        None, description="ID of the user who assigned the task", embeddable=False
    )
    due_date: Optional[str] = AirweaveField(
        None, description="Due date in YYYY-MM-DD format", embeddable=True
    )
    due_datetime: Optional[Any] = AirweaveField(
        None, description="Due date and time", embeddable=True
    )
    due_string: Optional[str] = AirweaveField(
        None, description="Original due date string (e.g., 'tomorrow')", embeddable=True
    )
    due_is_recurring: bool = AirweaveField(
        False, description="Whether the task is recurring", embeddable=False
    )
    due_timezone: Optional[str] = AirweaveField(
        None, description="Timezone for the due date", embeddable=False
    )
    deadline_date: Optional[str] = AirweaveField(
        None, description="Deadline date in YYYY-MM-DD format", embeddable=False
    )
    duration_amount: Optional[int] = AirweaveField(
        None, description="Duration amount", embeddable=False
    )
    duration_unit: Optional[str] = AirweaveField(
        None, description="Duration unit ('minute' or 'day')", embeddable=False
    )
    url: Optional[str] = AirweaveField(
        None, description="URL to access the task", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Todoist task URL."""
        return self.web_url_value or self.url or ""


class TodoistCommentEntity(BaseEntity):
    """Schema for Todoist comment entities.

    Reference:
        https://developer.todoist.com/api/v1/#tag/Comments
    """

    comment_id: str = AirweaveField(..., description="Todoist comment ID.", is_entity_id=True)
    task_id: str = AirweaveField(
        ..., description="ID of the task this comment belongs to", embeddable=False
    )
    content: str = AirweaveField(
        ..., description="The comment content", embeddable=True, is_name=True
    )
    posted_at: datetime = AirweaveField(
        ..., description="When the comment was posted", is_created_at=True
    )
