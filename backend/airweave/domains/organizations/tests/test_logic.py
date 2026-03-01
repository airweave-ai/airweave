"""Unit tests for organization pure logic.

Direct function calls — zero fixtures, zero I/O.
Tests every edge case and boundary condition.
"""

import pytest

from airweave.domains.organizations.logic import (
    can_manage_members,
    can_user_delete_org,
    can_user_leave_org,
    determine_user_role,
    format_role_from_invitation,
    generate_org_name,
    select_default_connections,
)


# ---------------------------------------------------------------------------
# select_default_connections
# ---------------------------------------------------------------------------


class TestSelectDefaultConnections:
    def test_selects_all_three_defaults(self):
        conns = [
            {"id": "c1", "name": "Username-Password-Authentication"},
            {"id": "c2", "name": "google-oauth2"},
            {"id": "c3", "name": "github"},
            {"id": "c4", "name": "enterprise-saml"},
        ]
        result = select_default_connections(conns)
        assert sorted(result) == ["c1", "c2", "c3"]

    def test_ignores_unknown_connections(self):
        conns = [{"id": "c1", "name": "enterprise-saml"}, {"id": "c2", "name": "okta"}]
        assert select_default_connections(conns) == []

    def test_empty_list(self):
        assert select_default_connections([]) == []

    def test_missing_name_key_does_not_crash(self):
        conns = [{"id": "c1"}, {"id": "c2", "name": "github"}]
        assert select_default_connections(conns) == ["c2"]


# ---------------------------------------------------------------------------
# generate_org_name
# ---------------------------------------------------------------------------


class TestGenerateOrgName:
    def test_format_prefix_slug_uuid(self):
        name = generate_org_name("My Company")
        assert name.startswith("airweave-my-company-")
        suffix = name.split("-")[-1]
        assert len(suffix) == 8

    def test_spaces_become_dashes(self):
        assert "foo-bar-baz" in generate_org_name("Foo Bar Baz")

    def test_uppercase_lowered(self):
        assert "acme-corp" in generate_org_name("ACME Corp")

    def test_two_calls_produce_different_names(self):
        assert generate_org_name("same") != generate_org_name("same")


# ---------------------------------------------------------------------------
# determine_user_role
# ---------------------------------------------------------------------------


class TestDetermineUserRole:
    def test_admin_wins_over_member(self):
        assert determine_user_role([{"name": "member"}, {"name": "admin"}]) == "admin"

    def test_single_role(self):
        assert determine_user_role([{"name": "editor"}]) == "editor"

    def test_empty_defaults_to_member(self):
        assert determine_user_role([]) == "member"

    def test_missing_name_key_ignored(self):
        assert determine_user_role([{"id": "r1"}, {"name": "admin"}]) == "admin"

    def test_none_names_filtered(self):
        assert determine_user_role([{"name": None}, {"name": "viewer"}]) == "viewer"

    def test_all_none_defaults_to_member(self):
        assert determine_user_role([{"name": None}]) == "member"


# ---------------------------------------------------------------------------
# can_user_delete_org
# ---------------------------------------------------------------------------


class TestCanUserDeleteOrg:
    def test_owner_with_multiple_orgs_allowed(self):
        allowed, reason = can_user_delete_org("owner", 3)
        assert allowed is True
        assert reason is None

    def test_non_owner_blocked(self):
        allowed, reason = can_user_delete_org("admin", 5)
        assert allowed is False
        assert "owners" in reason.lower()

    def test_member_blocked(self):
        allowed, _ = can_user_delete_org("member", 5)
        assert allowed is False

    def test_owner_last_org_blocked(self):
        allowed, reason = can_user_delete_org("owner", 1)
        assert allowed is False
        assert "only organization" in reason.lower()

    def test_zero_orgs_blocked(self):
        allowed, _ = can_user_delete_org("owner", 0)
        assert allowed is False


# ---------------------------------------------------------------------------
# can_user_leave_org
# ---------------------------------------------------------------------------


class TestCanUserLeaveOrg:
    def test_member_with_multiple_orgs(self):
        allowed, _ = can_user_leave_org("member", other_owner_count=1, total_user_orgs=2)
        assert allowed is True

    def test_only_org_blocked(self):
        allowed, reason = can_user_leave_org("member", other_owner_count=1, total_user_orgs=1)
        assert allowed is False
        assert "only organization" in reason.lower()

    def test_sole_owner_blocked(self):
        allowed, reason = can_user_leave_org("owner", other_owner_count=0, total_user_orgs=3)
        assert allowed is False
        assert "only owner" in reason.lower()

    def test_owner_with_co_owners_allowed(self):
        allowed, _ = can_user_leave_org("owner", other_owner_count=2, total_user_orgs=3)
        assert allowed is True

    def test_admin_can_leave(self):
        allowed, _ = can_user_leave_org("admin", other_owner_count=0, total_user_orgs=2)
        assert allowed is True

    def test_sole_owner_sole_org_only_org_check_fires_first(self):
        """Both conditions fail — 'only org' should win because it checks first."""
        allowed, reason = can_user_leave_org("owner", other_owner_count=0, total_user_orgs=1)
        assert allowed is False
        assert "only organization" in reason.lower()


# ---------------------------------------------------------------------------
# can_manage_members
# ---------------------------------------------------------------------------


class TestCanManageMembers:
    @pytest.mark.parametrize("role,expected", [
        ("owner", True),
        ("admin", True),
        ("member", False),
        ("viewer", False),
        ("", False),
    ])
    def test_role_permissions(self, role, expected):
        assert can_manage_members(role) is expected


# ---------------------------------------------------------------------------
# format_role_from_invitation
# ---------------------------------------------------------------------------


class TestFormatRoleFromInvitation:
    def test_maps_role_id_to_name(self):
        inv = {"roles": ["r1"]}
        assert format_role_from_invitation(inv, {"r1": "admin"}) == "admin"

    def test_unknown_id_defaults_to_member(self):
        inv = {"roles": ["r_unknown"]}
        assert format_role_from_invitation(inv, {"r1": "admin"}) == "member"

    def test_no_roles_key(self):
        assert format_role_from_invitation({}, {}) == "member"

    def test_empty_roles_list(self):
        assert format_role_from_invitation({"roles": []}, {"r1": "admin"}) == "member"

    def test_uses_first_role_only(self):
        inv = {"roles": ["r1", "r2"]}
        assert format_role_from_invitation(inv, {"r1": "viewer", "r2": "admin"}) == "viewer"
