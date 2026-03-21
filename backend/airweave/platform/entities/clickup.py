"""ClickUp entity schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb, FileEntity


def _parse_clickup_ts(timestamp: Any) -> Optional[datetime]:
    """Parse ClickUp millisecond-epoch timestamp to datetime."""
    if not timestamp:
        return None
    try:
        ts = int(timestamp)
        if ts > 1e10:
            return datetime.fromtimestamp(ts / 1000)
        return datetime.fromtimestamp(ts)
    except (ValueError, TypeError):
        return None


def _extract_comment_text(comment_content: Any) -> str:
    """Extract plain text from ClickUp's nested comment structure."""
    if isinstance(comment_content, list):
        parts = []
        for part in comment_content:
            if isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)
        return " ".join(parts)
    if isinstance(comment_content, str):
        return comment_content
    return ""


class ClickUpWorkspaceEntity(BaseEntity):
    """Schema for ClickUp workspace entities."""

    workspace_id: str = AirweaveField(..., description="Workspace ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Workspace name", is_name=True, embeddable=True)
    color: Optional[str] = AirweaveField(None, description="Workspace color", embeddable=False)
    avatar: Optional[str] = AirweaveField(
        None, description="Workspace avatar URL", embeddable=False, unhashable=True
    )
    members: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="List of workspace members", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this workspace."""
        return f"https://app.clickup.com/{self.workspace_id}"


class ClickUpSpaceEntity(BaseEntity):
    """Schema for ClickUp space entities."""

    space_id: str = AirweaveField(..., description="Space ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Space name", is_name=True, embeddable=True)
    workspace_id: str = AirweaveField(..., description="Parent workspace ID", embeddable=False)
    private: bool = AirweaveField(
        False, description="Whether the space is private", embeddable=False
    )
    status: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Space status configuration", embeddable=True
    )
    multiple_assignees: bool = AirweaveField(
        False, description="Whether multiple assignees are allowed", embeddable=False
    )
    features: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Space features configuration", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the ClickUp web URL for this space."""
        return f"https://app.clickup.com/{self.workspace_id}/v/b/{self.space_id}"


class ClickUpFolderEntity(BaseEntity):
    """Schema for ClickUp folder entities."""

    folder_id: str = AirweaveField(..., description="Folder ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Folder name", is_name=True, embeddable=True)
    workspace_id: str = AirweaveField(..., description="Parent workspace ID", embeddable=False)
    space_id: str = AirweaveField(..., description="Parent space ID", embeddable=False)
    hidden: bool = AirweaveField(
        False, description="Whether the folder is hidden", embeddable=False
    )
    task_count: Optional[int] = AirweaveField(
        None, description="Number of tasks in the folder", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the ClickUp web URL for this folder."""
        return f"https://app.clickup.com/{self.workspace_id}/v/f/{self.folder_id}"


class ClickUpListEntity(BaseEntity):
    """Schema for ClickUp list entities."""

    list_id: str = AirweaveField(..., description="List ID", is_entity_id=True)
    name: str = AirweaveField(..., description="List name", is_name=True, embeddable=True)
    workspace_id: str = AirweaveField(..., description="Parent workspace ID", embeddable=False)
    space_id: str = AirweaveField(..., description="Parent space ID", embeddable=False)
    folder_id: Optional[str] = AirweaveField(
        None, description="Parent folder ID (optional)", embeddable=False
    )
    content: Optional[str] = AirweaveField(
        None, description="List content/description", embeddable=True
    )
    status: Optional[Dict[str, Any]] = AirweaveField(
        None, description="List status configuration", embeddable=True
    )
    priority: Optional[Dict[str, Any]] = AirweaveField(
        None, description="List priority configuration", embeddable=True
    )
    assignee: Optional[str] = AirweaveField(
        None, description="List assignee username", embeddable=True
    )
    task_count: Optional[int] = AirweaveField(
        None, description="Number of tasks in the list", embeddable=False
    )
    due_date: Optional[Any] = AirweaveField(None, description="List due date", embeddable=False)
    start_date: Optional[Any] = AirweaveField(None, description="List start date", embeddable=False)
    folder_name: Optional[str] = AirweaveField(
        None, description="Parent folder name", embeddable=True
    )
    space_name: str = AirweaveField(..., description="Parent space name", embeddable=True)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this list."""
        return f"https://app.clickup.com/{self.workspace_id}/v/li/{self.list_id}"


class ClickUpTaskEntity(BaseEntity):
    """Schema for ClickUp task entities."""

    task_id: str = AirweaveField(..., description="Task ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Task name", is_name=True, embeddable=True)
    created_at: Optional[Any] = AirweaveField(
        None, description="Task creation timestamp", is_created_at=True
    )
    updated_at: Optional[Any] = AirweaveField(
        None, description="Task update timestamp", is_updated_at=True
    )
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
    due_date: Optional[Any] = AirweaveField(None, description="Task due date", embeddable=True)
    start_date: Optional[Any] = AirweaveField(None, description="Task start date", embeddable=True)
    time_estimate: Optional[int] = AirweaveField(
        None, description="Estimated time in milliseconds", embeddable=False
    )
    time_spent: Optional[int] = AirweaveField(
        None, description="Time spent in milliseconds", embeddable=False
    )
    custom_fields: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="List of custom fields", embeddable=True
    )
    list_id: str = AirweaveField(..., description="Parent list ID", embeddable=False)
    folder_id: Optional[str] = AirweaveField(None, description="Parent folder ID", embeddable=False)
    space_id: str = AirweaveField(..., description="Parent space ID", embeddable=False)
    workspace_id: str = AirweaveField(..., description="Parent workspace ID", embeddable=False)
    url: str = AirweaveField(..., description="Task URL", embeddable=False, unhashable=True)
    description: Optional[str] = AirweaveField(
        None, description="Task description", embeddable=True
    )
    parent: Optional[str] = AirweaveField(
        None, description="Parent task ID if this is a subtask", embeddable=False
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        list_meta: Dict[str, Any],
        breadcrumbs: List[Breadcrumb],
    ) -> ClickUpTaskEntity:
        """Build from a ClickUp API task object (top-level, non-subtask)."""
        return cls(
            task_id=data["id"],
            breadcrumbs=breadcrumbs,
            name=data["name"],
            created_at=_parse_clickup_ts(data.get("date_created")),
            updated_at=_parse_clickup_ts(data.get("date_updated")),
            status=data.get("status", {}),
            priority=data.get("priority"),
            assignees=data.get("assignees", []),
            tags=data.get("tags", []),
            due_date=data.get("due_date"),
            start_date=data.get("start_date"),
            time_estimate=data.get("time_estimate"),
            time_spent=data.get("time_spent"),
            custom_fields=data.get("custom_fields", []),
            list_id=list_meta["id"],
            folder_id=list_meta.get("folder_id"),
            space_id=list_meta.get("space_id"),
            workspace_id=list_meta.get("workspace_id"),
            url=data.get("url") or f"https://app.clickup.com/t/{data['id']}",
            description=data.get("description", ""),
            parent=data.get("parent"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the ClickUp web URL for this task."""
        return self.url


class ClickUpCommentEntity(BaseEntity):
    """Schema for ClickUp comment entities."""

    comment_id: str = AirweaveField(..., description="Comment ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Comment preview", is_name=True, embeddable=True)
    created_at: Optional[Any] = AirweaveField(
        None, description="When the comment was created", is_created_at=True
    )
    task_id: str = AirweaveField(..., description="Parent task ID", embeddable=False)
    user: Dict[str, Any] = AirweaveField(
        ..., description="Comment author information", embeddable=True
    )
    text_content: Optional[str] = AirweaveField(
        None, description="Comment text content", embeddable=True
    )
    resolved: bool = AirweaveField(
        False, description="Whether the comment is resolved", embeddable=False
    )
    assignee: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Comment assignee information", embeddable=True
    )
    assigned_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who assigned the comment", embeddable=True
    )
    reactions: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="List of reactions to the comment", embeddable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        task_id: str,
        breadcrumbs: List[Breadcrumb],
    ) -> ClickUpCommentEntity:
        """Build from a ClickUp API comment object."""
        text = _extract_comment_text(data.get("comment", []))
        preview = text[:50] + "..." if len(text) > 50 else text
        name = preview or f"Comment {data['id']}"

        return cls(
            comment_id=data["id"],
            breadcrumbs=breadcrumbs,
            name=name,
            created_at=_parse_clickup_ts(data.get("date") or data.get("date_created")),
            task_id=task_id,
            user=data.get("user", {}),
            text_content=text,
            resolved=data.get("resolved", False),
            assignee=data.get("assignee"),
            assigned_by=data.get("assigned_by"),
            reactions=data.get("reactions", []),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this comment."""
        return f"https://app.clickup.com/t/{self.task_id}"


class ClickUpSubtaskEntity(BaseEntity):
    """Schema for ClickUp subtask entities."""

    subtask_id: str = AirweaveField(..., description="Subtask ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Subtask name", is_name=True, embeddable=True)
    created_at: Optional[Any] = AirweaveField(
        None, description="Subtask creation timestamp", is_created_at=True
    )
    updated_at: Optional[Any] = AirweaveField(
        None, description="Subtask update timestamp", is_updated_at=True
    )
    parent_task_id: str = AirweaveField(
        ..., description="Immediate parent task/subtask ID", embeddable=False
    )
    status: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Subtask status configuration", embeddable=True
    )
    assignees: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="List of subtask assignees", embeddable=True
    )
    due_date: Optional[Any] = AirweaveField(None, description="Subtask due date", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Subtask description", embeddable=True
    )
    nesting_level: Optional[int] = AirweaveField(
        None,
        description="Nesting level (1 = direct subtask, 2 = nested subtask, etc.)",
        embeddable=False,
    )
    url: Optional[str] = AirweaveField(
        None, description="Subtask URL", embeddable=False, unhashable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        breadcrumbs: List[Breadcrumb],
        nesting_level: int,
    ) -> ClickUpSubtaskEntity:
        """Build from a ClickUp API task object that has a parent (subtask)."""
        return cls(
            subtask_id=data["id"],
            breadcrumbs=breadcrumbs,
            name=data["name"],
            created_at=_parse_clickup_ts(data.get("date_created")),
            updated_at=_parse_clickup_ts(data.get("date_updated")),
            parent_task_id=data.get("parent", ""),
            status=data.get("status", {}),
            assignees=data.get("assignees", []),
            due_date=data.get("due_date"),
            description=data.get("description", ""),
            nesting_level=nesting_level,
            url=data.get("url") or f"https://app.clickup.com/t/{data['id']}",
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this subtask."""
        return self.url or f"https://app.clickup.com/t/{self.subtask_id}"


class ClickUpFileEntity(FileEntity):
    """Schema for ClickUp file attachments."""

    attachment_id: str = AirweaveField(..., description="Attachment ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Attachment name", is_name=True, embeddable=True)
    task_id: str = AirweaveField(
        ..., description="ID of the task this file is attached to", embeddable=False
    )
    task_name: str = AirweaveField(
        ..., description="Name of the task this file is attached to", embeddable=True
    )
    version: Optional[int] = AirweaveField(
        None, description="Version number of the attachment", embeddable=False
    )
    title: Optional[str] = AirweaveField(
        None, description="Original title/name of the attachment", embeddable=True
    )
    extension: Optional[str] = AirweaveField(None, description="File extension", embeddable=False)
    hidden: bool = AirweaveField(
        False, description="Whether the attachment is hidden", embeddable=False
    )
    parent: Optional[str] = AirweaveField(
        None, description="Parent attachment ID if applicable", embeddable=False
    )
    thumbnail_small: Optional[str] = AirweaveField(
        None, description="URL for small thumbnail", embeddable=False, unhashable=True
    )
    thumbnail_medium: Optional[str] = AirweaveField(
        None, description="URL for medium thumbnail", embeddable=False, unhashable=True
    )
    thumbnail_large: Optional[str] = AirweaveField(
        None, description="URL for large thumbnail", embeddable=False, unhashable=True
    )
    is_folder: Optional[bool] = AirweaveField(
        None, description="Whether this is a folder attachment", embeddable=False
    )
    total_comments: Optional[int] = AirweaveField(
        None, description="Number of comments on this attachment", embeddable=False
    )
    url_w_query: Optional[str] = AirweaveField(
        None, description="URL with query parameters", embeddable=False, unhashable=True
    )
    url_w_host: Optional[str] = AirweaveField(
        None, description="URL with host parameters", embeddable=False, unhashable=True
    )
    email_data: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Email data if attachment is from email", embeddable=False
    )
    user: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who uploaded the attachment", embeddable=True
    )
    resolved: Optional[bool] = AirweaveField(
        None, description="Whether the attachment is resolved", embeddable=False
    )
    resolved_comments: Optional[int] = AirweaveField(
        None, description="Number of resolved comments", embeddable=False
    )
    source: Optional[int] = AirweaveField(
        None, description="Source type of the attachment (numeric)", embeddable=False
    )
    attachment_type: Optional[int] = AirweaveField(
        None, description="Type of the attachment (numeric)", embeddable=False
    )
    orientation: Optional[str] = AirweaveField(
        None, description="Image orientation if applicable", embeddable=False
    )
    parent_id: Optional[str] = AirweaveField(None, description="Parent task ID", embeddable=False)
    deleted: Optional[bool] = AirweaveField(
        None, description="Whether the attachment is deleted", embeddable=False
    )
    workspace_id: Optional[str] = AirweaveField(None, description="Workspace ID", embeddable=False)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this attachment."""
        return f"https://app.clickup.com/t/{self.task_id}"
