"""Tests for sync helper functions: cancel_running_sync_jobs, cleanup_temporal_schedules."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy import text

from airweave.core.shared_models import SyncJobStatus
from airweave.models.sync import (
    cancel_running_sync_jobs,
    cleanup_temporal_schedules,
)

# ---------------------------------------------------------------------------
# cancel_running_sync_jobs
# ---------------------------------------------------------------------------


def test_cancel_no_running_jobs(sync_job_db):
    sync_id = uuid4()

    cancel_running_sync_jobs(sync_job_db, sync_id)

    count = sync_job_db.execute(text("SELECT count(*) FROM sync_job")).scalar_one()
    assert count == 0


def test_cancel_single_running_job(sync_job_db, quiet_logger):
    sync_id = uuid4()
    job_id = uuid4()

    sync_job_db.execute(
        text(
            "INSERT INTO sync_job (id, sync_id, status, created_at)"
            " VALUES (:id, :sync_id, :status, CURRENT_TIMESTAMP)"
        ),
        {"id": str(job_id), "sync_id": str(sync_id), "status": "running"},
    )

    cancel_running_sync_jobs(sync_job_db, sync_id)

    status = sync_job_db.execute(
        text("SELECT status FROM sync_job WHERE id = :id"),
        {"id": str(job_id)},
    ).scalar_one()
    assert status == SyncJobStatus.CANCELLING.value
    assert quiet_logger.warnings == []


def test_cancel_multiple_running_jobs(sync_job_db):
    sync_id = uuid4()
    job_ids = [uuid4(), uuid4()]

    for jid in job_ids:
        sync_job_db.execute(
            text(
                "INSERT INTO sync_job (id, sync_id, status, created_at)"
                " VALUES (:id, :sync_id, :status, CURRENT_TIMESTAMP)"
            ),
            {"id": str(jid), "sync_id": str(sync_id), "status": "running"},
        )

    cancel_running_sync_jobs(sync_job_db, sync_id)

    rows = sync_job_db.execute(
        text("SELECT status FROM sync_job WHERE sync_id = :sync_id"),
        {"sync_id": str(sync_id)},
    ).fetchall()
    assert all(row[0] == SyncJobStatus.CANCELLING.value for row in rows)


def test_cancel_exception_is_swallowed():
    conn = MagicMock()
    conn.execute.side_effect = RuntimeError("db gone")
    sync_id = uuid4()

    # Must not propagate.
    cancel_running_sync_jobs(conn, sync_id)


# ---------------------------------------------------------------------------
# cleanup_temporal_schedules
# ---------------------------------------------------------------------------


def test_cleanup_temporal_schedules_happy_path():
    sync_id = uuid4()
    mock_svc = AsyncMock()
    mock_container_instance = MagicMock()
    mock_container_instance.temporal_schedule_service = mock_svc

    with patch("airweave.core.container.container", mock_container_instance):
        cleanup_temporal_schedules(sync_id)

    expected_ids = [
        f"sync-{sync_id}",
        f"minute-sync-{sync_id}",
        f"daily-cleanup-{sync_id}",
    ]
    assert mock_svc.delete_schedule_handle.await_count == 3
    actual_ids = [
        call.args[0]
        for call in mock_svc.delete_schedule_handle.await_args_list
    ]
    assert actual_ids == expected_ids


def test_cleanup_temporal_schedules_exception_is_swallowed():
    sync_id = uuid4()

    with patch("airweave.core.container.container", None):
        # Must not propagate.
        cleanup_temporal_schedules(sync_id)


# ---------------------------------------------------------------------------
# _cancel_workflow coverage (lines 93-99)
# ---------------------------------------------------------------------------


def test_cancel_workflow_success_path(sync_job_db, quiet_logger):
    """Temporal cancel succeeds — covers lines 93, 95-97."""
    sync_id = uuid4()
    job_id = uuid4()

    sync_job_db.execute(
        text(
            "INSERT INTO sync_job (id, sync_id, status, created_at)"
            " VALUES (:id, :sync_id, :status, CURRENT_TIMESTAMP)"
        ),
        {"id": str(job_id), "sync_id": str(sync_id), "status": "running"},
    )

    mock_handle = AsyncMock()
    mock_client = MagicMock()
    mock_client.get_workflow_handle.return_value = mock_handle

    with patch(
        "airweave.models.sync.temporal_client.get_client",
        new=AsyncMock(return_value=mock_client),
    ):
        cancel_running_sync_jobs(sync_job_db, sync_id)

    mock_handle.cancel.assert_awaited_once()
    assert any("Requested Temporal cancellation" in m for m in quiet_logger.infos)


def test_cancel_workflow_exception_path(sync_job_db, quiet_logger):
    """Temporal cancel raises — covers lines 93, 98-99."""
    sync_id = uuid4()
    job_id = uuid4()

    sync_job_db.execute(
        text(
            "INSERT INTO sync_job (id, sync_id, status, created_at)"
            " VALUES (:id, :sync_id, :status, CURRENT_TIMESTAMP)"
        ),
        {"id": str(job_id), "sync_id": str(sync_id), "status": "running"},
    )

    mock_handle = AsyncMock()
    mock_handle.cancel.side_effect = RuntimeError("temporal down")
    mock_client = MagicMock()
    mock_client.get_workflow_handle.return_value = mock_handle

    with patch(
        "airweave.models.sync.temporal_client.get_client",
        new=AsyncMock(return_value=mock_client),
    ):
        cancel_running_sync_jobs(sync_job_db, sync_id)

    assert any("Could not cancel Temporal workflow" in m for m in quiet_logger.debugs)


# ---------------------------------------------------------------------------
# cleanup_temporal_schedules outer exception (line 175)
# ---------------------------------------------------------------------------


def test_cleanup_temporal_schedules_outer_exception(quiet_logger):
    """delete_schedule_handle raises — exception caught at line 174-175."""
    sync_id = uuid4()
    mock_svc = AsyncMock()
    mock_svc.delete_schedule_handle.side_effect = RuntimeError("boom")
    mock_container_instance = MagicMock()
    mock_container_instance.temporal_schedule_service = mock_svc

    with patch("airweave.core.container.container", mock_container_instance):
        cleanup_temporal_schedules(sync_id)

    assert any("Could not schedule Temporal cleanup" in m for m in quiet_logger.infos)
