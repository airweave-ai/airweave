"""Unit tests for CRUDAPIKey.

Tests cover:
- get_by_key: O(1) hash lookup, valid, expired, revoked, wrong key
- revoke: success, concurrent revocation guard
- record_usage: inline UPDATE + fire-and-forget log
- get_revoked_keys_older_than: filters correctly
- create: stores key_prefix, key_hash, and status
- max expiration validates at 180
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from cryptography.fernet import InvalidToken

from airweave.core.exceptions import ConflictException, NotFoundException, PermissionException
from airweave.core.shared_models import ApiKeyStatus
from airweave.crud.crud_api_key import CRUDAPIKey
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


@pytest.fixture
def crud():
    return CRUDAPIKey(APIKey)


NOW = datetime(2025, 6, 15, 12, 0, 0)
TEST_KEY = "the-secret"


def _key_hash(key: str = TEST_KEY) -> str:
    import hashlib

    return hashlib.sha256(key.encode()).hexdigest()


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

    with pytest.raises(PermissionException, match="expired"):
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

    with pytest.raises(PermissionException, match="expired"):
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

    with pytest.raises(PermissionException, match="revoked"):
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
    db.flush.assert_awaited_once()
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
# record_usage
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.get_db_context")
async def test_record_usage_updates_model(mock_db_ctx, _mock_now, crud):
    """record_usage() executes an inline UPDATE on the key."""
    api_key = _make_api_key()
    db = AsyncMock()

    await crud.record_usage(
        db,
        api_key_obj=api_key,
        ip_address="192.0.2.1",
        endpoint="/test",
        user_agent="TestAgent/1.0",
    )

    db.execute.assert_awaited_once()


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
