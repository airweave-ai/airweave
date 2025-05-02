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

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, CodeFileEntity, ParentEntity


class GitHubRepositoryEntity(ParentEntity):
    """Schema for GitHub repository entity."""

    name: str = Field(..., description="Repository name")
    full_name: str = Field(..., description="Full repository name including owner")
    description: Optional[str] = Field(None, description="Repository description")
    default_branch: str = Field(..., description="Default branch of the repository")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    language: Optional[str] = Field(None, description="Primary language of the repository")
    fork: bool = Field(..., description="Whether the repository is a fork")
    size: int = Field(..., description="Size of the repository in KB")
    stars_count: Optional[int] = Field(None, description="Number of stars")
    watchers_count: Optional[int] = Field(None, description="Number of watchers")
    forks_count: Optional[int] = Field(None, description="Number of forks")
    open_issues_count: Optional[int] = Field(None, description="Number of open issues")


class GitHubDirectoryEntity(ChunkEntity):
    """Schema for GitHub directory entity."""

    path: str = Field(..., description="Path of the directory within the repository")
    repo_name: str = Field(..., description="Name of the repository containing this directory")
    repo_owner: str = Field(..., description="Owner of the repository")


class GitHubCodeFileEntity(CodeFileEntity):
    """Schema for GitHub code file entity."""

    # GitHub specific fields only
    sha: str = Field(..., description="SHA hash of the file content")
    path: str = Field(..., description="Path of the file within the repository")
    is_binary: bool = Field(False, description="Flag indicating if file is binary")


class GithubRepoEntity(ChunkEntity):
    """Schema for a GitHub repository.

    References:
      https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28
    """

    name: Optional[str] = Field(None, description="Name of the repository.")
    full_name: Optional[str] = Field(None, description="Full name (including owner) of the repo.")
    owner_login: Optional[str] = Field(None, description="Login/username of the repository owner.")
    private: bool = Field(False, description="Whether the repository is private.")
    description: Optional[str] = Field(None, description="Short description of the repository.")
    fork: bool = Field(False, description="Whether this repository is a fork.")
    created_at: Optional[datetime] = Field(None, description="When the repository was created.")
    updated_at: Optional[datetime] = Field(
        None, description="When the repository was last updated."
    )
    pushed_at: Optional[datetime] = Field(None, description="When the repository was last pushed.")
    homepage: Optional[str] = Field(None, description="Homepage URL for the repository.")
    size: Optional[int] = Field(None, description="Size of the repository (in kilobytes).")
    stargazers_count: int = Field(0, description="Number of stars on this repository.")
    watchers_count: int = Field(0, description="Number of people watching this repository.")
    language: Optional[str] = Field(None, description="Primary language of the repository.")
    forks_count: int = Field(0, description="Number of forks for this repository.")
    open_issues_count: int = Field(0, description="Number of open issues on this repository.")
    topics: List[str] = Field(default_factory=list, description="Topics/tags applied to this repo.")
    default_branch: Optional[str] = Field(
        None, description="Default branch name of the repository."
    )
    archived: bool = Field(False, description="Whether the repository is archived.")
    disabled: bool = Field(False, description="Whether the repository is disabled in GitHub.")


class GithubContentEntity(ChunkEntity):
    """Schema for a GitHub repository's content (file, directory, submodule, etc.).

    References:
      https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28
    """

    repo_full_name: Optional[str] = Field(None, description="Full name of the parent repository.")
    path: Optional[str] = Field(None, description="Path of the file or directory within the repo.")
    sha: Optional[str] = Field(None, description="SHA identifier for this content item.")
    item_type: Optional[str] = Field(
        None, description="Type of content. Typically 'file', 'dir', 'submodule', or 'symlink'."
    )
    size: Optional[int] = Field(None, description="Size of the content (in bytes).")
    html_url: Optional[str] = Field(
        None, description="HTML URL for viewing this content on GitHub."
    )
    download_url: Optional[str] = Field(None, description="Direct download URL if applicable.")
    content: Optional[str] = Field(
        None,
        description="File content (base64-encoded) if retrieved via 'mediaType=raw' or similar.",
    )
    encoding: Optional[str] = Field(
        None, description="Indicates the encoding of the content (e.g., 'base64')."
    )
