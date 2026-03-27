"""Tests for APIKeyMaintenanceWorkflow.

Verifies activity ordering and result aggregation using Temporal's
WorkflowEnvironment test harness.
"""

import uuid
from typing import Dict

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from airweave.domains.temporal.workflows.api_key_maintenance import (
    APIKeyMaintenanceWorkflow,
)

TASK_QUEUE = "test-api-key-maintenance"


class ActivityRecorder:
    """Records mock activity invocations for assertion."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def record(self, name: str) -> None:
        self.calls.append(name)


def mock_check_and_notify(recorder: ActivityRecorder, return_value: Dict[str, int]):
    @activity.defn(name="check_and_notify_expiring_keys_activity")
    async def _mock() -> Dict[str, int]:
        recorder.record("notify")
        return return_value

    return _mock


def mock_expire(recorder: ActivityRecorder, return_value: Dict[str, int]):
    @activity.defn(name="expire_past_due_keys_activity")
    async def _mock() -> Dict[str, int]:
        recorder.record("expire")
        return return_value

    return _mock


def mock_cleanup_revoked(recorder: ActivityRecorder, return_value: Dict[str, int]):
    @activity.defn(name="cleanup_revoked_keys_activity")
    async def _mock() -> Dict[str, int]:
        recorder.record("cleanup_revoked")
        return return_value

    return _mock


def mock_prune(recorder: ActivityRecorder, return_value: Dict[str, int]):
    @activity.defn(name="prune_usage_log_activity")
    async def _mock() -> Dict[str, int]:
        recorder.record("prune")
        return return_value

    return _mock


@pytest.mark.unit
async def test_activity_ordering():
    """Activities run in notify → expire → cleanup → prune order."""
    recorder = ActivityRecorder()

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[APIKeyMaintenanceWorkflow],
            activities=[
                mock_check_and_notify(
                    recorder,
                    {"14_days": 1, "3_days": 0, "expired": 0, "errors": 0},
                ),
                mock_expire(recorder, {"expired": 2}),
                mock_cleanup_revoked(recorder, {"deleted": 3, "errors": 0}),
                mock_prune(recorder, {"pruned": 100}),
            ],
        ):
            await env.client.execute_workflow(
                APIKeyMaintenanceWorkflow.run,
                id=f"test-maint-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )

    assert recorder.calls == ["notify", "expire", "cleanup_revoked", "prune"]


@pytest.mark.unit
async def test_result_aggregation():
    """Workflow merges counts from all four activities."""
    recorder = ActivityRecorder()
    notify_result = {"14_days": 2, "3_days": 1, "expired": 0, "errors": 0}
    expire_result = {"expired": 5}
    revoked_result = {"deleted": 3, "errors": 1}
    prune_result = {"pruned": 42}

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[APIKeyMaintenanceWorkflow],
            activities=[
                mock_check_and_notify(recorder, notify_result),
                mock_expire(recorder, expire_result),
                mock_cleanup_revoked(recorder, revoked_result),
                mock_prune(recorder, prune_result),
            ],
        ):
            result = await env.client.execute_workflow(
                APIKeyMaintenanceWorkflow.run,
                id=f"test-maint-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )

    assert result == {
        "14_days": 2,
        "3_days": 1,
        "expired": 5,
        "errors": 0,
        "deleted": 3,
        "delete_errors": 1,
        "usage_log_pruned": 42,
    }
