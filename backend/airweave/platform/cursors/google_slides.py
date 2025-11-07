"""Google Slides cursor schema for incremental sync."""

from pydantic import Field

from ._base import BaseCursor


class GoogleSlidesCursor(BaseCursor):
    """Google Slides incremental sync cursor using Drive Changes API.

    Google Slides uses the same Drive Changes API as Google Drive to track
    changes to presentations. Each change state is associated with a page token.

    Reference: https://developers.google.com/drive/api/guides/manage-changes
    """

    start_page_token: str = Field(
        default="",
        description="Drive Changes API page token for tracking presentation changes",
    )




