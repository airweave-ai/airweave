"""Shared fixtures and mock activity factories for workflow tests."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest
from temporalio import activity

from airweave.domains.temporal.activity_results import CreateSyncJobResult

# ---------------------------------------------------------------------------
# Shared test constants
# ---------------------------------------------------------------------------

ORG_ID = "00000000-0000-0000-0000-000000000001"
SYNC_ID = "00000000-0000-0000-0000-000000000010"
SYNC_JOB_ID = "00000000-0000-0000-0000-000000000020"
COLLECTION_ID = "00000000-0000-0000-0000-000000000030"
CONNECTION_ID = "00000000-0000-0000-0000-000000000040"

# ---------------------------------------------------------------------------
# Dict builders
# ---------------------------------------------------------------------------


def make_ctx_dict(org_id: str = ORG_ID) -> dict:
    return {
        "organization": {
            "id": org_id,
            "name": "Test Org",
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
            "modified_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        }
    }


def make_sync_dict(sync_id: str = SYNC_ID) -> dict:
    return {
        "id": sync_id,
        "name": "test-sync",
        "source_connection_id": CONNECTION_ID,
        "destination_connection_ids": [CONNECTION_ID],
        "organization_id": ORG_ID,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "modified_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "cron_schedule": None,
        "sync_config": None,
    }


def make_sync_job_dict(sync_job_id: str = SYNC_JOB_ID) -> dict:
    return {
        "id": sync_job_id,
        "sync_id": SYNC_ID,
        "status": "PENDING",
        "organization_id": ORG_ID,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "modified_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
        "error": None,
        "entity_count": 0,
    }


def make_collection_dict(collection_id: str = COLLECTION_ID) -> dict:
    return {
        "id": collection_id,
        "name": "test-collection",
        "readable_id": "test-collection",
        "organization_id": ORG_ID,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "modified_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
    }


def make_connection_dict(connection_id: str = CONNECTION_ID) -> dict:
    return {
        "id": connection_id,
        "name": "test-connection",
        "short_name": "test_source",
        "organization_id": ORG_ID,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "modified_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Activity call recorder
# ---------------------------------------------------------------------------


class ActivityRecorder:
    """Records mock activity invocations for assertion."""

    def __init__(self) -> None:
        self.calls: List[tuple[str, tuple]] = []

    def record(self, name: str, args: tuple) -> None:
        self.calls.append((name, args))

    def called(self, name: str) -> bool:
        return any(n == name for n, _ in self.calls)

    def call_count(self, name: str) -> int:
        return sum(1 for n, _ in self.calls if n == name)


@pytest.fixture
def recorder():
    return ActivityRecorder()


# ---------------------------------------------------------------------------
# Mock activity factories
# ---------------------------------------------------------------------------


def mock_create_sync_job(
    recorder: ActivityRecorder,
    return_value: Optional[CreateSyncJobResult] = None,
    raise_error: Optional[Exception] = None,
):
    if return_value is None:
        return_value = CreateSyncJobResult(sync_job_dict=make_sync_job_dict())

    @activity.defn(name="create_sync_job_activity")
    async def _mock(
        sync_id: str,
        ctx_dict: Dict[str, Any],
        force_full_sync: bool = False,
    ) -> CreateSyncJobResult:
        recorder.record("create_sync_job", (sync_id, force_full_sync))
        if raise_error:
            raise raise_error
        return return_value

    return _mock


def mock_run_sync(
    recorder: ActivityRecorder,
    raise_error: Optional[Exception] = None,
):
    @activity.defn(name="run_sync_activity")
    async def _mock(
        sync_dict: Dict[str, Any],
        sync_job_dict: Dict[str, Any],
        collection_dict: Dict[str, Any],
        connection_dict: Dict[str, Any],
        ctx_dict: Dict[str, Any],
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> None:
        recorder.record("run_sync", (sync_dict["id"],))
        if raise_error:
            raise raise_error

    return _mock


def mock_self_destruct(recorder: ActivityRecorder):
    @activity.defn(name="self_destruct_orphaned_sync_activity")
    async def _mock(
        sync_id: str,
        ctx_dict: Dict[str, Any],
        reason: str = "Resource not found",
    ) -> Dict[str, Any]:
        recorder.record("self_destruct", (sync_id, reason))
        return {"sync_id": sync_id, "reason": reason}

    return _mock


def mock_mark_cancelled(recorder: ActivityRecorder):
    @activity.defn(name="mark_sync_job_cancelled_activity")
    async def _mock(
        sync_job_id: str,
        ctx_dict: Dict[str, Any],
        reason: Optional[str] = None,
        when_iso: Optional[str] = None,
    ) -> None:
        recorder.record("mark_cancelled", (sync_job_id,))

    return _mock


def mock_transition_sync_job(recorder: ActivityRecorder):
    @activity.defn(name="transition_sync_job_activity")
    async def _mock(
        transition: str,
        sync_job_id: str,
        ctx_dict: Dict[str, Any],
        lifecycle_data: Dict[str, Any],
        error: Optional[str] = None,
        stats_dict: Optional[Dict[str, Any]] = None,
        timestamp_iso: Optional[str] = None,
    ) -> None:
        recorder.record(f"transition_{transition}", (sync_job_id,))

    return _mock


def mock_cleanup_stuck_sync_jobs(recorder: ActivityRecorder):
    @activity.defn(name="cleanup_stuck_sync_jobs_activity")
    async def _mock() -> None:
        recorder.record("cleanup_stuck", ())

    return _mock


def mock_cleanup_sync_data(
    recorder: ActivityRecorder,
    return_value: Optional[Dict[str, Any]] = None,
):
    @activity.defn(name="cleanup_sync_data_activity")
    async def _mock(
        sync_ids: list[str],
        collection_id: str,
        organization_id: str,
    ) -> Dict[str, Any]:
        recorder.record("cleanup_sync_data", (sync_ids, collection_id, organization_id))
        return return_value or {"cleaned": len(sync_ids)}

    return _mock
