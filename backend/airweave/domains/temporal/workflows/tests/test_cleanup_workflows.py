"""Tests for CleanupStuckSyncJobsWorkflow and CleanupSyncDataWorkflow."""

import uuid

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from airweave.domains.temporal.workflows.cleanup_stuck_sync_jobs import (
    CleanupStuckSyncJobsWorkflow,
)
from airweave.domains.temporal.workflows.cleanup_sync_data import (
    CleanupSyncDataWorkflow,
)

from .conftest import (
    COLLECTION_ID,
    ORG_ID,
    SYNC_ID,
    ActivityRecorder,
    mock_cleanup_stuck_sync_jobs,
    mock_cleanup_sync_data,
)

TASK_QUEUE = "test-cleanup"


@pytest.mark.unit
async def test_cleanup_stuck_sync_jobs_calls_activity():
    recorder = ActivityRecorder()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[CleanupStuckSyncJobsWorkflow],
            activities=[mock_cleanup_stuck_sync_jobs(recorder)],
        ):
            await env.client.execute_workflow(
                CleanupStuckSyncJobsWorkflow.run,
                id=f"test-cleanup-stuck-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )

    assert recorder.called("cleanup_stuck")
    assert recorder.call_count("cleanup_stuck") == 1


@pytest.mark.unit
async def test_cleanup_sync_data_calls_activity_and_returns_result():
    recorder = ActivityRecorder()
    expected = {"cleaned": 2, "errors": []}

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[CleanupSyncDataWorkflow],
            activities=[mock_cleanup_sync_data(recorder, return_value=expected)],
        ):
            result = await env.client.execute_workflow(
                CleanupSyncDataWorkflow.run,
                args=[[SYNC_ID, "another-sync-id"], COLLECTION_ID, ORG_ID],
                id=f"test-cleanup-data-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )

    assert recorder.called("cleanup_sync_data")
    assert result == expected
