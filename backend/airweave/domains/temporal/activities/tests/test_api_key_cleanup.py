"""Unit tests for API key cleanup Temporal activities.

Uses FakeApiKeyMaintenanceRepository instead of mocking crud.
"""

from unittest.mock import MagicMock, patch

import pytest

from airweave.domains.organizations.fakes.repository import (
    FakeApiKeyMaintenanceRepository,
)
from airweave.domains.temporal.activities.api_key_cleanup import (
    CleanupRevokedKeysActivity,
    ExpirePastDueKeysActivity,
    PruneUsageLogActivity,
)


@pytest.fixture(autouse=True)
def _patch_logger():
    """Replace structlog logger with a plain mock to avoid kwarg errors."""
    with patch(
        "airweave.domains.temporal.activities.api_key_cleanup.logger",
        MagicMock(),
    ):
        yield


class _FakeDbCtx:
    """Async context manager yielding a mock DB session."""

    def __init__(self, db: MagicMock) -> None:
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock(return_value=None)
    db.commit.__func__ = None  # make it awaitable-ish
    db.delete = MagicMock(return_value=None)
    db.flush = MagicMock(return_value=None)

    # Make these real coroutines

    async def _noop(*a, **kw):
        pass

    db.commit = _noop
    db.delete = _noop
    db.flush = _noop
    return db


def _patch_db(mock_db):
    return patch(
        "airweave.domains.temporal.activities.api_key_cleanup.get_db_context",
        return_value=_FakeDbCtx(mock_db),
    )


# -----------------------------------------------------------------------
# CleanupRevokedKeysActivity
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test_cleanup_deletes_revoked_keys(mock_db):
    repo = FakeApiKeyMaintenanceRepository()
    key1 = MagicMock(id=MagicMock(hex="aabb"))
    key2 = MagicMock(id=MagicMock(hex="ccdd"))
    repo.set_revoked_keys([key1, key2])

    activity = CleanupRevokedKeysActivity(api_key_repo=repo)
    with _patch_db(mock_db):
        result = await activity.run()

    assert result == {"deleted": 2, "errors": 0}
    assert repo.called("get_revoked_keys_older_than")


@pytest.mark.unit
async def test_cleanup_no_keys_returns_zero(mock_db):
    repo = FakeApiKeyMaintenanceRepository()
    activity = CleanupRevokedKeysActivity(api_key_repo=repo)

    with _patch_db(mock_db):
        result = await activity.run()

    assert result == {"deleted": 0, "errors": 0}


@pytest.mark.unit
async def test_cleanup_per_key_error_counted(mock_db):
    repo = FakeApiKeyMaintenanceRepository()
    key1 = MagicMock(id=MagicMock(hex="aabb"))
    repo.set_revoked_keys([key1])

    async def _failing_delete(obj):
        raise RuntimeError("FK constraint")

    mock_db.delete = _failing_delete

    activity = CleanupRevokedKeysActivity(api_key_repo=repo)
    with _patch_db(mock_db):
        result = await activity.run()

    assert result == {"deleted": 0, "errors": 1}


# -----------------------------------------------------------------------
# ExpirePastDueKeysActivity
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test_expire_transitions_keys(mock_db):
    repo = FakeApiKeyMaintenanceRepository()
    repo.set_expired_count(5)

    activity = ExpirePastDueKeysActivity(api_key_repo=repo)
    with _patch_db(mock_db):
        result = await activity.run()

    assert result == {"expired": 5}
    assert repo.called("expire_past_due_keys")


@pytest.mark.unit
async def test_expire_zero_keys(mock_db):
    repo = FakeApiKeyMaintenanceRepository()
    activity = ExpirePastDueKeysActivity(api_key_repo=repo)

    with _patch_db(mock_db):
        result = await activity.run()

    assert result == {"expired": 0}


# -----------------------------------------------------------------------
# PruneUsageLogActivity
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test_prune_removes_old_entries(mock_db):
    repo = FakeApiKeyMaintenanceRepository()
    repo.set_pruned_count(42)

    activity = PruneUsageLogActivity(api_key_repo=repo)
    with _patch_db(mock_db):
        result = await activity.run()

    assert result == {"pruned": 42}
    assert repo.called("prune_usage_log")


@pytest.mark.unit
async def test_prune_zero_entries(mock_db):
    repo = FakeApiKeyMaintenanceRepository()
    activity = PruneUsageLogActivity(api_key_repo=repo)

    with _patch_db(mock_db):
        result = await activity.run()

    assert result == {"pruned": 0}
