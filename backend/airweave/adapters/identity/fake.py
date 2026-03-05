"""Fake identity provider for tests.

Records all calls, supports seeding org/user data, and allows failure
injection via ``fail_with`` — set to any ``IdentityProviderError`` subclass
instance to simulate specific error modes (rate-limit, unavailable, etc.).
"""

from typing import Any, Optional
from uuid import uuid4

from airweave.core.protocols.identity import IdentityProvider, IdentityProviderError


class FakeIdentityProvider(IdentityProvider):
    """In-memory fake for IdentityProvider protocol."""

    def __init__(self) -> None:
        self._organizations: dict[str, dict] = {}
        self._user_orgs: dict[str, list[dict]] = {}
        self._invitations: list[dict] = []
        self._roles: list[dict] = [
            {"id": "role_owner", "name": "owner"},
            {"id": "role_admin", "name": "admin"},
            {"id": "role_member", "name": "member"},
        ]
        self._calls: list[tuple[str, ...]] = []
        self.fail_with: Optional[IdentityProviderError] = None

    # --- Seeding helpers ---

    def seed_user_organizations(self, user_id: str, orgs: list[dict]) -> None:
        self._user_orgs[user_id] = orgs

    def seed_organization(self, org_id: str, data: dict) -> None:
        self._organizations[org_id] = data

    # --- Assertion helpers ---

    def assert_called(self, method_name: str) -> tuple:
        for call in self._calls:
            if call[0] == method_name:
                return call
        raise AssertionError(f"{method_name} was not called")

    def assert_not_called(self, method_name: str) -> None:
        for call in self._calls:
            if call[0] == method_name:
                raise AssertionError(f"{method_name} was called unexpectedly")

    def call_count(self, method_name: str) -> int:
        return sum(1 for c in self._calls if c[0] == method_name)

    def reset(self) -> None:
        """Clear all recorded calls and state."""
        self._calls.clear()
        self._organizations.clear()
        self._user_orgs.clear()
        self._invitations.clear()
        self.fail_with = None

    # --- Protocol implementation ---

    def _check_fail(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    async def create_organization(self, name: str, display_name: str) -> Optional[dict]:
        self._calls.append(("create_organization", name, display_name))
        self._check_fail()
        org_id = f"org_{uuid4().hex[:8]}"
        data = {"id": org_id, "name": name, "display_name": display_name}
        self._organizations[org_id] = data
        return data

    async def delete_organization(self, org_id: str) -> None:
        self._calls.append(("delete_organization", org_id))
        self._check_fail()
        self._organizations.pop(org_id, None)

    async def get_all_connections(self) -> list[dict]:
        self._calls.append(("get_all_connections",))
        self._check_fail()
        return [
            {"id": "conn_1", "name": "Username-Password-Authentication"},
            {"id": "conn_2", "name": "google-oauth2"},
            {"id": "conn_3", "name": "github"},
        ]

    async def add_enabled_connection(self, org_id: str, connection_id: str) -> None:
        self._calls.append(("add_enabled_connection", org_id, connection_id))
        self._check_fail()

    async def add_user_to_organization(self, org_id: str, user_id: str) -> None:
        self._calls.append(("add_user_to_organization", org_id, user_id))
        self._check_fail()

    async def remove_user_from_organization(self, org_id: str, user_id: str) -> None:
        self._calls.append(("remove_user_from_organization", org_id, user_id))
        self._check_fail()

    async def get_user_organizations(self, user_id: str) -> list[dict]:
        self._calls.append(("get_user_organizations", user_id))
        self._check_fail()
        return self._user_orgs.get(user_id, [])

    async def get_member_roles(self, org_id: str, user_id: str) -> list[dict]:
        self._calls.append(("get_member_roles", org_id, user_id))
        self._check_fail()
        return [{"name": "member"}]

    async def invite_user(self, org_id: str, email: str, role: str, inviter: Any) -> dict:
        self._calls.append(("invite_user", org_id, email, role))
        self._check_fail()
        invitation = {
            "id": f"inv_{uuid4().hex[:8]}",
            "created_at": "2024-01-01T00:00:00Z",
        }
        self._invitations.append({**invitation, "org_id": org_id, "email": email, "role": role})
        return invitation

    async def get_pending_invitations(self, org_id: str) -> list[dict]:
        self._calls.append(("get_pending_invitations", org_id))
        self._check_fail()
        return [inv for inv in self._invitations if inv.get("org_id") == org_id]

    async def delete_invitation(self, org_id: str, invitation_id: str) -> None:
        self._calls.append(("delete_invitation", org_id, invitation_id))
        self._check_fail()
        self._invitations = [inv for inv in self._invitations if inv.get("id") != invitation_id]

    async def get_roles(self) -> list[dict]:
        self._calls.append(("get_roles",))
        self._check_fail()
        return self._roles
