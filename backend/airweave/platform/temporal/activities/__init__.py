"""Temporal activity classes.

Each activity is a class with:
- Dependencies declared in __init__
- A @activity.defn decorated method

Activities are instantiated and wired in worker.py using the DI container.

For workflow compatibility, we also export the activity method references.
These are used by workflows when calling execute_activity() with a function reference.
"""

from airweave.platform.temporal.activities.api_key_notifications import (
    CheckAndNotifyExpiringKeysActivity,
)
from airweave.platform.temporal.activities.cleanup import (
    CleanupSyncDataActivity,
    SelfDestructOrphanedSyncActivity,
)
from airweave.platform.temporal.activities.sync import (
    CleanupStuckSyncJobsActivity,
    CreateSyncJobActivity,
    MarkSyncJobCancelledActivity,
    RunSyncActivity,
)

# -----------------------------------------------------------------------------
# Activity method references for workflow compatibility
# These are the .run methods from the activity classes, which workflows use
# when calling execute_activity() with a function reference.
# The actual instances (with dependencies injected) are created in worker.py.
# -----------------------------------------------------------------------------

# Note: Workflows import these references to get the activity name at compile time.
# At runtime, Temporal matches by activity name (set via name= in @activity.defn).
# The actual activity instances with dependencies are registered separately in worker.py.

run_sync_activity = RunSyncActivity.run
mark_sync_job_cancelled_activity = MarkSyncJobCancelledActivity.run
create_sync_job_activity = CreateSyncJobActivity.run
cleanup_stuck_sync_jobs_activity = CleanupStuckSyncJobsActivity.run
self_destruct_orphaned_sync_activity = SelfDestructOrphanedSyncActivity.run
cleanup_sync_data_activity = CleanupSyncDataActivity.run
check_and_notify_expiring_keys_activity = CheckAndNotifyExpiringKeysActivity.run

__all__ = [
    # Activity classes (for worker.py instantiation)
    "RunSyncActivity",
    "MarkSyncJobCancelledActivity",
    "CreateSyncJobActivity",
    "CleanupStuckSyncJobsActivity",
    "SelfDestructOrphanedSyncActivity",
    "CleanupSyncDataActivity",
    "CheckAndNotifyExpiringKeysActivity",
    # Activity method references (for workflow imports)
    "run_sync_activity",
    "mark_sync_job_cancelled_activity",
    "create_sync_job_activity",
    "cleanup_stuck_sync_jobs_activity",
    "self_destruct_orphaned_sync_activity",
    "cleanup_sync_data_activity",
    "check_and_notify_expiring_keys_activity",
]
