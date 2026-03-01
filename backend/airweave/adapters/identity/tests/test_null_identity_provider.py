"""Tests for NullIdentityProvider — every method is a no-op.

Verifies that environments without Auth0 (AUTH_ENABLED=false, CI,
self-hosted) get safe no-op behaviour for all identity operations.
"""

import pytest

from airweave.adapters.identity.null import NullIdentityProvider


@pytest.fixture
def provider():
    return NullIdentityProvider()


class TestOrganizationLifecycle:
    @pytest.mark.asyncio
    async def test_create_returns_none(self, provider):
        result = await provider.create_organization("test", "Test Org")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_does_not_raise(self, provider):
        await provider.delete_organization("org_123")


class TestOrganizationSetup:
    @pytest.mark.asyncio
    async def test_get_all_connections_empty(self, provider):
        assert await provider.get_all_connections() == []

    @pytest.mark.asyncio
    async def test_add_enabled_connection_does_not_raise(self, provider):
        await provider.add_enabled_connection("org_1", "conn_1")


class TestUserOrgRelationships:
    @pytest.mark.asyncio
    async def test_add_user_does_not_raise(self, provider):
        await provider.add_user_to_organization("org_1", "user_1")

    @pytest.mark.asyncio
    async def test_remove_user_does_not_raise(self, provider):
        await provider.remove_user_from_organization("org_1", "user_1")

    @pytest.mark.asyncio
    async def test_get_user_organizations_empty(self, provider):
        assert await provider.get_user_organizations("user_1") == []

    @pytest.mark.asyncio
    async def test_get_member_roles_empty(self, provider):
        assert await provider.get_member_roles("org_1", "user_1") == []


class TestInvitations:
    @pytest.mark.asyncio
    async def test_invite_returns_null_stub(self, provider):
        result = await provider.invite_user("org_1", "a@b.com", "member", None)
        assert result["id"] == "null"
        assert result["created_at"] is None

    @pytest.mark.asyncio
    async def test_get_pending_invitations_empty(self, provider):
        assert await provider.get_pending_invitations("org_1") == []

    @pytest.mark.asyncio
    async def test_delete_invitation_does_not_raise(self, provider):
        await provider.delete_invitation("org_1", "inv_1")


class TestSystemLookups:
    @pytest.mark.asyncio
    async def test_get_roles_empty(self, provider):
        assert await provider.get_roles() == []
