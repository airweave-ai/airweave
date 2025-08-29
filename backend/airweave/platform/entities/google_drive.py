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

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import ChunkEntity, FileEntity
from airweave.platform.entities.utils import _determine_file_type_from_mime


class GoogleDriveDriveEntity(ChunkEntity):
    """Schema for a Drive resource (shared drive).

    Reference:
      https://developers.google.com/drive/api/v3/reference/drives
    """

    drive_id: str = AirweaveField(..., description="Unique ID of the shared drive.")
    name: Optional[str] = AirweaveField(
        None, description="The name of this shared drive.", embeddable=True
    )
    kind: Optional[str] = AirweaveField(
        None, description='Identifies what kind of resource this is; typically "drive#drive".'
    )
    color_rgb: Optional[str] = AirweaveField(
        None, description="The color of this shared drive as an RGB hex string."
    )
    created_time: Optional[datetime] = AirweaveField(
        None,
        description="When the shared drive was created (RFC 3339 date-time).",
        is_created_at=True,
    )
    hidden: bool = AirweaveField(
        False, description="Whether the shared drive is hidden from default view."
    )
    org_unit_id: Optional[str] = AirweaveField(
        None, description="The organizational unit of this shared drive, if applicable."
    )


class GoogleDriveFileEntity(FileEntity):
    """Schema for a File resource (in a user's or shared drive).

    Reference:
      https://developers.google.com/drive/api/v3/reference/files
    """

    file_id: str = AirweaveField(..., description="Unique ID of the file.")
    name: Optional[str] = AirweaveField(None, description="Name of the file.")
    mime_type: Optional[str] = AirweaveField(None, description="MIME type of the file.")
    description: Optional[str] = AirweaveField(
        None, description="Optional description of the file."
    )
    starred: bool = AirweaveField(
        False, description="Indicates whether the user has starred the file."
    )
    trashed: bool = AirweaveField(False, description="Whether the file is in the trash.")
    explicitly_trashed: bool = AirweaveField(
        False, description="Whether the file was explicitly trashed by the user."
    )
    parents: List[str] = AirweaveField(
        default_factory=list, description="IDs of the parent folders containing this file."
    )
    shared: bool = AirweaveField(False, description="Whether the file is shared.")
    web_view_link: Optional[str] = AirweaveField(
        None, description="Link for opening the file in a relevant Google editor or viewer."
    )
    icon_link: Optional[str] = AirweaveField(
        None, description="A static, far-reaching URL to the file's icon."
    )
    created_time: Optional[datetime] = AirweaveField(
        None, description="When the file was created (RFC 3339 date-time).", is_created_at=True
    )
    modified_time: Optional[datetime] = AirweaveField(
        None,
        description="When the file was last modified (RFC 3339 date-time).",
        is_updated_at=True,
    )
    size: Optional[int] = AirweaveField(
        None, description="The size of the file's content in bytes."
    )
    md5_checksum: Optional[str] = AirweaveField(
        None, description="MD5 checksum for the content of the file."
    )

    def __init__(self, **data):
        """Initialize the entity and set file_type from mime_type if not provided."""
        super().__init__(**data)
        if not self.file_type or self.file_type == "unknown":
            self.file_type = _determine_file_type_from_mime(self.mime_type)

    def model_dump(self, *args, **kwargs) -> dict[str, Any]:
        """Override model_dump to convert size to string."""
        data = super().model_dump(*args, **kwargs)
        if data.get("size") is not None:
            data["size"] = str(data["size"])
        return data


class GoogleDriveFileDeletionEntity(ChunkEntity):
    """Deletion signal for a Google Drive file.

    Emitted when the Drive Changes API reports a file was removed (deleted or access lost).
    The `entity_id` matches the original file's `file_id` used for `GoogleDriveFileEntity` so
    downstream deletion can target the correct parent/children.
    """

    file_id: str = AirweaveField(..., description="ID of the deleted file")
    deletion_status: str = AirweaveField(
        ..., description="Status indicating the file was removed (e.g., 'removed')"
    )
