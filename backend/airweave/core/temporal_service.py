"""Service for integrating Temporal workflows."""

from typing import Optional
from uuid import uuid4

from temporalio.client import WorkflowHandle

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.temporal.client import temporal_client
from airweave.platform.temporal.workflows import RunSourceConnectionWorkflow


class TemporalService:
    """Service for managing Temporal workflows."""

    async def run_source_connection_workflow(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        sync_dag: schemas.SyncDag,
        collection: schemas.Collection,
        source_connection: schemas.SourceConnection,
        ctx: ApiContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> WorkflowHandle:
        """Start a source connection sync workflow.

        Args:
            sync: The sync configuration
            sync_job: The sync job
            sync_dag: The sync DAG
            collection: The collection
            source_connection: The source connection
            ctx: The API context
            access_token: Optional access token
            force_full_sync: If True, forces a full sync ignoring cursor data

        Returns:
            The workflow handle
        """
        client = await temporal_client.get_client()
        task_queue = settings.TEMPORAL_TASK_QUEUE

        # Generate a unique workflow ID
        workflow_id = f"sync-{sync_job.id}-{uuid4()}"

        ctx.logger.info(f"Starting Temporal workflow {workflow_id} for sync job {sync_job.id}")
        ctx.logger.info(f"Source: {source_connection.name} | Collection: {collection.name}")

        # Convert Pydantic models to dicts for JSON serialization
        handle = await client.start_workflow(
            RunSourceConnectionWorkflow.run,
            args=[
                sync.model_dump(mode="json"),
                sync_job.model_dump(mode="json"),
                sync_dag.model_dump(mode="json"),
                collection.model_dump(mode="json"),
                source_connection.model_dump(mode="json"),
                ctx.to_serializable_dict(),  # Use serializable dict instead of model_dump
                access_token,
                force_full_sync,  # Add force_full_sync parameter
            ],
            id=workflow_id,
            task_queue=task_queue,
        )

        ctx.logger.info("✅ Temporal workflow started successfully!")

        return handle

    async def cancel_sync_job_workflow(self, sync_job_id: str) -> bool:
        """Cancel a running workflow by sync job ID.

        This will search for workflows with IDs matching the pattern sync-{sync_job_id}-*
        and cancel them. The workflow will catch the CancelledError and update the
        sync job status to CANCELLED.

        Args:
            sync_job_id: The sync job ID to cancel

        Returns:
            True if a workflow was found and cancelled, False otherwise
        """
        try:
            client = await temporal_client.get_client()

            # List workflows to find the one matching our sync job
            # Only look for RUNNING workflows
            workflows = []
            query = f'WorkflowId STARTS_WITH "sync-{sync_job_id}-" AND ExecutionStatus = "Running"'
            logger.info(f"Searching for workflows with query: {query}")

            async for workflow in client.list_workflows(query=query):
                workflows.append(workflow)
                logger.info(f"Found workflow: {workflow.id} with status: {workflow.status}")

            if not workflows:
                logger.warning(f"No running workflow found for sync job {sync_job_id}")

                # Let's also check without the status filter to see if workflow
                # exists but is not running
                all_workflows = []
                async for workflow in client.list_workflows(
                    query=f'WorkflowId STARTS_WITH "sync-{sync_job_id}-"'
                ):
                    all_workflows.append(workflow)
                    logger.info(
                        f"Found workflow (any status): {workflow.id} with status: {workflow.status}"
                    )

                if all_workflows:
                    logger.info(
                        f"Found {len(all_workflows)} workflow(s) for sync job "
                        f"{sync_job_id}, but none are running"
                    )

                return False

            # Cancel the workflow(s)
            cancelled_count = 0
            for workflow in workflows:
                try:
                    handle = client.get_workflow_handle(workflow.id)
                    await handle.cancel()
                    logger.info(
                        f"Successfully sent cancel request for workflow {workflow.id} "
                        f"(sync job {sync_job_id})"
                    )
                    cancelled_count += 1
                except Exception as e:
                    logger.error(f"Failed to cancel workflow {workflow.id}: {e}")

            return cancelled_count > 0

        except Exception as e:
            logger.error(f"Failed to cancel workflow for sync job {sync_job_id}: {e}")
            raise

    async def is_temporal_enabled(self) -> bool:
        """Check if Temporal is enabled and available.

        Returns:
            True if Temporal is enabled, False otherwise
        """
        temporal_enabled = settings.TEMPORAL_ENABLED

        if not temporal_enabled:
            return False

        try:
            _ = await temporal_client.get_client()
            return True
        except Exception as e:
            logger.warning(f"Temporal not available: {e}")
            return False


temporal_service = TemporalService()
