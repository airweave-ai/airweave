"""Tests for compute_status with NEEDS_REAUTH / PAUSED derivation."""

from types import SimpleNamespace

from airweave.core.shared_models import SourceConnectionStatus, SyncJobStatus, SyncStatus
from airweave.schemas.source_connection import compute_status


def test_needs_reauth_when_failed_with_error_category():
    """FAILED job + error_category → NEEDS_REAUTH."""
    source_conn = SimpleNamespace(
        is_authenticated=True,
        is_active=True,
    )
    status = compute_status(source_conn, SyncJobStatus.FAILED, "oauth_credentials_expired")
    assert status == SourceConnectionStatus.NEEDS_REAUTH


def test_error_when_failed_without_error_category():
    """FAILED job without error_category → ERROR."""
    source_conn = SimpleNamespace(
        is_authenticated=True,
        is_active=True,
    )
    status = compute_status(source_conn, SyncJobStatus.FAILED)
    assert status == SourceConnectionStatus.ERROR


def test_active_when_completed():
    """COMPLETED job → ACTIVE."""
    source_conn = SimpleNamespace(
        is_authenticated=True,
        is_active=True,
    )
    status = compute_status(source_conn, SyncJobStatus.COMPLETED)
    assert status == SourceConnectionStatus.ACTIVE


def test_syncing_when_running():
    """RUNNING job → SYNCING."""
    source_conn = SimpleNamespace(
        is_authenticated=True,
        is_active=True,
    )
    status = compute_status(source_conn, SyncJobStatus.RUNNING)
    assert status == SourceConnectionStatus.SYNCING


def test_pending_auth_when_not_authenticated():
    """Not authenticated → PENDING_AUTH regardless of job status."""
    source_conn = SimpleNamespace(is_authenticated=False)
    status = compute_status(source_conn, SyncJobStatus.FAILED)
    assert status == SourceConnectionStatus.PENDING_AUTH


def test_paused_when_sync_status_paused():
    """sync_status=PAUSED → PAUSED, even if job is running."""
    source_conn = SimpleNamespace(is_authenticated=True, is_active=True)
    status = compute_status(
        source_conn, SyncJobStatus.RUNNING, None, sync_status=SyncStatus.PAUSED
    )
    assert status == SourceConnectionStatus.PAUSED


def test_pending_auth_trumps_paused():
    """PENDING_AUTH takes priority over PAUSED."""
    source_conn = SimpleNamespace(is_authenticated=False, is_active=True)
    status = compute_status(
        source_conn, None, None, sync_status=SyncStatus.PAUSED
    )
    assert status == SourceConnectionStatus.PENDING_AUTH


def test_paused_trumps_inactive():
    """PAUSED takes priority over INACTIVE."""
    source_conn = SimpleNamespace(is_authenticated=True, is_active=False)
    status = compute_status(
        source_conn, None, None, sync_status=SyncStatus.PAUSED
    )
    assert status == SourceConnectionStatus.PAUSED


def test_active_sync_status_does_not_override_job_status():
    """sync_status=ACTIVE is a no-op — job status still drives SYNCING."""
    source_conn = SimpleNamespace(is_authenticated=True, is_active=True)
    status = compute_status(
        source_conn, SyncJobStatus.RUNNING, None, sync_status=SyncStatus.ACTIVE
    )
    assert status == SourceConnectionStatus.SYNCING


# ---------------------------------------------------------------------------
# SourceConnectionListItem.status computed field
# ---------------------------------------------------------------------------


def test_list_item_needs_reauth_status():
    """SourceConnectionListItem computed status returns NEEDS_REAUTH when error_category set."""
    from datetime import datetime, timezone

    from airweave.schemas.source_connection import SourceConnectionListItem

    now = datetime.now(timezone.utc)
    item = SourceConnectionListItem(
        id="550e8400-e29b-41d4-a716-446655440000",
        name="Test",
        short_name="github",
        readable_collection_id="col-123",
        created_at=now,
        modified_at=now,
        is_authenticated=True,
        entity_count=0,
        federated_search=False,
        is_active=True,
        last_job_status="failed",
        last_job_error_category="api_key_invalid",
    )
    assert item.status == SourceConnectionStatus.NEEDS_REAUTH


def test_list_item_error_status_without_error_category():
    """SourceConnectionListItem computed status returns ERROR when no error_category."""
    from datetime import datetime, timezone

    from airweave.schemas.source_connection import SourceConnectionListItem

    now = datetime.now(timezone.utc)
    item = SourceConnectionListItem(
        id="550e8400-e29b-41d4-a716-446655440000",
        name="Test",
        short_name="github",
        readable_collection_id="col-123",
        created_at=now,
        modified_at=now,
        is_authenticated=True,
        entity_count=0,
        federated_search=False,
        is_active=True,
        last_job_status="failed",
        last_job_error_category=None,
    )
    assert item.status == SourceConnectionStatus.ERROR


def test_list_item_paused_when_sync_status_paused():
    """SourceConnectionListItem returns PAUSED when sync_status is PAUSED."""
    from datetime import datetime, timezone

    from airweave.schemas.source_connection import SourceConnectionListItem

    now = datetime.now(timezone.utc)
    item = SourceConnectionListItem(
        id="550e8400-e29b-41d4-a716-446655440000",
        name="Test",
        short_name="github",
        readable_collection_id="col-123",
        created_at=now,
        modified_at=now,
        is_authenticated=True,
        entity_count=0,
        federated_search=False,
        is_active=True,
        last_job_status="completed",
        sync_status=SyncStatus.PAUSED,
    )
    assert item.status == SourceConnectionStatus.PAUSED
