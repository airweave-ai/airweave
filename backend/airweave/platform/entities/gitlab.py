"""GitLab entity schemas.

Based on the GitLab REST API, we define entity schemas for:
  • Projects (repositories)
  • Users
  • Repository Contents (files and directories)
  • Issues
  • Merge Requests

References:
  • https://docs.gitlab.com/ee/api/api_resources.html
  • https://docs.gitlab.com/ee/api/projects.html
  • https://docs.gitlab.com/ee/api/repository_files.html
"""

from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, CodeFileEntity


class GitLabProjectEntity(BaseEntity):
    """Schema for GitLab project (repository) entity.

    Reference:
        https://docs.gitlab.com/ee/api/projects.html
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the project ID)
    # - breadcrumbs (empty - projects are top-level)
    # - name (from project name)
    # - created_at (from created_at timestamp)
    # - updated_at (from last_activity_at timestamp)

    # API fields
    path: str = AirweaveField(..., description="Project path", embeddable=True)
    path_with_namespace: str = AirweaveField(
        ..., description="Full path with namespace", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Project description", embeddable=True
    )
    default_branch: Optional[str] = AirweaveField(
        None, description="Default branch of the repository", embeddable=True
    )
    visibility: str = AirweaveField(..., description="Project visibility level", embeddable=False)
    topics: List[str] = AirweaveField(
        default_factory=list, description="Project topics/tags", embeddable=True
    )
    namespace: Dict[str, Any] = AirweaveField(
        ..., description="Project namespace information", embeddable=True
    )
    star_count: int = AirweaveField(0, description="Number of stars", embeddable=False)
    forks_count: int = AirweaveField(0, description="Number of forks", embeddable=False)
    open_issues_count: int = AirweaveField(0, description="Number of open issues", embeddable=False)
    archived: bool = AirweaveField(
        False, description="Whether the project is archived", embeddable=False
    )
    empty_repo: bool = AirweaveField(
        False, description="Whether the repository is empty", embeddable=False
    )
    url: Optional[str] = AirweaveField(None, description="Web URL to the project", embeddable=False)


class GitLabUserEntity(BaseEntity):
    """Schema for GitLab user entity.

    Reference:
        https://docs.gitlab.com/ee/api/users.html
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the user ID)
    # - breadcrumbs (empty - users are top-level)
    # - name (from user's display name)
    # - created_at (from created_at timestamp)
    # - updated_at (None - users don't have update timestamp in API)

    # API fields
    username: str = AirweaveField(..., description="User's username", embeddable=True)
    state: str = AirweaveField(..., description="User account state", embeddable=False)
    avatar_url: Optional[str] = AirweaveField(
        None, description="User's avatar URL", embeddable=False
    )
    web_url: str = AirweaveField(..., description="User's profile URL", embeddable=False)
    bio: Optional[str] = AirweaveField(None, description="User's biography", embeddable=True)
    location: Optional[str] = AirweaveField(None, description="User's location", embeddable=True)
    public_email: Optional[str] = AirweaveField(
        None, description="User's public email", embeddable=True
    )
    organization: Optional[str] = AirweaveField(
        None, description="User's organization", embeddable=True
    )
    job_title: Optional[str] = AirweaveField(None, description="User's job title", embeddable=True)
    pronouns: Optional[str] = AirweaveField(None, description="User's pronouns", embeddable=True)


class GitLabDirectoryEntity(BaseEntity):
    """Schema for GitLab directory entity.

    Reference:
        https://docs.gitlab.com/ee/api/repositories.html
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (project_id/path)
    # - breadcrumbs (project and parent directory breadcrumbs)
    # - name (directory name from path)
    # - created_at (None - directories don't have timestamps)
    # - updated_at (None - directories don't have timestamps)

    # API fields
    path: str = AirweaveField(
        ..., description="Path of the directory within the repository", embeddable=True
    )
    project_id: str = AirweaveField(
        ..., description="ID of the project containing this directory", embeddable=False
    )
    project_path: str = AirweaveField(..., description="Path of the project", embeddable=True)
    url: Optional[str] = AirweaveField(
        None, description="Web URL to the directory", embeddable=False
    )


class GitLabCodeFileEntity(CodeFileEntity):
    """Schema for GitLab code file entity.

    Reference:
        https://docs.gitlab.com/ee/api/repository_files.html
    """

    # Base fields are inherited from BaseEntity:
    # - entity_id (project_id/path)
    # - breadcrumbs (project and directory breadcrumbs)
    # - name (filename)
    # - created_at (None - files have commit timestamps, not creation)
    # - updated_at (None - files have commit timestamps, not update)

    # File fields are inherited from FileEntity:
    # - url (GitLab web view URL)
    # - size (file size in bytes)
    # - file_type (determined from mime_type)
    # - mime_type
    # - local_path (set after saving content)

    # Code file fields are inherited from CodeFileEntity:
    # - repo_name (project name)
    # - path_in_repo (file path within repository)
    # - repo_owner (namespace)
    # - language (programming language)
    # - commit_id (blob ID)

    # API fields (GitLab-specific)
    blob_id: str = AirweaveField(..., description="Blob ID of the file content", embeddable=False)
    project_id: str = AirweaveField(..., description="ID of the project", embeddable=False)
    project_path: str = AirweaveField(..., description="Path of the project", embeddable=True)
    line_count: Optional[int] = AirweaveField(
        None, description="Number of lines in the file", embeddable=False
    )


class GitLabIssueEntity(BaseEntity):
    """Schema for GitLab issue entity.

    Reference:
        https://docs.gitlab.com/ee/api/issues.html
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (project_id/issues/iid)
    # - breadcrumbs (project breadcrumb)
    # - name (from issue title)
    # - created_at (from created_at timestamp)
    # - updated_at (from updated_at timestamp)

    # API fields
    title: str = AirweaveField(..., description="Issue title", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Issue description", embeddable=True
    )
    state: str = AirweaveField(..., description="Issue state (opened, closed)", embeddable=True)
    closed_at: Optional[Any] = AirweaveField(
        None, description="Issue close timestamp", embeddable=False
    )
    labels: List[str] = AirweaveField(
        default_factory=list, description="Issue labels", embeddable=True
    )
    author: Dict[str, Any] = AirweaveField(
        ..., description="Issue author information", embeddable=True
    )
    assignees: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Issue assignees", embeddable=True
    )
    milestone: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Issue milestone", embeddable=True
    )
    project_id: str = AirweaveField(..., description="ID of the project", embeddable=False)
    iid: int = AirweaveField(..., description="Internal issue ID", embeddable=False)
    web_url: str = AirweaveField(..., description="Web URL to the issue", embeddable=False)
    user_notes_count: int = AirweaveField(
        0, description="Number of user notes/comments", embeddable=False
    )
    upvotes: int = AirweaveField(0, description="Number of upvotes", embeddable=False)
    downvotes: int = AirweaveField(0, description="Number of downvotes", embeddable=False)


class GitLabMergeRequestEntity(BaseEntity):
    """Schema for GitLab merge request entity.

    Reference:
        https://docs.gitlab.com/ee/api/merge_requests.html
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (project_id/merge_requests/iid)
    # - breadcrumbs (project breadcrumb)
    # - name (from merge request title)
    # - created_at (from created_at timestamp)
    # - updated_at (from updated_at timestamp)

    # API fields
    title: str = AirweaveField(..., description="Merge request title", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Merge request description", embeddable=True
    )
    state: str = AirweaveField(
        ..., description="Merge request state (opened, closed, merged)", embeddable=True
    )
    merged_at: Optional[Any] = AirweaveField(
        None, description="Merge request merge timestamp", embeddable=False
    )
    closed_at: Optional[Any] = AirweaveField(
        None, description="Merge request close timestamp", embeddable=False
    )
    labels: List[str] = AirweaveField(
        default_factory=list, description="Merge request labels", embeddable=True
    )
    author: Dict[str, Any] = AirweaveField(
        ..., description="Merge request author information", embeddable=True
    )
    assignees: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Merge request assignees", embeddable=True
    )
    reviewers: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Merge request reviewers", embeddable=True
    )
    source_branch: str = AirweaveField(..., description="Source branch name", embeddable=True)
    target_branch: str = AirweaveField(..., description="Target branch name", embeddable=True)
    milestone: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Merge request milestone", embeddable=True
    )
    project_id: str = AirweaveField(..., description="ID of the project", embeddable=False)
    iid: int = AirweaveField(..., description="Internal merge request ID", embeddable=False)
    web_url: str = AirweaveField(..., description="Web URL to the merge request", embeddable=False)
    merge_status: str = AirweaveField(
        ..., description="Merge status (can_be_merged, cannot_be_merged)", embeddable=True
    )
    draft: bool = AirweaveField(
        False, description="Whether the merge request is a draft", embeddable=False
    )
    work_in_progress: bool = AirweaveField(
        False, description="Whether the merge request is work in progress", embeddable=False
    )
    upvotes: int = AirweaveField(0, description="Number of upvotes", embeddable=False)
    downvotes: int = AirweaveField(0, description="Number of downvotes", embeddable=False)
    user_notes_count: int = AirweaveField(
        0, description="Number of user notes/comments", embeddable=False
    )
