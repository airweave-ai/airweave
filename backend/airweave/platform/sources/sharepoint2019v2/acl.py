"""Access control helpers for SharePoint 2019 V2.

This module provides functions for:
- Cleaning and extracting role assignments from SharePoint API responses
- Resolving principals (users/groups) to canonical identifiers
- Building AccessControl objects from role assignments
- Extracting canonical IDs for access graph memberships
"""

from typing import Any, Dict, List, Optional

from airweave.platform.entities._base import AccessControl


def extract_canonical_id(login_name: str) -> str:
    r"""Extract canonical ID from SharePoint LoginName.

    Strips claims format prefix and domain to get the raw identifier.
    Used for membership member_id (users) and building group IDs.

    Args:
        login_name: SharePoint LoginName (e.g., "i:0#.w|DOMAIN\\user")

    Returns:
        Canonical ID (e.g., "user"), lowercase
    """
    # Extract identity portion from claims format
    if "|" in login_name:
        identity_part = login_name.split("|")[-1]
    else:
        identity_part = login_name

    # Check if it's an email (SAML/ADFS auth)
    if "@" in identity_part and "\\" not in identity_part:
        return identity_part.lower()

    # Extract from DOMAIN\name format
    if "\\" in identity_part:
        return identity_part.split("\\")[-1].lower()

    return identity_part.lower()


def format_sp_group_id(group_title: str) -> str:
    """Format SharePoint group title to canonical group_id.

    Must match the format used in entity viewers:
    - Entity viewer: "group:sp:{group_name}"
    - Membership group_id: "sp:{group_name}" (broker adds "group:" prefix)

    Args:
        group_title: SharePoint group title (e.g., "Site Members")

    Returns:
        Canonical group_id (e.g., "sp:site_members")
    """
    group_name = group_title.replace(" ", "_").lower()
    return f"sp:{group_name}"


def format_ad_group_id(login_name: str) -> str:
    r"""Format AD group LoginName to canonical group_id.

    Must match the format used in entity viewers:
    - Entity viewer: "group:ad:{canonical_id}"
    - Membership group_id: "ad:{canonical_id}" (broker adds "group:" prefix)

    Args:
        login_name: SharePoint LoginName for AD group

    Returns:
        Canonical group_id (e.g., "ad:engineering")
    """
    canonical_id = extract_canonical_id(login_name)
    return f"ad:{canonical_id}"


def clean_role_assignments(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract and clean role assignments from SharePoint API response.

    Extracts only Member and RoleDefinitionBindings from RoleAssignments,
    removing metadata and deferred references.

    Args:
        data: Raw RoleAssignments dict from SharePoint API with "results" key

    Returns:
        List of cleaned assignment dicts with Member and RoleDefinitionBindings
    """
    results = data.get("results", [])
    cleaned_assignments = []

    for assignment in results:
        member = assignment.get("Member", {})
        bindings = assignment.get("RoleDefinitionBindings", {}).get("results", [])

        cleaned_member = {
            "LoginName": member.get("LoginName"),
            "PrincipalType": member.get("PrincipalType"),
            "Title": member.get("Title"),
        }

        cleaned_bindings = []
        for b in bindings:
            cleaned_bindings.append(
                {
                    "Name": b.get("Name"),
                    "BasePermissions": b.get("BasePermissions"),
                }
            )

        cleaned_assignments.append(
            {
                "Member": cleaned_member,
                "RoleDefinitionBindings": cleaned_bindings,
            }
        )

    return cleaned_assignments


def _is_sid(value: str) -> bool:
    """Check if a value is a Windows SID format."""
    return value.startswith("s-1-")


async def resolve_principal(
    member: Dict[str, Any],
    ldap_client: Optional[Any] = None,
) -> Optional[str]:
    r"""Resolve a SharePoint principal to a canonical identifier.

    Handles different principal types:
    - PrincipalType 1: User -> "user:{canonical_id}"
    - PrincipalType 4: AD Security Group -> "group:ad:{canonical_id}"
    - PrincipalType 8: SharePoint Group -> "group:sp:{group_name}"

    LoginName formats handled:
    - Claims format: "i:0#.w|DOMAIN\\user" or "c:0+.w|s-1-5-21..."
    - Non-claims format: "DOMAIN\\user"

    If the canonical_id is a SID (s-1-5-...) and ldap_client is provided,
    resolves the SID to the sAMAccountName via LDAP.

    Args:
        member: Dict with LoginName and PrincipalType keys
        ldap_client: Optional LDAPClient for SID resolution

    Returns:
        Canonical principal ID string, or None if unresolvable
    """
    login_name = member.get("LoginName", "")
    principal_type = member.get("PrincipalType")

    if not login_name:
        return None

    # Extract identity portion from claims format
    if "|" in login_name:
        identity_part = login_name.split("|")[-1]
    else:
        identity_part = login_name

    # Extract canonical ID (remove domain prefix)
    canonical_id = identity_part.lower()
    if "\\" in identity_part:
        canonical_id = identity_part.split("\\")[-1].lower()

    # Resolve SID to sAMAccountName if it's a SID and we have an LDAP client
    if _is_sid(canonical_id) and ldap_client:
        resolved = await ldap_client.resolve_sid(canonical_id)
        if resolved:
            canonical_id = resolved

    if principal_type == 1:  # User
        return f"user:{canonical_id}"
    elif principal_type == 4:  # AD Security Group
        return f"group:ad:{canonical_id}"
    elif principal_type == 8:  # SharePoint Group
        group_name = member.get("Title", "").replace(" ", "_").lower()
        return f"group:sp:{group_name}"

    return None


async def extract_access_control(
    cleaned_roles: List[Dict[str, Any]],
    ldap_client: Optional[Any] = None,
) -> AccessControl:
    """Build AccessControl from cleaned role assignments.

    Extracts principals that have ViewListItems permission (bit 1 in Low).

    Args:
        cleaned_roles: List of cleaned role assignment dicts from clean_role_assignments()
        ldap_client: Optional LDAPClient for SID resolution

    Returns:
        AccessControl object with viewers list
    """
    viewers = []

    for assignment in cleaned_roles:
        member = assignment.get("Member", {})
        bindings = assignment.get("RoleDefinitionBindings", [])

        # Check if any role grants ViewListItems (Low bit 1)
        has_read = False
        for role in bindings:
            perms = role.get("BasePermissions", {})
            low = int(perms.get("Low", 0) or 0)
            if low & 1:  # ViewListItems permission
                has_read = True
                break

        if not has_read:
            continue

        principal_id = await resolve_principal(member, ldap_client)
        if principal_id:
            viewers.append(principal_id)

    return AccessControl(viewers=viewers)
