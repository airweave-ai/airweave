"""Shared types for the temporal domain."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ScheduleInfo:
    """Temporal schedule metadata returned by get_schedules_for_sync."""

    schedule_id: str
    schedule_type: str
    paused: bool
    note: str
    next_action_at: Optional[str]
    num_recent_actions: int
