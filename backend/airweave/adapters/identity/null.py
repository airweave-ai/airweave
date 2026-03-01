"""Null identity provider — no-ops for AUTH_ENABLED=false.

Replaces all ``if auth0_management_client:`` branches that were scattered
through the old organization service.  Every method is a no-op or returns
an empty/None result so the org domain can run without an external identity
system (local development, CI, self-hosted).
"""

from typing import Any, Optional

from airweave.core.protocols.identity import IdentityProvider


class NullIdentityProvider(IdentityProvider):
    """No-op identity provider for environments without Auth0."""

    async def create_organization(self, name: str, display_name: str) -> Optional[dict]:
        """Return None (no-op)."""
        return None

    async def delete_organization(self, org_id: str) -> None:
        """Do nothing (no-op)."""
        pass

    async def get_all_connections(self) -> list[dict]:
        """Return empty list (no-op)."""
        return []

    async def add_enabled_connection(self, org_id: str, connection_id: str) -> None:
        """Do nothing (no-op)."""
        pass

    async def add_user_to_organization(self, org_id: str, user_id: str) -> None:
        """Do nothing (no-op)."""
        pass

    async def remove_user_from_organization(self, org_id: str, user_id: str) -> None:
        """Do nothing (no-op)."""
        pass

    async def get_user_organizations(self, user_id: str) -> list[dict]:
        """Return empty list (no-op)."""
        return []

    async def get_member_roles(self, org_id: str, user_id: str) -> list[dict]:
        """Return empty list (no-op)."""
        return []

    async def invite_user(self, org_id: str, email: str, role: str, inviter: Any) -> dict:
        """Return stub invitation (no-op)."""
        return {"id": "null", "created_at": None}

    async def get_pending_invitations(self, org_id: str) -> list[dict]:
        """Return empty list (no-op)."""
        return []

    async def delete_invitation(self, org_id: str, invitation_id: str) -> None:
        """Do nothing (no-op)."""
        pass

    async def get_roles(self) -> list[dict]:
        """Return empty list (no-op)."""
        return []
