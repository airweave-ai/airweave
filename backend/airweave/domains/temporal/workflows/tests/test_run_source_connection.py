"""Tests for RunSourceConnectionWorkflow."""

import uuid

import pytest
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
    mock_create_sync_job,
    mock_run_sync,
    mock_self_destruct,
    mock_transition_sync_job,
)

TASK_QUEUE = "test-run-source-connection"


async def _run_workflow(
    env: WorkflowEnvironment,
    activities: list,
    sync_dict: dict | None = None,
    sync_job_dict: dict | None = None,
    collection_dict: dict | None = None,
    connection_dict: dict | None = None,
    ctx_dict: dict | None = None,
    access_token: str | None = None,
    force_full_sync: bool = False,
) -> None:
    """Start a worker and execute the workflow in the test environment."""
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
                collection_dict or make_collection_dict(),
                connection_dict or make_connection_dict(),
                ctx_dict or make_ctx_dict(),
                access_token,
                force_full_sync,
            ],
            id=f"test-wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )


# ------------------------------------------------------------------
# Happy path
# ------------------------------------------------------------------


@pytest.mark.unit
async def test_happy_path_with_provided_sync_job():
    """When sync_job_dict is provided, skip create and go straight to run_sync."""
    recorder = ActivityRecorder()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        await _run_workflow(
            env,
            activities=[
                mock_run_sync(recorder),
                mock_self_destruct(recorder),
                mock_transition_sync_job(recorder),
            ],
            sync_job_dict=make_sync_job_dict(),
        )

    assert recorder.called("run_sync")
    assert not recorder.called("create_sync_job")
    assert recorder.called("transition_completed")


@pytest.mark.unit
async def test_scheduled_run_creates_sync_job_then_executes():
    """When sync_job_dict is None (scheduled run), create job first, then run sync."""
    recorder = ActivityRecorder()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        await _run_workflow(
            env,
            activities=[
                mock_create_sync_job(recorder),
                mock_run_sync(recorder),
                mock_self_destruct(recorder),
                mock_transition_sync_job(recorder),
            ],
            sync_job_dict=None,
        )

    assert recorder.called("create_sync_job")
    assert recorder.called("run_sync")
    assert recorder.called("transition_completed")


# ------------------------------------------------------------------
# Phase 1: ensure sync job edge cases
# ------------------------------------------------------------------


@pytest.mark.unit
async def test_skips_when_sync_job_already_running():
    """When create_sync_job returns skipped, workflow exits without running sync."""
    from airweave.domains.temporal.activity_results import CreateSyncJobResult

    recorder = ActivityRecorder()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        await _run_workflow(
            env,
            activities=[
                mock_create_sync_job(
                    recorder,
                    return_value=CreateSyncJobResult(
                        skipped=True, reason="Already has 1 running job(s)"
                    ),
                ),
                mock_run_sync(recorder),
                mock_self_destruct(recorder),
                mock_transition_sync_job(recorder),
            ],
            sync_job_dict=None,
        )

    assert recorder.called("create_sync_job")
    assert not recorder.called("run_sync")


@pytest.mark.unit
async def test_skips_when_create_sync_job_raises():
    """When create_sync_job activity fails, workflow exits gracefully."""
    recorder = ActivityRecorder()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        await _run_workflow(
            env,
            activities=[
                mock_create_sync_job(recorder, raise_error=RuntimeError("db down")),
                mock_run_sync(recorder),
                mock_self_destruct(recorder),
                mock_transition_sync_job(recorder),
            ],
            sync_job_dict=None,
        )

    assert not recorder.called("run_sync")


# ------------------------------------------------------------------
# Phase 2: orphan detection
# ------------------------------------------------------------------


@pytest.mark.unit
async def test_orphaned_sync_triggers_self_destruct():
    """When create_sync_job returns orphaned, workflow self-destructs."""
    from airweave.domains.temporal.activity_results import CreateSyncJobResult

    recorder = ActivityRecorder()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        await _run_workflow(
            env,
            activities=[
                mock_create_sync_job(
                    recorder,
                    return_value=CreateSyncJobResult(
                        orphaned=True, sync_id=SYNC_ID, reason="Sync gone"
                    ),
                ),
                mock_run_sync(recorder),
                mock_self_destruct(recorder),
                mock_transition_sync_job(recorder),
            ],
            sync_job_dict=None,
        )

    assert recorder.called("self_destruct")
    assert not recorder.called("run_sync")


# ------------------------------------------------------------------
# Phase 4: failure routing
# ------------------------------------------------------------------


@pytest.mark.unit
async def test_orphaned_sync_error_during_execution_triggers_self_destruct():
    """When run_sync raises an orphaned-sync ApplicationError, workflow self-destructs."""
    from temporalio.exceptions import ApplicationError, ApplicationErrorCategory

    from airweave.domains.temporal.exceptions import ORPHANED_SYNC_ERROR_TYPE

    recorder = ActivityRecorder()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        await _run_workflow(
            env,
            activities=[
                mock_run_sync(
                    recorder,
                    raise_error=ApplicationError(
                        f"Orphaned sync {SYNC_ID}: Source connection not found",
                        SYNC_ID,
                        "Source connection not found",
                        type=ORPHANED_SYNC_ERROR_TYPE,
                        non_retryable=True,
                        category=ApplicationErrorCategory.BENIGN,
                    ),
                ),
                mock_self_destruct(recorder),
                mock_transition_sync_job(recorder),
            ],
            sync_job_dict=make_sync_job_dict(),
        )

    assert recorder.called("self_destruct")
    assert not recorder.called("transition_failed")


@pytest.mark.unit
async def test_non_orphan_sync_error_propagates():
    """When run_sync raises a non-orphan error, workflow transitions to failed and re-raises."""
    from temporalio.client import WorkflowFailureError

    recorder = ActivityRecorder()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        with pytest.raises(WorkflowFailureError) as exc_info:
            await _run_workflow(
                env,
                activities=[
                    mock_run_sync(recorder, raise_error=RuntimeError("Something broke")),
                    mock_self_destruct(recorder),
                    mock_transition_sync_job(recorder),
                ],
                sync_job_dict=make_sync_job_dict(),
            )

    cause = exc_info.value.__cause__
    root_message = str(cause.__cause__) if cause and cause.__cause__ else str(cause)
    assert "Something broke" in root_message
    assert not recorder.called("self_destruct")
    assert recorder.called("transition_failed")
