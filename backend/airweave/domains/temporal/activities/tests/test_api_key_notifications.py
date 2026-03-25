"""Unit tests for CheckAndNotifyExpiringKeysActivity.

Uses FakeApiKeyMaintenanceRepository and a FakeEmailService.
"""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from airweave.core.datetime_utils import utc_now_naive
from airweave.domains.organizations.fakes.repository import (
    FakeApiKeyMaintenanceRepository,
)
from airweave.domains.temporal.activities.api_key_notifications import (
    CheckAndNotifyExpiringKeysActivity,
)

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


class FakeEmailService:
    """Records send() calls and returns configurable success/failure."""

    def __init__(self, *, succeed: bool = True) -> None:
        self.calls: list[dict] = []
        self._succeed = succeed
        self._should_raise: Exception | None = None

    def set_error(self, error: Exception) -> None:
        self._should_raise = error

    async def send(self, to_email, subject, html_body, **kwargs) -> bool:
        self.calls.append({"to": to_email, "subject": subject})
        if self._should_raise:
            raise self._should_raise
        return self._succeed

    async def send_welcome(self, to_email: str, user_name: str) -> None:
        pass


def _make_api_key(*, days_until_expiration: int = 14, email: str | None = "user@example.com"):
    now = utc_now_naive()
    return SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        created_by_email=email,
        expiration_date=now + timedelta(days=days_until_expiration),
    )


class _FakeDbCtx:
    def __init__(self, db) -> None:
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        pass


@pytest.fixture(autouse=True)
def _patch_deps():
    """Patch logger and get_db_context for all tests."""
    mock_db = MagicMock()
    with (
        patch(
            "airweave.domains.temporal.activities.api_key_notifications.logger",
            MagicMock(),
        ),
        patch(
            "airweave.domains.temporal.activities.api_key_notifications.get_db_context",
            return_value=_FakeDbCtx(mock_db),
        ),
        patch(
            "airweave.domains.temporal.activities.api_key_notifications.get_api_key_expiration_email",
            return_value=("Subject", "<html>body</html>"),
        ),
        patch(
            "airweave.domains.temporal.activities.api_key_notifications.settings",
            MagicMock(APP_FULL_URL="https://app.example.com"),
        ),
    ):
        yield


# -----------------------------------------------------------------------
# Happy path
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test_happy_path_sends_emails():
    repo = FakeApiKeyMaintenanceRepository()
    key_14d = _make_api_key(days_until_expiration=14)
    key_3d = _make_api_key(days_until_expiration=3)
    repo.set_expiring_keys([key_14d, key_3d])

    email = FakeEmailService()
    activity = CheckAndNotifyExpiringKeysActivity(
        email_service=email, api_key_repo=repo,
    )
    result = await activity.run()

    # All three thresholds query the repo; two keys returned each time
    assert repo.call_count("get_keys_expiring_in_range") == 3
    assert len(email.calls) == 6  # 2 keys × 3 thresholds
    assert result["errors"] == 0


# -----------------------------------------------------------------------
# No keys found
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test_no_keys_returns_all_zeros():
    repo = FakeApiKeyMaintenanceRepository()
    email = FakeEmailService()
    activity = CheckAndNotifyExpiringKeysActivity(
        email_service=email, api_key_repo=repo,
    )
    result = await activity.run()

    assert result == {"14_days": 0, "3_days": 0, "expired": 0, "errors": 0}
    assert len(email.calls) == 0


# -----------------------------------------------------------------------
# Email send failure
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test_email_failure_counted_as_error():
    repo = FakeApiKeyMaintenanceRepository()
    repo.set_expiring_keys([_make_api_key()])

    email = FakeEmailService(succeed=False)
    activity = CheckAndNotifyExpiringKeysActivity(
        email_service=email, api_key_repo=repo,
    )
    result = await activity.run()

    # 3 thresholds × 1 key = 3 failed sends → 3 errors
    assert result["errors"] == 3


# -----------------------------------------------------------------------
# Key with no created_by_email is skipped
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test_key_without_email_skipped():
    repo = FakeApiKeyMaintenanceRepository()
    repo.set_expiring_keys([_make_api_key(email=None)])

    email = FakeEmailService()
    activity = CheckAndNotifyExpiringKeysActivity(
        email_service=email, api_key_repo=repo,
    )
    result = await activity.run()

    # _send_expiration_notification returns False for no email → counted as error
    assert result["errors"] == 3
    assert len(email.calls) == 0


# -----------------------------------------------------------------------
# Email service raises — counted as error, doesn't crash
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test_email_send_exception_counted_as_error():
    repo = FakeApiKeyMaintenanceRepository()
    repo.set_expiring_keys([_make_api_key()])

    email = FakeEmailService()
    email.set_error(RuntimeError("SMTP down"))

    activity = CheckAndNotifyExpiringKeysActivity(
        email_service=email, api_key_repo=repo,
    )
    result = await activity.run()

    assert result["errors"] == 3


# -----------------------------------------------------------------------
# Threshold-level exception — other thresholds still processed
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test_threshold_exception_does_not_block_others():
    call_count = 0

    class _FailOnSecondCall(FakeApiKeyMaintenanceRepository):
        async def get_keys_expiring_in_range(self, db, start_date, end_date):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("DB timeout")
            return []

    repo = _FailOnSecondCall()
    email = FakeEmailService()
    activity = CheckAndNotifyExpiringKeysActivity(
        email_service=email, api_key_repo=repo,
    )
    result = await activity.run()

    assert call_count == 3  # all three thresholds attempted
    assert result["errors"] == 1  # only the failing threshold
