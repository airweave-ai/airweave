"""Bitbucket entity schemas."""

from datetime import datetime
from typing import Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, CodeFileEntity


class BitbucketWorkspaceEntity(BaseEntity):
    """Schema for Bitbucket workspace entity."""

    uuid: str = AirweaveField(..., description="Workspace UUID", is_entity_id=True)
    display_name: str = AirweaveField(
        ..., description="Display name of the workspace", is_name=True, embeddable=True
    )
    created_on: Optional[datetime] = AirweaveField(
        None, description="Workspace creation timestamp", is_created_at=True
    )

    slug: str = AirweaveField(..., description="Workspace slug identifier", embeddable=True)
    is_private: bool = AirweaveField(
        ..., description="Whether the workspace is private", embeddable=False
    )
    html_url: Optional[str] = AirweaveField(
        None, description="URL to view the workspace", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the canonical workspace URL."""
        if self.html_url:
            return self.html_url
        return f"https://bitbucket.org/{self.slug}"


class BitbucketRepositoryEntity(BaseEntity):
    """Schema for Bitbucket repository entity."""

    uuid: str = AirweaveField(..., description="Repository UUID", is_entity_id=True)
    repo_name: str = AirweaveField(
        ..., description="Repository display name", is_name=True, embeddable=True
    )
    created_on: datetime = AirweaveField(
        ..., description="Repository creation timestamp", is_created_at=True
    )
    updated_on: datetime = AirweaveField(
        ..., description="Last update timestamp", is_updated_at=True
    )

    slug: str = AirweaveField(..., description="Repository slug", embeddable=True)
    full_name: str = AirweaveField(
        ..., description="Full repository name including workspace", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Repository description", embeddable=True
    )
    is_private: bool = AirweaveField(
        ..., description="Whether the repository is private", embeddable=False
    )
    fork_policy: Optional[str] = AirweaveField(
        None, description="Fork policy of the repository", embeddable=False
    )
    language: Optional[str] = AirweaveField(
        None, description="Primary language of the repository", embeddable=True
    )
    size: Optional[int] = AirweaveField(
        None, description="Size of the repository in bytes", embeddable=False
    )
    mainbranch: Optional[str] = AirweaveField(None, description="Main branch name", embeddable=True)
    workspace_slug: str = AirweaveField(
        ..., description="Slug of the parent workspace", embeddable=True
    )
    html_url: Optional[str] = AirweaveField(
        None, description="URL to view the repository", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the canonical repository URL."""
        if self.html_url:
            return self.html_url
        return f"https://bitbucket.org/{self.full_name}"


class BitbucketDirectoryEntity(BaseEntity):
    """Schema for Bitbucket directory entity."""

    path_id: str = AirweaveField(
        ..., description="Unique identifier for the directory path", is_entity_id=True
    )
    directory_name: str = AirweaveField(
        ..., description="Display name of the directory", is_name=True, embeddable=True
    )

    path: str = AirweaveField(
        ..., description="Path of the directory within the repository", embeddable=True
    )
    branch: Optional[str] = AirweaveField(
        None, description="Branch for this directory view", embeddable=False
    )
    repo_slug: str = AirweaveField(
        ..., description="Slug of the repository containing this directory", embeddable=True
    )
    repo_full_name: str = AirweaveField(
        ..., description="Full name of the repository", embeddable=True
    )
    workspace_slug: str = AirweaveField(..., description="Slug of the workspace", embeddable=True)
    html_url: Optional[str] = AirweaveField(
        None, description="URL to view the directory", embeddable=False, unhashable=True
    )

    @computed_field(return_type=Optional[str])
    def web_url(self) -> Optional[str]:
        """Return a link to browse this directory on Bitbucket."""
        if self.html_url:
            return self.html_url
        if self.branch is None:
            return None
        return (
            f"https://bitbucket.org/{self.workspace_slug}/{self.repo_slug}/src/"
            f"{self.branch}/{self.path}"
        )


class BitbucketCodeFileEntity(CodeFileEntity):
    """Schema for Bitbucket code file entity."""

    file_id: str = AirweaveField(
        ..., description="Unique identifier for the file path", is_entity_id=True
    )
    file_name: str = AirweaveField(
        ..., description="Display name of the file", is_name=True, embeddable=True
    )
    branch: Optional[str] = AirweaveField(
        None, description="Branch for this file version", embeddable=False
    )

    commit_hash: Optional[str] = AirweaveField(
        None, description="Commit hash of the file version", embeddable=False
    )
    repo_slug: str = AirweaveField(..., description="Slug of the repository", embeddable=True)
    repo_full_name: str = AirweaveField(
        ..., description="Full name of the repository", embeddable=True
    )
    workspace_slug: str = AirweaveField(..., description="Slug of the workspace", embeddable=True)
    line_count: Optional[int] = AirweaveField(
        None, description="Number of lines in the file", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Bitbucket web URL for this file."""
        return self.url
