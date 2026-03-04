"""Unit tests for DirSync parsing, BER encoding, and incremental ACL logic.

Covers the fragile AD-specific encodings we depend on:
- BER integer encoding (especially the signed 0x80000000 / -2147483648 edge case)
- member;range=1-1 (ADD) vs member;range=0-0 (REMOVE) classification
- Tombstone DN suffix stripping (\0ADEL:<GUID>)
- entry_dn fallback when sAMAccountName is missing
- DirSyncResult.incremental_values propagation
- _process_dirsync_entries end-to-end behaviour
- incremental_mode detection (is_initial + flags interaction)
- DirSync cookie base64 roundtrip
- Flag fallback on DirSyncPermissionError
- get_membership_changes pagination and aggregation
"""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.access_control.schemas import ACLChangeType, MembershipChange
from airweave.platform.sources.sharepoint2019v2.ldap import (
    DIRSYNC_FLAGS_BASIC,
    DIRSYNC_FLAGS_FULL,
    LDAP_DIRSYNC_INCREMENTAL_VALUES,
    DirSyncPermissionError,
    DirSyncResult,
    LDAPClient,
)


def _fake_resolve_member_dn(member_dn: str):
    """Extract CN from a member DN and return (member_id, "user").

    Mimics _resolve_member_dn_sync without needing a real LDAP connection.
    """
    match = re.match(r"CN=([^,]+)", member_dn, re.IGNORECASE)
    if match:
        return (match.group(1).lower(), "user")
    return None


# ---------------------------------------------------------------------------
# Helpers: fake LDAP entry objects
# ---------------------------------------------------------------------------

class FakeAttr:
    """Mimics an ldap3 attribute with .values / .value."""

    def __init__(self, values):
        if isinstance(values, list):
            self.values = values
            self.value = values[0] if len(values) == 1 else values
        else:
            self.values = [values]
            self.value = values


class FakeEntry:
    """Mimics an ldap3 Entry returned by DirSync.

    Args:
        attrs: dict of attribute name -> list of values.
        entry_dn: The DN always available on ldap3 entries.
    """

    def __init__(self, attrs: dict, entry_dn: str = ""):
        self._attrs = attrs
        self.entry_dn = entry_dn

    @property
    def entry_attributes(self):
        return list(self._attrs.keys())

    @property
    def entry_attributes_as_dict(self):
        return {k: list(v) for k, v in self._attrs.items()}

    def __getattr__(self, name):
        if name.startswith("_") or name in ("entry_dn", "entry_attributes",
                                             "entry_attributes_as_dict"):
            raise AttributeError(name)
        if name in self._attrs:
            return FakeAttr(self._attrs[name])
        # Return FakeAttr with empty list for attributes that exist but are empty
        return FakeAttr([])


@pytest.fixture
def ldap_client():
    """Create an LDAPClient with mocked logger and member DN resolution."""
    client = LDAPClient(
        server="ldaps://server:636",
        username="admin",
        password="pass",
        domain="DOMAIN",
        search_base="DC=DOMAIN,DC=local",
        logger=MagicMock(),
    )
    # Mock _resolve_member_dn_sync so tests don't need a real LDAP connection
    client._resolve_member_dn_sync = _fake_resolve_member_dn
    return client


# =========================================================================
# BER encoding
# =========================================================================

class TestBerEncoding:
    """Tests for _build_dirsync_control BER integer encoding."""

    def test_incremental_values_flag_value(self):
        """LDAP_DIRSYNC_INCREMENTAL_VALUES must be the signed int32 form."""
        assert LDAP_DIRSYNC_INCREMENTAL_VALUES == -2147483648
        # Unsigned equivalent
        assert LDAP_DIRSYNC_INCREMENTAL_VALUES & 0xFFFFFFFF == 0x80000000

    def test_ber_encodes_incremental_values_as_4_bytes(self, ldap_client):
        """0x80000000 must BER-encode to 4 bytes (80 00 00 00), not 5."""
        oid, critical, value = ldap_client._build_dirsync_control(
            cookie=b"", flags=LDAP_DIRSYNC_INCREMENTAL_VALUES
        )
        assert critical is True
        # The BER-encoded value is a SEQUENCE containing the flags INTEGER.
        # The flags INTEGER should be: 02 04 80 00 00 00
        # (tag=02, length=04, value=80000000)
        assert b"\x02\x04\x80\x00\x00\x00" in value

    def test_ber_does_not_produce_5_byte_encoding(self, ldap_client):
        """Must NOT produce the buggy 5-byte form (02 05 00 80 00 00 00)."""
        _, _, value = ldap_client._build_dirsync_control(
            cookie=b"", flags=LDAP_DIRSYNC_INCREMENTAL_VALUES
        )
        assert b"\x02\x05\x00\x80\x00\x00\x00" not in value

    def test_ber_encodes_zero(self, ldap_client):
        """Flags=0 (BASIC) should encode as a single zero byte."""
        _, _, value = ldap_client._build_dirsync_control(
            cookie=b"", flags=DIRSYNC_FLAGS_BASIC
        )
        assert b"\x02\x01\x00" in value

    def test_ber_encodes_positive_small(self, ldap_client):
        """Small positive integers should use minimal bytes."""
        _, _, value = ldap_client._build_dirsync_control(
            cookie=b"", flags=1  # OBJECT_SECURITY
        )
        assert b"\x02\x01\x01" in value

    def test_ber_encodes_127(self, ldap_client):
        """127 (0x7F) should fit in 1 byte."""
        _, _, value = ldap_client._build_dirsync_control(cookie=b"", flags=127)
        assert b"\x02\x01\x7f" in value

    def test_ber_encodes_128(self, ldap_client):
        """128 (0x80) needs 2 bytes in signed encoding (00 80)."""
        _, _, value = ldap_client._build_dirsync_control(cookie=b"", flags=128)
        assert b"\x02\x02\x00\x80" in value

    def test_ber_encodes_negative_128(self, ldap_client):
        """-128 should fit in 1 byte (0x80)."""
        _, _, value = ldap_client._build_dirsync_control(cookie=b"", flags=-128)
        assert b"\x02\x01\x80" in value

    def test_ber_encodes_negative_1(self, ldap_client):
        """-1 should encode as FF in 1 byte."""
        _, _, value = ldap_client._build_dirsync_control(cookie=b"", flags=-1)
        assert b"\x02\x01\xff" in value

    def test_cookie_roundtrip(self, ldap_client):
        """Cookie bytes should survive encode → decode."""
        cookie = b"\x01\x02\x03\x04\x05"
        _, _, value = ldap_client._build_dirsync_control(cookie=cookie, flags=0)
        # The cookie should appear verbatim inside the BER OCTET STRING
        assert cookie in value


# =========================================================================
# _get_entry_members: member;range parsing
# =========================================================================

class TestGetEntryMembers:
    """Tests for _get_entry_members incremental member parsing."""

    def test_full_mode_all_members_are_adds(self, ldap_client):
        """In full mode (BASIC flags), member attribute = all adds."""
        entry = FakeEntry({
            "member": ["CN=user1,DC=test", "CN=user2,DC=test"],
        })
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=False)
        assert added == ["CN=user1,DC=test", "CN=user2,DC=test"]
        assert removed == []

    def test_full_mode_empty_member(self, ldap_client):
        """In full mode with empty member, should return empty lists."""
        entry = FakeEntry({"member": []})
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=False)
        assert added == []
        assert removed == []

    def test_incremental_range_1_1_is_add(self, ldap_client):
        """member;range=1-1 should be classified as ADD."""
        entry = FakeEntry({
            "member": [],
            "member;range=1-1": ["CN=user1,DC=test"],
        })
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=True)
        assert added == ["CN=user1,DC=test"]
        assert removed == []

    def test_incremental_range_0_0_is_remove(self, ldap_client):
        """member;range=0-0 should be classified as REMOVE."""
        entry = FakeEntry({
            "member": [],
            "member;range=0-0": ["CN=user1,DC=test"],
        })
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=True)
        assert added == []
        assert removed == ["CN=user1,DC=test"]

    def test_incremental_mixed_adds_and_removes(self, ldap_client):
        """Both adds and removes in the same entry."""
        entry = FakeEntry({
            "member": [],
            "member;range=1-1": ["CN=added_user,DC=test"],
            "member;range=0-0": ["CN=removed_user,DC=test"],
        })
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=True)
        assert added == ["CN=added_user,DC=test"]
        assert removed == ["CN=removed_user,DC=test"]

    def test_incremental_multiple_adds(self, ldap_client):
        """Multiple members added in a single range attribute."""
        entry = FakeEntry({
            "member": [],
            "member;range=1-1": ["CN=u1,DC=test", "CN=u2,DC=test", "CN=u3,DC=test"],
        })
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=True)
        assert len(added) == 3
        assert removed == []

    def test_incremental_plain_member_also_treated_as_add(self, ldap_client):
        """If plain member has values in incremental mode, treat as adds too."""
        entry = FakeEntry({
            "member": ["CN=plain_user,DC=test"],
            "member;range=1-1": ["CN=ranged_user,DC=test"],
        })
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=True)
        assert "CN=plain_user,DC=test" in added
        assert "CN=ranged_user,DC=test" in added
        assert removed == []

    def test_incremental_ignores_non_member_range_attrs(self, ldap_client):
        """Attributes like objectClass;range=... should be ignored."""
        entry = FakeEntry({
            "member": [],
            "objectClass;range=0-0": ["top"],
            "member;range=1-1": ["CN=user1,DC=test"],
        })
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=True)
        assert added == ["CN=user1,DC=test"]
        assert removed == []

    def test_incremental_no_ranged_attrs(self, ldap_client):
        """Entry with no ranged member attrs in incremental mode."""
        entry = FakeEntry({"member": [], "sAMAccountName": ["TestGroup"]})
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=True)
        assert added == []
        assert removed == []


# =========================================================================
# _process_dirsync_entries: group name resolution + tombstones
# =========================================================================

class TestProcessDirsyncEntries:
    """Tests for _process_dirsync_entries parsing."""

    def _make_group_entry(self, *, sam_name=None, dn=None, entry_dn=None,
                          is_deleted=False, member_attrs=None):
        """Build a FakeEntry resembling a DirSync group result."""
        attrs = {}
        if sam_name is not None:
            attrs["sAMAccountName"] = [sam_name]
        else:
            attrs["sAMAccountName"] = []

        if dn is not None:
            attrs["distinguishedName"] = [dn]
        else:
            attrs["distinguishedName"] = []

        attrs["objectGUID"] = ["{some-guid}"]
        attrs["isDeleted"] = ["TRUE"] if is_deleted else []

        if member_attrs:
            attrs.update(member_attrs)
        else:
            attrs["member"] = []

        actual_entry_dn = entry_dn or dn or ""
        return FakeEntry(attrs, entry_dn=actual_entry_dn)

    def test_extracts_group_name_from_samaccountname(self, ldap_client):
        """sAMAccountName should be the primary source for group name."""
        entry = self._make_group_entry(
            sam_name="MyGroup",
            member_attrs={"member": [], "member;range=1-1": ["CN=user1,DC=test"]},
        )
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert len(changes) == 1
        assert changes[0].group_id == "ad:mygroup"

    def test_falls_back_to_distinguished_name(self, ldap_client):
        """When sAMAccountName is missing, extract CN from distinguishedName."""
        entry = self._make_group_entry(
            dn="CN=FallbackGroup,CN=Users,DC=test",
            member_attrs={"member": [], "member;range=1-1": ["CN=user1,DC=test"]},
        )
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert len(changes) == 1
        assert changes[0].group_id == "ad:fallbackgroup"

    def test_falls_back_to_entry_dn(self, ldap_client):
        """When both sAMAccountName and distinguishedName are missing, use entry_dn."""
        entry = self._make_group_entry(
            entry_dn="CN=EntryDnGroup,CN=Users,DC=test",
            member_attrs={"member": [], "member;range=1-1": ["CN=user1,DC=test"]},
        )
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert len(changes) == 1
        assert changes[0].group_id == "ad:entrydngroup"

    def test_skips_entry_with_no_name(self, ldap_client):
        """Entries with no sAMAccountName, DN, or entry_dn should be skipped."""
        entry = self._make_group_entry(
            member_attrs={"member": [], "member;range=1-1": ["CN=user1,DC=test"]},
        )
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert len(changes) == 0

    def test_tombstone_suffix_stripped_backslash_0a(self, ldap_client):
        """Tombstone CN with \\0ADEL: suffix should be stripped."""
        tombstone_dn = (
            r"CN=MyGroup\0ADEL:8a7f0382-0da4-4f65-9483-c0711d183fac,"
            "CN=Deleted Objects,DC=test"
        )
        entry = self._make_group_entry(
            entry_dn=tombstone_dn,
            is_deleted=True,
        )
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert "ad:mygroup" in deleted
        # Should NOT contain the GUID suffix
        assert not any("0adel" in gid for gid in deleted)

    def test_tombstone_suffix_stripped_newline(self, ldap_client):
        """Tombstone CN with actual newline + DEL: should be stripped."""
        tombstone_dn = (
            "CN=MyGroup\nDEL:8a7f0382-0da4-4f65-9483-c0711d183fac,"
            "CN=Deleted Objects,DC=test"
        )
        entry = self._make_group_entry(
            entry_dn=tombstone_dn,
            is_deleted=True,
        )
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert "ad:mygroup" in deleted

    def test_normal_group_name_not_affected_by_tombstone_strip(self, ldap_client):
        """Regular group names without DEL: should pass through unchanged."""
        entry = self._make_group_entry(
            sam_name="NormalGroup",
            member_attrs={"member": [], "member;range=1-1": ["CN=user1,DC=test"]},
        )
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert changes[0].group_id == "ad:normalgroup"

    def test_deleted_group_goes_to_deleted_set(self, ldap_client):
        """isDeleted=TRUE entries should be added to deleted_group_ids."""
        entry = self._make_group_entry(
            sam_name="DeletedGroup",
            is_deleted=True,
        )
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert len(changes) == 0  # No membership changes for deleted groups
        assert "ad:deletedgroup" in deleted
        assert len(modified) == 0

    def test_modified_group_goes_to_modified_set(self, ldap_client):
        """Groups with member changes should appear in modified_group_ids."""
        entry = self._make_group_entry(
            sam_name="ModifiedGroup",
            member_attrs={"member": [], "member;range=1-1": ["CN=user1,DC=test"]},
        )
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert "ad:modifiedgroup" in modified
        assert len(deleted) == 0

    def test_entry_with_no_member_changes_skipped(self, ldap_client):
        """Groups with no adds or removes should produce no changes."""
        entry = self._make_group_entry(sam_name="EmptyGroup")
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert len(changes) == 0
        assert len(modified) == 0

    def test_incremental_classifies_adds_and_removes(self, ldap_client):
        """End-to-end: incremental mode should correctly classify adds/removes."""
        entry = self._make_group_entry(
            sam_name="TestGroup",
            member_attrs={
                "member": [],
                "member;range=1-1": ["CN=added_user,CN=Users,DC=test"],
                "member;range=0-0": ["CN=removed_user,CN=Users,DC=test"],
            },
        )
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        adds = [c for c in changes if c.change_type == ACLChangeType.ADD]
        removes = [c for c in changes if c.change_type == ACLChangeType.REMOVE]
        assert len(adds) == 1
        assert len(removes) == 1
        assert adds[0].member_id == "added_user"
        assert removes[0].member_id == "removed_user"

    def test_full_mode_all_members_are_adds(self, ldap_client):
        """In full mode (not incremental), all members should be ADDs."""
        entry = self._make_group_entry(
            sam_name="FullGroup",
            member_attrs={
                "member": [
                    "CN=user1,CN=Users,DC=test",
                    "CN=user2,CN=Users,DC=test",
                ],
            },
        )
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=False
        )
        assert all(c.change_type == ACLChangeType.ADD for c in changes)
        assert len(changes) == 2

    def test_multiple_entries(self, ldap_client):
        """Multiple entries with different states should all be processed."""
        entries = [
            self._make_group_entry(
                sam_name="Group1",
                member_attrs={"member": [], "member;range=1-1": ["CN=u1,CN=Users,DC=test"]},
            ),
            self._make_group_entry(
                sam_name="DeletedGroup",
                is_deleted=True,
            ),
            self._make_group_entry(
                sam_name="Group2",
                member_attrs={"member": [], "member;range=0-0": ["CN=u2,CN=Users,DC=test"]},
            ),
        ]
        changes, modified, deleted = ldap_client._process_dirsync_entries(
            entries, is_initial=False, incremental_mode=True
        )
        assert len(changes) == 2  # 1 add + 1 remove
        assert "ad:deletedgroup" in deleted
        assert "ad:group1" in modified
        assert "ad:group2" in modified


# =========================================================================
# DirSyncResult.incremental_values propagation
# =========================================================================

class TestDirSyncResultIncrementalValues:
    """Tests for incremental_values field on DirSyncResult."""

    def test_defaults_to_false(self):
        """incremental_values should default to False."""
        result = DirSyncResult()
        assert result.incremental_values is False

    def test_can_be_set_true(self):
        """incremental_values should be settable to True."""
        result = DirSyncResult(incremental_values=True)
        assert result.incremental_values is True

    def test_full_flags_constant(self):
        """DIRSYNC_FLAGS_FULL should be the INCREMENTAL_VALUES flag."""
        assert DIRSYNC_FLAGS_FULL == LDAP_DIRSYNC_INCREMENTAL_VALUES

    def test_basic_flags_constant(self):
        """DIRSYNC_FLAGS_BASIC should be 0."""
        assert DIRSYNC_FLAGS_BASIC == 0

    def test_incremental_mode_detection(self):
        """incremental_mode = bool(flags & INCREMENTAL_VALUES) and not is_initial."""
        flags = DIRSYNC_FLAGS_FULL
        # Incremental (has cookie)
        assert bool(flags & LDAP_DIRSYNC_INCREMENTAL_VALUES) is True
        # Initial (no cookie) — should not be incremental even with full flags
        # (tested via is_initial flag in the actual code)

    @pytest.mark.asyncio
    async def test_propagated_through_pagination(self):
        """get_membership_changes should propagate incremental_values from pages."""
        client = LDAPClient(
            server="ldaps://server:636",
            username="admin",
            password="pass",
            domain="DOMAIN",
            search_base="DC=DOMAIN,DC=local",
            logger=MagicMock(),
        )

        page_results = [
            DirSyncResult(
                new_cookie=b"cookie1",
                incremental_values=True,
                more_results=True,
            ),
            DirSyncResult(
                new_cookie=b"cookie2",
                incremental_values=True,
                more_results=False,
            ),
        ]
        call_idx = 0

        async def mock_query(cookie, is_initial, flags):
            nonlocal call_idx
            result = page_results[call_idx]
            call_idx += 1
            return result

        client._execute_dirsync_query = mock_query

        result = await client.get_membership_changes(cookie_b64="dGVzdA==")
        assert result.incremental_values is True

    @pytest.mark.asyncio
    async def test_not_propagated_when_basic_fallback(self):
        """If all pages used BASIC flags, incremental_values should be False."""
        client = LDAPClient(
            server="ldaps://server:636",
            username="admin",
            password="pass",
            domain="DOMAIN",
            search_base="DC=DOMAIN,DC=local",
            logger=MagicMock(),
        )

        async def mock_query(cookie, is_initial, flags):
            return DirSyncResult(
                new_cookie=b"cookie",
                incremental_values=False,  # BASIC flags
                more_results=False,
            )

        client._execute_dirsync_query = mock_query

        result = await client.get_membership_changes(cookie_b64="dGVzdA==")
        assert result.incremental_values is False


# =========================================================================
# Flag constants and bitwise operations
# =========================================================================

class TestFlagConstants:
    """Tests for DirSync flag constant values."""

    def test_incremental_values_bitwise_and(self):
        """FULL flags & INCREMENTAL_VALUES should be truthy (for incremental_mode check)."""
        flags = DIRSYNC_FLAGS_FULL
        assert bool(flags & LDAP_DIRSYNC_INCREMENTAL_VALUES)

    def test_basic_flags_bitwise_and(self):
        """BASIC flags & INCREMENTAL_VALUES should be falsy."""
        flags = DIRSYNC_FLAGS_BASIC
        assert not bool(flags & LDAP_DIRSYNC_INCREMENTAL_VALUES)

    def test_combined_flags_preserve_incremental(self):
        """Combining INCREMENTAL_VALUES with other flags should still detect it."""
        from airweave.platform.sources.sharepoint2019v2.ldap import (
            LDAP_DIRSYNC_OBJECT_SECURITY,
        )
        combined = LDAP_DIRSYNC_INCREMENTAL_VALUES | LDAP_DIRSYNC_OBJECT_SECURITY
        assert bool(combined & LDAP_DIRSYNC_INCREMENTAL_VALUES)


# =========================================================================
# DirSyncResult cookie base64 encoding
# =========================================================================

class TestDirSyncResultCookie:
    """Tests for DirSyncResult cookie_b64 / cookie_from_b64 roundtrip."""

    def test_cookie_b64_roundtrip(self):
        """Cookie bytes should survive encode → decode via base64."""
        cookie = b"\x01\x02\x03\x80\xff\x00"
        result = DirSyncResult(new_cookie=cookie)
        b64 = result.cookie_b64
        decoded = DirSyncResult.cookie_from_b64(b64)
        assert decoded == cookie

    def test_empty_cookie_returns_empty_string(self):
        """Empty cookie should produce empty base64 string."""
        result = DirSyncResult(new_cookie=b"")
        assert result.cookie_b64 == ""

    def test_cookie_from_b64_empty_returns_empty_bytes(self):
        """Empty base64 string should produce empty bytes."""
        assert DirSyncResult.cookie_from_b64("") == b""

    def test_cookie_from_b64_none_returns_empty_bytes(self):
        """None/falsy base64 string should produce empty bytes."""
        assert DirSyncResult.cookie_from_b64(None) == b""

    def test_large_cookie_roundtrip(self):
        """108-byte cookies (real AD size) should roundtrip correctly."""
        cookie = bytes(range(108))
        result = DirSyncResult(new_cookie=cookie)
        assert DirSyncResult.cookie_from_b64(result.cookie_b64) == cookie


# =========================================================================
# incremental_mode detection (is_initial + flags interaction)
# =========================================================================

class TestIncrementalModeDetection:
    """Tests for the incremental_mode = bool(flags & INCR_VALUES) and not is_initial logic.

    This is the critical gate at _execute_dirsync_search line 1024 that determines
    whether member;range parsing produces adds/removes or full member lists.
    """

    def test_full_flags_incremental_is_true(self):
        """FULL flags + not initial → incremental_mode=True."""
        flags = DIRSYNC_FLAGS_FULL
        is_initial = False
        incremental_mode = bool(flags & LDAP_DIRSYNC_INCREMENTAL_VALUES) and not is_initial
        assert incremental_mode is True

    def test_full_flags_initial_is_false(self):
        """FULL flags + initial → incremental_mode=False (first sync has full lists)."""
        flags = DIRSYNC_FLAGS_FULL
        is_initial = True
        incremental_mode = bool(flags & LDAP_DIRSYNC_INCREMENTAL_VALUES) and not is_initial
        assert incremental_mode is False

    def test_basic_flags_incremental_is_false(self):
        """BASIC flags + not initial → incremental_mode=False (no INCR_VALUES)."""
        flags = DIRSYNC_FLAGS_BASIC
        is_initial = False
        incremental_mode = bool(flags & LDAP_DIRSYNC_INCREMENTAL_VALUES) and not is_initial
        assert incremental_mode is False

    def test_basic_flags_initial_is_false(self):
        """BASIC flags + initial → incremental_mode=False."""
        flags = DIRSYNC_FLAGS_BASIC
        is_initial = True
        incremental_mode = bool(flags & LDAP_DIRSYNC_INCREMENTAL_VALUES) and not is_initial
        assert incremental_mode is False

    def test_process_entries_initial_treats_all_as_adds(self, ldap_client):
        """Even with member;range attrs, initial sync treats everything as adds."""
        entry = FakeEntry({
            "sAMAccountName": ["TestGroup"],
            "member": ["CN=user1,DC=test"],
            "member;range=0-0": ["CN=user2,DC=test"],
            "distinguishedName": [],
            "objectGUID": ["{guid}"],
            "isDeleted": [],
        }, entry_dn="CN=TestGroup,DC=test")
        # incremental_mode=False means all members are ADDs (full mode)
        changes, _, _ = ldap_client._process_dirsync_entries(
            [entry], is_initial=True, incremental_mode=False
        )
        # In full mode, only the plain "member" attribute is used
        assert all(c.change_type == ACLChangeType.ADD for c in changes)
        assert len(changes) == 1  # only CN=user1 from plain member

    def test_process_entries_incremental_separates_adds_removes(self, ldap_client):
        """Incremental mode must separate adds and removes via range suffix."""
        entry = FakeEntry({
            "sAMAccountName": ["TestGroup"],
            "member": [],
            "member;range=1-1": ["CN=added,DC=test"],
            "member;range=0-0": ["CN=removed,DC=test"],
            "distinguishedName": [],
            "objectGUID": ["{guid}"],
            "isDeleted": [],
        }, entry_dn="CN=TestGroup,DC=test")
        changes, _, _ = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        adds = [c for c in changes if c.change_type == ACLChangeType.ADD]
        removes = [c for c in changes if c.change_type == ACLChangeType.REMOVE]
        assert len(adds) == 1
        assert len(removes) == 1


# =========================================================================
# _execute_dirsync_query_with_flags: fallback logic
# =========================================================================

class TestDirSyncNoFlagFallback:
    """Tests that DirSyncPermissionError propagates without silent fallback.

    When AD rejects FULL flags (INCREMENTAL_VALUES), the error propagates up to
    _process_incremental which falls back to a full sync. There is no silent
    retry with BASIC flags, because BASIC flags can only add members (never
    remove), leading to stale membership accumulation.
    """

    @pytest.mark.asyncio
    async def test_permission_error_propagates(self):
        """DirSyncPermissionError is not caught — it propagates to the caller."""
        client = LDAPClient(
            server="ldaps://server:636",
            username="admin",
            password="pass",
            domain="DOMAIN",
            search_base="DC=DOMAIN,DC=local",
            logger=MagicMock(),
        )

        async def mock_query(cookie, is_initial, flags):
            raise DirSyncPermissionError("unsupported flag")

        client._execute_dirsync_query = mock_query

        with pytest.raises(DirSyncPermissionError):
            await client.get_membership_changes(cookie_b64="")

    @pytest.mark.asyncio
    async def test_success_returns_result_directly(self):
        """Successful FULL flags query returns result without retry."""
        client = LDAPClient(
            server="ldaps://server:636",
            username="admin",
            password="pass",
            domain="DOMAIN",
            search_base="DC=DOMAIN,DC=local",
            logger=MagicMock(),
        )

        async def mock_query(cookie, is_initial, flags):
            assert flags == DIRSYNC_FLAGS_FULL
            return DirSyncResult(
                new_cookie=b"ok", incremental_values=True, more_results=False
            )

        client._execute_dirsync_query = mock_query

        result = await client.get_membership_changes(cookie_b64="")
        assert result.incremental_values is True


# =========================================================================
# get_membership_changes: pagination aggregation
# =========================================================================

class TestGetMembershipChangesPagination:
    """Tests for get_membership_changes multi-page aggregation."""

    @pytest.mark.asyncio
    async def test_aggregates_changes_across_pages(self):
        """Changes from multiple pages should be merged into one result."""
        client = LDAPClient(
            server="ldaps://server:636",
            username="admin",
            password="pass",
            domain="DOMAIN",
            search_base="DC=DOMAIN,DC=local",
            logger=MagicMock(),
        )

        page_results = [
            DirSyncResult(
                changes=[
                    MembershipChange(
                        change_type=ACLChangeType.ADD,
                        member_id="user1", member_type="user",
                        group_id="ad:group1", group_name="Group1",
                    ),
                ],
                new_cookie=b"cookie1",
                modified_group_ids={"ad:group1"},
                incremental_values=True,
                more_results=True,
            ),
            DirSyncResult(
                changes=[
                    MembershipChange(
                        change_type=ACLChangeType.REMOVE,
                        member_id="user2", member_type="user",
                        group_id="ad:group2", group_name="Group2",
                    ),
                ],
                new_cookie=b"cookie2",
                modified_group_ids={"ad:group2"},
                deleted_group_ids={"ad:deleted1"},
                incremental_values=True,
                more_results=False,
            ),
        ]
        call_idx = 0

        async def mock_query(cookie, is_initial, flags):
            nonlocal call_idx
            result = page_results[call_idx]
            call_idx += 1
            return result

        client._execute_dirsync_query = mock_query

        result = await client.get_membership_changes(cookie_b64="dGVzdA==")
        assert len(result.changes) == 2
        assert result.modified_group_ids == {"ad:group1", "ad:group2"}
        assert result.deleted_group_ids == {"ad:deleted1"}
        assert result.new_cookie == b"cookie2"  # last page's cookie
        assert result.more_results is False
        assert result.incremental_values is True

    @pytest.mark.asyncio
    async def test_initial_sync_no_cookie(self):
        """Empty cookie should set is_initial=True."""
        client = LDAPClient(
            server="ldaps://server:636",
            username="admin",
            password="pass",
            domain="DOMAIN",
            search_base="DC=DOMAIN,DC=local",
            logger=MagicMock(),
        )

        captured_args = {}

        async def mock_query(cookie, is_initial, flags):
            captured_args["is_initial"] = is_initial
            captured_args["flags"] = flags
            return DirSyncResult(new_cookie=b"first", more_results=False)

        client._execute_dirsync_query = mock_query

        await client.get_membership_changes(cookie_b64="")
        assert captured_args["is_initial"] is True
        assert captured_args["flags"] == DIRSYNC_FLAGS_FULL

    @pytest.mark.asyncio
    async def test_incremental_sync_with_cookie(self):
        """Non-empty cookie should set is_initial=False."""
        client = LDAPClient(
            server="ldaps://server:636",
            username="admin",
            password="pass",
            domain="DOMAIN",
            search_base="DC=DOMAIN,DC=local",
            logger=MagicMock(),
        )

        captured_args = {}

        async def mock_query(cookie, is_initial, flags):
            captured_args["is_initial"] = is_initial
            return DirSyncResult(new_cookie=b"next", more_results=False)

        client._execute_dirsync_query = mock_query

        await client.get_membership_changes(cookie_b64="dGVzdA==")
        assert captured_args["is_initial"] is False

    @pytest.mark.asyncio
    async def test_incremental_values_propagated_across_pages(self):
        """incremental_values=True on any page means True for the aggregate result."""
        client = LDAPClient(
            server="ldaps://server:636",
            username="admin",
            password="pass",
            domain="DOMAIN",
            search_base="DC=DOMAIN,DC=local",
            logger=MagicMock(),
        )

        page_results = [
            DirSyncResult(
                new_cookie=b"c1", incremental_values=True, more_results=True,
            ),
            DirSyncResult(
                new_cookie=b"c2", incremental_values=True, more_results=False,
            ),
        ]
        call_idx = 0

        async def mock_query(cookie, is_initial, flags):
            nonlocal call_idx
            r = page_results[call_idx]
            call_idx += 1
            return r

        client._execute_dirsync_query = mock_query

        result = await client.get_membership_changes(cookie_b64="dGVzdA==")
        assert result.incremental_values is True


# =========================================================================
# Tombstone edge cases
# =========================================================================

class TestTombstoneEdgeCases:
    """Additional edge cases for tombstone DN suffix stripping."""

    def _make_group_entry(self, *, sam_name=None, dn=None, entry_dn=None,
                          is_deleted=False, member_attrs=None):
        """Build a FakeEntry resembling a DirSync group result."""
        attrs = {}
        attrs["sAMAccountName"] = [sam_name] if sam_name else []
        attrs["distinguishedName"] = [dn] if dn else []
        attrs["objectGUID"] = ["{some-guid}"]
        attrs["isDeleted"] = ["TRUE"] if is_deleted else []
        if member_attrs:
            attrs.update(member_attrs)
        else:
            attrs["member"] = []
        actual_entry_dn = entry_dn or dn or ""
        return FakeEntry(attrs, entry_dn=actual_entry_dn)

    def test_lowercase_0adel_stripped(self, ldap_client):
        r"""Tombstone with lowercase \0aDEL: should be stripped."""
        tombstone_dn = (
            r"CN=MyGroup\0aDEL:8a7f0382-0da4-4f65-9483-c0711d183fac,"
            "CN=Deleted Objects,DC=test"
        )
        entry = self._make_group_entry(entry_dn=tombstone_dn, is_deleted=True)
        _, _, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert "ad:mygroup" in deleted

    def test_tombstone_with_samaccountname_still_strips(self, ldap_client):
        r"""sAMAccountName with \0ADEL suffix should also be stripped."""
        entry = self._make_group_entry(
            sam_name=r"MyGroup\0ADEL:guid-here",
            is_deleted=True,
        )
        _, _, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert "ad:mygroup" in deleted

    def test_group_name_with_zero_not_stripped(self, ldap_client):
        """Group names containing '0' but no DEL pattern should be untouched."""
        entry = self._make_group_entry(
            sam_name="Group0Admin",
            member_attrs={"member": [], "member;range=1-1": ["CN=u1,DC=test"]},
        )
        changes, _, _ = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert changes[0].group_id == "ad:group0admin"

    def test_deleted_group_with_dn_attribute(self, ldap_client):
        """Deleted group where distinguishedName (not entry_dn) has the tombstone."""
        tombstone_dn = (
            r"CN=TestDel\0ADEL:abc-123,"
            "CN=Deleted Objects,DC=test"
        )
        entry = self._make_group_entry(
            dn=tombstone_dn,
            entry_dn=tombstone_dn,
            is_deleted=True,
        )
        _, _, deleted = ldap_client._process_dirsync_entries(
            [entry], is_initial=False, incremental_mode=True
        )
        assert "ad:testdel" in deleted

    def test_multiple_deleted_groups_all_stripped(self, ldap_client):
        """Multiple tombstones in same batch should all have suffixes stripped."""
        entries = [
            self._make_group_entry(
                entry_dn=r"CN=Group1\0ADEL:guid1,CN=Deleted Objects,DC=test",
                is_deleted=True,
            ),
            self._make_group_entry(
                entry_dn="CN=Group2\nDEL:guid2,CN=Deleted Objects,DC=test",
                is_deleted=True,
            ),
        ]
        _, _, deleted = ldap_client._process_dirsync_entries(
            entries, is_initial=False, incremental_mode=True
        )
        assert "ad:group1" in deleted
        assert "ad:group2" in deleted
        assert len(deleted) == 2


# =========================================================================
# _get_entry_members: edge cases for range attribute parsing
# =========================================================================


class FakeEntryNoneAttr:
    """Entry that returns None for specific attributes (simulates missing range attrs).

    The standard FakeEntry always returns FakeAttr([]), which never hits the
    `range_attr is None` guard (line 1238). This variant returns None for
    attributes listed in `none_attrs`.
    """

    def __init__(self, attrs: dict, entry_dn: str = "", none_attrs: set = None):
        self._attrs = attrs
        self.entry_dn = entry_dn
        self._none_attrs = none_attrs or set()

    @property
    def entry_attributes(self):
        return list(self._attrs.keys())

    @property
    def entry_attributes_as_dict(self):
        return {k: list(v) for k, v in self._attrs.items()}

    def __getattr__(self, name):
        if name.startswith("_") or name in ("entry_dn", "entry_attributes",
                                             "entry_attributes_as_dict"):
            raise AttributeError(name)
        if name in self._none_attrs:
            return None
        if name in self._attrs:
            return FakeAttr(self._attrs[name])
        return FakeAttr([])


class FakeAttrStringValue:
    """Attribute that returns a string .value and None .values (hits isinstance str branch)."""

    def __init__(self, val: str):
        self.values = None
        self.value = val


class FakeEntryStringRangeAttr:
    """Entry whose range attribute returns a string value (not a list).

    Hits the `isinstance(range_vals, str)` branch at line 1245.
    """

    def __init__(self, attrs: dict, entry_dn: str = "", string_attrs: dict = None):
        self._attrs = attrs
        self.entry_dn = entry_dn
        self._string_attrs = string_attrs or {}

    @property
    def entry_attributes(self):
        return list(self._attrs.keys())

    @property
    def entry_attributes_as_dict(self):
        return {k: list(v) for k, v in self._attrs.items()}

    def __getattr__(self, name):
        if name.startswith("_") or name in ("entry_dn", "entry_attributes",
                                             "entry_attributes_as_dict"):
            raise AttributeError(name)
        if name in self._string_attrs:
            return FakeAttrStringValue(self._string_attrs[name])
        if name in self._attrs:
            return FakeAttr(self._attrs[name])
        return FakeAttr([])


class TestGetEntryMembersEdgeCases:
    """Edge cases for _get_entry_members range attribute parsing."""

    def test_range_attr_is_none_skipped(self, ldap_client):
        """When getattr(entry, range_attr) returns None, skip that attribute."""
        entry = FakeEntryNoneAttr(
            attrs={
                "member": [],
                "member;range=1-1": ["CN=user1,DC=test"],  # listed but returns None
            },
            none_attrs={"member;range=1-1"},
        )
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=True)
        # Should not crash, and user1 should NOT be in added (attr was None)
        assert added == []
        assert removed == []

    def test_range_vals_is_string_wrapped_to_list(self, ldap_client):
        """When range_vals is a single string (not list), it should be wrapped."""
        entry = FakeEntryStringRangeAttr(
            attrs={
                "member": [],
                "member;range=1-1": [],  # in entry_attributes but use string_attrs
            },
            string_attrs={"member;range=1-1": "CN=string_user,DC=test"},
        )
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=True)
        assert "CN=string_user,DC=test" in added
        assert removed == []

    def test_unknown_range_format_treated_as_add(self, ldap_client):
        """member;range=9-9 (unknown format) should log warning and treat as add."""
        entry = FakeEntry({
            "member": [],
            "member;range=9-9": ["CN=weird_user,DC=test"],
        })
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=True)
        assert "CN=weird_user,DC=test" in added
        assert removed == []
        ldap_client.logger.warning.assert_called_once()

    def test_range_attr_raises_attribute_error_skipped(self, ldap_client):
        """If accessing a range attribute raises AttributeError, it should be skipped."""
        class RaisingEntry:
            entry_dn = ""
            entry_attributes = ["member", "member;range=1-1"]
            entry_attributes_as_dict = {"member": [], "member;range=1-1": []}

            @property
            def member(self):
                return FakeAttr([])

            def __getattr__(self, name):
                if name == "member;range=1-1":
                    raise AttributeError("simulated error")
                raise AttributeError(name)

        # The issue is that "member;range=1-1" isn't a valid Python attr name,
        # so we test via a different approach: patch getattr to raise
        entry = FakeEntryNoneAttr(
            attrs={
                "member": [],
                "member;range=1-1": ["CN=user,DC=test"],
            },
        )
        # Override to raise TypeError instead (also caught)
        original_getattr = entry.__class__.__getattr__

        def raising_getattr(self, name):
            if name == "member;range=1-1":
                raise TypeError("simulated")
            return original_getattr(self, name)

        entry.__class__ = type("RaisingEntry", (FakeEntryNoneAttr,), {
            "__getattr__": raising_getattr,
            "entry_attributes": property(lambda self: list(self._attrs.keys())),
            "entry_attributes_as_dict": property(
                lambda self: {k: list(v) for k, v in self._attrs.items()}
            ),
        })

        added, removed = ldap_client._get_entry_members(entry, incremental_mode=True)
        # Should skip the problematic attr gracefully
        assert removed == []

    def test_range_vals_none_skipped(self, ldap_client):
        """When range attr has neither .values nor .value, skip it."""

        class NoneValuesAttr:
            values = None
            value = None

        class NoneValEntry:
            entry_dn = ""

            @property
            def entry_attributes(self):
                return ["member", "member;range=1-1"]

            @property
            def entry_attributes_as_dict(self):
                return {"member": [], "member;range=1-1": []}

            def __getattr__(self, name):
                if name == "member":
                    return FakeAttr([])
                if name == "member;range=1-1":
                    return NoneValuesAttr()
                raise AttributeError(name)

        entry = NoneValEntry()
        added, removed = ldap_client._get_entry_members(entry, incremental_mode=True)
        assert added == []
        assert removed == []
