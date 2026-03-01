"""Pure business logic for the organization domain.

Every function here is deterministic and performs zero I/O.
Test with direct calls — no fixtures needed.
"""

import uuid
from typing import Optional

# ---------------------------------------------------------------------------
# Auth0 connection selection
# ---------------------------------------------------------------------------

DEFAULT_AUTH_CONNECTIONS = frozenset(
    {
        "Username-Password-Authentication",
        "google-oauth2",
        "github",
    }
)


def select_default_connections(all_connections: list[dict]) -> list[str]:
    """Return IDs of connections that should be auto-enabled for new orgs."""
    return [c["id"] for c in all_connections if c.get("name") in DEFAULT_AUTH_CONNECTIONS]


# ---------------------------------------------------------------------------
# Org naming
# ---------------------------------------------------------------------------


def generate_org_name(display_name: str) -> str:
    """Create a unique, URL-safe Auth0 org name from a display name."""
    slug = display_name.lower().replace(" ", "-")
    short_uuid = str(uuid.uuid4())[:8]
    return f"airweave-{slug}-{short_uuid}"


# ---------------------------------------------------------------------------
# Role determination
# ---------------------------------------------------------------------------


def determine_user_role(member_roles: list[dict]) -> str:
    """Pick the best role from an identity provider roles list.

    Prioritises ``admin`` > first named role > ``member`` default.
    """
    role_names: list[str] = [r["name"] for r in member_roles if r.get("name")]
    if "admin" in role_names:
        return "admin"
    if role_names:
        return role_names[0]
    return "member"


# ---------------------------------------------------------------------------
# Permission / guard-rail checks
# ---------------------------------------------------------------------------


def can_user_delete_org(role: str, total_user_orgs: int) -> tuple[bool, Optional[str]]:
    """Check whether a user may delete an organization.

    Returns ``(allowed, reason)`` — reason is ``None`` when allowed.
    """
    if role != "owner":
        return False, "Only organization owners can delete organizations"
    if total_user_orgs <= 1:
        return (
            False,
            "Cannot delete your only organization. Contact support to delete your account.",
        )
    return True, None


def can_user_leave_org(
    role: str, other_owner_count: int, total_user_orgs: int
) -> tuple[bool, Optional[str]]:
    """Check whether a user may leave an organization.

    Returns ``(allowed, reason)``.
    """
    if total_user_orgs <= 1:
        return (
            False,
            "Cannot leave your only organization. "
            "Users must belong to at least one organization. "
            "Delete the organization instead.",
        )
    if role == "owner" and other_owner_count == 0:
        return (
            False,
            "Cannot leave organization as the only owner. "
            "Transfer ownership to another member first.",
        )
    return True, None


def can_manage_members(role: str) -> bool:
    """Return whether a user with this role may invite / remove members."""
    return role in ("owner", "admin")


# ---------------------------------------------------------------------------
# Invitation formatting
# ---------------------------------------------------------------------------


def format_role_from_invitation(invitation: dict, role_id_to_name: dict[str, str]) -> str:
    """Map Auth0 role IDs in an invitation to a human-readable role name."""
    role_ids = invitation.get("roles", [])
    if role_ids:
        return role_id_to_name.get(role_ids[0], "member")
    return "member"
