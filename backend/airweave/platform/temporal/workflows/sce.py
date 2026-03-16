"""Temporal workflow for Structural Context Extraction (SCE)."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class ExtractStructuralContextWorkflow:
    """Workflow that runs SCE on all entities produced by a sync."""

    @workflow.run
    async def run(self, collection_id: str, sync_id: str) -> list:
        """Run SCE on all entities produced by a sync."""
        from airweave.platform.temporal.activities import (
            extract_structural_context_activity,
        )

        return await workflow.execute_activity(
            extract_structural_context_activity,
            args=[collection_id, sync_id],
            start_to_close_timeout=timedelta(minutes=30),
            heartbeat_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
