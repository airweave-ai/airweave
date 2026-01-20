"""Access control action types, resolver, and dispatcher.

Access control membership action pipeline for sync operations.

Supports two sync modes:
- Full sync: MembershipTuple → ACUpsertAction (with orphan detection)
- Incremental sync: MembershipChange → ACUpsertAction/ACDeleteAction/etc.
"""

from airweave.platform.sync.actions.access_control.dispatcher import ACActionDispatcher
from airweave.platform.sync.actions.access_control.resolver import ACActionResolver
from airweave.platform.sync.actions.access_control.types import (
    ACActionBatch,
    ACDeleteAction,
    ACDeleteGroupAction,
    ACDeleteMemberAction,
    ACInsertAction,
    ACKeepAction,
    ACUpdateAction,
    ACUpsertAction,
)

__all__ = [
    # Types
    "ACActionBatch",
    "ACDeleteAction",
    "ACDeleteGroupAction",
    "ACDeleteMemberAction",
    "ACInsertAction",
    "ACKeepAction",
    "ACUpdateAction",
    "ACUpsertAction",
    # Resolver and Dispatcher
    "ACActionResolver",
    "ACActionDispatcher",
]
