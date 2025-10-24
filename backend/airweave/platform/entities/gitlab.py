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

from pydantic import Field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base_legacy import ChunkEntity, CodeFileEntity, ParentEntity


class GitLabProjectEntity(ParentEntity):
    """Schema for GitLab project (repository) entity."""

    name: str = AirweaveField(..., description="Project name", embeddable=True)
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
    created_at: datetime = AirweaveField(
        ..., description="Creation timestamp", embeddable=True, is_created_at=True
    )
    last_activity_at: Optional[datetime] = AirweaveField(
        None, description="Last activity timestamp", embeddable=True, is_updated_at=True
    )
    visibility: str = AirweaveField(..., description="Project visibility level", embeddable=True)
    topics: List[str] = AirweaveField(
        default_factory=list, description="Project topics/tags", embeddable=True
    )
    namespace: Dict[str, Any] = AirweaveField(
        ..., description="Project namespace information", embeddable=True
    )
    star_count: int = AirweaveField(0, description="Number of stars")
    forks_count: int = AirweaveField(0, description="Number of forks")
    open_issues_count: int = AirweaveField(0, description="Number of open issues")
    archived: bool = AirweaveField(False, description="Whether the project is archived")
    empty_repo: bool = AirweaveField(False, description="Whether the repository is empty")


class GitLabUserEntity(ChunkEntity):
    """Schema for GitLab user entity."""

    username: str = AirweaveField(..., description="User's username", embeddable=True)
    name: str = AirweaveField(..., description="User's display name", embeddable=True)
    state: str = AirweaveField(..., description="User account state", embeddable=True)
    avatar_url: Optional[str] = Field(None, description="User's avatar URL")
    web_url: str = Field(..., description="User's profile URL")
    created_at: Optional[datetime] = AirweaveField(
        None, description="Account creation timestamp", embeddable=True, is_created_at=True
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


class GitLabDirectoryEntity(ChunkEntity):
    """Schema for GitLab directory entity."""

    path: str = AirweaveField(
        ..., description="Path of the directory within the repository", embeddable=True
    )
    project_id: str = AirweaveField(
        ..., description="ID of the project containing this directory", embeddable=True
    )
    project_path: str = AirweaveField(..., description="Path of the project", embeddable=True)


class GitLabCodeFileEntity(CodeFileEntity):
    """Schema for GitLab code file entity."""

    # GitLab specific fields only
    blob_id: str = AirweaveField(..., description="Blob ID of the file content")
    path: str = AirweaveField(
        ..., description="Path of the file within the repository", embeddable=True
    )
    project_id: str = AirweaveField(..., description="ID of the project", embeddable=True)
    project_path: str = AirweaveField(..., description="Path of the project", embeddable=True)


class GitLabIssueEntity(ChunkEntity):
    """Schema for GitLab issue entity."""

    title: str = AirweaveField(..., description="Issue title", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Issue description", embeddable=True
    )
    state: str = AirweaveField(..., description="Issue state (opened, closed)", embeddable=True)
    created_at: datetime = AirweaveField(
        ..., description="Issue creation timestamp", embeddable=True, is_created_at=True
    )
    updated_at: datetime = AirweaveField(
        ..., description="Issue last update timestamp", embeddable=True, is_updated_at=True
    )
    closed_at: Optional[datetime] = AirweaveField(
        None, description="Issue close timestamp", embeddable=True
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
    project_id: str = Field(..., description="ID of the project")
    iid: int = Field(..., description="Internal issue ID")
    web_url: str = Field(..., description="Web URL to the issue")
    user_notes_count: int = Field(0, description="Number of user notes/comments")
    upvotes: int = Field(0, description="Number of upvotes")
    downvotes: int = Field(0, description="Number of downvotes")


class GitLabMergeRequestEntity(ChunkEntity):
    """Schema for GitLab merge request entity."""

    title: str = AirweaveField(..., description="Merge request title", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Merge request description", embeddable=True
    )
    state: str = AirweaveField(
        ..., description="Merge request state (opened, closed, merged)", embeddable=True
    )
    created_at: datetime = AirweaveField(
        ..., description="Merge request creation timestamp", embeddable=True, is_created_at=True
    )
    updated_at: datetime = AirweaveField(
        ...,
        description="Merge request last update timestamp",
        embeddable=True,
        is_updated_at=True,
    )
    merged_at: Optional[datetime] = AirweaveField(
        None, description="Merge request merge timestamp", embeddable=True
    )
    closed_at: Optional[datetime] = AirweaveField(
        None, description="Merge request close timestamp", embeddable=True
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
    project_id: str = Field(..., description="ID of the project")
    iid: int = Field(..., description="Internal merge request ID")
    web_url: str = Field(..., description="Web URL to the merge request")
    merge_status: str = AirweaveField(
        ..., description="Merge status (can_be_merged, cannot_be_merged)", embeddable=True
    )
    draft: bool = AirweaveField(False, description="Whether the merge request is a draft")
    work_in_progress: bool = AirweaveField(
        False, description="Whether the merge request is work in progress"
    )
    upvotes: int = Field(0, description="Number of upvotes")
    downvotes: int = Field(0, description="Number of downvotes")
    user_notes_count: int = Field(0, description="Number of user notes/comments")
