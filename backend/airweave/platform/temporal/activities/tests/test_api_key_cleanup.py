"""Unit tests for API key cleanup Temporal activities.

Each activity gets a basic happy-path test with mocked DB and CRUD.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.temporal.activities.api_key_cleanup import (
    CleanupRevokedKeysActivity,
    ExpirePastDueKeysActivity,
    PruneUsageLogActivity,
)


@pytest.fixture(autouse=True)
def _patch_logger():
    """Replace structlog logger with a plain mock to avoid kwarg errors."""
    with patch(
        "airweave.platform.temporal.activities.api_key_cleanup.logger",
        MagicMock(),
    ):
        yield


@pytest.fixture
def mock_db():
    """An AsyncMock DB session usable as an async context manager."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.delete = AsyncMock()
    return db


def _patch_db_context(mock_db):
    """Return a patch for get_db_context that yields mock_db."""

    class _FakeCtx:
        async def __aenter__(self):
            return mock_db

        async def __aexit__(self, *args):
            pass

    return patch(
        "airweave.platform.temporal.activities.api_key_cleanup.get_db_context",
        return_value=_FakeCtx(),
    )


# -----------------------------------------------------------------------
# CleanupRevokedKeysActivity
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.platform.temporal.activities.api_key_cleanup.crud")
async def test_cleanup_deletes_revoked_keys(mock_crud, mock_db):
    stale_key_1 = MagicMock(id="key-1")
    stale_key_2 = MagicMock(id="key-2")
    mock_crud.api_key.get_revoked_keys_older_than = AsyncMock(
        return_value=[stale_key_1, stale_key_2],
    )

    activity = CleanupRevokedKeysActivity()

    with _patch_db_context(mock_db):
        result = await activity.run()

    assert result == 2
    assert mock_db.delete.await_count == 2
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
@patch("airweave.platform.temporal.activities.api_key_cleanup.crud")
async def test_cleanup_no_keys_returns_zero(mock_crud, mock_db):
    mock_crud.api_key.get_revoked_keys_older_than = AsyncMock(
        return_value=[],
    )

    activity = CleanupRevokedKeysActivity()

    with _patch_db_context(mock_db):
        result = await activity.run()

    assert result == 0
    mock_db.delete.assert_not_awaited()


# -----------------------------------------------------------------------
# ExpirePastDueKeysActivity
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.platform.temporal.activities.api_key_cleanup.crud")
async def test_expire_transitions_keys(mock_crud, mock_db):
    mock_crud.api_key.expire_past_due_keys = AsyncMock(return_value=5)

    activity = ExpirePastDueKeysActivity()

    with _patch_db_context(mock_db):
        result = await activity.run()

    assert result == 5
    mock_crud.api_key.expire_past_due_keys.assert_awaited_once_with(mock_db)
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
@patch("airweave.platform.temporal.activities.api_key_cleanup.crud")
async def test_expire_zero_keys(mock_crud, mock_db):
    mock_crud.api_key.expire_past_due_keys = AsyncMock(return_value=0)

    activity = ExpirePastDueKeysActivity()

    with _patch_db_context(mock_db):
        result = await activity.run()

    assert result == 0


# -----------------------------------------------------------------------
# PruneUsageLogActivity
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.platform.temporal.activities.api_key_cleanup.crud")
async def test_prune_removes_old_entries(mock_crud, mock_db):
    mock_crud.api_key.prune_usage_log = AsyncMock(return_value=42)

    activity = PruneUsageLogActivity()

    with _patch_db_context(mock_db):
        result = await activity.run()

    assert result == 42
    mock_crud.api_key.prune_usage_log.assert_awaited_once_with(
        mock_db, max_age_days=90,
    )
    mock_db.commit.assert_awaited_once()
