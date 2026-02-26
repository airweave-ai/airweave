"""Fake TemporalWorkflowService for testing."""

from typing import List, Optional

from temporalio.client import WorkflowHandle

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.domains.temporal.protocols import TemporalWorkflowServiceProtocol


class FakeTemporalWorkflowService(TemporalWorkflowServiceProtocol):
    """In-memory fake for TemporalWorkflowServiceProtocol.

    Records all calls and returns canned results.
    Consumer code never inspects the returned WorkflowHandle,
    so returning None is safe.
    """

    def __init__(self) -> None:
        """Initialize with empty call log and default responses."""
        self._calls: list[tuple] = []
        self._enabled: bool = True
        self._cancel_result: dict[str, bool] = {"success": True, "workflow_found": True}
        self._should_raise: Optional[Exception] = None

    def set_enabled(self, enabled: bool) -> None:
        """Configure is_temporal_enabled return value."""
        self._enabled = enabled

    def set_cancel_result(self, result: dict[str, bool]) -> None:
        """Configure cancel_sync_job_workflow return value."""
        self._cancel_result = result

    def set_error(self, error: Exception) -> None:
        """Make all subsequent calls raise this error."""
        self._should_raise = error

    async def run_source_connection_workflow(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        connection: schemas.Connection,
        ctx: ApiContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> WorkflowHandle:
        """Record call and return None (consumer ignores handle)."""
        self._calls.append(
            (
                "run_source_connection_workflow",
                sync,
                sync_job,
                collection,
                connection,
                ctx,
                access_token,
                force_full_sync,
            )
        )
        if self._should_raise:
            raise self._should_raise
        return None  # type: ignore[return-value]

    async def cancel_sync_job_workflow(self, sync_job_id: str, ctx: ApiContext) -> dict[str, bool]:
        """Record call and return canned cancel result."""
        self._calls.append(("cancel_sync_job_workflow", sync_job_id, ctx))
        if self._should_raise:
            raise self._should_raise
        return dict(self._cancel_result)

    async def start_cleanup_sync_data_workflow(
        self,
        sync_ids: List[str],
        collection_id: str,
        organization_id: str,
        ctx: ApiContext,
    ) -> Optional[WorkflowHandle]:
        """Record call and return None."""
        self._calls.append(
            (
                "start_cleanup_sync_data_workflow",
                sync_ids,
                collection_id,
                organization_id,
                ctx,
            )
        )
        if self._should_raise:
            raise self._should_raise
        return None

    async def is_temporal_enabled(self) -> bool:
        """Record call and return configured enabled state."""
        self._calls.append(("is_temporal_enabled",))
        return self._enabled
