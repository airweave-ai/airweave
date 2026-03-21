"""SharePoint entity schemas.

Entity schemas for SharePoint objects based on Microsoft Graph API:
 - User
 - Group
 - Site
 - Drive (document library)
 - DriveItem (file/folder)

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/sharepoint
  https://learn.microsoft.com/en-us/graph/api/resources/site
  https://learn.microsoft.com/en-us/graph/api/resources/drive
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb, FileEntity


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse Microsoft Graph ISO8601 timestamps into timezone-aware datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class SharePointUserEntity(BaseEntity):
    """Schema for a SharePoint user.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/user
    """

    id: str = AirweaveField(
        ...,
        description="SharePoint user ID.",
        is_entity_id=True,
    )
    display_name: str = AirweaveField(
        ...,
        description="The name displayed in the address book for the user.",
        embeddable=True,
        is_name=True,
    )
    user_principal_name: Optional[str] = AirweaveField(
        None,
        description="The user principal name (UPN) of the user (e.g., user@contoso.com).",
        embeddable=True,
    )
    mail: Optional[str] = AirweaveField(
        None, description="The SMTP address for the user.", embeddable=True
    )
    job_title: Optional[str] = AirweaveField(
        None, description="The user's job title.", embeddable=True
    )
    department: Optional[str] = AirweaveField(
        None, description="The department in which the user works.", embeddable=True
    )
    office_location: Optional[str] = AirweaveField(
        None, description="The office location in the user's place of business.", embeddable=True
    )
    mobile_phone: Optional[str] = AirweaveField(
        None, description="The primary cellular telephone number for the user.", embeddable=False
    )
    business_phones: Optional[List[str]] = AirweaveField(
        None, description="The telephone numbers for the user.", embeddable=False
    )
    account_enabled: Optional[bool] = AirweaveField(
        None, description="Whether the account is enabled.", embeddable=False
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="Link to the user's profile in SharePoint.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL that opens the SharePoint user profile or mailto link."""
        if self.web_url_override:
            return self.web_url_override
        if self.mail:
            return f"mailto:{self.mail}"
        return "https://sharepoint.com/"


class SharePointGroupEntity(BaseEntity):
    """Schema for a SharePoint group.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/group
    """

    id: str = AirweaveField(
        ...,
        description="Group ID.",
        is_entity_id=True,
    )
    display_name: str = AirweaveField(
        ...,
        description="The display name for the group.",
        embeddable=True,
        is_name=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="An optional description for the group.", embeddable=True
    )
    mail: Optional[str] = AirweaveField(
        None, description="The SMTP address for the group.", embeddable=True
    )
    mail_enabled: Optional[bool] = AirweaveField(
        None, description="Whether the group is mail-enabled.", embeddable=False
    )
    security_enabled: Optional[bool] = AirweaveField(
        None, description="Whether the group is a security group.", embeddable=False
    )
    group_types: List[str] = AirweaveField(
        default_factory=list,
        description="Specifies the group type (e.g., 'Unified' for Microsoft 365 groups).",
        embeddable=True,
    )
    visibility: Optional[str] = AirweaveField(
        None,
        description="Visibility of the group (Public, Private, HiddenMembership).",
        embeddable=False,
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="Link to the group in Microsoft 365.",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> SharePointGroupEntity:
        """Construct from a Microsoft Graph ``groups`` response item."""
        group_id = data.get("id")
        display_name = data.get("displayName", "Unknown Group")
        created = _parse_dt(data.get("createdDateTime"))

        return cls(
            breadcrumbs=[],
            id=group_id,
            name=display_name,
            created_at=created,
            updated_at=None,
            display_name=display_name,
            description=data.get("description"),
            mail=data.get("mail"),
            mail_enabled=data.get("mailEnabled"),
            security_enabled=data.get("securityEnabled"),
            group_types=data.get("groupTypes", []),
            visibility=data.get("visibility"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Outlook web URL for this group."""
        if self.web_url_override:
            return self.web_url_override
        return f"https://outlook.office.com/groups/{self.id}"


class SharePointSiteEntity(BaseEntity):
    """Schema for a SharePoint site.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/site
    """

    id: str = AirweaveField(
        ...,
        description="Site ID from Microsoft Graph.",
        is_entity_id=True,
    )
    display_name: str = AirweaveField(
        ...,
        description="The full title for the site.",
        embeddable=True,
        is_name=True,
    )
    site_name: Optional[str] = AirweaveField(
        None, description="The name/title of the site.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="The descriptive text for the site.", embeddable=True
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="URL that displays the site in the browser.",
        embeddable=False,
        unhashable=True,
    )
    is_personal_site: Optional[bool] = AirweaveField(
        None, description="Whether the site is a personal site.", embeddable=False
    )
    site_collection: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Details about the site's site collection.", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the SharePoint web URL for this site."""
        if self.web_url_override:
            return self.web_url_override
        return f"https://sharepoint.com/sites/{self.id}"


class SharePointDriveEntity(BaseEntity):
    """Schema for a SharePoint drive (document library).

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/drive
    """

    id: str = AirweaveField(
        ...,
        description="Drive ID.",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Drive name.",
        embeddable=True,
        is_name=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="User-visible description of the drive.", embeddable=True
    )
    drive_type: Optional[str] = AirweaveField(
        None,
        description="Type of drive (documentLibrary, business, etc.).",
        embeddable=True,
    )
    web_url_override: Optional[str] = AirweaveField(
        None, description="URL to view the drive in a browser.", embeddable=False, unhashable=True
    )
    owner: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the drive's owner.", embeddable=True
    )
    quota: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the drive's storage quota.", embeddable=False
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this drive.", embeddable=False
    )

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, site_id: str, site_name: str
    ) -> SharePointDriveEntity:
        """Construct from a Microsoft Graph ``drives`` response item."""
        drive_id = data.get("id")
        drive_name = data.get("name", "Unknown Drive")
        site_breadcrumb = Breadcrumb(
            entity_id=site_id,
            name=site_name,
            entity_type="SharePointSiteEntity",
        )

        return cls(
            breadcrumbs=[site_breadcrumb],
            id=drive_id,
            name=drive_name,
            created_at=_parse_dt(data.get("createdDateTime")),
            updated_at=_parse_dt(data.get("lastModifiedDateTime")),
            description=data.get("description"),
            drive_type=data.get("driveType"),
            web_url_override=data.get("webUrl"),
            owner=data.get("owner"),
            quota=data.get("quota"),
            site_id=site_id,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the SharePoint web URL for this drive."""
        if self.web_url_override:
            return self.web_url_override
        if self.site_id:
            return f"https://sharepoint.com/sites/{self.site_id}/_layouts/15/onedrive.aspx"
        return "https://onedrive.live.com/"


class SharePointDriveItemEntity(FileEntity):
    """Schema for a SharePoint drive item (file or folder).

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/driveitem
    """

    id: str = AirweaveField(
        ...,
        description="Drive item ID.",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Graph item name.",
        embeddable=True,
        is_name=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="User-visible description of the item.", embeddable=True
    )
    web_url_override: Optional[str] = AirweaveField(
        None, description="URL to display the item in a browser.", embeddable=False
    )
    file: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="File metadata if the item is a file (e.g., mimeType, hashes).",
        embeddable=False,
    )
    folder: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Folder metadata if the item is a folder (e.g., childCount).",
        embeddable=False,
    )
    parent_reference: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Information about the parent of this item (driveId, path, etc).",
        embeddable=False,
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the item.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who last modified the item.", embeddable=True
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this item.", embeddable=False
    )
    drive_id: Optional[str] = AirweaveField(
        None, description="ID of the drive that contains this item.", embeddable=False
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        site_id: str,
        drive_id: str,
        site_breadcrumb: Breadcrumb,
        drive_breadcrumb: Breadcrumb,
        download_url: Optional[str] = None,
    ) -> Optional[SharePointDriveItemEntity]:
        """Construct from a Microsoft Graph ``driveItem`` response.

        Returns None for folders or items without a download URL.
        """
        if "folder" in data:
            return None
        if not download_url:
            return None

        file_info = data.get("file", {})
        mime_type = file_info.get("mimeType") or "application/octet-stream"

        if mime_type and "/" in mime_type:
            file_type = mime_type.split("/")[0]
        else:
            ext = os.path.splitext(data.get("name", ""))[1].lower().lstrip(".")
            file_type = ext if ext else "file"

        return cls(
            id=data["id"],
            breadcrumbs=[site_breadcrumb, drive_breadcrumb],
            name=data.get("name"),
            created_at=_parse_dt(data.get("createdDateTime")),
            updated_at=_parse_dt(data.get("lastModifiedDateTime")),
            url=download_url,
            size=data.get("size", 0),
            file_type=file_type,
            mime_type=mime_type,
            local_path=None,
            description=data.get("description"),
            web_url_override=data.get("webUrl"),
            file=file_info,
            folder=data.get("folder"),
            parent_reference=data.get("parentReference", {}),
            created_by=data.get("createdBy"),
            last_modified_by=data.get("lastModifiedBy"),
            site_id=site_id,
            drive_id=drive_id,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the SharePoint web URL for this drive item."""
        if self.web_url_override:
            return self.web_url_override
        return f"https://sharepoint.com/_layouts/15/Doc.aspx?sourcedoc={self.id}"


class SharePointListEntity(BaseEntity):
    """Schema for a SharePoint list.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/list
    """

    id: str = AirweaveField(
        ...,
        description="List ID.",
        is_entity_id=True,
    )
    display_name: str = AirweaveField(
        ...,
        description="The displayable title of the list.",
        embeddable=True,
        is_name=True,
    )
    list_name: Optional[str] = AirweaveField(
        None, description="The name of the list.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="The description of the list.", embeddable=True
    )
    web_url_override: Optional[str] = AirweaveField(
        None, description="URL to view the list in browser.", embeddable=False
    )
    list_info: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Additional list metadata (template, hidden, etc).", embeddable=False
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this list.", embeddable=False
    )

    @classmethod
    def from_api(
        cls, data: Dict[str, Any], *, site_id: str, site_breadcrumb: Breadcrumb
    ) -> SharePointListEntity:
        """Construct from a Microsoft Graph ``lists`` response item."""
        list_id = data.get("id")
        display_name = data.get("displayName", "Unknown List")

        return cls(
            breadcrumbs=[site_breadcrumb],
            id=list_id,
            name=display_name,
            created_at=_parse_dt(data.get("createdDateTime")),
            updated_at=_parse_dt(data.get("lastModifiedDateTime")),
            display_name=display_name,
            list_name=data.get("name"),
            description=data.get("description"),
            web_url_override=data.get("webUrl"),
            list_info=data.get("list"),
            site_id=site_id,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the SharePoint web URL for this list."""
        if self.web_url_override:
            return self.web_url_override
        if self.site_id:
            return f"https://sharepoint.com/sites/{self.site_id}/lists/{self.id}"
        return "https://sharepoint.com/"


class SharePointListItemEntity(BaseEntity):
    """Schema for a SharePoint list item.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/listitem
    """

    id: str = AirweaveField(
        ...,
        description="List item ID.",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Display title for the list item.",
        embeddable=True,
        is_name=True,
    )
    fields: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="The values of the columns set on this list item (dynamic schema).",
        embeddable=True,
    )
    content_type: Optional[Dict[str, Any]] = AirweaveField(
        None, description="The content type of this list item.", embeddable=False
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the item.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who last modified the item.", embeddable=True
    )
    web_url_override: Optional[str] = AirweaveField(
        None, description="URL to view the item in browser.", embeddable=False
    )
    list_id: Optional[str] = AirweaveField(
        None, description="ID of the list that contains this item.", embeddable=False
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this item.", embeddable=False
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        site_id: str,
        list_id: str,
        site_breadcrumb: Breadcrumb,
        list_breadcrumb: Breadcrumb,
    ) -> SharePointListItemEntity:
        """Construct from a Microsoft Graph ``listItem`` response."""
        item_id = data.get("id")
        fields = data.get("fields", {})
        item_name = fields.get("Title") or fields.get("Name") or f"ListItem {item_id}"

        return cls(
            breadcrumbs=[site_breadcrumb, list_breadcrumb],
            id=item_id,
            name=item_name,
            created_at=_parse_dt(data.get("createdDateTime")),
            updated_at=_parse_dt(data.get("lastModifiedDateTime")),
            title=item_name,
            fields=fields,
            content_type=data.get("contentType"),
            created_by=data.get("createdBy"),
            last_modified_by=data.get("lastModifiedBy"),
            web_url_override=data.get("webUrl"),
            list_id=list_id,
            site_id=site_id,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the SharePoint web URL for this list item."""
        if self.web_url_override:
            return self.web_url_override
        if self.site_id and self.list_id:
            return f"https://sharepoint.com/sites/{self.site_id}/lists/{self.list_id}/DispForm.aspx?ID={self.id}"
        return "https://sharepoint.com/"


class SharePointPageEntity(BaseEntity):
    """Schema for a SharePoint site page.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/sitepage
    """

    id: str = AirweaveField(
        ...,
        description="Page ID.",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="The title of the page.",
        embeddable=True,
        is_name=True,
    )
    page_name: Optional[str] = AirweaveField(
        None, description="The name of the page.", embeddable=True
    )
    content: Optional[str] = AirweaveField(
        None,
        description="The actual page content (extracted from webParts).",
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="Description or summary of the page content.", embeddable=True
    )
    page_layout: Optional[str] = AirweaveField(
        None, description="The layout type of the page (article, home, etc).", embeddable=False
    )
    web_url_override: Optional[str] = AirweaveField(
        None, description="URL to view the page in browser.", embeddable=False
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the page.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who last modified the page.", embeddable=True
    )
    publishing_state: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Publishing status of the page.", embeddable=False
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this page.", embeddable=False
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        site_id: str,
        site_breadcrumb: Breadcrumb,
        content: str = "",
    ) -> SharePointPageEntity:
        """Construct from a Microsoft Graph ``sitePage`` response."""
        page_id = data.get("id")
        title = data.get("title", "Untitled Page")

        return cls(
            breadcrumbs=[site_breadcrumb],
            id=page_id,
            name=title,
            created_at=_parse_dt(data.get("createdDateTime")),
            updated_at=_parse_dt(data.get("lastModifiedDateTime")),
            title=title,
            page_name=data.get("name"),
            content=content,
            description=data.get("description"),
            page_layout=data.get("pageLayout"),
            web_url_override=data.get("webUrl"),
            created_by=data.get("createdBy"),
            last_modified_by=data.get("lastModifiedBy"),
            publishing_state=data.get("publishingState"),
            site_id=site_id,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the SharePoint web URL for this page."""
        if self.web_url_override:
            return self.web_url_override
        if self.site_id:
            page = self.page_name or self.id
            return f"https://sharepoint.com/sites/{self.site_id}/SitePages/{page}.aspx"
        return "https://sharepoint.com/"
