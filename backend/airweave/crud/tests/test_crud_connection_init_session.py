"""Unit tests for CRUDConnectionInitSession.get_by_oauth_token_no_auth.

Tests cover:
- Happy path: matching token returns the session
- Wrong token returns None
- No pending sessions returns None
- Session with overrides=None is skipped
- Session with overrides missing oauth_token key is skipped
- Log messages redact token values
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.crud.crud_connection_init_session import CRUDConnectionInitSession
from airweave.models.connection_init_session import (
    ConnectionInitSession,
    ConnectionInitStatus,
)


def _make_session(overrides=None):
    """Build a stub ConnectionInitSession."""
    stub = MagicMock(spec=ConnectionInitSession)
    stub.id = uuid4()
    stub.status = ConnectionInitStatus.PENDING
    stub.overrides = overrides
    return stub


def _mock_db(sessions: list):
    """Return an AsyncMock db whose execute() yields the given sessions."""
    db = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = sessions
    result = MagicMock()
    result.scalars.return_value = scalars
    db.execute.return_value = result
    return db


@pytest.fixture
def crud():
    return CRUDConnectionInitSession(ConnectionInitSession, track_user=False)


@pytest.mark.asyncio
async def test_matching_token_returns_session(crud):
    """Happy path: session with matching oauth_token is returned."""
    session = _make_session(overrides={"oauth_token": "tok_abc12345xyz"})
    db = _mock_db([session])

    result = await crud.get_by_oauth_token_no_auth(db, oauth_token="tok_abc12345xyz")

    assert result is session


@pytest.mark.asyncio
async def test_wrong_token_returns_none(crud):
    """No token matches → returns None."""
    session = _make_session(overrides={"oauth_token": "tok_correct"})
    db = _mock_db([session])

    result = await crud.get_by_oauth_token_no_auth(db, oauth_token="tok_wrong")

    assert result is None


@pytest.mark.asyncio
async def test_no_pending_sessions_returns_none(crud):
    """Empty query result → returns None."""
    db = _mock_db([])

    result = await crud.get_by_oauth_token_no_auth(db, oauth_token="tok_anything")

    assert result is None


@pytest.mark.asyncio
async def test_session_with_overrides_none_is_skipped(crud):
    """Session whose overrides is None is skipped; compare_digest not called."""
    session_none = _make_session(overrides=None)
    session_match = _make_session(overrides={"oauth_token": "tok_target"})
    db = _mock_db([session_none, session_match])

    result = await crud.get_by_oauth_token_no_auth(db, oauth_token="tok_target")

    assert result is session_match


@pytest.mark.asyncio
async def test_session_missing_oauth_token_key_is_skipped(crud):
    """Session whose overrides lacks oauth_token key is skipped."""
    session_no_key = _make_session(overrides={"other_key": "value"})
    session_match = _make_session(overrides={"oauth_token": "tok_target"})
    db = _mock_db([session_no_key, session_match])

    result = await crud.get_by_oauth_token_no_auth(db, oauth_token="tok_target")

    assert result is session_match


@pytest.mark.asyncio
async def test_non_string_token_is_skipped(crud):
    """Session whose oauth_token is a non-string (e.g. int) is skipped."""
    session_bad = _make_session(overrides={"oauth_token": 12345})
    db = _mock_db([session_bad])

    result = await crud.get_by_oauth_token_no_auth(db, oauth_token="12345")

    assert result is None


@pytest.mark.asyncio
@patch("airweave.crud.crud_connection_init_session.logger")
async def test_logs_redact_token_values(mock_logger, crud):
    """Logger.debug receives truncated token, not the full value."""
    full_token = "tok_abc12345xyz_full_secret"
    session = _make_session(overrides={"oauth_token": full_token})
    db = _mock_db([session])

    await crud.get_by_oauth_token_no_auth(db, oauth_token=full_token)

    # Collect all debug call args into a single string for inspection
    debug_args = " ".join(
        str(call) for call in mock_logger.debug.call_args_list
    )

    # The SHA-256 fingerprint should appear in the logs
    expected_fp = hashlib.sha256(full_token.encode()).hexdigest()[:8]
    assert f"fp={expected_fp}" in debug_args
    # The full token must NOT appear in any log message
    assert full_token not in debug_args
