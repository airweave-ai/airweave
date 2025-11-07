"""Google Drive cursor schema for incremental sync."""

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




