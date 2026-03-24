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
    from airweave.domains.temporal.activities import (
        CheckAndNotifyExpiringKeysActivity,
        CleanupStuckSyncJobsActivity,
        CleanupSyncDataActivity,
        CreateSyncJobActivity,
        RunSyncActivity,
        SelfDestructOrphanedSyncActivity,
        TransitionSyncJobActivity,
    )

    email_service = container.email_service
    event_bus = container.event_bus
    sync_service = container.sync_service
    state_machine = container.sync_job_state_machine
    sync_repo = container.sync_repo
    sync_job_repo = container.sync_job_repo
    sc_repo = container.sc_repo
    conn_repo = container.conn_repo
    collection_repo = container.collection_repo
    temporal_workflow_service = container.temporal_workflow_service
    temporal_schedule_service = container.temporal_schedule_service
    arf_service = container.arf_service

    logger.debug("Wiring activities with container dependencies")

    return [
        RunSyncActivity(
            sync_service=sync_service,
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
        TransitionSyncJobActivity(
            state_machine=state_machine,
        ).run,
        CleanupStuckSyncJobsActivity(
            temporal_workflow_service=temporal_workflow_service,
            state_machine=state_machine,
        ).run,
        # Cleanup
        SelfDestructOrphanedSyncActivity(
            temporal_schedule_service=temporal_schedule_service,
        ).run,
        CleanupSyncDataActivity(
            temporal_schedule_service=temporal_schedule_service,
            arf_service=arf_service,
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
    from airweave.domains.temporal.workflows import (
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
