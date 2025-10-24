"""GitHub entity schemas.

Based on the GitHub REST API (read-only scope), we define entity schemas for:
  • Repository
  • Repository Contents

References:
  • https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28 (Repositories)
  • https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28 (Repository contents)
"""

from datetime import datetime
from typing import List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, CodeFileEntity, DeletionEntity


class GitHubRepositoryEntity(BaseEntity):
    """Schema for GitHub repository entity."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (the repository ID)
    # - breadcrumbs (empty - repositories are top-level)
    # - name (from repository name)
    # - created_at (from created_at timestamp)
    # - updated_at (from updated_at timestamp)

    # API fields
    full_name: str = AirweaveField(
        ..., description="Full repository name including owner", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Repository description", embeddable=True
    )
    default_branch: str = AirweaveField(
        ..., description="Default branch of the repository", embeddable=True
    )
    language: Optional[str] = AirweaveField(
        None, description="Primary language of the repository", embeddable=True
    )
    fork: bool = AirweaveField(
        ..., description="Whether the repository is a fork", embeddable=False
    )
    size: int = AirweaveField(..., description="Size of the repository in KB", embeddable=False)
    stars_count: Optional[int] = AirweaveField(
        None, description="Number of stars", embeddable=False
    )
    watchers_count: Optional[int] = AirweaveField(
        None, description="Number of watchers", embeddable=False
    )
    forks_count: Optional[int] = AirweaveField(
        None, description="Number of forks", embeddable=False
    )
    open_issues_count: Optional[int] = AirweaveField(
        None, description="Number of open issues", embeddable=False
    )


class GitHubDirectoryEntity(BaseEntity):
    """Schema for GitHub directory entity."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (repo_name/path)
    # - breadcrumbs (repository and parent directory breadcrumbs)
    # - name (directory name)
    # - created_at (None - directories don't have timestamps)
    # - updated_at (None - directories don't have timestamps)

    # API fields
    path: str = AirweaveField(
        ..., description="Path of the directory within the repository", embeddable=True
    )
    repo_name: str = AirweaveField(
        ..., description="Name of the repository containing this directory", embeddable=True
    )
    repo_owner: str = AirweaveField(..., description="Owner of the repository", embeddable=True)


class GitHubCodeFileEntity(CodeFileEntity):
    """Schema for GitHub code file entity."""

    # Base fields are inherited from BaseEntity:
    # - entity_id (repo_name/path)
    # - breadcrumbs (repository and directory breadcrumbs)
    # - name (filename)
    # - created_at (None - files have commit timestamps, not creation)
    # - updated_at (None - files have commit timestamps, not update)

    # File fields are inherited from FileEntity:
    # - url (GitHub html_url)
    # - size (file size in bytes)
    # - file_type (determined from mime_type)
    # - mime_type
    # - local_path (None for code files - content is inline)

    # Code file fields are inherited from CodeFileEntity:
    # - repo_name (repository name)
    # - path_in_repo (file path within repository)
    # - repo_owner (repository owner)
    # - language (programming language)
    # - commit_id (SHA of the commit)

    # API fields (GitHub-specific)
    sha: str = AirweaveField(..., description="SHA hash of the file content", embeddable=False)
    line_count: Optional[int] = AirweaveField(
        None, description="Number of lines in the file", embeddable=False
    )
    is_binary: bool = AirweaveField(
        False, description="Flag indicating if file is binary", embeddable=False
    )


class GithubRepoEntity(BaseEntity):
    """Schema for a GitHub repository (alternative schema).

    References:
      https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28

    Note: This is an alternative repository entity schema. Consider using GitHubRepositoryEntity.
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the repository ID)
    # - breadcrumbs (empty - repositories are top-level)
    # - name (from repository name)
    # - created_at (from created_at timestamp)
    # - updated_at (from updated_at timestamp)

    # API fields
    full_name: Optional[str] = AirweaveField(
        None, description="Full name (including owner) of the repo.", embeddable=True
    )
    owner_login: Optional[str] = AirweaveField(
        None, description="Login/username of the repository owner.", embeddable=True
    )
    private: bool = AirweaveField(
        False, description="Whether the repository is private.", embeddable=False
    )
    description: Optional[str] = AirweaveField(
        None, description="Short description of the repository.", embeddable=True
    )
    fork: bool = AirweaveField(
        False, description="Whether this repository is a fork.", embeddable=False
    )
    pushed_at: Optional[datetime] = AirweaveField(
        None, description="When the repository was last pushed.", embeddable=False
    )
    homepage: Optional[str] = AirweaveField(
        None, description="Homepage URL for the repository.", embeddable=False
    )
    size: Optional[int] = AirweaveField(
        None, description="Size of the repository (in kilobytes).", embeddable=False
    )
    stargazers_count: int = AirweaveField(
        0, description="Number of stars on this repository.", embeddable=False
    )
    watchers_count: int = AirweaveField(
        0, description="Number of people watching this repository.", embeddable=False
    )
    language: Optional[str] = AirweaveField(
        None, description="Primary language of the repository.", embeddable=True
    )
    forks_count: int = AirweaveField(
        0, description="Number of forks for this repository.", embeddable=False
    )
    open_issues_count: int = AirweaveField(
        0, description="Number of open issues on this repository.", embeddable=False
    )
    topics: List[str] = AirweaveField(
        default_factory=list, description="Topics/tags applied to this repo.", embeddable=True
    )
    default_branch: Optional[str] = AirweaveField(
        None, description="Default branch name of the repository.", embeddable=True
    )
    archived: bool = AirweaveField(
        False, description="Whether the repository is archived.", embeddable=False
    )
    disabled: bool = AirweaveField(
        False, description="Whether the repository is disabled in GitHub.", embeddable=False
    )


class GithubContentEntity(BaseEntity):
    """Schema for a GitHub repository's content (file, directory, submodule, etc.).

    References:
      https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28

    Note: This is a generic content entity. Consider using specific entities like
    GitHubCodeFileEntity or GitHubDirectoryEntity.
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (content path or SHA)
    # - breadcrumbs (repository and parent breadcrumbs)
    # - name (file/directory name)
    # - created_at (None - content items don't have creation timestamps)
    # - updated_at (None - content items don't have update timestamps)

    # API fields
    repo_full_name: Optional[str] = AirweaveField(
        None, description="Full name of the parent repository.", embeddable=True
    )
    path: Optional[str] = AirweaveField(
        None, description="Path of the file or directory within the repo.", embeddable=True
    )
    sha: Optional[str] = AirweaveField(
        None, description="SHA identifier for this content item.", embeddable=False
    )
    item_type: Optional[str] = AirweaveField(
        None,
        description="Type of content. Typically 'file', 'dir', 'submodule', or 'symlink'.",
        embeddable=False,
    )
    size: Optional[int] = AirweaveField(
        None, description="Size of the content (in bytes).", embeddable=False
    )
    html_url: Optional[str] = AirweaveField(
        None, description="HTML URL for viewing this content on GitHub.", embeddable=False
    )
    download_url: Optional[str] = AirweaveField(
        None, description="Direct download URL if applicable.", embeddable=False
    )
    content: Optional[str] = AirweaveField(
        None,
        description="File content (base64-encoded) if retrieved via 'mediaType=raw' or similar.",
        embeddable=True,
    )
    encoding: Optional[str] = AirweaveField(
        None,
        description="Indicates the encoding of the content (e.g., 'base64').",
        embeddable=False,
    )


class GitHubFileDeletionEntity(DeletionEntity):
    """Schema for GitHub file deletion entity.

    This entity is used to signal that a file has been removed from the repository
    and should be deleted from the destination.
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (repo_name/file_path - matches the original file's entity_id)
    # - breadcrumbs (empty - deletion signals are top-level)
    # - name (generic deletion name)
    # - created_at (None - deletions don't have timestamps)
    # - updated_at (None - deletions don't have timestamps)
    # - deletion_status (inherited from DeletionEntity)

    # API fields
    file_path: str = AirweaveField(
        ..., description="Path of the deleted file within the repository", embeddable=False
    )
    repo_name: str = AirweaveField(
        ..., description="Name of the repository containing the deleted file", embeddable=False
    )
    repo_owner: str = AirweaveField(..., description="Owner of the repository", embeddable=False)
