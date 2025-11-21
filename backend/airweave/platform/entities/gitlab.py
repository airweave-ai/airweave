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

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, CodeFileEntity


class GitLabProjectEntity(BaseEntity):
    """Schema for GitLab project (repository) entity.

    Reference:
        https://docs.gitlab.com/ee/api/projects.html
    """

    project_id: int = AirweaveField(
        ...,
        description="GitLab project ID",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Project name",
        is_name=True,
        embeddable=True,
    )
    created_at: datetime = AirweaveField(
        ...,
        description="Creation timestamp",
        is_created_at=True,
    )
    last_activity_at: datetime = AirweaveField(
        ...,
        description="Timestamp of last activity",
        is_updated_at=True,
    )
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
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Web URL to the project",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable project URL."""
        return self.web_url_value or f"https://gitlab.com/{self.path_with_namespace}"


class GitLabUserEntity(BaseEntity):
    """Schema for GitLab user entity.

    Reference:
        https://docs.gitlab.com/ee/api/users.html
    """

    user_id: int = AirweaveField(
        ...,
        description="GitLab user ID",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="User's display name",
        is_name=True,
        embeddable=True,
    )
    created_at: datetime = AirweaveField(
        ...,
        description="Account creation timestamp",
        is_created_at=True,
    )
    username: str = AirweaveField(..., description="User's username", embeddable=True)
    state: str = AirweaveField(..., description="User account state", embeddable=False)
    avatar_url: Optional[str] = AirweaveField(
        None, description="User's avatar URL", embeddable=False
    )
    profile_url: Optional[str] = AirweaveField(
        None,
        description="User's profile URL",
        embeddable=False,
        unhashable=True,
    )
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

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable profile URL."""
        return self.profile_url or f"https://gitlab.com/{self.username}"


class GitLabDirectoryEntity(BaseEntity):
    """Schema for GitLab directory entity.

    Reference:
        https://docs.gitlab.com/ee/api/repositories.html
    """

    full_path: str = AirweaveField(
        ...,
        description="Project-qualified directory path (project_id/path)",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Directory name",
        is_name=True,
        embeddable=True,
    )
    path: str = AirweaveField(
        ..., description="Path of the directory within the repository", embeddable=True
    )
    project_id: str = AirweaveField(
        ..., description="ID of the project containing this directory", embeddable=False
    )
    project_path: str = AirweaveField(..., description="Path of the project", embeddable=True)
    branch: str = AirweaveField(
        ..., description="Branch used when traversing this directory", embeddable=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Web URL to the directory",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable directory URL."""
        if self.web_url_value:
            return self.web_url_value
        if not self.path:
            return f"https://gitlab.com/{self.project_path}"
        return f"https://gitlab.com/{self.project_path}/-/tree/{self.branch}/{self.path}"


class GitLabCodeFileEntity(CodeFileEntity):
    """Schema for GitLab code file entity.

    Reference:
        https://docs.gitlab.com/ee/api/repository_files.html
    """

    full_path: str = AirweaveField(
        ...,
        description="Project-qualified file path (project_id/path)",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Filename",
        is_name=True,
        embeddable=True,
    )
    branch: str = AirweaveField(
        ..., description="Branch used when fetching the file", embeddable=True
    )
    blob_id: str = AirweaveField(..., description="Blob ID of the file content", embeddable=False)
    project_id: str = AirweaveField(..., description="ID of the project", embeddable=False)
    project_path: str = AirweaveField(..., description="Path of the project", embeddable=True)
    line_count: Optional[int] = AirweaveField(
        None, description="Number of lines in the file", embeddable=False
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Web URL to view the file",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable file URL."""
        return self.web_url_value or (
            f"https://gitlab.com/{self.project_path}/-/blob/{self.branch}/{self.path_in_repo}"
        )


class GitLabIssueEntity(BaseEntity):
    """Schema for GitLab issue entity.

    Reference:
        https://docs.gitlab.com/ee/api/issues.html
    """

    issue_id: int = AirweaveField(
        ...,
        description="Global GitLab issue ID",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Issue title",
        is_name=True,
        embeddable=True,
    )
    created_at: datetime = AirweaveField(
        ...,
        description="Issue creation timestamp",
        is_created_at=True,
    )
    updated_at: datetime = AirweaveField(
        ...,
        description="Issue update timestamp",
        is_updated_at=True,
    )
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
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Web URL to the issue",
        embeddable=False,
        unhashable=True,
    )
    user_notes_count: int = AirweaveField(
        0, description="Number of user notes/comments", embeddable=False
    )
    upvotes: int = AirweaveField(0, description="Number of upvotes", embeddable=False)
    downvotes: int = AirweaveField(0, description="Number of downvotes", embeddable=False)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable issue URL."""
        return (
            self.web_url_value
            or f"https://gitlab.com/projects/{self.project_id}/-/issues/{self.iid}"
        )


class GitLabMergeRequestEntity(BaseEntity):
    """Schema for GitLab merge request entity.

    Reference:
        https://docs.gitlab.com/ee/api/merge_requests.html
    """

    merge_request_id: int = AirweaveField(
        ...,
        description="Global GitLab merge request ID",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Merge request title",
        is_name=True,
        embeddable=True,
    )
    created_at: datetime = AirweaveField(
        ...,
        description="Merge request creation timestamp",
        is_created_at=True,
    )
    updated_at: datetime = AirweaveField(
        ...,
        description="Merge request update timestamp",
        is_updated_at=True,
    )
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
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Web URL to the merge request",
        embeddable=False,
        unhashable=True,
    )
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

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Clickable merge request URL."""
        if self.web_url_value:
            return self.web_url_value
        return f"https://gitlab.com/projects/{self.project_id}/-/merge_requests/{self.iid}"
