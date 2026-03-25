"""Integration-style tests for API key lifecycle.

Tests the full create -> authenticate -> revoke -> rejection flow
and create -> rotate -> old key rejected, new key works.
"""

import hashlib
import hmac
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.core.exceptions import ConflictException, PermissionException
from airweave.core.shared_models import ApiKeyStatus
from airweave.crud.crud_api_key import CRUDAPIKey
from airweave.models.api_key import APIKey

TEST_KEY = "the-secret"


def _key_hash(key: str = TEST_KEY) -> str:
    return hmac.new(b"test-encryption-key", key.encode(), hashlib.sha256).hexdigest()


def _make_api_key(
    key_id=None,
    encrypted_key="enc",
    expiration_date=None,
    status=ApiKeyStatus.ACTIVE.value,
    revoked_at=None,
    organization_id=None,
    key_hash=None,
):
    stub = MagicMock(spec=APIKey)
    stub.id = key_id or uuid4()
    stub.encrypted_key = encrypted_key
    stub.expiration_date = expiration_date or datetime(2099, 1, 1)
    stub.status = status
    stub.revoked_at = revoked_at
    stub.organization_id = organization_id or uuid4()
    stub.created_by_email = "test@example.com"
    stub.key_prefix = "abcd1234"
    stub.key_hash = key_hash or _key_hash()
    stub.description = None
    stub.last_used_date = None
    stub.last_used_ip = None
    return stub


def _mock_db_scalar(api_key):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = api_key
    db.execute.return_value = result
    return db


NOW = datetime(2025, 6, 15, 12, 0, 0)


@pytest.fixture(autouse=True)
def _patch_encryption_key():
    with patch("airweave.crud.crud_api_key.settings") as mock_settings:
        mock_settings.ENCRYPTION_KEY = "test-encryption-key"
        yield


# -----------------------------------------------------------------------
# Full lifecycle: create -> auth -> revoke -> immediately rejected
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.credentials")
async def test_lifecycle_create_auth_revoke_reject(mock_creds):
    """Walk through the full API key lifecycle.

    1. Active key authenticates
    2. After revocation, key is immediately rejected
    """
    crud = CRUDAPIKey(APIKey)
    org_id = uuid4()
    key_id = uuid4()

    # --- Step 1: active key authenticates ---
    active_key = _make_api_key(
        key_id=key_id,
        organization_id=org_id,
        status=ApiKeyStatus.ACTIVE.value,
    )
    mock_creds.decrypt.return_value = {"key": TEST_KEY}

    with patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW):
        db = _mock_db_scalar(active_key)
        result = await crud.get_by_key(db, key=TEST_KEY)
        assert result is active_key

    # --- Step 2: revoked key is immediately rejected ---
    revoked_key = _make_api_key(
        key_id=key_id,
        organization_id=org_id,
        status=ApiKeyStatus.REVOKED.value,
        revoked_at=NOW,
    )

    with patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW):
        db = _mock_db_scalar(revoked_key)
        with pytest.raises(PermissionException, match="not active"):
            await crud.get_by_key(db, key=TEST_KEY)


# -----------------------------------------------------------------------
# Rotation lifecycle: create -> rotate -> old rejected, new works
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.credentials")
async def test_lifecycle_rotate_old_rejected_new_works(mock_creds):
    """After rotation, old key is rejected and new key works."""
    crud = CRUDAPIKey(APIKey)
    org_id = uuid4()
    old_key_id = uuid4()
    new_key_id = uuid4()

    new_key_secret = "new-secret"
    new_key_hash = hmac.new(
        b"test-encryption-key", new_key_secret.encode(), hashlib.sha256,
    ).hexdigest()

    # Old key is now revoked
    old_key = _make_api_key(
        key_id=old_key_id,
        organization_id=org_id,
        status=ApiKeyStatus.REVOKED.value,
        revoked_at=NOW,
    )
    mock_creds.decrypt.return_value = {"key": TEST_KEY}

    with patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW):
        db = _mock_db_scalar(old_key)
        with pytest.raises(PermissionException, match="not active"):
            await crud.get_by_key(db, key=TEST_KEY)

    # New key works
    new_key = _make_api_key(
        key_id=new_key_id,
        organization_id=org_id,
        status=ApiKeyStatus.ACTIVE.value,
        key_hash=new_key_hash,
    )
    mock_creds.decrypt.return_value = {"key": new_key_secret}

    with patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW):
        db = _mock_db_scalar(new_key)
        result = await crud.get_by_key(db, key=new_key_secret)
        assert result is new_key


# -----------------------------------------------------------------------
# Concurrent revocation guard
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_revocation_one_succeeds_one_conflicts():
    """Two revocations of the same key: first succeeds, second raises conflict."""
    crud = CRUDAPIKey(APIKey)
    key_id = uuid4()

    refreshed = _make_api_key(
        key_id=key_id,
        status=ApiKeyStatus.REVOKED.value,
        revoked_at=NOW,
    )

    with patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW):
        # First revocation succeeds (rowcount=1)
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.rowcount = 1
        db.execute.return_value = result_mock
        db.get.return_value = refreshed

        result = await crud.revoke(db, api_key_id=key_id)
        assert result is refreshed

        # Second revocation fails (rowcount=0, key already revoked)
        db2 = AsyncMock()
        result_mock2 = MagicMock()
        result_mock2.rowcount = 0
        db2.execute.return_value = result_mock2

        with pytest.raises(ConflictException, match="not active"):
            await crud.revoke(db2, api_key_id=key_id)
