"""Temporal workflow lifecycle service.

Manages starting, cancelling, and cleaning up Temporal workflows.
Replaces the core/temporal_service.py singleton.

Does NOT cover:
- Schedule management (see TemporalScheduleService)
- Workflow/activity definitions (platform/temporal/workflows/)
- Worker runtime (platform/temporal/worker/)

# [code blue] core/temporal_service.py can be deleted once all consumers
# are migrated to use this via the container.
"""

import uuid
from typing import List, Optional

from temporalio.client import WorkflowHandle
from temporalio.service import RPCError, RPCStatusCode

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.temporal.client import temporal_client
from airweave.domains.temporal.protocols import TemporalWorkflowServiceProtocol
from airweave.platform.temporal.workflows import (
    CleanupSyncDataWorkflow,
    RunSourceConnectionWorkflow,
)


class TemporalWorkflowService(TemporalWorkflowServiceProtocol):
    """Manages Temporal workflow lifecycle: start, cancel, cleanup.

    Thin wrapper over the Temporal SDK client. Consumers interact with
    this service to launch sync workflows, request cancellations, or
    kick off fire-and-forget cleanup workflows. The actual workflow and
    activity logic lives in platform/temporal/.
    """

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
        """Start a source connection sync workflow.

        Args:
            sync: The sync configuration.
            sync_job: The sync job.
            collection: The collection.
            connection: The Connection schema (NOT SourceConnection).
            ctx: API context.
            access_token: Optional access token.
            force_full_sync: If True, ignores cursor data and cleans orphaned entities.

        Returns:
            The workflow handle.
        """
        client = await temporal_client.get_client()
        workflow_id = f"sync-{sync_job.id}"

        ctx.logger.info(f"Starting Temporal workflow {workflow_id} for sync job {sync_job.id}")
        ctx.logger.info(f"Connection: {connection.name} | Collection: {collection.name}")
        if force_full_sync:
            ctx.logger.info("Force full sync enabled - will ignore cursor data")

        handle = await client.start_workflow(
            RunSourceConnectionWorkflow.run,
            args=[
                sync.model_dump(mode="json"),
                sync_job.model_dump(mode="json"),
                collection.model_dump(mode="json"),
                connection.model_dump(mode="json"),
                ctx.to_serializable_dict(),
                access_token,
                force_full_sync,
            ],
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )

        ctx.logger.info("Temporal workflow started successfully")
        return handle

    async def cancel_sync_job_workflow(self, sync_job_id: str, ctx: ApiContext) -> dict[str, bool]:
        """Request cancellation of a running workflow by sync job ID.

        Only acknowledges the cancellation request was sent. Does not
        guarantee the workflow has completed graceful cancellation.

        Returns:
            dict with 'success' and 'workflow_found' boolean keys.
        """
        client = await temporal_client.get_client()
        workflow_id = f"sync-{sync_job_id}"
        try:
            handle = client.get_workflow_handle(workflow_id)
            await handle.cancel()
            ctx.logger.info(f"Cancellation requested for workflow {workflow_id}")
            return {"success": True, "workflow_found": True}
        except RPCError as e:
            if e.status == RPCStatusCode.NOT_FOUND:
                ctx.logger.warning(
                    f"Workflow {workflow_id} not found in Temporal - "
                    "may have already completed or never started"
                )
                return {"success": True, "workflow_found": False}
            ctx.logger.error(f"Failed to request cancellation for {workflow_id}: {e}")
            return {"success": False, "workflow_found": False}

    async def start_cleanup_sync_data_workflow(
        self,
        sync_ids: List[str],
        collection_id: str,
        organization_id: str,
        ctx: ApiContext,
    ) -> Optional[WorkflowHandle]:
        """Start a fire-and-forget cleanup workflow for deleted syncs.

        The DELETE endpoint returns immediately; Temporal handles the
        potentially slow external data cleanup with retries.

        Returns:
            WorkflowHandle if started, None on failure.
        """
        client = await temporal_client.get_client()
        workflow_id = f"cleanup-sync-data-{uuid.uuid4().hex[:12]}"

        try:
            handle = await client.start_workflow(
                CleanupSyncDataWorkflow.run,
                args=[sync_ids, collection_id, organization_id],
                id=workflow_id,
                task_queue=settings.TEMPORAL_TASK_QUEUE,
            )
            ctx.logger.info(
                f"Started async cleanup workflow {workflow_id} for {len(sync_ids)} sync(s)"
            )
            return handle
        except Exception as e:
            ctx.logger.error(f"Failed to start cleanup workflow for {len(sync_ids)} sync(s): {e}")
            return None

    async def is_temporal_enabled(self) -> bool:
        """Check if Temporal is enabled and reachable."""
        if not settings.TEMPORAL_ENABLED:
            return False
        try:
            await temporal_client.get_client()
            return True
        except Exception as e:
            logger.warning(f"Temporal not available: {e}")
            return False
