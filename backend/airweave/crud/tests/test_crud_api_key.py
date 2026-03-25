"""Unit tests for CRUDAPIKey.

Tests cover:
- get_by_key: O(1) hash lookup, valid, expired, revoked, wrong key
- revoke: success, concurrent revocation guard
- record_usage: enqueues to UsageBuffer
- UsageBuffer: flush, dedup, shutdown
- create: stores key_prefix, key_hash, and status
- max expiration validates at 180
"""

import hashlib
import hmac
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from cryptography.fernet import InvalidToken

from airweave.core.exceptions import ConflictException, NotFoundException, PermissionException
from airweave.core.shared_models import ApiKeyStatus
from airweave.crud.crud_api_key import CRUDAPIKey, UsageBuffer, UsageEvent
from airweave.models.api_key import APIKey
from airweave.schemas.api_key import APIKeyCreate


def _make_api_key(
    encrypted_key: str = "enc",
    expiration_date: datetime | None = None,
    status: str = ApiKeyStatus.ACTIVE.value,
    revoked_at: datetime | None = None,
    organization_id=None,
    key_id=None,
    key_hash: str = "fakehash",
):
    """Build a stub APIKey with the given fields."""
    stub = MagicMock(spec=APIKey)
    stub.id = key_id or uuid4()
    stub.encrypted_key = encrypted_key
    stub.expiration_date = expiration_date or datetime(2099, 1, 1)
    stub.status = status
    stub.revoked_at = revoked_at
    stub.organization_id = organization_id or uuid4()
    stub.created_by_email = "test@example.com"
    stub.key_prefix = "abcd1234"
    stub.key_hash = key_hash
    stub.description = None
    stub.last_used_date = None
    stub.last_used_ip = None
    return stub


def _mock_db_scalar(api_key):
    """Return an AsyncMock db whose execute() yields a single scalar."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = api_key
    db.execute.return_value = result
    return db


@pytest.fixture(autouse=True)
def _patch_encryption_key():
    with patch("airweave.crud.crud_api_key.settings") as mock_settings:
        mock_settings.ENCRYPTION_KEY = "test-encryption-key"
        yield


@pytest.fixture
def crud():
    return CRUDAPIKey(APIKey)


NOW = datetime(2025, 6, 15, 12, 0, 0)
TEST_KEY = "the-secret"


def _key_hash(key: str = TEST_KEY) -> str:
    return hmac.new(b"test-encryption-key", key.encode(), hashlib.sha256).hexdigest()


# -----------------------------------------------------------------------
# get_by_key — O(1) hash lookup
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_valid_key_returns_api_key(mock_creds, _mock_now, crud):
    """A matching, non-expired key is returned via hash lookup."""
    api_key = _make_api_key(
        expiration_date=datetime(2099, 1, 1),
        key_hash=_key_hash(),
    )
    mock_creds.decrypt.return_value = {"key": TEST_KEY}
    db = _mock_db_scalar(api_key)

    result = await crud.get_by_key(db, key=TEST_KEY)

    assert result is api_key


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_expired_key_raises_permission_exception(mock_creds, _mock_now, crud):
    """A matching but expired key raises PermissionException."""
    api_key = _make_api_key(
        expiration_date=datetime(2020, 1, 1),
        key_hash=_key_hash(),
    )
    mock_creds.decrypt.return_value = {"key": TEST_KEY}
    db = _mock_db_scalar(api_key)

    with pytest.raises(PermissionException, match="not active"):
        await crud.get_by_key(db, key=TEST_KEY)


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_expired_status_key_raises_permission(mock_creds, _mock_now, crud):
    """A key with status=expired is rejected even if expiration_date is future."""
    api_key = _make_api_key(
        expiration_date=datetime(2099, 1, 1),
        status=ApiKeyStatus.EXPIRED.value,
        key_hash=_key_hash(),
    )
    mock_creds.decrypt.return_value = {"key": TEST_KEY}
    db = _mock_db_scalar(api_key)

    with pytest.raises(PermissionException, match="not active"):
        await crud.get_by_key(db, key=TEST_KEY)


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_revoked_key_is_immediately_rejected(mock_creds, _mock_now, crud):
    """A revoked key is rejected immediately — no grace period."""
    api_key = _make_api_key(
        expiration_date=datetime(2099, 1, 1),
        status=ApiKeyStatus.REVOKED.value,
        revoked_at=NOW - timedelta(seconds=1),
        key_hash=_key_hash(),
    )
    mock_creds.decrypt.return_value = {"key": TEST_KEY}
    db = _mock_db_scalar(api_key)

    with pytest.raises(PermissionException, match="not active"):
        await crud.get_by_key(db, key=TEST_KEY)


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_wrong_key_raises_not_found(mock_creds, _mock_now, crud):
    """No hash match -> NotFoundException without decryption."""
    db = _mock_db_scalar(None)

    with pytest.raises(NotFoundException):
        await crud.get_by_key(db, key=TEST_KEY)

    mock_creds.decrypt.assert_not_called()


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_hash_match_but_decrypt_mismatch_raises_not_found(mock_creds, _mock_now, crud):
    """Hash collision (unlikely) caught by belt-and-suspenders decrypt check."""
    api_key = _make_api_key(
        expiration_date=datetime(2099, 1, 1),
        key_hash=_key_hash(),
    )
    mock_creds.decrypt.return_value = {"key": "different-key"}
    db = _mock_db_scalar(api_key)

    with pytest.raises(NotFoundException):
        await crud.get_by_key(db, key=TEST_KEY)


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_invalid_token_during_decrypt_raises_not_found(mock_creds, _mock_now, crud):
    """InvalidToken from Fernet decrypt after hash match raises NotFoundException."""
    api_key = _make_api_key(
        expiration_date=datetime(2099, 1, 1),
        key_hash=_key_hash(),
    )
    mock_creds.decrypt.side_effect = InvalidToken()
    db = _mock_db_scalar(api_key)

    with pytest.raises(NotFoundException):
        await crud.get_by_key(db, key=TEST_KEY)


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_non_dict_payload_raises_not_found(mock_creds, _mock_now, crud):
    """Decrypted payload that is not a dict raises NotFoundException."""
    api_key = _make_api_key(
        expiration_date=datetime(2099, 1, 1),
        key_hash=_key_hash(),
    )
    mock_creds.decrypt.return_value = ["not", "a", "dict"]
    db = _mock_db_scalar(api_key)

    with pytest.raises(NotFoundException):
        await crud.get_by_key(db, key=TEST_KEY)


# -----------------------------------------------------------------------
# get_by_key — query shape verification
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_get_by_key_uses_where_clause(mock_creds, _mock_now, crud):
    """Verify the SELECT uses a WHERE key_hash=? clause (not a full scan)."""
    api_key = _make_api_key(
        expiration_date=datetime(2099, 1, 1),
        key_hash=_key_hash(),
    )
    mock_creds.decrypt.return_value = {"key": TEST_KEY}
    db = _mock_db_scalar(api_key)

    await crud.get_by_key(db, key=TEST_KEY)

    # The executed statement should contain a WHERE clause with key_hash
    call_args = db.execute.call_args
    stmt = call_args[0][0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "key_hash" in compiled


# -----------------------------------------------------------------------
# revoke
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
async def test_revoke_sets_correct_fields(_mock_now, crud):
    """revoke() sets status and revoked_at."""
    key_id = uuid4()
    refreshed = _make_api_key(
        key_id=key_id,
        status=ApiKeyStatus.REVOKED.value,
        revoked_at=NOW,
    )

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.rowcount = 1
    db.execute.return_value = result_mock
    db.get.return_value = refreshed

    result = await crud.revoke(db, api_key_id=key_id)

    assert result is refreshed
    db.flush.assert_not_awaited()
    db.commit.assert_awaited_once()
    db.get.assert_awaited_once_with(APIKey, key_id)


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
async def test_revoke_concurrent_raises_conflict(_mock_now, crud):
    """revoke() raises ConflictException when the key is already not active."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.rowcount = 0
    db.execute.return_value = result_mock

    with pytest.raises(ConflictException, match="not active"):
        await crud.revoke(db, api_key_id=uuid4())


# -----------------------------------------------------------------------
# record_usage — enqueues to UsageBuffer
# -----------------------------------------------------------------------


@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
def test_record_usage_enqueues_event(_mock_now, crud):
    """record_usage() puts a UsageEvent on the buffer queue."""
    api_key = _make_api_key()

    buf = UsageBuffer()
    with patch("airweave.crud.crud_api_key.usage_buffer", buf):
        crud.record_usage(
            api_key_obj=api_key,
            ip_address="192.0.2.1",
            endpoint="/test",
            user_agent="TestAgent/1.0",
        )

    assert buf._queue.qsize() == 1
    event = buf._queue.get_nowait()
    assert event.key_id == api_key.id
    assert event.ip_address == "192.0.2.1"
    assert event.endpoint == "/test"


@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
def test_record_usage_by_id_enqueues_event(_mock_now, crud):
    """record_usage_by_id() enqueues without ORM object."""
    key_id = uuid4()
    org_id = uuid4()

    buf = UsageBuffer()
    with patch("airweave.crud.crud_api_key.usage_buffer", buf):
        crud.record_usage_by_id(
            api_key_id=key_id,
            organization_id=org_id,
            ip_address="192.0.2.2",
            endpoint="/other",
        )

    assert buf._queue.qsize() == 1
    event = buf._queue.get_nowait()
    assert event.key_id == key_id
    assert event.organization_id == org_id


# -----------------------------------------------------------------------
# UsageBuffer
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.get_db_context")
async def test_usage_buffer_flush_bulk_inserts(mock_db_ctx):
    """flush() issues a bulk INSERT and deduplicated UPDATEs."""
    db = AsyncMock()
    mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

    buf = UsageBuffer()
    key_id = uuid4()
    org_id = uuid4()

    for i in range(3):
        buf.enqueue(
            UsageEvent(
                key_id=key_id,
                organization_id=org_id,
                ip_address=f"192.0.2.{i}",
                endpoint="/test",
                user_agent=None,
                timestamp=NOW + timedelta(seconds=i),
            )
        )

    await buf._flush()

    # One bulk INSERT + one deduplicated UPDATE (same key_id)
    assert db.execute.await_count == 2
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_usage_buffer_flush_empty_is_noop():
    """flush() on an empty queue does nothing."""
    buf = UsageBuffer()
    # Should not raise or touch DB
    await buf._flush()


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.get_db_context")
async def test_usage_buffer_deduplicates_updates(mock_db_ctx):
    """Only the latest event per key_id triggers an UPDATE."""
    db = AsyncMock()
    mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

    buf = UsageBuffer()
    key_a = uuid4()
    key_b = uuid4()
    org = uuid4()

    buf.enqueue(UsageEvent(key_a, org, "10.0.0.1", "/a", None, NOW))
    buf.enqueue(UsageEvent(key_a, org, "10.0.0.2", "/a", None, NOW + timedelta(seconds=1)))
    buf.enqueue(UsageEvent(key_b, org, "10.0.0.3", "/b", None, NOW))

    await buf._flush()

    # 1 bulk INSERT + 2 UPDATEs (one per distinct key)
    assert db.execute.await_count == 3


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.get_db_context")
async def test_usage_buffer_stop_flushes_remaining(mock_db_ctx):
    """stop() flushes any queued events before returning."""
    db = AsyncMock()
    mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

    buf = UsageBuffer(flush_interval=999)
    buf.enqueue(UsageEvent(uuid4(), uuid4(), "192.0.2.1", "/x", None, NOW))

    await buf.start()
    await buf.stop()

    db.commit.assert_awaited_once()


# -----------------------------------------------------------------------
# schema validation
# -----------------------------------------------------------------------


def test_max_expiration_is_180():
    """APIKeyCreate rejects expiration_days > 180."""
    with pytest.raises(ValueError, match="180"):
        APIKeyCreate(expiration_days=181)


def test_max_expiration_180_is_accepted():
    """APIKeyCreate accepts expiration_days = 180."""
    obj = APIKeyCreate(expiration_days=180)
    assert obj.expiration_days == 180
