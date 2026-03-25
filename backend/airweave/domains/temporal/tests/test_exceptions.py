"""Tests for Temporal domain exceptions."""

import pytest

from airweave.domains.temporal.exceptions import (
    InvalidCronExpressionError,
    OrphanedSyncError,
)


@pytest.mark.unit
def test_orphaned_sync_error_init():
    err = OrphanedSyncError("sync-123")
    assert err.sync_id == "sync-123"
    assert err.reason == "Source connection not found"
    assert "Orphaned sync sync-123" in str(err)


@pytest.mark.unit
def test_orphaned_sync_error_custom_reason():
    err = OrphanedSyncError("sync-456", reason="Deleted during execution")
    assert err.sync_id == "sync-456"
    assert err.reason == "Deleted during execution"
    assert "Deleted during execution" in str(err)
