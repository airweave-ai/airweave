"""Google Drive cursor schema for incremental sync."""

from typing import Any, Dict

from pydantic import Field

from ._base import BaseCursor


class GoogleDriveCursor(BaseCursor):
    """Google Drive incremental sync cursor using Changes API.

    Google Drive's Changes API uses page tokens to track changes to files
    and folders. Each change state is associated with a page token.

    Reference: https://developers.google.com/drive/api/guides/manage-changes
    """

    start_page_token: str = Field(
        default="",
        description="Drive Changes API page token for tracking incremental changes",
    )

    file_metadata: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Map of file_id -> {modified_time, md5_checksum, size} for change detection",
    )
