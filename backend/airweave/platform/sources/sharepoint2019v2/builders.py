"""Entity builders for SharePoint 2019 V2.

This module provides functions for building entity objects from SharePoint
API response data. Each builder validates required fields and extracts
access control information.

Entity types:
- Site (Web): SharePoint site or subsite
- List: Document library or custom list
- Item: Regular list item (contacts, tasks, etc.)
- File: Document in a document library
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from airweave.platform.entities._base import AccessControl, Breadcrumb
from airweave.platform.entities.sharepoint2019v2 import (
    SharePoint2019V2FileEntity,
    SharePoint2019V2ItemEntity,
    SharePoint2019V2ListEntity,
    SharePoint2019V2SiteEntity,
)
from airweave.platform.sources.sharepoint2019v2.acl import (
    clean_role_assignments,
    extract_access_control,
)
from airweave.platform.sync.exceptions import EntityProcessingError


def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string from SharePoint API.

    Handles the 'Z' suffix by converting to '+00:00' for fromisoformat().

    Args:
        dt_str: ISO format datetime string, possibly ending in 'Z'

    Returns:
        Parsed datetime or None if input is None/invalid
    """
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


async def _extract_access(
    data: Dict[str, Any],
    ldap_client: Optional[Any] = None,
) -> AccessControl:
    """Extract AccessControl from SharePoint entity data.

    Args:
        data: Entity dict with RoleAssignments key
        ldap_client: Optional LDAPClient for SID resolution

    Returns:
        AccessControl object with viewers list
    """
    role_assignments_raw = data.get("RoleAssignments", {})
    cleaned_roles = clean_role_assignments(role_assignments_raw)
    return await extract_access_control(cleaned_roles, ldap_client)


def build_web_url(site_url: str, server_relative_url: str) -> str:
    """Construct full web URL from server relative path.

    Args:
        site_url: Base site URL (e.g. http://sharepoint.example.com/sites/mysite)
        server_relative_url: Server relative path (e.g. /sites/mysite/doc.docx)

    Returns:
        Full URL (e.g. http://sharepoint.example.com/sites/mysite/doc.docx)
    """
    parsed = urlparse(site_url)
    return f"{parsed.scheme}://{parsed.netloc}{server_relative_url}"


# -----------------------------------------------------------------------------
# Site Entity Builder
# -----------------------------------------------------------------------------


async def build_site_entity(
    site_data: Dict[str, Any],
    breadcrumbs: List[Breadcrumb],
    ldap_client: Optional[Any] = None,
) -> SharePoint2019V2SiteEntity:
    """Build Site Entity from SharePoint API response.

    Args:
        site_data: Site metadata from /_api/web endpoint
        breadcrumbs: Parent breadcrumb trail
        ldap_client: Optional LDAPClient for SID resolution

    Returns:
        SharePoint2019V2SiteEntity instance

    Raises:
        EntityProcessingError: If required fields are missing
    """
    # Validate required fields
    site_id: Optional[str] = site_data.get("Id")
    if not site_id:
        raise EntityProcessingError("Missing Id for site")

    title: Optional[str] = site_data.get("Title")
    if not title:
        raise EntityProcessingError(f"Missing Title for site {site_id}")

    url: Optional[str] = site_data.get("Url")
    if not url:
        raise EntityProcessingError(f"Missing Url for site {site_id}")

    server_relative_url: Optional[str] = site_data.get("ServerRelativeUrl")
    if not server_relative_url:
        raise EntityProcessingError(f"Missing ServerRelativeUrl for site {site_id}")

    return SharePoint2019V2SiteEntity(
        site_id=site_id,
        title=title,
        url=url,
        server_relative_url=server_relative_url,
        web_template=site_data.get("WebTemplate"),
        description=site_data.get("Description"),
        created_at=_parse_datetime(site_data.get("Created")),
        last_modified_date=_parse_datetime(site_data.get("LastItemModifiedDate")),
        access=await _extract_access(site_data, ldap_client),
        breadcrumbs=breadcrumbs,
    )


# -----------------------------------------------------------------------------
# List Entity Builder
# -----------------------------------------------------------------------------


async def build_list_entity(
    list_data: Dict[str, Any],
    parent_web_url: str,
    breadcrumbs: List[Breadcrumb],
    ldap_client: Optional[Any] = None,
) -> SharePoint2019V2ListEntity:
    """Build List Entity from SharePoint API response.

    Args:
        list_data: List metadata from /_api/web/lists endpoint
        parent_web_url: URL of the parent site
        breadcrumbs: Parent breadcrumb trail
        ldap_client: Optional LDAPClient for SID resolution

    Returns:
        SharePoint2019V2ListEntity instance

    Raises:
        EntityProcessingError: If required fields are missing
    """
    # Validate required fields
    list_id: Optional[str] = list_data.get("Id")
    if not list_id:
        raise EntityProcessingError("Missing Id for list")

    title: Optional[str] = list_data.get("Title")
    if not title:
        raise EntityProcessingError(f"Missing Title for list {list_id}")

    base_template: Optional[int] = list_data.get("BaseTemplate")
    if base_template is None:
        raise EntityProcessingError(f"Missing BaseTemplate for list {list_id}")

    item_count: Optional[int] = list_data.get("ItemCount")
    if item_count is None:
        raise EntityProcessingError(f"Missing ItemCount for list {list_id}")

    hidden: Optional[bool] = list_data.get("Hidden")
    if hidden is None:
        raise EntityProcessingError(f"Missing Hidden for list {list_id}")

    return SharePoint2019V2ListEntity(
        list_id=list_id,
        title=title,
        description=list_data.get("Description"),
        parent_web_url=parent_web_url,
        item_count=item_count,
        base_template=base_template,
        hidden=hidden,
        created_at=_parse_datetime(list_data.get("Created")),
        last_modified_date=_parse_datetime(list_data.get("LastItemModifiedDate")),
        access=await _extract_access(list_data, ldap_client),
        breadcrumbs=breadcrumbs,
    )


# -----------------------------------------------------------------------------
# Item Entity Builder
# -----------------------------------------------------------------------------


async def build_item_entity(
    item_data: Dict[str, Any],
    site_url: str,
    list_id: str,
    breadcrumbs: List[Breadcrumb],
    ldap_client: Optional[Any] = None,
) -> SharePoint2019V2ItemEntity:
    """Build Item Entity for non-file list items.

    Args:
        item_data: Item metadata from /_api/web/lists/items endpoint
        site_url: Base URL of the site (for building web_url)
        list_id: GUID of the parent list (used for composite entity ID)
        breadcrumbs: Parent breadcrumb trail
        ldap_client: Optional LDAPClient for SID resolution

    Returns:
        SharePoint2019V2ItemEntity instance

    Raises:
        EntityProcessingError: If required fields are missing
    """
    # Validate required fields
    item_id: Optional[int] = item_data.get("Id")
    if item_id is None:
        raise EntityProcessingError("Missing Id for item")

    guid: Optional[str] = item_data.get("GUID")
    if not guid:
        raise EntityProcessingError(f"Missing GUID for item {item_id}")

    title: Optional[str] = item_data.get("Title")
    if not title:
        raise EntityProcessingError(f"Missing Title for item {item_id}")

    fs_obj_type: Optional[int] = item_data.get("FileSystemObjectType")
    if fs_obj_type is None:
        raise EntityProcessingError(f"Missing FileSystemObjectType for item {item_id}")

    fields_raw: Optional[Dict[str, Any]] = item_data.get("FieldValuesAsText")
    if not fields_raw:
        raise EntityProcessingError(f"Missing FieldValuesAsText for item {item_id}")

    file_ref: Optional[str] = fields_raw.get("FileRef")
    if not file_ref:
        raise EntityProcessingError(f"Missing FileRef for item {item_id}")

    web_url = build_web_url(site_url, file_ref)
    sp_entity_id = f"sp2019v2:item:{list_id}:{item_id}"

    return SharePoint2019V2ItemEntity(
        list_id=list_id,
        item_id=item_id,
        sp_entity_id=sp_entity_id,
        guid=guid,
        title=title,
        web_url=web_url,
        created_at=_parse_datetime(item_data.get("Created")),
        updated_at=_parse_datetime(item_data.get("Modified")),
        file_system_object_type=fs_obj_type,
        fields=fields_raw,
        access=await _extract_access(item_data, ldap_client),
        breadcrumbs=breadcrumbs,
    )


# -----------------------------------------------------------------------------
# File Entity Builder
# -----------------------------------------------------------------------------


async def build_file_entity(
    item_data: Dict[str, Any],
    site_url: str,
    list_id: str,
    breadcrumbs: List[Breadcrumb],
    ldap_client: Optional[Any] = None,
) -> SharePoint2019V2FileEntity:
    """Build File Entity for files in Document Libraries.

    Args:
        item_data: Item metadata with expanded File object
        site_url: Base URL of the site
        list_id: GUID of the parent document library (used for composite entity ID)
        breadcrumbs: Parent breadcrumb trail
        ldap_client: Optional LDAPClient for SID resolution

    Returns:
        SharePoint2019V2FileEntity instance

    Raises:
        EntityProcessingError: If required fields are missing
    """
    # Validate required fields
    item_id: Optional[int] = item_data.get("Id")
    if item_id is None:
        raise EntityProcessingError("Missing Id for file item")

    guid: Optional[str] = item_data.get("GUID")
    if not guid:
        raise EntityProcessingError(f"Missing GUID for file item {item_id}")

    fs_obj_type: Optional[int] = item_data.get("FileSystemObjectType")
    if fs_obj_type is None:
        raise EntityProcessingError(f"Missing FileSystemObjectType for file item {item_id}")

    file_obj: Optional[Dict[str, Any]] = item_data.get("File")
    if not file_obj or "__deferred" in file_obj:
        raise EntityProcessingError(f"Missing or deferred File object for item {item_id}")

    file_name: Optional[str] = file_obj.get("Name")
    if not file_name:
        raise EntityProcessingError(f"Missing Name in File object for item {item_id}")

    file_size_raw = file_obj.get("Length")
    if file_size_raw is None:
        raise EntityProcessingError(f"Missing Length in File object for item {item_id}")
    file_size: int = int(file_size_raw)

    server_relative_url: Optional[str] = file_obj.get("ServerRelativeUrl")
    if not server_relative_url:
        raise EntityProcessingError(f"Missing ServerRelativeUrl for file {item_id}")

    if "." not in file_name:
        raise EntityProcessingError(f"File {file_name} has no extension for item {item_id}")
    file_ext: str = file_name.rsplit(".", 1)[-1].lower()

    # Build URLs
    download_url: str = (
        f"{site_url.rstrip('/')}/_api/web/GetFileByServerRelativeUrl"
        f"('{server_relative_url}')/$value"
    )
    web_url: str = build_web_url(site_url, server_relative_url)

    # Title: use item Title if present, otherwise file name
    title: str = item_data.get("Title") or file_name

    # Fields (optional for files, but include if present)
    fields_raw: Dict[str, Any] = item_data.get("FieldValuesAsText") or {}

    sp_entity_id = f"sp2019v2:file:{list_id}:{item_id}"

    return SharePoint2019V2FileEntity(
        url=download_url,
        size=file_size,
        file_type=file_ext,
        list_id=list_id,
        item_id=item_id,
        sp_entity_id=sp_entity_id,
        guid=guid,
        title=title,
        web_url=web_url,
        created_at=_parse_datetime(item_data.get("Created")),
        updated_at=_parse_datetime(item_data.get("Modified")),
        file_system_object_type=fs_obj_type,
        file_name=file_name,
        server_relative_url=server_relative_url,
        fields=fields_raw,
        access=await _extract_access(item_data, ldap_client),
        breadcrumbs=breadcrumbs,
    )
