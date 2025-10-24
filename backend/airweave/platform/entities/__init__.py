"""The Airweave entities module.

Contains entity schemas for various data sources and destinations.
"""

from ._base import Breadcrumb, CodeFileEntity
from ._base_legacy import ChunkEntity, ParentEntity  # Legacy entities for old sources
from .github import (
    GitHubCodeFileEntity,
    GithubContentEntity,
    GitHubDirectoryEntity,
    GitHubFileDeletionEntity,
    GithubRepoEntity,
    GitHubRepositoryEntity,
)

__all__ = [
    "Breadcrumb",
    "ChunkEntity",
    "CodeFileEntity",
    "ParentEntity",
    "GitHubCodeFileEntity",
    "GitHubDirectoryEntity",
    "GitHubFileDeletionEntity",
    "GitHubRepositoryEntity",
    "GithubRepoEntity",
    "GithubContentEntity",
]
