from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from sqlalchemy import text

import airweave.models.sync as sync_model


@dataclass(frozen=True)
class _Target:
    id: str


def test_before_delete_transitions_running_job_to_cancelling(
    sync_job_db, quiet_logger
):
    target = _Target(id="sync-123")
    job_id = "job-1"

    sync_job_db.execute(
        text(
            "INSERT INTO sync_job (id, sync_id, status, created_at)"
            " VALUES (:id, :sync_id, :status, CURRENT_TIMESTAMP)"
        ),
        {"id": job_id, "sync_id": target.id, "status": "running"},
    )

    sync_model.cancel_running_jobs_before_sync_delete(
        mapper=None,
        connection=sync_job_db,
        target=target,
    )

    status = sync_job_db.execute(
        text("SELECT status FROM sync_job WHERE id = :id"),
        {"id": job_id},
    ).scalar_one()

    assert status == "cancelling"
    assert quiet_logger.warnings == []
    assert any(
        f"Cancelling job {job_id} for sync {target.id} before deletion" in m
        for m in quiet_logger.infos
    )


def test_after_delete_calls_cleanup_temporal_schedules():
    target = _Target(id="sync-456")

    with patch.object(sync_model, "cleanup_temporal_schedules") as mock_cleanup:
        sync_model.delete_temporal_schedules_after_sync_delete(
            mapper=None,
            connection=None,
            target=target,
        )

    mock_cleanup.assert_called_once_with(target.id)
