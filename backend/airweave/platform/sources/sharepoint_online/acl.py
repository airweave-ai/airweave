"""Access control helpers for SharePoint Online.

Maps Microsoft Graph API permissions to Airweave's AccessControl format.

Graph permission model:
- grantedToV2.user → user:{email}
- grantedToV2.group (Entra ID) → group:entra:{group_id}
- grantedToV2.siteGroup → group:sp:{site_group_name}
- link with scope "organization" → is_public (org-wide access)
"""

from typing import Any, Dict, List, Optional

from airweave.platform.entities._base import AccessControl


def extract_principal_from_permission(permission: Dict[str, Any]) -> Optional[str]:
    """Extract a canonical principal ID from a Graph permission object.

    Args:
        permission: Graph API permission dict with grantedToV2, roles, link, etc.

    Returns:
        Canonical principal string or None if not resolvable.
    """
    granted_to = permission.get("grantedToV2") or permission.get("grantedTo")
    if not granted_to:
        return None

    user = granted_to.get("user")
    if user:
        for field in ("email", "userPrincipalName"):
            val = user.get(field, "")
            if val and "@" in val:
                return f"user:{val.lower()}"
        user_id = user.get("id", "")
        if user_id:
            return f"user:id:{user_id}"
        return None

    group = granted_to.get("group")
    if group:
        group_id = group.get("id", "")
        if group_id:
            return f"group:entra:{group_id}"
        return None

    site_group = granted_to.get("siteGroup")
    if site_group:
        group_name = site_group.get("displayName", "")
        if group_name:
            return f"group:sp:{group_name.lower().replace(' ', '_')}"
        return None

    return None


def has_read_permission(permission: Dict[str, Any]) -> bool:
    """Check if a permission grants at least read access."""
    roles = permission.get("roles", [])
    return any(r in ("read", "write", "owner", "sp.full control") for r in roles)


def is_org_wide_link(permission: Dict[str, Any]) -> bool:
    """Check if a permission is an organization-wide sharing link."""
    link = permission.get("link")
    if not link:
        return False
    return link.get("scope", "") == "organization"


def is_anonymous_link(permission: Dict[str, Any]) -> bool:
    """Check if a permission is an anonymous sharing link."""
    link = permission.get("link")
    if not link:
        return False
    return link.get("scope", "") == "anonymous"


async def extract_access_control(
    permissions: List[Dict[str, Any]],
) -> AccessControl:
    """Build AccessControl from Graph API permissions.

    Args:
        permissions: List of permission objects from Graph API.

    Returns:
        AccessControl with viewers and is_public flag.
    """
    viewers: List[str] = []
    is_public = False

    for perm in permissions:
        if not has_read_permission(perm):
            continue

        if is_org_wide_link(perm) or is_anonymous_link(perm):
            is_public = True
            continue

        principal = extract_principal_from_permission(perm)
        if principal and principal not in viewers:
            viewers.append(principal)

    return AccessControl(viewers=viewers, is_public=is_public)


def format_entra_group_id(group_id: str) -> str:
    """Format Entra ID group ID for membership records.

    Membership group_id: "entra:{group_id}"
    Entity viewer: "group:entra:{group_id}"
    """
    return f"entra:{group_id}"
