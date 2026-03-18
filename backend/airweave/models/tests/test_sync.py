from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy import create_engine, text

import airweave.models.sync as sync_model


@dataclass(frozen=True)
class _Target:
    id: str


def test_cancel_running_jobs_before_sync_delete_transitions_running_job_to_cancelling_without_warning(
    monkeypatch: pytest.MonkeyPatch,
):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    target = _Target(id="sync-123")
    job_id = "job-1"
    warnings: list[str] = []
    infos: list[str] = []

    class _FakeLogger:
        def warning(self, message: str):
            warnings.append(message)

        def info(self, message: str):
            infos.append(message)

        def debug(self, message: str):
            return None

    monkeypatch.setattr(sync_model, "logger", _FakeLogger())

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE sync_job (
                    id TEXT PRIMARY KEY,
                    sync_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO sync_job (id, sync_id, status, created_at, updated_at)
                VALUES (:id, :sync_id, :status, CURRENT_TIMESTAMP, NULL)
                """
            ),
            {"id": job_id, "sync_id": target.id, "status": "running"},
        )

        sync_model.cancel_running_jobs_before_sync_delete(
            mapper=None,
            connection=connection,
            target=target,
        )

        status = connection.execute(
            text("SELECT status FROM sync_job WHERE id = :id"),
            {"id": job_id},
        ).scalar_one()

    assert status == "cancelling"
    assert warnings == []
    assert any(f"Cancelling job {job_id} for sync {target.id} before deletion" in m for m in infos)
