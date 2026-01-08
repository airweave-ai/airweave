"""The Airweave entities module.

Contains entity schemas for various data sources and destinations.
"""

from ._base import AccessControl, BaseEntity, Breadcrumb, CodeFileEntity, FileEntity
from .github import (
    GitHubCodeFileEntity,
    GithubContentEntity,
    GitHubDirectoryEntity,
    GitHubFileDeletionEntity,
    GithubRepoEntity,
    GitHubRepositoryEntity,
)
from .sharepoint2019v2 import (
    SharePoint2019V2FileEntity,
    SharePoint2019V2ItemEntity,
    SharePoint2019V2ListEntity,
    SharePoint2019V2SiteEntity,
)

__all__ = [
    "AccessControl",
    "BaseEntity",
    "Breadcrumb",
    "CodeFileEntity",
    "FileEntity",
    "GitHubCodeFileEntity",
    "GitHubDirectoryEntity",
    "GitHubFileDeletionEntity",
    "GitHubRepositoryEntity",
    "GithubRepoEntity",
    "GithubContentEntity",
    "SharePoint2019V2FileEntity",
    "SharePoint2019V2ItemEntity",
    "SharePoint2019V2ListEntity",
    "SharePoint2019V2SiteEntity",
]
