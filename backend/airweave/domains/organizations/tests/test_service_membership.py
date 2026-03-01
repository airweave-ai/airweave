"""Tests for OrganizationService membership methods.

Verifies invite_user, remove_member, leave_organization,
get_members, get_pending_invitations, and remove_invitation.
All I/O is faked — no database or external providers.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from airweave import schemas
from airweave.adapters.event_bus.fake import FakeEventBus
from airweave.adapters.identity.fake import FakeIdentityProvider
from airweave.core.protocols.identity import IdentityProviderError
from airweave.domains.organizations.fakes.repository import (
    FakeOrganizationRepository,
    FakeUserOrganizationRepository,
)
from airweave.domains.organizations.service import OrganizationService


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _UserStub:
    def __init__(self, *, user_id=None, email="user@test.com", auth0_id="auth0|u1"):
        self.id = user_id or uuid4()
        self.email = email
        self.auth0_id = auth0_id
        self.full_name = "Test User"


class _OrgStub:
    def __init__(self, *, org_id=None, name="Test Org", auth0_org_id="org_abc"):
        self.id = org_id or uuid4()
        self.name = name
        self.auth0_org_id = auth0_org_id


def _make_user_schema(user_id=None, email="user@test.com"):
    return SimpleNamespace(
        id=user_id or uuid4(), email=email, auth0_id="auth0|u1", full_name="Test"
    )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _make_service(
    *,
    identity=None,
    event_bus=None,
    org_repo=None,
    user_org_repo=None,
):
    return OrganizationService(
        lifecycle_ops=AsyncMock(),
        provisioning_ops=AsyncMock(),
        org_repo=org_repo or FakeOrganizationRepository(),
        user_org_repo=user_org_repo or FakeUserOrganizationRepository(),
        identity_provider=identity or FakeIdentityProvider(),
        event_bus=event_bus or FakeEventBus(),
    )


# ===========================================================================
# invite_user
# ===========================================================================


class TestInviteUser:
    @pytest.mark.asyncio
    async def test_calls_identity_and_returns_invitation(self):
        identity = FakeIdentityProvider()
        org_repo = FakeOrganizationRepository()
        org_id = uuid4()
        org = _OrgStub(org_id=org_id)
        org_repo.seed(org_id, org)

        svc = _make_service(identity=identity, org_repo=org_repo)
        db = AsyncMock()

        result = await svc.invite_user(
            db, org_id, "new@test.com", "member", _make_user_schema()
        )

        assert "id" in result
        identity.assert_called("invite_user")

    @pytest.mark.asyncio
    async def test_org_not_found_raises(self):
        svc = _make_service()
        db = AsyncMock()

        with pytest.raises(ValueError, match="Organization not found"):
            await svc.invite_user(db, uuid4(), "new@test.com", "member", _make_user_schema())


# ===========================================================================
# remove_member
# ===========================================================================


class TestRemoveMember:
    @pytest.mark.asyncio
    async def test_removes_locally_and_publishes_event(self):
        identity = FakeIdentityProvider()
        event_bus = FakeEventBus()
        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        org_id = uuid4()
        user_id = uuid4()

        org = _OrgStub(org_id=org_id, auth0_org_id="org_xyz")
        org_repo.seed(org_id, org)
        user_org_repo.seed_membership(user_id, org_id, role="member")

        svc = _make_service(
            identity=identity, event_bus=event_bus,
            org_repo=org_repo, user_org_repo=user_org_repo,
        )

        target_user = _UserStub(user_id=user_id, auth0_id="auth0|target")

        db = AsyncMock()
        # Simulate db.execute returning the user to remove
        db.execute = AsyncMock(
            return_value=SimpleNamespace(
                scalar_one_or_none=lambda: target_user
            )
        )

        result = await svc.remove_member(db, org_id, user_id, _UserStub())
        assert result is True
        event_bus.assert_published("organization.member_removed")

    @pytest.mark.asyncio
    async def test_user_not_found_raises(self):
        org_repo = FakeOrganizationRepository()
        org_id = uuid4()
        org_repo.seed(org_id, _OrgStub(org_id=org_id))

        svc = _make_service(org_repo=org_repo)
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: None)
        )

        with pytest.raises(ValueError, match="User not found"):
            await svc.remove_member(db, org_id, uuid4(), _UserStub())

    @pytest.mark.asyncio
    async def test_identity_failure_does_not_block_removal(self):
        """Identity provider cleanup is best-effort after local delete."""
        identity = FakeIdentityProvider()
        event_bus = FakeEventBus()
        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        org_id = uuid4()
        user_id = uuid4()

        org = _OrgStub(org_id=org_id, auth0_org_id="org_xyz")
        org_repo.seed(org_id, org)

        target_user = _UserStub(user_id=user_id, auth0_id="auth0|t")

        async def fail_remove(oid, uid):
            raise IdentityProviderError("down")

        identity.remove_user_from_organization = fail_remove

        svc = _make_service(
            identity=identity, event_bus=event_bus,
            org_repo=org_repo, user_org_repo=user_org_repo,
        )
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: target_user)
        )

        result = await svc.remove_member(db, org_id, user_id, _UserStub())
        assert result is True
        event_bus.assert_published("organization.member_removed")


# ===========================================================================
# get_members
# ===========================================================================


class TestGetMembers:
    @pytest.mark.asyncio
    async def test_returns_formatted_member_list(self):
        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        org_id = uuid4()
        org_repo.seed(org_id, _OrgStub(org_id=org_id))

        user = _UserStub(email="member@test.com")
        # Override get_members_with_users to return test data
        user_org_repo.get_members_with_users = AsyncMock(
            return_value=[(user, "admin", True)]
        )

        svc = _make_service(org_repo=org_repo, user_org_repo=user_org_repo)
        result = await svc.get_members(AsyncMock(), org_id)

        assert len(result) == 1
        assert result[0]["email"] == "member@test.com"
        assert result[0]["role"] == "admin"
        assert result[0]["is_primary"] is True
        assert result[0]["status"] == "active"


# ===========================================================================
# get_pending_invitations
# ===========================================================================


class TestGetPendingInvitations:
    @pytest.mark.asyncio
    async def test_returns_pending_invitations_with_status(self):
        identity = FakeIdentityProvider()
        org_repo = FakeOrganizationRepository()
        org_id = uuid4()
        org = _OrgStub(org_id=org_id, auth0_org_id="org_abc")
        org_repo.seed(org_id, org)

        # Seed an invitation with Auth0-style invitee structure
        identity._invitations.append({
            "id": "inv_1",
            "org_id": "org_abc",
            "invitee": {"email": "invitee@test.com"},
            "roles": ["role_member"],
            "created_at": "2024-01-01T00:00:00Z",
        })

        svc = _make_service(identity=identity, org_repo=org_repo)
        result = await svc.get_pending_invitations(AsyncMock(), org_id)

        assert len(result) == 1
        assert result[0]["email"] == "invitee@test.com"
        assert result[0]["role"] == "member"
        assert result[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_empty_when_no_invitations(self):
        identity = FakeIdentityProvider()
        org_repo = FakeOrganizationRepository()
        org_id = uuid4()
        org = _OrgStub(org_id=org_id, auth0_org_id="org_abc")
        org_repo.seed(org_id, org)

        svc = _make_service(identity=identity, org_repo=org_repo)
        result = await svc.get_pending_invitations(AsyncMock(), org_id)
        assert result == []


# ===========================================================================
# remove_invitation
# ===========================================================================


class TestRemoveInvitation:
    @pytest.mark.asyncio
    async def test_calls_identity_delete_invitation(self):
        identity = FakeIdentityProvider()
        org_repo = FakeOrganizationRepository()
        org_id = uuid4()
        org = _OrgStub(org_id=org_id, auth0_org_id="org_abc")
        org_repo.seed(org_id, org)

        svc = _make_service(identity=identity, org_repo=org_repo)
        result = await svc.remove_invitation(AsyncMock(), org_id, "inv_123")
        assert result is True
        identity.assert_called("delete_invitation")

    @pytest.mark.asyncio
    async def test_org_not_found_raises(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Organization not found"):
            await svc.remove_invitation(AsyncMock(), uuid4(), "inv_123")


# ===========================================================================
# _get_org helper
# ===========================================================================


class TestGetOrgHelper:
    @pytest.mark.asyncio
    async def test_raises_on_missing_org(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Organization not found"):
            await svc._get_org(AsyncMock(), uuid4())

    @pytest.mark.asyncio
    async def test_returns_org_on_hit(self):
        org_repo = FakeOrganizationRepository()
        org_id = uuid4()
        org = _OrgStub(org_id=org_id)
        org_repo.seed(org_id, org)

        svc = _make_service(org_repo=org_repo)
        result = await svc._get_org(AsyncMock(), org_id)
        assert result.id == org_id
