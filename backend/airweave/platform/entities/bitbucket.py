"""Bitbucket entity schemas.

Based on the Bitbucket REST API, we define entity schemas for:
  • Workspace
  • Repository
  • Repository Contents (files and directories)

References:
  • https://developer.atlassian.com/cloud/bitbucket/rest/intro/
  • https://developer.atlassian.com/cloud/bitbucket/rest/api-group-repositories/
"""

from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, CodeFileEntity


class BitbucketWorkspaceEntity(BaseEntity):
    """Schema for Bitbucket workspace entity.

    Reference:
        https://developer.atlassian.com/cloud/bitbucket/rest/api-group-workspaces/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the workspace UUID)
    # - breadcrumbs (empty - workspaces are top-level)
    # - name (from workspace name)
    # - created_at (from created_on timestamp)
    # - updated_at (None - workspaces don't have update timestamp)

    # API fields
    slug: str = AirweaveField(..., description="Workspace slug identifier", embeddable=True)
    uuid: str = AirweaveField(..., description="Workspace UUID", embeddable=False)
    is_private: bool = AirweaveField(
        ..., description="Whether the workspace is private", embeddable=False
    )
    url: Optional[str] = AirweaveField(
        None, description="URL to view the workspace", embeddable=False
    )


class BitbucketRepositoryEntity(BaseEntity):
    """Schema for Bitbucket repository entity.

    Reference:
        https://developer.atlassian.com/cloud/bitbucket/rest/api-group-repositories/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the repository UUID)
    # - breadcrumbs (workspace breadcrumb)
    # - name (from repository name)
    # - created_at (from created_on timestamp)
    # - updated_at (from updated_on timestamp)

    # API fields
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
    url: Optional[str] = AirweaveField(
        None, description="URL to view the repository", embeddable=False
    )


class BitbucketDirectoryEntity(BaseEntity):
    """Schema for Bitbucket directory entity."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (workspace/repo/path)
    # - breadcrumbs (workspace, repository, and parent directory breadcrumbs)
    # - name (directory name from path)
    # - created_at (None - directories don't have timestamps)
    # - updated_at (None - directories don't have timestamps)

    # API fields
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
    url: Optional[str] = AirweaveField(
        None, description="URL to view the directory", embeddable=False
    )


class BitbucketCodeFileEntity(CodeFileEntity):
    """Schema for Bitbucket code file entity.

    Reference:
        https://developer.atlassian.com/cloud/bitbucket/rest/api-group-source/
    """

    # Base fields are inherited from BaseEntity:
    # - entity_id (workspace/repo/path)
    # - breadcrumbs (workspace, repository, and directory breadcrumbs)
    # - name (filename)
    # - created_at (None - files have commit timestamps, not creation)
    # - updated_at (None - files have commit timestamps, not update)

    # File fields are inherited from FileEntity:
    # - url (Bitbucket web view URL)
    # - size (file size in bytes)
    # - file_type (determined from mime_type)
    # - mime_type
    # - local_path (set after saving content)

    # Code file fields are inherited from CodeFileEntity:
    # - repo_name (repository slug)
    # - path_in_repo (file path within repository)
    # - repo_owner (workspace slug)
    # - language (programming language)
    # - commit_id (commit hash)

    # API fields (Bitbucket-specific)
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
