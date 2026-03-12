"""Activity and workflow wiring.

This module is the DI wiring point for Temporal.
It connects activities to their dependencies from the container.
"""

from airweave.core.logging import logger


def create_activities() -> list:
    """Create activity instances with dependencies from the container.

    This is the DI wiring point for Temporal activities.
    Each activity class declares its dependencies in __init__.

    Returns:
        List of activity .run methods to register with the worker.

    Future: This will evolve as we add more protocols to the container.
    """
    from airweave.core.container import container
    from airweave.platform.temporal.activities import (
        CheckAndNotifyExpiringKeysActivity,
        CleanupStuckSyncJobsActivity,
        CleanupSyncDataActivity,
        CreateSyncJobActivity,
        MarkSyncJobCancelledActivity,
        RunSyncActivity,
        SelfDestructOrphanedSyncActivity,
    )

    event_bus = container.event_bus
    email_service = container.email_service
    sync_service = container.sync_service
    sync_job_service = container.sync_job_service
    sync_repo = container.sync_repo
    sync_job_repo = container.sync_job_repo
    sc_repo = container.sc_repo
    conn_repo = container.conn_repo
    collection_repo = container.collection_repo
    temporal_workflow_service = container.temporal_workflow_service
    temporal_schedule_service = container.temporal_schedule_service

    logger.debug("Wiring activities with container dependencies")

    return [
        RunSyncActivity(
            event_bus=event_bus,
            sync_service=sync_service,
            sync_job_service=sync_job_service,
            collection_repo=collection_repo,
        ).run,
        CreateSyncJobActivity(
            event_bus=event_bus,
            sync_repo=sync_repo,
            sync_job_repo=sync_job_repo,
            sc_repo=sc_repo,
            conn_repo=conn_repo,
            collection_repo=collection_repo,
        ).run,
        MarkSyncJobCancelledActivity(
            sync_job_service=sync_job_service,
        ).run,
        CleanupStuckSyncJobsActivity(
            temporal_workflow_service=temporal_workflow_service,
            sync_job_service=sync_job_service,
        ).run,
        # Cleanup
        SelfDestructOrphanedSyncActivity(
            temporal_schedule_service=temporal_schedule_service,
        ).run,
        CleanupSyncDataActivity(
            temporal_schedule_service=temporal_schedule_service,
        ).run,
        # Notifications
        CheckAndNotifyExpiringKeysActivity(
            email_service=email_service,
        ).run,
    ]


def get_workflows() -> list:
    """Get workflow classes to register.

    Returns:
        List of workflow classes.
    """
    from airweave.platform.temporal.workflows import (
        APIKeyExpirationCheckWorkflow,
        CleanupStuckSyncJobsWorkflow,
        CleanupSyncDataWorkflow,
        RunSourceConnectionWorkflow,
    )

    return [
        RunSourceConnectionWorkflow,
        CleanupStuckSyncJobsWorkflow,
        CleanupSyncDataWorkflow,
        APIKeyExpirationCheckWorkflow,
    ]
