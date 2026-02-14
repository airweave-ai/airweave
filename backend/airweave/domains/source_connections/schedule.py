"""Schedule logic for source connections.

Pure functions for cron schedule defaults, determination, and validation.
No dependencies, no I/O, no state.
"""

import re
from datetime import datetime, timezone
from typing import Any, Optional

from airweave.core.exceptions import BadRequestError


class InvalidScheduleError(BadRequestError):
    """Raised when a cron schedule is invalid for the source type."""

    def __init__(self, short_name: str, detail: str):
        self.short_name = short_name
        super().__init__(detail)


def get_default_daily_cron() -> str:
    """Generate a default daily cron schedule at the current UTC time.

    Returns:
        Cron expression like "30 14 * * *" (daily at 14:30 UTC).
    """
    now_utc = datetime.now(timezone.utc)
    return f"{now_utc.minute} {now_utc.hour} * * *"


def get_default_continuous_cron() -> str:
    """Get default cron schedule for continuous sources.

    Returns:
        Cron expression for 5-minute intervals.
    """
    return "*/5 * * * *"


def determine_schedule(
    schedule_input: Any,
    supports_continuous: bool,
) -> Optional[str]:
    """Determine the cron schedule from input and source capabilities.

    Args:
        schedule_input: The schedule object from the request (has .cron attribute).
        supports_continuous: Whether the source supports sub-hourly syncs.

    Returns:
        Cron expression string, or None if no schedule should be created.
    """
    if (
        hasattr(schedule_input, "schedule")
        and schedule_input.schedule
        and hasattr(schedule_input.schedule, "cron")
    ):
        if schedule_input.schedule.cron is None:
            return None
        return schedule_input.schedule.cron

    if supports_continuous:
        return get_default_continuous_cron()

    return get_default_daily_cron()


def validate_cron_for_source(
    cron_schedule: str,
    short_name: str,
    supports_continuous: bool,
) -> None:
    """Validate that a cron schedule is compatible with the source type.

    Non-continuous sources cannot have sub-hourly schedules.

    Args:
        cron_schedule: The cron expression to validate.
        short_name: Source short_name (for error messages).
        supports_continuous: Whether the source supports sub-hourly syncs.

    Raises:
        InvalidScheduleError: If the schedule is too frequent for the source.
    """
    if not cron_schedule:
        return

    detail = (
        f"Source '{short_name}' does not support continuous syncs. "
        f"Minimum schedule interval is 1 hour (e.g., '0 * * * *' for hourly)."
    )

    # Pattern: */N * * * * where N < 60 (sub-hourly interval)
    match = re.match(r"^\*/([1-5]?[0-9]) \* \* \* \*$", cron_schedule)
    if match:
        interval = int(match.group(1))
        if interval < 60 and not supports_continuous:
            raise InvalidScheduleError(short_name, detail)
        return

    # Pattern: * * * * * (every minute)
    if cron_schedule == "* * * * *" and not supports_continuous:
        raise InvalidScheduleError(short_name, detail)
