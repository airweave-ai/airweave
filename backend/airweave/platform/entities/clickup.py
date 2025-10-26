"""ClickUp entity schemas."""

from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


class ClickUpWorkspaceEntity(BaseEntity):
    """Schema for ClickUp workspace entities.

    Reference:
        https://clickup.com/api/clickupreference/operation/GetAuthorizedTeams/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the workspace ID)
    # - breadcrumbs (empty - workspaces are top-level)
    # - name (from workspace name)
    # - created_at (None - workspaces don't have creation timestamp in API)
    # - updated_at (None - workspaces don't have update timestamp in API)

    # API fields
    color: Optional[str] = AirweaveField(None, description="Workspace color", embeddable=False)
    avatar: Optional[str] = AirweaveField(
        None, description="Workspace avatar URL", embeddable=False
    )
    members: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="List of workspace members", embeddable=True
    )


class ClickUpSpaceEntity(BaseEntity):
    """Schema for ClickUp space entities.

    Reference:
        https://clickup.com/api/clickupreference/operation/GetSpaces/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the space ID)
    # - breadcrumbs (workspace breadcrumb)
    # - name (from space name)
    # - created_at (None - spaces don't have creation timestamp in API)
    # - updated_at (None - spaces don't have update timestamp in API)

    # API fields
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


class ClickUpFolderEntity(BaseEntity):
    """Schema for ClickUp folder entities.

    Reference:
        https://clickup.com/api/clickupreference/operation/GetFolders/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the folder ID)
    # - breadcrumbs (workspace and space breadcrumbs)
    # - name (from folder name)
    # - created_at (None - folders don't have creation timestamp in API)
    # - updated_at (None - folders don't have update timestamp in API)

    # API fields
    hidden: bool = AirweaveField(
        False, description="Whether the folder is hidden", embeddable=False
    )
    space_id: str = AirweaveField(..., description="Parent space ID", embeddable=False)
    task_count: Optional[int] = AirweaveField(
        None, description="Number of tasks in the folder", embeddable=False
    )


class ClickUpListEntity(BaseEntity):
    """Schema for ClickUp list entities.

    Reference:
        https://clickup.com/api/clickupreference/operation/GetLists/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the list ID)
    # - breadcrumbs (workspace, space, and optionally folder breadcrumbs)
    # - name (from list name)
    # - created_at (None - lists don't have creation timestamp in API)
    # - updated_at (None - lists don't have update timestamp in API)

    # API fields
    folder_id: Optional[str] = AirweaveField(
        None, description="Parent folder ID (optional)", embeddable=False
    )
    space_id: str = AirweaveField(..., description="Parent space ID", embeddable=False)
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


class ClickUpTaskEntity(BaseEntity):
    """Schema for ClickUp task entities.

    Reference:
        https://clickup.com/api/clickupreference/operation/GetTasks/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the task ID)
    # - breadcrumbs (workspace, space, folder, and list breadcrumbs)
    # - name (from task name)
    # - created_at (None - tasks don't have creation timestamp in API)
    # - updated_at (None - tasks don't have update timestamp in API)

    # API fields
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
    folder_id: str = AirweaveField(..., description="Parent folder ID", embeddable=False)
    space_id: str = AirweaveField(..., description="Parent space ID", embeddable=False)
    url: str = AirweaveField(..., description="Task URL", embeddable=False)
    description: Optional[str] = AirweaveField(
        None, description="Task description", embeddable=True
    )
    parent: Optional[str] = AirweaveField(
        None, description="Parent task ID if this is a subtask", embeddable=False
    )


class ClickUpCommentEntity(BaseEntity):
    """Schema for ClickUp comment entities.

    Reference:
        https://clickup.com/api/clickupreference/operation/GetTaskComments/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the comment ID)
    # - breadcrumbs (workspace, space, folder, list, and task breadcrumbs)
    # - name (from text content preview)
    # - created_at (from date timestamp)
    # - updated_at (None - comments don't have update timestamp in API)

    # API fields
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


class ClickUpSubtaskEntity(BaseEntity):
    """Schema for ClickUp subtask entities.

    Supports nested subtasks where subtasks can have their own subtasks.
    The parent_task_id points to the immediate parent (task or subtask).

    Reference:
        https://clickup.com/api/clickupreference/operation/GetTasks/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the subtask ID)
    # - breadcrumbs (includes all parent tasks in the chain)
    # - name (from subtask name)
    # - created_at (None - subtasks don't have creation timestamp in API)
    # - updated_at (None - subtasks don't have update timestamp in API)

    # API fields
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


class ClickUpFileEntity(FileEntity):
    """Schema for ClickUp file attachments.

    Represents files attached to ClickUp tasks.

    Reference:
        https://api.clickup.com/api/v2/task/{task_id}
    """

    # Base fields are inherited from BaseEntity:
    # - entity_id (the attachment ID)
    # - breadcrumbs (workspace, space, folder, list, and task breadcrumbs)
    # - name (from title or filename)
    # - created_at (from date timestamp)
    # - updated_at (None - attachments don't have update timestamp)

    # File fields are inherited from FileEntity:
    # - url (download URL)
    # - size (file size in bytes)
    # - file_type (determined from mime_type or extension)
    # - mime_type
    # - local_path (set after download)

    # API fields (ClickUp-specific)
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
        None, description="URL for small thumbnail", embeddable=False
    )
    thumbnail_medium: Optional[str] = AirweaveField(
        None, description="URL for medium thumbnail", embeddable=False
    )
    thumbnail_large: Optional[str] = AirweaveField(
        None, description="URL for large thumbnail", embeddable=False
    )
    is_folder: Optional[bool] = AirweaveField(
        None, description="Whether this is a folder attachment", embeddable=False
    )
    total_comments: Optional[int] = AirweaveField(
        None, description="Number of comments on this attachment", embeddable=False
    )
    url_w_query: Optional[str] = AirweaveField(
        None, description="URL with query parameters", embeddable=False
    )
    url_w_host: Optional[str] = AirweaveField(
        None, description="URL with host parameters", embeddable=False
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
