"""Unit tests for AccessControlPipeline incremental ACL processing.

Tests the incremental sync path:
- _apply_membership_changes: Applies ADDs and REMOVEs from DirSync results
- _process_incremental: Full incremental flow including deleted group handling,
  cookie updates, and fallback to full sync on failure

Note: Reconciliation (diffing DB vs DirSync for BASIC flags) was intentionally
removed because _resolve_member_dn_sync failures would cause false deletions.
Removed members are cleaned up during the next full sync instead.
"""

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Set
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.platform.access_control.schemas import ACLChangeType, MembershipChange
from airweave.platform.sync.access_control_pipeline import AccessControlPipeline


# ---------------------------------------------------------------------------
# Helpers: lightweight fakes for SyncContext, SyncRuntime, DirSync results
# ---------------------------------------------------------------------------


@dataclass
class FakeSyncContext:
    """Minimal SyncContext for pipeline tests."""

    organization_id: object = field(default_factory=uuid4)
    source_connection_id: object = field(default_factory=uuid4)
    logger: object = field(default_factory=lambda: MagicMock())


@dataclass
class FakeCursor:
    """Minimal cursor supporting .data and .update()."""

    data: dict = field(default_factory=dict)

    def update(self, **kwargs):
        self.data.update(kwargs)


@dataclass
class FakeRuntime:
    """Minimal SyncRuntime."""

    cursor: FakeCursor = field(default_factory=FakeCursor)


@dataclass
class FakeDirSyncResult:
    """DirSync result returned by source.get_acl_changes()."""

    changes: list = field(default_factory=list)
    modified_group_ids: Set[str] = field(default_factory=set)
    deleted_group_ids: Set[str] = field(default_factory=set)
    incremental_values: bool = False
    cookie_b64: str = "new_cookie"


def _make_change(change_type, member_id, member_type, group_id, group_name=None):
    """Helper to build a MembershipChange."""
    return MembershipChange(
        change_type=change_type,
        member_id=member_id,
        member_type=member_type,
        group_id=group_id,
        group_name=group_name,
    )


def _make_pipeline():
    """Create an AccessControlPipeline with mocked internals."""
    return AccessControlPipeline(
        resolver=MagicMock(),
        dispatcher=MagicMock(),
        tracker=MagicMock(),
    )


# ---------------------------------------------------------------------------
# Tests: _apply_membership_changes
# ---------------------------------------------------------------------------


class TestApplyMembershipChanges:
    """Tests for _apply_membership_changes ADD/REMOVE processing."""

    @pytest.mark.asyncio
    async def test_applies_adds_and_removes(self):
        """ADDs are upserted and REMOVEs are deleted."""
        pipeline = _make_pipeline()
        ctx = FakeSyncContext()
        db = MagicMock()
        source = SimpleNamespace(_short_name="sp2019v2")

        result = FakeDirSyncResult(
            changes=[
                _make_change(ACLChangeType.ADD, "alice@acme.com", "user", "group-A"),
                _make_change(ACLChangeType.REMOVE, "bob@acme.com", "user", "group-A"),
                _make_change(ACLChangeType.ADD, "charlie@acme.com", "user", "group-B"),
            ],
            modified_group_ids={"group-A", "group-B"},
        )

        with patch("airweave.platform.sync.access_control_pipeline.crud") as mock_crud:
            mock_crud.access_control_membership.upsert = AsyncMock()
            mock_crud.access_control_membership.delete_by_key = AsyncMock()

            adds, removes = await pipeline._apply_membership_changes(
                db, result, source, ctx
            )

        assert adds == 2
        assert removes == 1
        assert mock_crud.access_control_membership.upsert.call_count == 2
        assert mock_crud.access_control_membership.delete_by_key.call_count == 1

    @pytest.mark.asyncio
    async def test_basic_flags_does_not_reconcile(self):
        """With BASIC flags (incremental_values=False), no reconciliation occurs.

        Reconciliation was removed because _resolve_member_dn_sync failures
        would cause false deletions of valid memberships.
        """
        pipeline = _make_pipeline()
        ctx = FakeSyncContext()
        db = MagicMock()
        source = SimpleNamespace(_short_name="sp2019v2")

        result = FakeDirSyncResult(
            changes=[
                _make_change(ACLChangeType.ADD, "alice@acme.com", "user", "group-A"),
                _make_change(ACLChangeType.ADD, "charlie@acme.com", "user", "group-A"),
            ],
            modified_group_ids={"group-A"},
            incremental_values=False,
        )

        with patch("airweave.platform.sync.access_control_pipeline.crud") as mock_crud:
            mock_crud.access_control_membership.upsert = AsyncMock()
            mock_crud.access_control_membership.delete_by_key = AsyncMock()
            mock_crud.access_control_membership.get_memberships_by_groups = AsyncMock()

            adds, removes = await pipeline._apply_membership_changes(
                db, result, source, ctx
            )

        assert adds == 2
        assert removes == 0
        # No reconciliation — get_memberships_by_groups never called
        mock_crud.access_control_membership.get_memberships_by_groups.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_passes_correct_fields(self):
        """Verify upsert is called with all correct keyword arguments."""
        pipeline = _make_pipeline()
        ctx = FakeSyncContext()
        db = MagicMock()
        source = SimpleNamespace(_short_name="sp2019v2")

        result = FakeDirSyncResult(
            changes=[
                _make_change(
                    ACLChangeType.ADD, "alice@acme.com", "user", "group-eng", "Engineering"
                ),
            ],
            modified_group_ids=set(),
        )

        with patch("airweave.platform.sync.access_control_pipeline.crud") as mock_crud:
            mock_crud.access_control_membership.upsert = AsyncMock()

            await pipeline._apply_membership_changes(
                db, result, source, ctx
            )

        mock_crud.access_control_membership.upsert.assert_called_once_with(
            db,
            member_id="alice@acme.com",
            member_type="user",
            group_id="group-eng",
            group_name="Engineering",
            organization_id=ctx.organization_id,
            source_connection_id=ctx.source_connection_id,
            source_name="sp2019v2",
        )

    @pytest.mark.asyncio
    async def test_empty_changes_returns_zero(self):
        """No changes means zero adds and removes."""
        pipeline = _make_pipeline()
        ctx = FakeSyncContext()
        db = MagicMock()
        source = SimpleNamespace(_short_name="sp2019v2")

        result = FakeDirSyncResult(changes=[], modified_group_ids=set())

        with patch("airweave.platform.sync.access_control_pipeline.crud") as mock_crud:
            mock_crud.access_control_membership.upsert = AsyncMock()
            mock_crud.access_control_membership.delete_by_key = AsyncMock()

            adds, removes = await pipeline._apply_membership_changes(
                db, result, source, ctx
            )

        assert adds == 0
        assert removes == 0


# ---------------------------------------------------------------------------
# Tests: _process_incremental (full flow)
# ---------------------------------------------------------------------------


class TestProcessIncremental:
    """Integration tests for the full _process_incremental flow with mocked DB."""

    @pytest.mark.asyncio
    async def test_deleted_groups_remove_all_memberships(self):
        """Deleted AD groups should have all their memberships removed via delete_by_group."""
        pipeline = _make_pipeline()
        ctx = FakeSyncContext()
        runtime = FakeRuntime(
            cursor=FakeCursor(data={"acl_dirsync_cookie": "old_cookie"})
        )
        source = SimpleNamespace(
            _short_name="sp2019v2",
            get_acl_changes=AsyncMock(),
        )

        result = FakeDirSyncResult(
            changes=[],
            modified_group_ids=set(),
            deleted_group_ids={"deleted-group-1", "deleted-group-2"},
            incremental_values=True,
            cookie_b64="new_cookie_123",
        )
        source.get_acl_changes.return_value = result

        with patch("airweave.platform.sync.access_control_pipeline.crud") as mock_crud, \
             patch("airweave.platform.sync.access_control_pipeline.get_db_context") as mock_db_ctx:
            mock_db = MagicMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_crud.access_control_membership.delete_by_group = AsyncMock(return_value=5)

            total = await pipeline._process_incremental(source, ctx, runtime)

        assert total == 10  # 5 members x 2 groups
        assert mock_crud.access_control_membership.delete_by_group.call_count == 2

    @pytest.mark.asyncio
    async def test_no_changes_returns_zero_and_updates_cookie(self):
        """When DirSync reports zero changes, return 0 but still advance the cookie."""
        pipeline = _make_pipeline()
        ctx = FakeSyncContext()
        runtime = FakeRuntime(
            cursor=FakeCursor(data={"acl_dirsync_cookie": "old_cookie"})
        )
        source = SimpleNamespace(
            _short_name="sp2019v2",
            get_acl_changes=AsyncMock(),
        )

        result = FakeDirSyncResult(
            changes=[],
            modified_group_ids=set(),
            deleted_group_ids=set(),
            cookie_b64="advanced_cookie",
        )
        source.get_acl_changes.return_value = result

        total = await pipeline._process_incremental(source, ctx, runtime)

        assert total == 0
        assert runtime.cursor.data["acl_dirsync_cookie"] == "advanced_cookie"

    @pytest.mark.asyncio
    async def test_fallback_to_full_sync_on_exception(self):
        """If get_acl_changes raises, fall back to full sync."""
        pipeline = _make_pipeline()
        ctx = FakeSyncContext()
        runtime = FakeRuntime()
        source = SimpleNamespace(
            _short_name="sp2019v2",
            get_acl_changes=AsyncMock(side_effect=Exception("LDAP timeout")),
        )

        # Mock _process_full to track fallback
        pipeline._process_full = AsyncMock(return_value=42)

        total = await pipeline._process_incremental(source, ctx, runtime)

        assert total == 42
        pipeline._process_full.assert_called_once_with(source, ctx, runtime)

    @pytest.mark.asyncio
    async def test_full_flow_with_adds_removes_and_deletes(self):
        """End-to-end: ADDs + REMOVEs + deleted groups in one incremental sync."""
        pipeline = _make_pipeline()
        ctx = FakeSyncContext()
        runtime = FakeRuntime(
            cursor=FakeCursor(data={"acl_dirsync_cookie": "old"})
        )
        source = SimpleNamespace(
            _short_name="sp2019v2",
            get_acl_changes=AsyncMock(),
        )

        result = FakeDirSyncResult(
            changes=[
                _make_change(ACLChangeType.ADD, "alice@acme.com", "user", "group-A"),
                _make_change(ACLChangeType.ADD, "bob@acme.com", "user", "group-A"),
                _make_change(ACLChangeType.REMOVE, "charlie@acme.com", "user", "group-B"),
            ],
            modified_group_ids={"group-A", "group-B"},
            deleted_group_ids={"dead-group"},
            incremental_values=True,
            cookie_b64="final_cookie",
        )
        source.get_acl_changes.return_value = result

        with patch("airweave.platform.sync.access_control_pipeline.crud") as mock_crud, \
             patch("airweave.platform.sync.access_control_pipeline.get_db_context") as mock_db_ctx:
            mock_db = MagicMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_crud.access_control_membership.upsert = AsyncMock()
            mock_crud.access_control_membership.delete_by_key = AsyncMock()
            mock_crud.access_control_membership.delete_by_group = AsyncMock(return_value=3)

            total = await pipeline._process_incremental(source, ctx, runtime)

        # 2 adds + 1 remove + 3 group-deletion removals = 6
        assert total == 6
        assert mock_crud.access_control_membership.upsert.call_count == 2
        assert mock_crud.access_control_membership.delete_by_key.call_count == 1
        assert mock_crud.access_control_membership.delete_by_group.call_count == 1
        # Cookie should be updated
        assert runtime.cursor.data["acl_dirsync_cookie"] == "final_cookie"

    @pytest.mark.asyncio
    async def test_basic_flags_does_not_reconcile_in_full_flow(self):
        """With BASIC flags, _process_incremental only applies ADDs (no reconciliation)."""
        pipeline = _make_pipeline()
        ctx = FakeSyncContext()
        runtime = FakeRuntime(
            cursor=FakeCursor(data={"acl_dirsync_cookie": "old"})
        )
        source = SimpleNamespace(
            _short_name="sp2019v2",
            get_acl_changes=AsyncMock(),
        )

        result = FakeDirSyncResult(
            changes=[
                _make_change(ACLChangeType.ADD, "alice@acme.com", "user", "group-A"),
            ],
            modified_group_ids={"group-A"},
            deleted_group_ids=set(),
            incremental_values=False,
        )
        source.get_acl_changes.return_value = result

        with patch("airweave.platform.sync.access_control_pipeline.crud") as mock_crud, \
             patch("airweave.platform.sync.access_control_pipeline.get_db_context") as mock_db_ctx:
            mock_db = MagicMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_crud.access_control_membership.upsert = AsyncMock()
            mock_crud.access_control_membership.get_memberships_by_groups = AsyncMock()

            total = await pipeline._process_incremental(source, ctx, runtime)

        # Only the 1 ADD — no reconciliation removals
        assert total == 1
        mock_crud.access_control_membership.get_memberships_by_groups.assert_not_called()
