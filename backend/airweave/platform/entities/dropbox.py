"""Dropbox entity schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb, FileEntity


class DropboxAccountEntity(BaseEntity):
    """Schema for Dropbox account-level entities based on the Dropbox API.

    Reference:
        https://www.dropbox.com/developers/documentation/http/documentation#users-get_current_account
    """

    account_id: str = AirweaveField(
        ...,
        description="Dropbox account ID",
        is_entity_id=True,
    )
    display_name: str = AirweaveField(
        ...,
        description="Display name for the account",
        is_name=True,
        embeddable=True,
    )
    abbreviated_name: Optional[str] = AirweaveField(
        None,
        description="Abbreviated form of the person's name (typically initials)",
        embeddable=False,
    )
    familiar_name: Optional[str] = AirweaveField(
        None, description="Locale-dependent name (usually given name in US)", embeddable=True
    )
    given_name: Optional[str] = AirweaveField(
        None, description="Also known as first name", embeddable=True
    )
    surname: Optional[str] = AirweaveField(
        None, description="Also known as last name or family name", embeddable=True
    )
    email: Optional[str] = AirweaveField(
        None, description="The user's email address", embeddable=True
    )
    email_verified: bool = AirweaveField(
        False, description="Whether the user has verified their email address", embeddable=False
    )
    disabled: bool = AirweaveField(
        False, description="Whether the user has been disabled", embeddable=False
    )
    account_type: Optional[str] = AirweaveField(
        None, description="Type of account (basic, pro, business, etc.)", embeddable=True
    )
    is_teammate: bool = AirweaveField(
        False, description="Whether this user is a teammate of the current user", embeddable=False
    )
    is_paired: bool = AirweaveField(
        False,
        description="Whether the user has both personal and work accounts linked",
        embeddable=False,
    )
    team_member_id: Optional[str] = AirweaveField(
        None, description="The user's unique team member ID (if part of a team)", embeddable=False
    )
    locale: Optional[str] = AirweaveField(
        None,
        description="The language that the user specified (IETF language tag)",
        embeddable=False,
    )
    country: Optional[str] = AirweaveField(
        None, description="The user's two-letter country code (ISO 3166-1)", embeddable=False
    )
    profile_photo_url: Optional[str] = AirweaveField(
        None, description="URL for the profile photo", embeddable=False
    )
    referral_link: Optional[str] = AirweaveField(
        None, description="The user's referral link", embeddable=False
    )
    space_used: Optional[int] = AirweaveField(
        None, description="The user's total space usage in bytes", embeddable=False
    )
    space_allocated: Optional[int] = AirweaveField(
        None, description="The user's total space allocation in bytes", embeddable=False
    )
    team_info: Optional[Dict] = AirweaveField(
        None,
        description="Information about the team if user is a member",
        embeddable=True,
    )
    root_info: Optional[Dict] = AirweaveField(
        None, description="Information about the user's root namespace", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to Dropbox home."""
        return "https://www.dropbox.com/home"

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> DropboxAccountEntity:
        """Build from a Dropbox /users/get_current_account API response."""
        name_data = data.get("name", {})
        space_usage = data.get("space_usage")
        account_type_obj = data.get("account_type")

        return cls(
            breadcrumbs=[],
            account_id=data.get("account_id") or "dropbox-account",
            display_name=name_data.get("display_name") or "Dropbox Account",
            abbreviated_name=name_data.get("abbreviated_name"),
            familiar_name=name_data.get("familiar_name"),
            given_name=name_data.get("given_name"),
            surname=name_data.get("surname"),
            email=data.get("email"),
            email_verified=data.get("email_verified", False),
            disabled=data.get("disabled", False),
            account_type=account_type_obj.get(".tag") if account_type_obj else None,
            is_teammate=data.get("is_teammate", False),
            is_paired=data.get("is_paired", False),
            team_member_id=data.get("team_member_id"),
            locale=data.get("locale"),
            country=data.get("country"),
            profile_photo_url=data.get("profile_photo_url"),
            referral_link=data.get("referral_link"),
            space_used=space_usage.get("used") if space_usage else None,
            space_allocated=(
                space_usage.get("allocation", {}).get("allocated") if space_usage else None
            ),
            team_info=data.get("team"),
            root_info=data.get("root_info"),
        )


class DropboxFolderEntity(BaseEntity):
    """Schema for Dropbox folder entities matching the Dropbox API.

    Reference:
        https://www.dropbox.com/developers/documentation/http/documentation#files-list_folder
    """

    id: str = AirweaveField(
        ...,
        description="Dropbox folder ID",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Folder name",
        is_name=True,
        embeddable=True,
    )
    path_lower: Optional[str] = AirweaveField(
        None,
        description="Lowercase full path starting with slash",
        embeddable=False,
    )
    path_display: Optional[str] = AirweaveField(
        None, description="Display path with proper casing", embeddable=True
    )
    sharing_info: Optional[Dict] = AirweaveField(
        None, description="Sharing information for the folder", embeddable=True
    )
    read_only: bool = AirweaveField(
        False, description="Whether the folder is read-only", embeddable=False
    )
    traverse_only: bool = AirweaveField(
        False, description="Whether the folder can only be traversed", embeddable=False
    )
    no_access: bool = AirweaveField(
        False, description="Whether the folder cannot be accessed", embeddable=False
    )
    property_groups: Optional[List[Dict]] = AirweaveField(
        None, description="Custom properties and tags", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Web URL pointing to the folder in Dropbox."""
        path = self.path_display or ""
        return f"https://www.dropbox.com/home{path}"

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, breadcrumbs: list[Breadcrumb]
    ) -> DropboxFolderEntity:
        """Build from a Dropbox files/list_folder entry with .tag == 'folder'."""
        folder_id = data.get("id", "")
        folder_path = data.get("path_lower", "")
        sharing_info = data.get("sharing_info", {})
        return cls(
            id=folder_id if folder_id else f"folder-{folder_path}",
            breadcrumbs=breadcrumbs,
            name=data.get("name", "Unnamed Folder"),
            path_lower=data.get("path_lower"),
            path_display=data.get("path_display"),
            sharing_info=sharing_info,
            read_only=sharing_info.get("read_only", False),
            traverse_only=sharing_info.get("traverse_only", False),
            no_access=sharing_info.get("no_access", False),
            property_groups=data.get("property_groups"),
        )


class DropboxFileEntity(FileEntity):
    """Schema for Dropbox file entities matching the Dropbox API.

    Reference:
        https://www.dropbox.com/developers/documentation/http/documentation#files-list_folder
    """

    id: str = AirweaveField(
        ...,
        description="Dropbox file ID",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="File name",
        is_name=True,
        embeddable=True,
    )
    path_lower: Optional[str] = AirweaveField(
        None, description="Lowercase full path in Dropbox", embeddable=False
    )
    path_display: Optional[str] = AirweaveField(
        None, description="Display path with proper casing", embeddable=True
    )
    rev: Optional[str] = AirweaveField(
        None, description="Unique identifier for the file revision", embeddable=False
    )
    client_modified: Optional[Any] = AirweaveField(
        None,
        description="When file was modified by client",
        embeddable=False,
        is_created_at=True,
    )
    server_modified: Optional[Any] = AirweaveField(
        None,
        description="When file was modified on server",
        embeddable=False,
        is_updated_at=True,
    )
    is_downloadable: bool = AirweaveField(
        True, description="Whether file can be downloaded directly", embeddable=False
    )
    content_hash: Optional[str] = AirweaveField(
        None, description="Dropbox content hash for integrity checks", embeddable=False
    )
    sharing_info: Optional[Dict] = AirweaveField(
        None, description="Sharing information for the file", embeddable=True
    )
    has_explicit_shared_members: Optional[bool] = AirweaveField(
        None, description="Whether file has explicit shared members", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Web URL that opens the file in Dropbox."""
        path = self.path_display or ""
        return f"https://www.dropbox.com/home{path}"
