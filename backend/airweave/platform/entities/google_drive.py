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

from typing import Any, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, DeletionEntity, FileEntity
from airweave.platform.entities.utils import _determine_file_type_from_mime


class GoogleDriveDriveEntity(BaseEntity):
    """Schema for a Drive resource (shared drive).

    Reference:
      https://developers.google.com/drive/api/v3/reference/drives
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the drive ID)
    # - breadcrumbs
    # - name
    # - created_at (from created_time)
    # - updated_at (None - drives don't have modified time)

    # API fields
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


class GoogleDriveFileEntity(FileEntity):
    """Schema for a File resource (in a user's or shared drive).

    Reference:
      https://developers.google.com/drive/api/v3/reference/files
    """

    # Base fields are inherited from BaseEntity:
    # - entity_id (the file ID)
    # - breadcrumbs
    # - name
    # - created_at (from created_time)
    # - updated_at (from modified_time)

    # File fields are inherited from FileEntity:
    # - url (download_url or export URL)
    # - size (from file size in bytes)
    # - file_type (determined from mime_type)
    # - mime_type
    # - local_path (set after download)

    # API fields (Google Drive-specific)
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
    )
    icon_link: Optional[str] = AirweaveField(
        None, description="A static, far-reaching URL to the file's icon.", embeddable=False
    )
    md5_checksum: Optional[str] = AirweaveField(
        None, description="MD5 checksum for the content of the file.", embeddable=False
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


class GoogleDriveFileDeletionEntity(DeletionEntity):
    """Deletion signal for a Google Drive file.

    Emitted when the Drive Changes API reports a file was removed (deleted or access lost).
    The `entity_id` matches the original file's ID so downstream deletion can target
    the correct parent/children.
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the file ID)
    # - breadcrumbs
    # - name (generic deletion name)
    # - created_at (None - deletions don't have timestamps)
    # - updated_at (None - deletions don't have timestamps)
    # - deletion_status (inherited from DeletionEntity)
