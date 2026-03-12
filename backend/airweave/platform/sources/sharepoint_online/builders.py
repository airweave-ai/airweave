"""Entity builders for SharePoint Online.

Functions that build typed entity objects from Microsoft Graph API responses.
Each builder validates required fields and extracts access control.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.sharepoint_online import (
    SharePointOnlineDriveEntity,
    SharePointOnlineFileEntity,
    SharePointOnlineItemEntity,
    SharePointOnlinePageEntity,
    SharePointOnlineSiteEntity,
)
from airweave.platform.sources.sharepoint_online.acl import extract_access_control
from airweave.platform.sync.exceptions import EntityProcessingError


def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


async def build_site_entity(
    site_data: Dict[str, Any],
    breadcrumbs: List[Breadcrumb],
) -> SharePointOnlineSiteEntity:
    """Build a site entity from Graph API site data."""
    site_id = site_data.get("id")
    if not site_id:
        raise EntityProcessingError("Missing id for site")

    display_name = site_data.get("displayName")
    if not display_name:
        raise EntityProcessingError(f"Missing displayName for site {site_id}")

    web_url = site_data.get("webUrl", "")

    return SharePointOnlineSiteEntity(
        site_id=site_id,
        display_name=display_name,
        web_url=web_url,
        description=site_data.get("description"),
        is_personal_site=site_data.get("isPersonalSite", False),
        created_at=_parse_datetime(site_data.get("createdDateTime")),
        last_modified_at=_parse_datetime(site_data.get("lastModifiedDateTime")),
        breadcrumbs=breadcrumbs,
    )


async def build_drive_entity(
    drive_data: Dict[str, Any],
    site_id: str,
    breadcrumbs: List[Breadcrumb],
) -> SharePointOnlineDriveEntity:
    """Build a drive entity from Graph API drive data."""
    drive_id = drive_data.get("id")
    if not drive_id:
        raise EntityProcessingError("Missing id for drive")

    name = drive_data.get("name")
    if not name:
        raise EntityProcessingError(f"Missing name for drive {drive_id}")

    quota = drive_data.get("quota", {}) or {}

    return SharePointOnlineDriveEntity(
        drive_id=drive_id,
        name=name,
        drive_type=drive_data.get("driveType", "documentLibrary"),
        web_url=drive_data.get("webUrl", ""),
        description=drive_data.get("description"),
        site_id=site_id,
        quota_total=quota.get("total"),
        quota_used=quota.get("used"),
        created_at=_parse_datetime(drive_data.get("createdDateTime")),
        last_modified_at=_parse_datetime(drive_data.get("lastModifiedDateTime")),
        breadcrumbs=breadcrumbs,
    )


async def build_file_entity(
    item_data: Dict[str, Any],
    drive_id: str,
    site_id: str,
    breadcrumbs: List[Breadcrumb],
    permissions: Optional[List[Dict[str, Any]]] = None,
) -> SharePointOnlineFileEntity:
    """Build a file entity from Graph API drive item data."""
    item_id = item_data.get("id")
    if not item_id:
        raise EntityProcessingError("Missing id for file item")

    file_name = item_data.get("name")
    if not file_name:
        raise EntityProcessingError(f"Missing name for file item {item_id}")

    file_obj = item_data.get("file")
    if not file_obj:
        raise EntityProcessingError(f"Item {item_id} is not a file")

    size = item_data.get("size", 0)
    mime_type = file_obj.get("mimeType", "")

    if "." in file_name:
        file_ext = file_name.rsplit(".", 1)[-1].lower()
    else:
        file_ext = ""

    parent_ref = item_data.get("parentReference", {}) or {}
    parent_path = parent_ref.get("path", "")

    created_by_obj = item_data.get("createdBy", {}) or {}
    created_by_user = created_by_obj.get("user", {}) or {}
    created_by = created_by_user.get("email") or created_by_user.get("displayName")

    modified_by_obj = item_data.get("lastModifiedBy", {}) or {}
    modified_by_user = modified_by_obj.get("user", {}) or {}
    last_modified_by = modified_by_user.get("email") or modified_by_user.get("displayName")

    download_url = item_data.get("@microsoft.graph.downloadUrl", "")
    spo_entity_id = f"spo:file:{drive_id}:{item_id}"

    access = await extract_access_control(permissions or []) if permissions else None

    return SharePointOnlineFileEntity(
        url=download_url or item_data.get("webUrl", ""),
        size=size,
        file_type=file_ext,
        mime_type=mime_type,
        name=file_name,
        spo_entity_id=spo_entity_id,
        item_id=item_id,
        drive_id=drive_id,
        site_id=site_id,
        file_name=file_name,
        web_url=item_data.get("webUrl", ""),
        download_url=download_url,
        parent_path=parent_path,
        created_by=created_by,
        last_modified_by=last_modified_by,
        created_at=_parse_datetime(item_data.get("createdDateTime")),
        updated_at=_parse_datetime(item_data.get("lastModifiedDateTime")),
        access=access,
        breadcrumbs=breadcrumbs,
    )


async def build_item_entity(
    item_data: Dict[str, Any],
    site_id: str,
    list_id: str,
    breadcrumbs: List[Breadcrumb],
) -> SharePointOnlineItemEntity:
    """Build a list item entity from Graph API list item data."""
    item_id = item_data.get("id")
    if not item_id:
        raise EntityProcessingError("Missing id for list item")

    fields = item_data.get("fields", {}) or {}
    title = fields.get("Title") or fields.get("title") or item_data.get("id", "Untitled")

    content_type = None
    ct_obj = item_data.get("contentType")
    if ct_obj:
        content_type = ct_obj.get("name")

    spo_entity_id = f"spo:item:{site_id}:{list_id}:{item_id}"

    return SharePointOnlineItemEntity(
        spo_entity_id=spo_entity_id,
        item_id=item_id,
        list_id=list_id,
        site_id=site_id,
        title=title,
        web_url=item_data.get("webUrl", ""),
        content_type=content_type,
        fields=fields,
        created_at=_parse_datetime(item_data.get("createdDateTime")),
        updated_at=_parse_datetime(item_data.get("lastModifiedDateTime")),
        breadcrumbs=breadcrumbs,
    )


async def build_page_entity(
    page_data: Dict[str, Any],
    site_id: str,
    breadcrumbs: List[Breadcrumb],
) -> SharePointOnlinePageEntity:
    """Build a page entity from Graph API site page data."""
    page_id = page_data.get("id")
    if not page_id:
        raise EntityProcessingError("Missing id for page")

    title = page_data.get("title")
    if not title:
        raise EntityProcessingError(f"Missing title for page {page_id}")

    return SharePointOnlinePageEntity(
        page_id=page_id,
        title=title,
        web_url=page_data.get("webUrl", ""),
        description=page_data.get("description"),
        page_content=json.dumps(page_data["webParts"]) if page_data.get("webParts") else None,
        site_id=site_id,
        created_at=_parse_datetime(page_data.get("createdDateTime")),
        updated_at=_parse_datetime(page_data.get("lastModifiedDateTime")),
        breadcrumbs=breadcrumbs,
    )
