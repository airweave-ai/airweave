"""GitHub cursor schema for incremental sync."""

from typing import Optional

from pydantic import Field

from ._base import BaseCursor


class GitHubCursor(BaseCursor):
    """GitHub incremental sync cursor using repository pushed_at timestamp.

    GitHub tracks repository updates using the pushed_at timestamp. We use this
    to determine if a repository has been updated since the last sync.

    Additional metadata is stored for context and debugging.
    """

    last_repository_pushed_at: str = Field(
        default="",
        description="ISO 8601 timestamp of last repository push (e.g., '2024-11-03T10:00:00Z')",
    )
    repo_name: Optional[str] = Field(
        default=None, description="Name of the repository being synced"
    )
    branch: Optional[str] = Field(default=None, description="Branch being synced")




