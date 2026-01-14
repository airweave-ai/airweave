"""Google Docs cursor schema for incremental sync."""

from typing import Any, Dict

from pydantic import Field

from ._base import BaseCursor


class GoogleDocsCursor(BaseCursor):
    """Google Docs incremental sync cursor using Drive Changes API.

    Google Docs uses the same Drive Changes API as Google Drive to track
    changes to documents. Each change state is associated with a page token.

    Reference: https://developers.google.com/drive/api/guides/manage-changes
    """

    start_page_token: str = Field(
        default="",
        description="Drive Changes API page token for tracking document changes",
    )

    file_metadata: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Map of file_id -> {modified_time, md5_checksum, size} for change detection",
    )
