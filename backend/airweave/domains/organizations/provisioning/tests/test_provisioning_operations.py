"""Tests for ProvisioningOperations — new user signup and org sync.

Verifies:
- provision_new_user dispatches correctly for each scenario
- sync_user_organizations syncs identity provider orgs to local DB
- Identity provider errors fall back gracefully
- Edge cases: no auth0_id, empty org lists, pre-existing memberships
"""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from airweave.adapters.identity.fake import FakeIdentityProvider
from airweave.core.protocols.identity import IdentityProviderError
from airweave.domains.organizations.fakes.repository import (
    FakeOrganizationRepository,
    FakeUserOrganizationRepository,
)
from airweave.domains.organizations.provisioning.operations import ProvisioningOperations
from airweave.domains.users.fakes.repository import FakeUserRepository

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _UserStub:
    """Lightweight stand-in for models.User."""

    def __init__(self, *, user_id=None, email="user@test.com", auth0_id="auth0|u1"):
        self.id = user_id or uuid4()
        self.email = email
        self.auth0_id = auth0_id
        self.full_name = "Test User"


class _OrgModelStub:
    """Lightweight stand-in for models.Organization (with auth0_org_id)."""

    def __init__(self, *, org_id=None, name="Test Org", auth0_org_id=None):
        self.id = org_id or uuid4()
        self.name = name
        self.auth0_org_id = auth0_org_id


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _make_ops(*, identity=None, org_repo=None, user_org_repo=None, user_repo=None):
    return ProvisioningOperations(
        org_repo=org_repo or FakeOrganizationRepository(),
        user_org_repo=user_org_repo or FakeUserOrganizationRepository(),
        user_repo=user_repo or FakeUserRepository(),
        identity_provider=identity or FakeIdentityProvider(),
    )


USER_DATA = {"email": "new@test.com", "auth0_id": "auth0|new123"}


# ===========================================================================
# provision_new_user — table-driven dispatch
# ===========================================================================


@dataclass
class ProvisionCase:
    name: str
    auth0_orgs: list[dict]
    create_org: bool
    identity_error: Optional[Exception] = None
    expect_method: str = ""  # which private method should run


PROVISION_CASES = [
    ProvisionCase(
        name="has_auth0_orgs",
        auth0_orgs=[{"id": "org_a", "name": "Alpha"}],
        create_org=False,
        expect_method="_create_user_with_existing_orgs",
    ),
    ProvisionCase(
        name="no_orgs_create_flag",
        auth0_orgs=[],
        create_org=True,
        expect_method="_create_user_with_new_org",
    ),
    ProvisionCase(
        name="no_orgs_no_create",
        auth0_orgs=[],
        create_org=False,
        expect_method="_create_user_without_org",
    ),
    ProvisionCase(
        name="identity_error_with_create",
        auth0_orgs=[],
        create_org=True,
        identity_error=IdentityProviderError("boom"),
        expect_method="_create_user_with_new_org",
    ),
    ProvisionCase(
        name="identity_error_without_create",
        auth0_orgs=[],
        create_org=False,
        identity_error=IdentityProviderError("boom"),
        expect_method="_create_user_without_org",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", PROVISION_CASES, ids=lambda c: c.name)
async def test_provision_new_user_dispatch(case: ProvisionCase):
    identity = FakeIdentityProvider()
    if case.identity_error:
        identity.fail_with = case.identity_error
    else:
        identity.seed_user_organizations("auth0|new123", case.auth0_orgs)

    ops = _make_ops(identity=identity)
    sentinel = _UserStub()

    with patch.object(ops, case.expect_method, new_callable=AsyncMock, return_value=sentinel) as m:
        # Patch unused methods to ensure they're NOT called
        other_methods = {
            "_create_user_with_existing_orgs",
            "_create_user_with_new_org",
            "_create_user_without_org",
        } - {case.expect_method}
        patches = {}
        for meth in other_methods:
            patches[meth] = patch.object(ops, meth, new_callable=AsyncMock)

        ctx_managers = {k: p.__enter__() for k, p in patches.items()}
        try:
            await ops.provision_new_user(AsyncMock(), USER_DATA, create_org=case.create_org)
            m.assert_called_once()
            for _k, mock_obj in ctx_managers.items():
                mock_obj.assert_not_called()
        finally:
            for p in patches.values():
                p.__exit__(None, None, None)


class TestProvisionNewUserValidation:
    @pytest.mark.asyncio
    async def test_missing_auth0_id_raises(self):
        ops = _make_ops()
        with pytest.raises(ValueError, match="No Auth0 ID provided"):
            await ops.provision_new_user(AsyncMock(), {"email": "x@test.com"})


# ===========================================================================
# sync_user_organizations
# ===========================================================================


class TestSyncUserOrganizations:
    @pytest.mark.asyncio
    async def test_no_identity_orgs_returns_user_unchanged(self):
        identity = FakeIdentityProvider()
        ops = _make_ops(identity=identity)
        user = _UserStub()

        db = AsyncMock()
        result = await ops.sync_user_organizations(db, user)
        assert result.id == user.id

    @pytest.mark.asyncio
    async def test_identity_error_returns_user_unchanged(self):
        identity = FakeIdentityProvider()
        identity.fail_with = IdentityProviderError("down")
        ops = _make_ops(identity=identity)
        user = _UserStub()

        db = AsyncMock()
        result = await ops.sync_user_organizations(db, user)
        assert result.id == user.id

    @pytest.mark.asyncio
    async def test_syncs_new_org_and_membership(self):
        """When identity provider returns an org, local records should be created."""
        identity = FakeIdentityProvider()
        identity.seed_user_organizations(
            "auth0|u1", [{"id": "org_remote", "name": "remote-org", "display_name": "Remote"}]
        )
        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        user_repo = FakeUserRepository()
        ops = _make_ops(
            identity=identity,
            org_repo=org_repo,
            user_org_repo=user_org_repo,
            user_repo=user_repo,
        )
        user = _UserStub()

        db = AsyncMock()
        await ops.sync_user_organizations(db, user)

        # Verify org was created via repo
        identity_calls = [c for c in org_repo._calls if c[0] == "create_from_identity"]
        assert len(identity_calls) == 1

        # Verify membership was created
        create_calls = [c for c in user_org_repo._calls if c[0] == "create"]
        assert len(create_calls) == 1

    @pytest.mark.asyncio
    async def test_sync_updates_role_when_identity_differs(self):
        """When the identity provider returns 'owner' but local is 'member', update."""
        identity = FakeIdentityProvider()
        identity.seed_user_organizations("auth0|u1", [{"id": "org_remote", "name": "remote-org"}])

        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        org_id = uuid4()
        user_id = uuid4()

        local_org = _OrgModelStub(org_id=org_id, auth0_org_id="org_remote")
        org_repo.seed(org_id, local_org)
        user_org_repo.seed_membership(user_id, org_id, role="member")

        identity.seed_member_roles("org_remote", "auth0|u1", [{"name": "owner"}])

        user_repo = FakeUserRepository()
        ops = _make_ops(
            identity=identity,
            org_repo=org_repo,
            user_org_repo=user_org_repo,
            user_repo=user_repo,
        )

        user = _UserStub(user_id=user_id)

        db = AsyncMock()
        await ops.sync_user_organizations(db, user)

        update_calls = [c for c in user_org_repo._calls if c[0] == "update_role"]
        assert len(update_calls) == 1
        _, u_id, o_id, new_role = update_calls[0]
        assert u_id == user_id
        assert o_id == org_id
        assert new_role == "owner"

    @pytest.mark.asyncio
    async def test_sync_does_not_update_when_roles_match(self):
        """When identity provider role matches local role, no update should occur."""
        identity = FakeIdentityProvider()
        identity.seed_user_organizations("auth0|u1", [{"id": "org_remote", "name": "remote-org"}])

        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        org_id = uuid4()
        user_id = uuid4()

        local_org = _OrgModelStub(org_id=org_id, auth0_org_id="org_remote")
        org_repo.seed(org_id, local_org)
        user_org_repo.seed_membership(user_id, org_id, role="admin")

        identity.seed_member_roles("org_remote", "auth0|u1", [{"name": "admin"}])

        user_repo = FakeUserRepository()
        ops = _make_ops(
            identity=identity,
            org_repo=org_repo,
            user_org_repo=user_org_repo,
            user_repo=user_repo,
        )

        user = _UserStub(user_id=user_id)

        db = AsyncMock()
        await ops.sync_user_organizations(db, user)

        update_calls = [c for c in user_org_repo._calls if c[0] == "update_role"]
        assert len(update_calls) == 0

    @pytest.mark.asyncio
    async def test_sync_assigns_member_when_no_identity_roles(self):
        """When identity provider returns empty roles, new membership gets 'member'."""
        identity = FakeIdentityProvider()
        identity.seed_user_organizations("auth0|u1", [{"id": "org_remote", "name": "remote-org"}])
        # No seed_member_roles → returns []

        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        user_repo = FakeUserRepository()

        ops = _make_ops(
            identity=identity,
            org_repo=org_repo,
            user_org_repo=user_org_repo,
            user_repo=user_repo,
        )
        user = _UserStub()

        db = AsyncMock()
        await ops.sync_user_organizations(db, user)

        create_calls = [c for c in user_org_repo._calls if c[0] == "create"]
        assert len(create_calls) == 1
        _, _uid, _oid, role = create_calls[0]
        assert role == "member"

    @pytest.mark.asyncio
    async def test_existing_membership_not_duplicated(self):
        """When the user already has a membership, don't create another."""
        identity = FakeIdentityProvider()
        identity.seed_user_organizations("auth0|u1", [{"id": "org_remote", "name": "remote-org"}])

        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        org_id = uuid4()
        user_id = uuid4()

        local_org = _OrgModelStub(org_id=org_id, auth0_org_id="org_remote")
        org_repo.seed(org_id, local_org)
        user_org_repo.seed_membership(user_id, org_id, role="member")

        user_repo = FakeUserRepository()
        ops = _make_ops(
            identity=identity,
            org_repo=org_repo,
            user_org_repo=user_org_repo,
            user_repo=user_repo,
        )

        user = _UserStub(user_id=user_id)

        db = AsyncMock()
        await ops.sync_user_organizations(db, user)

        create_calls = [c for c in user_org_repo._calls if c[0] == "create"]
        assert len(create_calls) == 0
