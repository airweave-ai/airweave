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
    dense_embedder = container.dense_embedder
    sparse_embedder = container.sparse_embedder

    logger.debug("Wiring activities with container dependencies")

    return [
        RunSyncActivity(
            event_bus=event_bus,
            dense_embedder=dense_embedder,
            sparse_embedder=sparse_embedder,
        ).run,
        CreateSyncJobActivity(event_bus=event_bus).run,
        MarkSyncJobCancelledActivity().run,
        CleanupStuckSyncJobsActivity().run,
        # Cleanup
        SelfDestructOrphanedSyncActivity().run,
        CleanupSyncDataActivity().run,
        # Notifications
        CheckAndNotifyExpiringKeysActivity().run,
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
