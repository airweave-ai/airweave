"""Google Drive entity schemas.

Based on the Google Drive API reference (readonly scopes),
we define entity schemas for:
 - Drive objects (e.g., shared drives)
 - File objects (e.g., user-drive files)

They follow a style similar to that of Asana, HubSpot, and Todoist entity schemas.

References:
    https://developers.google.com/drive/api/v3/reference/drives (Drive)
    https://developers.google.com/drive/api/v3/reference/files  (File)
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity
from airweave.platform.entities._lazy import LazyEntity


class GoogleDriveDriveEntity(ChunkEntity):
    """Schema for a Drive resource (shared drive).

    Reference:
      https://developers.google.com/drive/api/v3/reference/drives
    """

    drive_id: str = Field(..., description="Unique ID of the shared drive.")
    name: Optional[str] = Field(None, description="The name of this shared drive.")
    kind: Optional[str] = Field(
        None, description='Identifies what kind of resource this is; typically "drive#drive".'
    )
    color_rgb: Optional[str] = Field(
        None, description="The color of this shared drive as an RGB hex string."
    )
    created_time: Optional[datetime] = Field(
        None, description="When the shared drive was created (RFC 3339 date-time)."
    )
    hidden: bool = Field(False, description="Whether the shared drive is hidden from default view.")
    org_unit_id: Optional[str] = Field(
        None, description="The organizational unit of this shared drive, if applicable."
    )


class GoogleDriveFileEntity(FileEntity, LazyEntity):
    """Schema for a File resource (in a user's or shared drive) with lazy download support.

    Reference:
      https://developers.google.com/drive/api/v3/reference/files
    """

    file_id: str = Field(..., description="Unique ID of the file.")
    name: Optional[str] = Field(None, description="Name of the file.")
    mime_type: Optional[str] = Field(None, description="MIME type of the file.")
    description: Optional[str] = Field(None, description="Optional description of the file.")
    starred: bool = Field(False, description="Indicates whether the user has starred the file.")
    trashed: bool = Field(False, description="Whether the file is in the trash.")
    explicitly_trashed: bool = Field(
        False, description="Whether the file was explicitly trashed by the user."
    )
    parents: List[str] = Field(
        default_factory=list, description="IDs of the parent folders containing this file."
    )
    shared: bool = Field(False, description="Whether the file is shared.")
    web_view_link: Optional[str] = Field(
        None, description="Link for opening the file in a relevant Google editor or viewer."
    )
    icon_link: Optional[str] = Field(
        None, description="A static, far-reaching URL to the file's icon."
    )
    created_time: Optional[datetime] = Field(
        None, description="When the file was created (RFC 3339 date-time)."
    )
    modified_time: Optional[datetime] = Field(
        None, description="When the file was last modified (RFC 3339 date-time)."
    )
    size: Optional[int] = Field(None, description="The size of the file's content in bytes.")
    md5_checksum: Optional[str] = Field(
        None, description="MD5 checksum for the content of the file."
    )

    def __init__(self, **data):
        """Initialize GoogleDriveFileEntity ensuring LazyEntity setup."""
        super().__init__(**data)
        # Ensure LazyEntity initialization
        if not hasattr(self, "_lazy_operations"):
            self._lazy_operations = {}
        if not hasattr(self, "_lazy_results"):
            self._lazy_results = {}
        if not hasattr(self, "_is_materialized"):
            self._is_materialized = False

    def model_dump(self, *args, **kwargs) -> dict[str, Any]:
        """Override model_dump to convert size to string."""
        data = super().model_dump(*args, **kwargs)
        if data.get("size") is not None:
            data["size"] = str(data["size"])
        return data

    async def _apply_results(self) -> None:
        """Apply lazy operation results to entity fields."""
        if "download_file" in self._lazy_results:
            result = self._lazy_results["download_file"]
            # The result should be the processed entity with local_path set
            if result and hasattr(result, "local_path"):
                self.local_path = result.local_path
                if hasattr(result, "metadata"):
                    self.metadata = result.metadata
                if hasattr(result, "should_skip"):
                    self.should_skip = result.should_skip
