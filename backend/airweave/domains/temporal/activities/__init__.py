"""Temporal activity classes.

Each activity is a class with:
- Dependencies declared in __init__
- A @activity.defn decorated method

Activities are instantiated and wired in worker/wiring.py using the DI container.

For workflow compatibility, we also export the activity method references.
These are used by workflows when calling execute_activity() with a function reference.
"""

from airweave.domains.temporal.activities.api_key_notifications import (
    CheckAndNotifyExpiringKeysActivity,
)
from airweave.domains.temporal.activities.cleanup_revoked_keys import (
    CleanupRevokedKeysActivity,
)
from airweave.domains.temporal.activities.cleanup_stuck_sync_jobs import (
    CleanupStuckSyncJobsActivity,
)
from airweave.domains.temporal.activities.cleanup_sync_data import (
    CleanupSyncDataActivity,
)
from airweave.domains.temporal.activities.create_sync_job import (
    CreateSyncJobActivity,
)
from airweave.domains.temporal.activities.expire_past_due_keys import (
    ExpirePastDueKeysActivity,
)
from airweave.domains.temporal.activities.prune_usage_log import (
    PruneUsageLogActivity,
)
from airweave.domains.temporal.activities.run_sync import (
    RunSyncActivity,
)
from airweave.domains.temporal.activities.self_destruct_orphaned_sync import (
    SelfDestructOrphanedSyncActivity,
)
from airweave.domains.temporal.activities.transition_sync_job import (
    TransitionSyncJobActivity,
)

# Activity method references for workflow compatibility.
# Workflows import these to get the activity name at compile time.
# At runtime, Temporal matches by activity name (set via name= in @activity.defn).
# The actual activity instances with dependencies are registered separately in worker/wiring.py.

run_sync_activity = RunSyncActivity.run
create_sync_job_activity = CreateSyncJobActivity.run
cleanup_stuck_sync_jobs_activity = CleanupStuckSyncJobsActivity.run
self_destruct_orphaned_sync_activity = SelfDestructOrphanedSyncActivity.run
cleanup_sync_data_activity = CleanupSyncDataActivity.run
check_and_notify_expiring_keys_activity = CheckAndNotifyExpiringKeysActivity.run
transition_sync_job_activity = TransitionSyncJobActivity.run
cleanup_revoked_keys_activity = CleanupRevokedKeysActivity.run
expire_past_due_keys_activity = ExpirePastDueKeysActivity.run
prune_usage_log_activity = PruneUsageLogActivity.run

__all__ = [
    # Activity classes (for worker/wiring.py instantiation)
    "RunSyncActivity",
    "CreateSyncJobActivity",
    "CleanupStuckSyncJobsActivity",
    "SelfDestructOrphanedSyncActivity",
    "CleanupSyncDataActivity",
    "CheckAndNotifyExpiringKeysActivity",
    "TransitionSyncJobActivity",
    "CleanupRevokedKeysActivity",
    "ExpirePastDueKeysActivity",
    "PruneUsageLogActivity",
    # Activity method references (for workflow imports)
    "run_sync_activity",
    "create_sync_job_activity",
    "cleanup_stuck_sync_jobs_activity",
    "self_destruct_orphaned_sync_activity",
    "cleanup_sync_data_activity",
    "check_and_notify_expiring_keys_activity",
    "transition_sync_job_activity",
    "cleanup_revoked_keys_activity",
    "expire_past_due_keys_activity",
    "prune_usage_log_activity",
]
