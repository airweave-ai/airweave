"""Fake temporal service for testing."""

from typing import Any, List, Optional


class FakeTemporalService:
    """In-memory fake for TemporalServiceProtocol."""

    def __init__(self, should_raise: Optional[Exception] = None) -> None:
        self._should_raise = should_raise
        self.workflows_started: list[dict] = []
        self.cancellations: list[str] = []
        self.cleanups: list[dict] = []
        self._cancel_result: dict = {"success": True, "workflow_found": True}

    def _maybe_raise(self) -> None:
        if self._should_raise:
            raise self._should_raise

    async def run_source_connection_workflow(
        self,
        sync: Any,
        sync_job: Any,
        collection: Any,
        connection: Any,
        ctx: Any,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> Any:
        self._maybe_raise()
        self.workflows_started.append(
            {
                "sync": sync,
                "sync_job": sync_job,
                "collection": collection,
                "connection": connection,
            }
        )
        return None

    async def cancel_sync_job_workflow(self, sync_job_id: str, ctx: Any) -> dict:
        self._maybe_raise()
        self.cancellations.append(sync_job_id)
        return self._cancel_result

    async def start_cleanup_sync_data_workflow(
        self,
        sync_ids: List[str],
        collection_id: str,
        organization_id: str,
        ctx: Any,
    ) -> Optional[Any]:
        self._maybe_raise()
        self.cleanups.append(
            {
                "sync_ids": sync_ids,
                "collection_id": collection_id,
                "organization_id": organization_id,
            }
        )
        return None

    def set_cancel_result(self, result: dict) -> None:
        self._cancel_result = result

    def set_should_raise(self, exc: Optional[Exception]) -> None:
        self._should_raise = exc

    def clear(self) -> None:
        self._should_raise = None
        self.workflows_started.clear()
        self.cancellations.clear()
        self.cleanups.clear()
        self._cancel_result = {"success": True, "workflow_found": True}
