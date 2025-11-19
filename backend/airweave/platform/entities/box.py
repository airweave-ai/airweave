"""Box entity schemas."""

from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


class BoxUserEntity(BaseEntity):
    """Schema for Box user entities."""

    user_id: str = AirweaveField(..., description="Box user ID", is_entity_id=True)
    name: str = AirweaveField(
        ..., description="Display name of the user", is_name=True, embeddable=True
    )
    created_at: Optional[str] = AirweaveField(
        None, description="When the user was created", is_created_at=True
    )
    updated_at: Optional[str] = AirweaveField(
        None, description="When the user was last modified", is_updated_at=True
    )

    login: Optional[str] = AirweaveField(
        None, description="Login email address of the user", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the user (active, inactive, etc.)", embeddable=False
    )
    job_title: Optional[str] = AirweaveField(
        None, description="Job title of the user", embeddable=True
    )
    phone: Optional[str] = AirweaveField(
        None, description="Phone number of the user", embeddable=True
    )
    address: Optional[str] = AirweaveField(None, description="Address of the user", embeddable=True)
    language: Optional[str] = AirweaveField(
        None, description="Language of the user", embeddable=False
    )
    timezone: Optional[str] = AirweaveField(
        None, description="Timezone of the user", embeddable=False
    )
    space_amount: Optional[int] = AirweaveField(
        None, description="Total storage space available to the user in bytes", embeddable=False
    )
    space_used: Optional[int] = AirweaveField(
        None, description="Storage space used by the user in bytes", embeddable=False
    )
    max_upload_size: Optional[int] = AirweaveField(
        None, description="Maximum file size the user can upload in bytes", embeddable=False
    )
    avatar_url: Optional[str] = AirweaveField(
        None, description="URL to the user's avatar image", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the user's Box profile."""
        return f"https://app.box.com/profile/{self.user_id}"


class BoxFolderEntity(BaseEntity):
    """Schema for Box folder entities."""

    folder_id: str = AirweaveField(..., description="Box folder ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Folder name", is_name=True, embeddable=True)
    created_at: Optional[str] = AirweaveField(
        None, description="When the folder was created", is_created_at=True
    )
    updated_at: Optional[str] = AirweaveField(
        None, description="When the folder was last modified", is_updated_at=True
    )

    description: Optional[str] = AirweaveField(
        None, description="Description of the folder", embeddable=True
    )
    size: Optional[int] = AirweaveField(
        None, description="Size of the folder in bytes", embeddable=False
    )
    path_collection: List[Dict] = AirweaveField(
        default_factory=list,
        description="Path of parent folders from root to this folder",
        embeddable=True,
    )
    content_created_at: Optional[Any] = AirweaveField(
        None,
        description="When the content in this folder was originally created",
        embeddable=False,
    )
    content_modified_at: Optional[Any] = AirweaveField(
        None,
        description="When the content in this folder was last modified",
        embeddable=False,
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created this folder", embeddable=True
    )
    modified_by: Optional[Dict] = AirweaveField(
        None, description="User who last modified this folder", embeddable=True
    )
    owned_by: Optional[Dict] = AirweaveField(
        None, description="User who owns this folder", embeddable=True
    )
    parent_id: Optional[str] = AirweaveField(
        None, description="ID of the parent folder", embeddable=False
    )
    parent_name: Optional[str] = AirweaveField(
        None, description="Name of the parent folder", embeddable=True
    )
    item_status: Optional[str] = AirweaveField(
        None,
        description="Status of the folder (active, trashed, deleted)",
        embeddable=False,
    )
    shared_link: Optional[Dict] = AirweaveField(
        None, description="Shared link information for this folder", embeddable=True
    )
    folder_upload_email: Optional[Dict] = AirweaveField(
        None,
        description="Email address that can be used to upload files to this folder",
        embeddable=True,
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with this folder", embeddable=True
    )
    has_collaborations: Optional[bool] = AirweaveField(
        None, description="Whether this folder has collaborations", embeddable=False
    )
    permissions: Optional[Dict] = AirweaveField(
        None, description="Permissions the current user has on this folder", embeddable=False
    )
    permalink_url: Optional[str] = AirweaveField(
        None,
        description="Direct link to view the folder in Box",
        embeddable=False,
        unhashable=True,
    )
    etag: Optional[str] = AirweaveField(
        None, description="Entity tag for versioning", embeddable=False
    )
    sequence_id: Optional[str] = AirweaveField(
        None, description="Sequence ID for the most recent user event", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Direct link to the folder."""
        if self.permalink_url:
            return self.permalink_url
        return f"https://app.box.com/folder/{self.folder_id}"


class BoxFileEntity(FileEntity):
    """Schema for Box file entities."""

    file_id: str = AirweaveField(..., description="Box file ID", is_entity_id=True)
    name: str = AirweaveField(..., description="File name", is_name=True, embeddable=True)
    created_at: Optional[str] = AirweaveField(
        None, description="When the file was created", is_created_at=True
    )
    updated_at: Optional[str] = AirweaveField(
        None, description="When the file was last modified", is_updated_at=True
    )

    description: Optional[str] = AirweaveField(
        None, description="Description of the file", embeddable=True
    )
    parent_folder_id: str = AirweaveField(
        ..., description="ID of the parent folder", embeddable=False
    )
    parent_folder_name: str = AirweaveField(
        ..., description="Name of the parent folder", embeddable=True
    )
    path_collection: List[Dict] = AirweaveField(
        default_factory=list,
        description="Path of parent folders from root to this file",
        embeddable=True,
    )
    sha1: Optional[str] = AirweaveField(
        None, description="SHA1 hash of the file contents", embeddable=False
    )
    extension: Optional[str] = AirweaveField(None, description="File extension", embeddable=False)
    version_number: Optional[str] = AirweaveField(
        None, description="Version number of the file", embeddable=False
    )
    comment_count: Optional[int] = AirweaveField(
        None, description="Number of comments on this file", embeddable=False
    )
    content_created_at: Optional[Any] = AirweaveField(
        None,
        description="When the content of this file was originally created",
        embeddable=False,
    )
    content_modified_at: Optional[Any] = AirweaveField(
        None,
        description="When the content of this file was last modified",
        embeddable=False,
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created this file", embeddable=True
    )
    modified_by: Optional[Dict] = AirweaveField(
        None, description="User who last modified this file", embeddable=True
    )
    owned_by: Optional[Dict] = AirweaveField(
        None, description="User who owns this file", embeddable=True
    )
    item_status: Optional[str] = AirweaveField(
        None, description="Status of the file (active, trashed, deleted)", embeddable=False
    )
    shared_link: Optional[Dict] = AirweaveField(
        None, description="Shared link information for this file", embeddable=True
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with this file", embeddable=True
    )
    has_collaborations: Optional[bool] = AirweaveField(
        None, description="Whether this file has collaborations", embeddable=False
    )
    permissions: Optional[Dict] = AirweaveField(
        None, description="Permissions the current user has on this file", embeddable=False
    )
    lock: Optional[Dict] = AirweaveField(
        None, description="Lock information if the file is locked", embeddable=False
    )
    permalink_url: Optional[str] = AirweaveField(
        None,
        description="Direct link to view the file in Box",
        embeddable=False,
        unhashable=True,
    )
    etag: Optional[str] = AirweaveField(
        None, description="Entity tag for versioning", embeddable=False
    )
    sequence_id: Optional[str] = AirweaveField(
        None, description="Sequence ID for the most recent user event", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Direct link to the file."""
        if self.permalink_url:
            return self.permalink_url
        return f"https://app.box.com/file/{self.file_id}"


class BoxCommentEntity(BaseEntity):
    """Schema for Box comment entities."""

    comment_id: str = AirweaveField(..., description="Box comment ID", is_entity_id=True)
    name: str = AirweaveField(
        ..., description="Comment preview or identifier", is_name=True, embeddable=True
    )
    created_at: Optional[str] = AirweaveField(
        None, description="When the comment was created", is_created_at=True
    )
    updated_at: Optional[str] = AirweaveField(
        None, description="When the comment was last modified", is_updated_at=True
    )

    file_id: str = AirweaveField(
        ..., description="ID of the file this comment is on", embeddable=False
    )
    file_name: str = AirweaveField(..., description="Name of the file", embeddable=True)
    message: str = AirweaveField(..., description="Content of the comment", embeddable=True)
    created_by: Dict = AirweaveField(
        ..., description="User who created this comment", embeddable=True
    )
    is_reply_comment: bool = AirweaveField(
        False, description="Whether this comment is a reply to another comment", embeddable=False
    )
    tagged_message: Optional[str] = AirweaveField(
        None,
        description="Tagged version of the message with user mentions",
        embeddable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link back to the file that hosts this comment."""
        return f"https://app.box.com/file/{self.file_id}"


class BoxCollaborationEntity(BaseEntity):
    """Schema for Box collaboration entities."""

    collaboration_id: str = AirweaveField(
        ..., description="Box collaboration ID", is_entity_id=True
    )
    name: str = AirweaveField(
        ..., description="Collaboration display label", is_name=True, embeddable=True
    )
    created_at: Optional[str] = AirweaveField(
        None, description="When the collaboration was created", is_created_at=True
    )
    updated_at: Optional[str] = AirweaveField(
        None, description="When the collaboration was last modified", is_updated_at=True
    )

    role: str = AirweaveField(
        ...,
        description="Role of the collaborator (editor, viewer, previewer, etc.)",
        embeddable=True,
    )
    accessible_by: Dict = AirweaveField(
        ...,
        description="User or group that this collaboration applies to",
        embeddable=True,
    )
    item: Dict = AirweaveField(
        ..., description="File or folder that is being collaborated on", embeddable=True
    )
    item_id: str = AirweaveField(
        ..., description="ID of the item being collaborated on", embeddable=False
    )
    item_type: str = AirweaveField(
        ..., description="Type of the item (file or folder)", embeddable=True
    )
    item_name: str = AirweaveField(
        ..., description="Name of the item being collaborated on", embeddable=True
    )
    status: str = AirweaveField(
        ..., description="Status of the collaboration (accepted, pending, etc.)", embeddable=True
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created this collaboration", embeddable=True
    )
    expires_at: Optional[Any] = AirweaveField(
        None, description="When this collaboration expires", embeddable=False
    )
    is_access_only: Optional[bool] = AirweaveField(
        None, description="Whether this is an access-only collaboration", embeddable=False
    )
    invite_email: Optional[str] = AirweaveField(
        None, description="Email address invited to collaborate", embeddable=True
    )
    acknowledged_at: Optional[Any] = AirweaveField(
        None, description="When the collaboration was acknowledged", embeddable=False
    )

    @computed_field(return_type=Optional[str])
    def web_url(self) -> Optional[str]:
        """Link back to the collaborated item."""
        if self.item_type == "file":
            return f"https://app.box.com/file/{self.item_id}"
        if self.item_type == "folder":
            return f"https://app.box.com/folder/{self.item_id}"
        return None
