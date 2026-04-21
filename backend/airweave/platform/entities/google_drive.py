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

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb, DeletionEntity, FileEntity
from airweave.platform.entities.utils import _determine_file_type_from_mime

_GOOGLE_EXPORT_MAP: Dict[str, tuple[str, str]] = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
}


def _parse_drive_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse Google Drive RFC3339 timestamp into an aware datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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
    sha256_checksum: Optional[str] = AirweaveField(
        None, description="SHA256 checksum for the content of the file.", embeddable=False,
        unhashable=True,
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

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        breadcrumbs: List[Breadcrumb],
    ) -> GoogleDriveFileEntity:
        """Build from a Google Drive API file object.

        Args:
            data: Raw file metadata dict from the Drive API.
            breadcrumbs: Parent hierarchy breadcrumbs.
        """
        mime_type = data.get("mimeType", "")
        file_name = data.get("name", "Untitled")
        file_id = data["id"]

        if mime_type.startswith("application/vnd.google-apps."):
            export_mime_type, file_extension = _GOOGLE_EXPORT_MAP.get(
                mime_type, ("application/pdf", ".pdf")
            )
            download_url = (
                f"https://www.googleapis.com/drive/v3/files/{file_id}"
                f"/export?mimeType={export_mime_type}"
            )
            if not file_name.lower().endswith(file_extension):
                file_name = f"{file_name}{file_extension}"
        else:
            download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

        created_time = _parse_drive_dt(data.get("createdTime")) or datetime.utcnow()
        modified_time = _parse_drive_dt(data.get("modifiedTime")) or created_time

        return cls(
            breadcrumbs=breadcrumbs,
            file_id=file_id,
            title=data.get("name", "Untitled"),
            created_time=created_time,
            modified_time=modified_time,
            name=file_name,
            created_at=created_time,
            updated_at=modified_time,
            url=download_url,
            size=int(data["size"]) if data.get("size") else 0,
            file_type=_determine_file_type_from_mime(mime_type),
            mime_type=mime_type or "application/octet-stream",
            local_path=None,
            description=data.get("description"),
            starred=data.get("starred", False),
            trashed=data.get("trashed", False),
            explicitly_trashed=data.get("explicitlyTrashed", False),
            parents=data.get("parents", []),
            owners=data.get("owners", []),
            shared=data.get("shared", False),
            web_view_link=data.get("webViewLink"),
            icon_link=data.get("iconLink"),
            md5_checksum=data.get("md5Checksum"),
            sha256_checksum=data.get("sha256Checksum"),
            shared_with_me_time=_parse_drive_dt(data.get("sharedWithMeTime")),
            modified_by_me_time=_parse_drive_dt(data.get("modifiedByMeTime")),
            viewed_by_me_time=_parse_drive_dt(data.get("viewedByMeTime")),
            source_hash=(
                f"sha256:{data['sha256Checksum']}"
                if data.get("sha256Checksum")
                else f"version:{data['version']}" if data.get("version") else None
            ),
        )

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

    @classmethod
    def from_api(
        cls,
        change: Dict[str, Any],
    ) -> GoogleDriveFileDeletionEntity:
        """Build from a Google Drive Changes API change object.

        Args:
            change: A single change dict from the Drive Changes API. Must contain
                    a resolvable ``fileId`` (either top-level or nested in ``file``).
        """
        file_obj = change.get("file") or {}
        file_id = change.get("fileId") or file_obj.get("id")
        label = file_obj.get("name") or file_id

        drive_id = file_obj.get("driveId") or change.get("driveId")
        parents = file_obj.get("parents") or []
        if not drive_id and parents:
            drive_id = parents[0]

        return cls(
            breadcrumbs=[],
            file_id=file_id,
            label=f"Deleted file {label}",
            drive_id=drive_id,
            deletion_status="removed",
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Fallback drive link for deleted files."""
        if self.drive_id:
            return f"https://drive.google.com/drive/folders/{self.drive_id}"
        return "https://drive.google.com/drive/my-drive"
