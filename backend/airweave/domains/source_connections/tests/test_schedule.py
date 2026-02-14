"""Unit tests for schedule logic.

Pure functions -- no mocks, no async, no fixtures needed.
"""

import re
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock

import pytest

from airweave.domains.source_connections.schedule import (
    InvalidScheduleError,
    determine_schedule,
    get_default_continuous_cron,
    get_default_daily_cron,
    validate_cron_for_source,
)


# ---------------------------------------------------------------------------
# get_default_daily_cron
# ---------------------------------------------------------------------------


def test_default_daily_cron_is_valid_cron():
    cron = get_default_daily_cron()
    # Should match: M H * * *
    assert re.match(r"^\d{1,2} \d{1,2} \* \* \*$", cron)


def test_default_daily_cron_uses_current_time():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    cron = get_default_daily_cron()
    parts = cron.split()
    assert int(parts[0]) == now.minute
    assert int(parts[1]) == now.hour


# ---------------------------------------------------------------------------
# get_default_continuous_cron
# ---------------------------------------------------------------------------


def test_default_continuous_cron():
    assert get_default_continuous_cron() == "*/5 * * * *"


# ---------------------------------------------------------------------------
# determine_schedule
# ---------------------------------------------------------------------------


@dataclass
class DetermineCase:
    desc: str
    schedule_cron: object  # None = no schedule attr, "explicit" = has .schedule.cron
    supports_continuous: bool
    expect_result: str  # "daily", "continuous", "explicit", or "none"


def _make_input_with_schedule(cron_value):
    """Build a mock obj_in with schedule.cron set."""
    schedule = MagicMock()
    schedule.cron = cron_value
    obj_in = MagicMock()
    obj_in.schedule = schedule
    return obj_in


def _make_input_without_schedule():
    """Build a mock obj_in with no schedule."""
    obj_in = MagicMock(spec=[])  # Empty spec = no attributes
    return obj_in


DETERMINE_CASES = [
    DetermineCase(
        desc="explicit cron from input",
        schedule_cron="0 */6 * * *",
        supports_continuous=False,
        expect_result="explicit",
    ),
    DetermineCase(
        desc="explicit null cron returns None",
        schedule_cron=None,
        supports_continuous=False,
        expect_result="none",
    ),
    DetermineCase(
        desc="no schedule + continuous defaults to 5min",
        schedule_cron="no_schedule",
        supports_continuous=True,
        expect_result="continuous",
    ),
    DetermineCase(
        desc="no schedule + non-continuous defaults to daily",
        schedule_cron="no_schedule",
        supports_continuous=False,
        expect_result="daily",
    ),
]


@pytest.mark.parametrize("case", DETERMINE_CASES, ids=lambda c: c.desc)
def test_determine_schedule(case: DetermineCase):
    if case.schedule_cron == "no_schedule":
        obj_in = _make_input_without_schedule()
    elif case.schedule_cron is None:
        obj_in = _make_input_with_schedule(None)
    else:
        obj_in = _make_input_with_schedule(case.schedule_cron)

    result = determine_schedule(obj_in, case.supports_continuous)

    if case.expect_result == "none":
        assert result is None
    elif case.expect_result == "explicit":
        assert result == case.schedule_cron
    elif case.expect_result == "continuous":
        assert result == "*/5 * * * *"
    elif case.expect_result == "daily":
        assert re.match(r"^\d{1,2} \d{1,2} \* \* \*$", result)


# ---------------------------------------------------------------------------
# validate_cron_for_source
# ---------------------------------------------------------------------------


@dataclass
class ValidateCase:
    desc: str
    cron: str
    supports_continuous: bool
    expect_error: bool = False


VALIDATE_CASES = [
    ValidateCase(
        desc="hourly allowed for non-continuous",
        cron="0 * * * *",
        supports_continuous=False,
    ),
    ValidateCase(
        desc="daily allowed for non-continuous",
        cron="30 14 * * *",
        supports_continuous=False,
    ),
    ValidateCase(
        desc="every-6-hours allowed for non-continuous",
        cron="0 */6 * * *",
        supports_continuous=False,
    ),
    ValidateCase(
        desc="5-min rejected for non-continuous",
        cron="*/5 * * * *",
        supports_continuous=False,
        expect_error=True,
    ),
    ValidateCase(
        desc="15-min rejected for non-continuous",
        cron="*/15 * * * *",
        supports_continuous=False,
        expect_error=True,
    ),
    ValidateCase(
        desc="every-minute rejected for non-continuous",
        cron="* * * * *",
        supports_continuous=False,
        expect_error=True,
    ),
    ValidateCase(
        desc="5-min allowed for continuous",
        cron="*/5 * * * *",
        supports_continuous=True,
    ),
    ValidateCase(
        desc="every-minute allowed for continuous",
        cron="* * * * *",
        supports_continuous=True,
    ),
    ValidateCase(
        desc="empty cron is no-op",
        cron="",
        supports_continuous=False,
    ),
]


@pytest.mark.parametrize("case", VALIDATE_CASES, ids=lambda c: c.desc)
def test_validate_cron_for_source(case: ValidateCase):
    if case.expect_error:
        with pytest.raises(InvalidScheduleError) as exc_info:
            validate_cron_for_source(case.cron, "test_source", case.supports_continuous)
        assert "test_source" in str(exc_info.value)
    else:
        validate_cron_for_source(case.cron, "test_source", case.supports_continuous)


def test_invalid_schedule_error_is_bad_request():
    """InvalidScheduleError inherits from BadRequestError for 400 mapping."""
    from airweave.core.exceptions import BadRequestError

    exc = InvalidScheduleError("src", "bad schedule")
    assert isinstance(exc, BadRequestError)
