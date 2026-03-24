"""Coverage tests for RunSourceConnectionWorkflow — cancellation and edge cases."""

import uuid

import pytest
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from airweave.domains.temporal.workflows.run_source_connection import (
    RunSourceConnectionWorkflow,
)

from .conftest import (
    SYNC_ID,
    ActivityRecorder,
    make_collection_dict,
    make_connection_dict,
    make_ctx_dict,
    make_sync_dict,
    make_sync_job_dict,
    mock_run_sync,
    mock_self_destruct,
    mock_transition_sync_job,
)

TASK_QUEUE = "test-rsc-coverage"


async def _run_workflow(
    env: WorkflowEnvironment,
    activities: list,
    sync_dict: dict | None = None,
    sync_job_dict: dict | None = None,
    **kwargs,
) -> str:
    """Run the workflow and return the workflow handle ID."""
    wf_id = f"test-wf-{uuid.uuid4()}"
    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[RunSourceConnectionWorkflow],
        activities=activities,
    ):
        await env.client.execute_workflow(
            RunSourceConnectionWorkflow.run,
            args=[
                sync_dict or make_sync_dict(),
                sync_job_dict,
                make_collection_dict(),
                make_connection_dict(),
                make_ctx_dict(),
                None,
                False,
            ],
            id=wf_id,
            task_queue=TASK_QUEUE,
        )
    return wf_id


# ── _is_orphaned_sync_error() ─────────────────────────────────────


@pytest.mark.unit
def test_is_orphaned_sync_error_non_activity_error():
    result = RunSourceConnectionWorkflow._is_orphaned_sync_error(RuntimeError("nope"))
    assert result is False


@pytest.mark.unit
def test_is_orphaned_sync_error_non_app_error_cause():
    from temporalio.exceptions import ActivityError

    err = ActivityError(
        message="fail",
        scheduled_event_id=1,
        started_event_id=2,
        identity="test-worker",
        retry_state=None,
        activity_id="act-1",
        activity_type="run_sync_activity",
    )
    err.__cause__ = RuntimeError("not ApplicationError")
    result = RunSourceConnectionWorkflow._is_orphaned_sync_error(err)
    assert result is False


# ── _extract_orphaned_reason() ────────────────────────────────────


@pytest.mark.unit
def test_extract_orphaned_reason_fallback():
    err = RuntimeError("some error string")
    result = RunSourceConnectionWorkflow._extract_orphaned_reason(err)
    assert result == "some error string"


# ── Self-destruct error recovery ──────────────────────────────────


@pytest.mark.unit
async def test_self_destruct_cleanup_error_still_completes():
    """When self_destruct_orphaned_sync_activity raises, workflow still completes gracefully."""
    from typing import Any, Dict

    from temporalio import activity

    from airweave.domains.temporal.activity_results import CreateSyncJobResult

    recorder = ActivityRecorder()

    @activity.defn(name="create_sync_job_activity")
    async def create_orphan(
        sync_id: str, ctx_dict: Dict[str, Any], force_full_sync: bool = False
    ) -> CreateSyncJobResult:
        recorder.record("create_sync_job", (sync_id,))
        return CreateSyncJobResult(
            orphaned=True, sync_id=sync_id, reason="Sync gone"
        )

    @activity.defn(name="self_destruct_orphaned_sync_activity")
    async def failing_destruct(
        sync_id: str, ctx_dict: Dict[str, Any], reason: str = ""
    ) -> Dict[str, Any]:
        recorder.record("self_destruct", (sync_id,))
        raise RuntimeError("cleanup failed!")

    async with await WorkflowEnvironment.start_time_skipping() as env:
        await _run_workflow(
            env,
            activities=[
                create_orphan,
                mock_run_sync(recorder),
                failing_destruct,
                mock_transition_sync_job(recorder),
            ],
            sync_job_dict=None,
        )

    assert recorder.called("self_destruct")
    assert not recorder.called("run_sync")


# ── Transition failure path ──────────────────────────────────────


@pytest.mark.unit
async def test_transition_failure_is_tolerated():
    """When transition_sync_job_activity raises, workflow still propagates the original error."""
    from typing import Any, Dict, Optional

    from temporalio import activity

    recorder = ActivityRecorder()

    @activity.defn(name="transition_sync_job_activity")
    async def failing_transition(
        transition: str,
        sync_job_id: str,
        ctx_dict: Dict[str, Any],
        lifecycle_data: Dict[str, Any],
        error: Optional[str] = None,
        stats_dict: Optional[Dict[str, Any]] = None,
        timestamp_iso: Optional[str] = None,
    ) -> None:
        recorder.record(f"transition_{transition}", (sync_job_id,))
        raise RuntimeError("transition activity exploded")

    async with await WorkflowEnvironment.start_time_skipping() as env:
        with pytest.raises(WorkflowFailureError):
            await _run_workflow(
                env,
                activities=[
                    mock_run_sync(recorder, raise_error=RuntimeError("sync broke")),
                    mock_self_destruct(recorder),
                    failing_transition,
                ],
                sync_job_dict=make_sync_job_dict(),
            )

    assert recorder.called("transition_failed")
