"""Unit tests for webhook event types.

Tests the event type enumeration and conversion functions.
"""

import pytest

from airweave.core.shared_models import SyncJobStatus
from airweave.webhooks.constants.event_types import (
    EventType,
    event_type_from_sync_job_status,
)


class TestEventType:
    """Tests for EventType enumeration."""

    def test_event_type_values(self):
        """Test that EventType has correct string values."""
        assert EventType.SYNC_PENDING.value == "sync.pending"
        assert EventType.SYNC_RUNNING.value == "sync.running"
        assert EventType.SYNC_COMPLETED.value == "sync.completed"
        assert EventType.SYNC_FAILED.value == "sync.failed"
        assert EventType.SYNC_CANCELLED.value == "sync.cancelled"

    def test_event_type_is_string_enum(self):
        """Test that EventType values are strings."""
        for event_type in EventType:
            assert isinstance(event_type.value, str)
            # Should also be usable as string directly
            assert isinstance(event_type, str)

    def test_event_type_comparison(self):
        """Test that EventType can be compared with strings."""
        assert EventType.SYNC_COMPLETED == "sync.completed"
        assert EventType.SYNC_FAILED == "sync.failed"

    def test_all_event_types_exist(self):
        """Test that all expected event types exist."""
        expected_types = [
            "SYNC_PENDING",
            "SYNC_RUNNING",
            "SYNC_COMPLETED",
            "SYNC_FAILED",
            "SYNC_CANCELLED",
        ]
        actual_types = [e.name for e in EventType]
        assert set(expected_types) == set(actual_types)

    def test_event_type_count(self):
        """Test that we have exactly 5 event types."""
        assert len(EventType) == 5


class TestEventTypeFromSyncJobStatus:
    """Tests for event_type_from_sync_job_status function."""

    def test_pending_status_returns_pending_event(self):
        """Test PENDING status maps to sync.pending event."""
        result = event_type_from_sync_job_status(SyncJobStatus.PENDING)
        assert result == EventType.SYNC_PENDING

    def test_running_status_returns_running_event(self):
        """Test RUNNING status maps to sync.running event."""
        result = event_type_from_sync_job_status(SyncJobStatus.RUNNING)
        assert result == EventType.SYNC_RUNNING

    def test_completed_status_returns_completed_event(self):
        """Test COMPLETED status maps to sync.completed event."""
        result = event_type_from_sync_job_status(SyncJobStatus.COMPLETED)
        assert result == EventType.SYNC_COMPLETED

    def test_failed_status_returns_failed_event(self):
        """Test FAILED status maps to sync.failed event."""
        result = event_type_from_sync_job_status(SyncJobStatus.FAILED)
        assert result == EventType.SYNC_FAILED

    def test_cancelled_status_returns_cancelled_event(self):
        """Test CANCELLED status maps to sync.cancelled event."""
        result = event_type_from_sync_job_status(SyncJobStatus.CANCELLED)
        assert result == EventType.SYNC_CANCELLED

    def test_created_status_returns_none(self):
        """Test CREATED status returns None (no webhook)."""
        result = event_type_from_sync_job_status(SyncJobStatus.CREATED)
        assert result is None

    def test_cancelling_status_returns_none(self):
        """Test CANCELLING status returns None (no webhook)."""
        result = event_type_from_sync_job_status(SyncJobStatus.CANCELLING)
        assert result is None

    def test_all_mapped_statuses(self):
        """Test all statuses that should be mapped."""
        mapped_statuses = [
            (SyncJobStatus.PENDING, EventType.SYNC_PENDING),
            (SyncJobStatus.RUNNING, EventType.SYNC_RUNNING),
            (SyncJobStatus.COMPLETED, EventType.SYNC_COMPLETED),
            (SyncJobStatus.FAILED, EventType.SYNC_FAILED),
            (SyncJobStatus.CANCELLED, EventType.SYNC_CANCELLED),
        ]

        for status, expected_event in mapped_statuses:
            result = event_type_from_sync_job_status(status)
            assert result == expected_event, f"Expected {expected_event} for {status}"

    def test_all_unmapped_statuses(self):
        """Test all statuses that should NOT be mapped."""
        unmapped_statuses = [
            SyncJobStatus.CREATED,
            SyncJobStatus.CANCELLING,
        ]

        for status in unmapped_statuses:
            result = event_type_from_sync_job_status(status)
            assert result is None, f"Expected None for {status}, got {result}"

    def test_function_handles_all_sync_job_statuses(self):
        """Test that function handles every SyncJobStatus value."""
        # This ensures we don't miss any new status values added to SyncJobStatus
        for status in SyncJobStatus:
            # Should not raise
            result = event_type_from_sync_job_status(status)
            # Result should be either an EventType or None
            assert result is None or isinstance(result, EventType)


class TestEventTypeUsability:
    """Tests for EventType usability in various contexts."""

    def test_event_type_in_set(self):
        """Test that EventType can be used in sets."""
        event_set = {EventType.SYNC_COMPLETED, EventType.SYNC_FAILED}
        assert EventType.SYNC_COMPLETED in event_set
        assert EventType.SYNC_PENDING not in event_set

    def test_event_type_in_list(self):
        """Test that EventType can be used in lists."""
        event_list = [EventType.SYNC_COMPLETED, EventType.SYNC_FAILED]
        assert EventType.SYNC_COMPLETED in event_list

    def test_event_type_string_formatting(self):
        """Test that EventType value formats correctly in strings."""
        message = f"Event type: {EventType.SYNC_COMPLETED.value}"
        assert "sync.completed" in message

    def test_event_type_json_serializable(self):
        """Test that EventType value is JSON serializable."""
        import json

        data = {"event_type": EventType.SYNC_COMPLETED.value}
        json_str = json.dumps(data)
        assert "sync.completed" in json_str

    def test_event_type_from_string(self):
        """Test creating EventType from string value."""
        event = EventType("sync.completed")
        assert event == EventType.SYNC_COMPLETED

    def test_event_type_invalid_string_raises(self):
        """Test that invalid string raises ValueError."""
        with pytest.raises(ValueError):
            EventType("invalid.event")
