"""Bitbucket entity schemas.

Based on the Bitbucket REST API, we define entity schemas for:
  • Workspace
  • Repository
  • Repository Contents (files and directories)

References:
  • https://developer.atlassian.com/cloud/bitbucket/rest/intro/
  • https://developer.atlassian.com/cloud/bitbucket/rest/api-group-repositories/
"""

from datetime import datetime
from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base_legacy import ChunkEntity, CodeFileEntity, ParentEntity


class BitbucketWorkspaceEntity(ParentEntity):
    """Schema for Bitbucket workspace entity."""

    slug: str = AirweaveField(..., description="Workspace slug identifier", embeddable=True)
    name: str = AirweaveField(..., description="Workspace display name", embeddable=True)
    uuid: str = AirweaveField(..., description="Workspace UUID")
    is_private: bool = AirweaveField(..., description="Whether the workspace is private")
    created_on: Optional[datetime] = AirweaveField(
        None, description="Creation timestamp", is_created_at=True
    )


class BitbucketRepositoryEntity(ParentEntity):
    """Schema for Bitbucket repository entity."""

    name: str = AirweaveField(..., description="Repository name", embeddable=True)
    slug: str = AirweaveField(..., description="Repository slug", embeddable=True)
    full_name: str = AirweaveField(
        ..., description="Full repository name including workspace", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Repository description", embeddable=True
    )
    is_private: bool = AirweaveField(..., description="Whether the repository is private")
    fork_policy: Optional[str] = AirweaveField(None, description="Fork policy of the repository")
    language: Optional[str] = AirweaveField(
        None, description="Primary language of the repository", embeddable=True
    )
    created_on: datetime = AirweaveField(..., description="Creation timestamp", is_created_at=True)
    updated_on: datetime = AirweaveField(
        ..., description="Last update timestamp", is_updated_at=True
    )
    size: Optional[int] = AirweaveField(None, description="Size of the repository in bytes")
    mainbranch: Optional[str] = AirweaveField(None, description="Main branch name", embeddable=True)
    workspace_slug: str = AirweaveField(
        ..., description="Slug of the parent workspace", embeddable=True
    )


class BitbucketDirectoryEntity(ChunkEntity):
    """Schema for Bitbucket directory entity."""

    path: str = AirweaveField(
        ..., description="Path of the directory within the repository", embeddable=True
    )
    repo_slug: str = AirweaveField(
        ..., description="Slug of the repository containing this directory", embeddable=True
    )
    repo_full_name: str = AirweaveField(
        ..., description="Full name of the repository", embeddable=True
    )
    workspace_slug: str = AirweaveField(..., description="Slug of the workspace", embeddable=True)


class BitbucketCodeFileEntity(CodeFileEntity):
    """Schema for Bitbucket code file entity."""

    # Bitbucket specific fields only
    commit_hash: Optional[str] = AirweaveField(None, description="Commit hash of the file version")
    path: str = AirweaveField(
        ..., description="Path of the file within the repository", embeddable=True
    )
    repo_slug: str = AirweaveField(..., description="Slug of the repository", embeddable=True)
    repo_full_name: str = AirweaveField(
        ..., description="Full name of the repository", embeddable=True
    )
    workspace_slug: str = AirweaveField(..., description="Slug of the workspace", embeddable=True)
