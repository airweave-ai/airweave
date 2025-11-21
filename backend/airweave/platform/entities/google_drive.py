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

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, DeletionEntity, FileEntity
from airweave.platform.entities.utils import _determine_file_type_from_mime


class GoogleDriveDriveEntity(BaseEntity):
    """Schema for a Drive resource (shared drive).

    Reference:
      https://developers.google.com/drive/api/v3/reference/drives
    """

    drive_id: str = AirweaveField(
        ...,
        description="Unique identifier for the shared drive.",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Display name of the shared drive.",
        is_name=True,
        embeddable=True,
    )
    created_time: Optional[datetime] = AirweaveField(
        None,
        description="Creation timestamp of the shared drive.",
        is_created_at=True,
    )
    kind: Optional[str] = AirweaveField(
        None,
        description='Identifies what kind of resource this is; typically "drive#drive".',
        embeddable=False,
    )
    color_rgb: Optional[str] = AirweaveField(
        None, description="The color of this shared drive as an RGB hex string.", embeddable=False
    )
    hidden: bool = AirweaveField(
        False, description="Whether the shared drive is hidden from default view.", embeddable=False
    )
    org_unit_id: Optional[str] = AirweaveField(
        None,
        description="The organizational unit of this shared drive, if applicable.",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to open the shared drive in Google Drive."""
        return f"https://drive.google.com/drive/folders/{self.drive_id}"


class GoogleDriveFileEntity(FileEntity):
    """Schema for a File resource (in a user's or shared drive).

    Reference:
      https://developers.google.com/drive/api/v3/reference/files
    """

    file_id: str = AirweaveField(
        ...,
        description="Unique identifier for the file.",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Display title of the file.",
        is_name=True,
        embeddable=True,
    )
    created_time: datetime = AirweaveField(
        ...,
        description="Timestamp when the file was created.",
        is_created_at=True,
    )
    modified_time: datetime = AirweaveField(
        ...,
        description="Timestamp when the file was last modified.",
        is_updated_at=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="Optional description of the file.", embeddable=True
    )
    starred: bool = AirweaveField(
        False, description="Indicates whether the user has starred the file.", embeddable=False
    )
    trashed: bool = AirweaveField(
        False, description="Whether the file is in the trash.", embeddable=False
    )
    explicitly_trashed: bool = AirweaveField(
        False, description="Whether the file was explicitly trashed by the user.", embeddable=False
    )
    parents: List[str] = AirweaveField(
        default_factory=list,
        description="IDs of the parent folders containing this file.",
        embeddable=False,
    )
    owners: List[Any] = AirweaveField(
        default_factory=list, description="Owners of the file.", embeddable=False
    )
    shared: bool = AirweaveField(False, description="Whether the file is shared.", embeddable=False)
    web_view_link: Optional[str] = AirweaveField(
        None,
        description="Link for opening the file in a relevant Google editor or viewer.",
        embeddable=False,
        unhashable=True,
    )
    icon_link: Optional[str] = AirweaveField(
        None, description="A static, far-reaching URL to the file's icon.", embeddable=False
    )
    md5_checksum: Optional[str] = AirweaveField(
        None, description="MD5 checksum for the content of the file.", embeddable=False
    )
    shared_with_me_time: Optional[datetime] = AirweaveField(
        None, description="Time when this file was shared with the user.", embeddable=False
    )
    modified_by_me_time: Optional[datetime] = AirweaveField(
        None, description="Last time the user modified the file.", embeddable=False
    )
    viewed_by_me_time: Optional[datetime] = AirweaveField(
        None, description="Last time the user viewed the file.", embeddable=False
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

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to open the file in Google Drive."""
        if self.web_view_link:
            return self.web_view_link
        return f"https://drive.google.com/file/d/{self.file_id}/view"


class GoogleDriveFileDeletionEntity(DeletionEntity):
    """Deletion signal for a Google Drive file."""

    deletes_entity_class = GoogleDriveFileEntity

    file_id: str = AirweaveField(
        ...,
        description="ID of the file that was deleted.",
        is_entity_id=True,
    )
    label: str = AirweaveField(
        ...,
        description="Human-readable deletion label.",
        is_name=True,
        embeddable=True,
    )
    drive_id: Optional[str] = AirweaveField(
        None, description="Drive identifier that contained the file.", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Fallback drive link for deleted files."""
        if self.drive_id:
            return f"https://drive.google.com/drive/folders/{self.drive_id}"
        return "https://drive.google.com/drive/my-drive"
