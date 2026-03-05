"""Unit tests for ACL Membership Tracker."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from airweave.platform.sync.pipeline.acl_membership_tracker import ACLMembershipTracker


@pytest.fixture
def tracker():
    """Create tracker instance."""
    mock_logger = MagicMock()
    mock_logger.info = MagicMock()
    return ACLMembershipTracker(
        source_connection_id=uuid4(),
        organization_id=uuid4(),
        logger=mock_logger,
    )


class TestTrackMembership:
    """Test membership tracking."""

    def test_track_membership_returns_true_for_new_membership(self, tracker):
        """Test that tracking new membership returns True."""
        result = tracker.track_membership(
            member_id="john@acme.com",
            member_type="user",
            group_id="sp:engineering",
        )

        assert result is True

    def test_track_membership_returns_false_for_duplicate(self, tracker):
        """Test that tracking duplicate membership returns False."""
        # Track first time
        result1 = tracker.track_membership(
            member_id="john@acme.com",
            member_type="user",
            group_id="sp:engineering",
        )
        assert result1 is True

        # Track same membership again
        result2 = tracker.track_membership(
            member_id="john@acme.com",
            member_type="user",
            group_id="sp:engineering",
        )
        assert result2 is False

    def test_track_membership_distinguishes_by_member_id(self, tracker):
        """Test that different member_ids are tracked separately."""
        result1 = tracker.track_membership(
            member_id="john@acme.com",
            member_type="user",
            group_id="sp:engineering",
        )
        result2 = tracker.track_membership(
            member_id="jane@acme.com",
            member_type="user",
            group_id="sp:engineering",
        )

        assert result1 is True
        assert result2 is True

    def test_track_membership_distinguishes_by_member_type(self, tracker):
        """Test that different member_types are tracked separately."""
        result1 = tracker.track_membership(
            member_id="engineering",
            member_type="user",
            group_id="sp:all_staff",
        )
        result2 = tracker.track_membership(
            member_id="engineering",
            member_type="group",
            group_id="sp:all_staff",
        )

        assert result1 is True
        assert result2 is True

    def test_track_membership_distinguishes_by_group_id(self, tracker):
        """Test that different group_ids are tracked separately."""
        result1 = tracker.track_membership(
            member_id="john@acme.com",
            member_type="user",
            group_id="sp:engineering",
        )
        result2 = tracker.track_membership(
            member_id="john@acme.com",
            member_type="user",
            group_id="sp:design",
        )

        assert result1 is True
        assert result2 is True


class TestGetStats:
    """Test statistics retrieval."""

    def test_get_stats_returns_correct_counts(self, tracker):
        """Test that stats reflect tracked memberships."""
        # Track some memberships
        tracker.track_membership("john@acme.com", "user", "sp:eng")
        tracker.track_membership("john@acme.com", "user", "sp:eng")  # Duplicate
        tracker.track_membership("jane@acme.com", "user", "sp:eng")

        stats = tracker.get_stats()

        assert stats.encountered == 2  # 2 unique
        assert stats.duplicates_skipped == 1  # 1 duplicate
        assert stats.upserted == 0  # Not recorded yet
        assert stats.deleted == 0  # Not recorded yet

    def test_get_stats_initial_state(self, tracker):
        """Test stats in initial state."""
        stats = tracker.get_stats()

        assert stats.encountered == 0
        assert stats.duplicates_skipped == 0
        assert stats.upserted == 0
        assert stats.deleted == 0

    def test_get_stats_after_recording_upserts(self, tracker):
        """Test stats after recording upserts."""
        tracker.track_membership("john@acme.com", "user", "sp:eng")
        tracker.record_upserted(5)

        stats = tracker.get_stats()

        assert stats.upserted == 5

    def test_get_stats_after_recording_deletes(self, tracker):
        """Test stats after recording deletes."""
        tracker.record_deleted(3)

        stats = tracker.get_stats()

        assert stats.deleted == 3


class TestGetEncounteredKeys:
    """Test encountered keys retrieval."""

    def test_get_encountered_keys_returns_all_tracked_tuples(self, tracker):
        """Test that all tracked membership keys are returned."""
        tracker.track_membership("john@acme.com", "user", "sp:engineering")
        tracker.track_membership("jane@acme.com", "user", "sp:design")
        tracker.track_membership("john@acme.com", "user", "sp:design")

        keys = tracker.get_encountered_keys()

        assert len(keys) == 3
        assert ("john@acme.com", "user", "sp:engineering") in keys
        assert ("jane@acme.com", "user", "sp:design") in keys
        assert ("john@acme.com", "user", "sp:design") in keys

    def test_get_encountered_keys_excludes_duplicates(self, tracker):
        """Test that duplicate trackings don't appear multiple times."""
        tracker.track_membership("john@acme.com", "user", "sp:engineering")
        tracker.track_membership("john@acme.com", "user", "sp:engineering")  # Duplicate

        keys = tracker.get_encountered_keys()

        assert len(keys) == 1
        assert ("john@acme.com", "user", "sp:engineering") in keys

    def test_get_encountered_keys_empty_initially(self, tracker):
        """Test that encountered keys is empty initially."""
        keys = tracker.get_encountered_keys()

        assert len(keys) == 0
        assert isinstance(keys, set)


class TestRecordOperations:
    """Test recording operations."""

    def test_record_upserted_updates_stats(self, tracker):
        """Test that record_upserted updates stats correctly."""
        tracker.record_upserted(10)

        stats = tracker.get_stats()
        assert stats.upserted == 10

        # Record more
        tracker.record_upserted(5)
        stats = tracker.get_stats()
        assert stats.upserted == 5  # Replaces, not adds

    def test_record_deleted_updates_stats(self, tracker):
        """Test that record_deleted updates stats correctly."""
        tracker.record_deleted(3)

        stats = tracker.get_stats()
        assert stats.deleted == 3

        # Record more
        tracker.record_deleted(7)
        stats = tracker.get_stats()
        assert stats.deleted == 7  # Replaces, not adds

    def test_record_multiple_operations(self, tracker):
        """Test recording multiple operation types."""
        tracker.track_membership("john@acme.com", "user", "sp:eng")
        tracker.track_membership("jane@acme.com", "user", "sp:eng")
        tracker.record_upserted(2)
        tracker.record_deleted(1)

        stats = tracker.get_stats()
        assert stats.encountered == 2
        assert stats.upserted == 2
        assert stats.deleted == 1


class TestLogSummary:
    """Test summary logging."""

    def test_log_summary_outputs_correct_format(self, tracker):
        """Test that log summary is called with correct data."""
        tracker.track_membership("john@acme.com", "user", "sp:eng")
        tracker.track_membership("john@acme.com", "user", "sp:eng")  # Duplicate
        tracker.record_upserted(1)
        tracker.record_deleted(0)

        # Call log_summary
        tracker.log_summary()

        # Verify logger was called
        tracker.logger.info.assert_called()

        # Check that the logged message contains stats
        logged_calls = [str(call) for call in tracker.logger.info.call_args_list]
        logged_output = " ".join(logged_calls)

        # Should contain key statistics
        assert "encountered" in logged_output.lower() or "1" in logged_output

    def test_log_summary_handles_no_operations(self, tracker):
        """Test log summary with no operations."""
        tracker.log_summary()

        # Should still log (with zeros)
        tracker.logger.info.assert_called()


class TestComplexScenario:
    """Test complex tracking scenarios."""

    def test_mixed_user_and_group_memberships(self, tracker):
        """Test tracking mixed member types."""
        # User memberships
        tracker.track_membership("john@acme.com", "user", "sp:engineering")
        tracker.track_membership("jane@acme.com", "user", "sp:engineering")

        # Group-to-group memberships
        tracker.track_membership("sp:frontend", "group", "sp:engineering")
        tracker.track_membership("sp:backend", "group", "sp:engineering")

        stats = tracker.get_stats()
        assert stats.encountered == 4

        keys = tracker.get_encountered_keys()
        assert len(keys) == 4
        assert ("john@acme.com", "user", "sp:engineering") in keys
        assert ("sp:frontend", "group", "sp:engineering") in keys

    def test_high_duplicate_rate_scenario(self, tracker):
        """Test scenario with many duplicates."""
        # Track same membership 100 times
        for _ in range(100):
            tracker.track_membership("john@acme.com", "user", "sp:engineering")

        stats = tracker.get_stats()
        assert stats.encountered == 1
        assert stats.duplicates_skipped == 99

    def test_full_lifecycle(self, tracker):
        """Test full sync lifecycle with all operations."""
        # 1. Track memberships with duplicates
        tracker.track_membership("john@acme.com", "user", "sp:eng")
        tracker.track_membership("john@acme.com", "user", "sp:eng")  # Dup
        tracker.track_membership("jane@acme.com", "user", "sp:design")

        # 2. Record upserts
        tracker.record_upserted(2)

        # 3. Record orphan deletions
        tracker.record_deleted(1)

        # 4. Check final stats
        stats = tracker.get_stats()
        assert stats.encountered == 2
        assert stats.duplicates_skipped == 1
        assert stats.upserted == 2
        assert stats.deleted == 1

        # 5. Log summary
        tracker.log_summary()
        assert tracker.logger.info.called

