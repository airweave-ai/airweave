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

    # Get dependencies from container (attribute access, not method call)
    event_bus = container.event_bus

    logger.debug("Wiring activities with container dependencies")

    # Instantiate activities with dependencies
    # The .run method is what Temporal calls
    return [
        # Sync activities
        RunSyncActivity(event_bus=event_bus).run,
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
