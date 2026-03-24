"""Centralized schedule ID construction.

Every Temporal schedule ID in the system is built here. This eliminates
the duplicated f-string patterns scattered across activities and services.
"""

from uuid import UUID


def sync_schedule_id(sync_id: str | UUID) -> str:
    """Regular sync schedule: ``sync-{sync_id}``."""
    return f"sync-{sync_id}"


def minute_schedule_id(sync_id: str | UUID) -> str:
    """Minute-level incremental schedule: ``minute-sync-{sync_id}``."""
    return f"minute-sync-{sync_id}"


def cleanup_schedule_id(sync_id: str | UUID) -> str:
    """Daily forced-full-sync cleanup schedule: ``daily-cleanup-{sync_id}``."""
    return f"daily-cleanup-{sync_id}"


def all_schedule_ids(sync_id: str | UUID) -> list[str]:
    """All possible schedule IDs for a given sync."""
    return [
        sync_schedule_id(sync_id),
        minute_schedule_id(sync_id),
        cleanup_schedule_id(sync_id),
    ]
