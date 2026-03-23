"""API tests for api_keys endpoints.

Tests cover:
- GET does not return decrypted key
- LIST does not return decrypted keys
- CREATE returns decrypted key + key_prefix
- ROTATE revokes old key, returns new key
- REVOKE endpoint marks key as revoked
- DELETE invalidates cache
- Usage endpoints return correct data
- model_validate pattern works for all responses
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave import schemas
from airweave.api.v1.endpoints import api_keys as api_keys_endpoint
from airweave.core.shared_models import ApiKeyStatus
from airweave.models.api_key import APIKey


def _make_ctx(org_id=None):
    """Build a minimal mock ApiContext."""
    org_id = org_id or uuid4()
    org = SimpleNamespace(id=org_id, name="Test Org")
    mock_logger = MagicMock()
    mock_logger.with_context.return_value = mock_logger
    return SimpleNamespace(
        organization=org,
        tracking_email="admin@example.com",
        logger=mock_logger,
    )


def _make_api_key_model(
    org_id=None,
    status=ApiKeyStatus.ACTIVE.value,
    key_prefix="abcd1234",
    encrypted_key="enc",
):
    """Build a stub APIKey ORM model."""
    stub = MagicMock(spec=APIKey)
    stub.id = uuid4()
    stub.organization_id = org_id or uuid4()
    stub.created_at = datetime(2025, 1, 1)
    stub.modified_at = datetime(2025, 1, 1)
    stub.expiration_date = datetime(2099, 1, 1)
    stub.last_used_date = None
    stub.last_used_ip = None
    stub.status = status
    stub.revoked_at = None
    stub.key_prefix = key_prefix
    stub.key_hash = "fakehash"
    stub.created_by_email = "creator@example.com"
    stub.modified_by_email = "creator@example.com"
    stub.encrypted_key = encrypted_key
    return stub


# -----------------------------------------------------------------------
# GET /{id} — no decrypted key
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.api.v1.endpoints.api_keys.crud")
async def test_read_api_key_does_not_return_decrypted_key(mock_crud):
    org_id = uuid4()
    model = _make_api_key_model(org_id=org_id)
    mock_crud.api_key.get = AsyncMock(return_value=model)
    ctx = _make_ctx(org_id=org_id)
    db = AsyncMock()

    result = await api_keys_endpoint.read_api_key(db=db, id=model.id, ctx=ctx)

    assert result.decrypted_key is None
    assert result.key_prefix == "abcd1234"
    assert result.status == ApiKeyStatus.ACTIVE.value


# -----------------------------------------------------------------------
# GET / — no decrypted keys
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.api.v1.endpoints.api_keys.crud")
async def test_read_api_keys_does_not_return_decrypted_keys(mock_crud):
    org_id = uuid4()
    models = [_make_api_key_model(org_id=org_id) for _ in range(3)]
    mock_crud.api_key.get_multi = AsyncMock(return_value=models)
    ctx = _make_ctx(org_id=org_id)
    db = AsyncMock()

    result = await api_keys_endpoint.read_api_keys(db=db, skip=0, limit=100, ctx=ctx)

    assert len(result) == 3
    for key in result:
        assert key.decrypted_key is None
        assert key.key_prefix is not None


# -----------------------------------------------------------------------
# POST / — returns decrypted key
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.api.v1.endpoints.api_keys.credentials")
@patch("airweave.api.v1.endpoints.api_keys.crud")
async def test_create_api_key_returns_decrypted_key(mock_crud, mock_creds):
    org_id = uuid4()
    model = _make_api_key_model(org_id=org_id, key_prefix="newprefi")
    mock_crud.api_key.create = AsyncMock(return_value=model)
    mock_creds.decrypt.return_value = {"key": "the-full-secret-key"}
    ctx = _make_ctx(org_id=org_id)
    db = AsyncMock()

    result = await api_keys_endpoint.create_api_key(
        db=db,
        api_key_in=schemas.APIKeyCreate(),
        ctx=ctx,
    )

    assert result.decrypted_key == "the-full-secret-key"
    assert result.key_prefix == "newprefi"
    assert result.status == ApiKeyStatus.ACTIVE.value


# -----------------------------------------------------------------------
# POST /{id}/rotate — revokes old, returns new
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.api.v1.endpoints.api_keys.credentials")
@patch("airweave.api.v1.endpoints.api_keys.crud")
async def test_rotate_revokes_old_returns_new(mock_crud, mock_creds):
    org_id = uuid4()
    old_model = _make_api_key_model(org_id=org_id)
    new_model = _make_api_key_model(org_id=org_id, key_prefix="newkey12")

    mock_crud.api_key.get = AsyncMock(return_value=old_model)
    mock_crud.api_key.create = AsyncMock(return_value=new_model)
    mock_crud.api_key.revoke = AsyncMock(return_value=old_model)
    mock_creds.decrypt.return_value = {"key": "new-secret-key"}
    ctx = _make_ctx(org_id=org_id)
    db = AsyncMock()
    cache = AsyncMock()

    result = await api_keys_endpoint.rotate_api_key(
        db=db, id=old_model.id, ctx=ctx, cache=cache,
    )

    assert result.decrypted_key == "new-secret-key"
    mock_crud.api_key.revoke.assert_awaited_once_with(
        db=db,
        api_key_id=old_model.id,
    )


# -----------------------------------------------------------------------
# POST /{id}/revoke — explicit revocation
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.api.v1.endpoints.api_keys.credentials")
@patch("airweave.api.v1.endpoints.api_keys.crud")
async def test_revoke_endpoint_marks_key_revoked(mock_crud, mock_creds):
    org_id = uuid4()
    model = _make_api_key_model(org_id=org_id)
    revoked_model = _make_api_key_model(org_id=org_id, status=ApiKeyStatus.REVOKED.value)

    mock_crud.api_key.get = AsyncMock(return_value=model)
    mock_crud.api_key.revoke = AsyncMock(return_value=revoked_model)
    mock_creds.decrypt.return_value = {"key": "the-secret"}
    ctx = _make_ctx(org_id=org_id)
    db = AsyncMock()
    cache = AsyncMock()

    result = await api_keys_endpoint.revoke_api_key(
        db=db, id=model.id, ctx=ctx, cache=cache,
    )

    assert result.decrypted_key is None
    assert result.status == ApiKeyStatus.REVOKED.value
    cache.invalidate_api_key.assert_awaited_once_with("the-secret")
    mock_crud.api_key.revoke.assert_awaited_once()


# -----------------------------------------------------------------------
# DELETE / — no decrypted key in response
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.api.v1.endpoints.api_keys.credentials")
@patch("airweave.api.v1.endpoints.api_keys.crud")
async def test_delete_does_not_return_decrypted_key(mock_crud, mock_creds):
    org_id = uuid4()
    model = _make_api_key_model(org_id=org_id)
    mock_crud.api_key.get = AsyncMock(return_value=model)
    mock_crud.api_key.remove = AsyncMock()
    mock_creds.decrypt.return_value = {"key": "the-secret"}
    ctx = _make_ctx(org_id=org_id)
    db = AsyncMock()
    cache = AsyncMock()

    result = await api_keys_endpoint.delete_api_key(
        db=db, id=model.id, ctx=ctx, cache=cache,
    )

    assert result.decrypted_key is None
    assert result.revoked_at is None
    assert result.last_used_ip is None
    cache.invalidate_api_key.assert_awaited_once_with("the-secret")
    mock_crud.api_key.remove.assert_awaited_once()


# -----------------------------------------------------------------------
# Usage endpoints
# -----------------------------------------------------------------------


@pytest.mark.asyncio
@patch("airweave.api.v1.endpoints.api_keys.crud")
async def test_read_usage_stats_returns_correct_data(mock_crud):
    org_id = uuid4()
    key_id = uuid4()
    model = _make_api_key_model(org_id=org_id)
    model.id = key_id
    mock_crud.api_key.get = AsyncMock(return_value=model)
    mock_crud.api_key.get_usage_stats = AsyncMock(
        return_value=schemas.APIKeyUsageStats(
            api_key_id=key_id,
            total_requests=42,
            first_used=datetime(2025, 1, 1),
            last_used=datetime(2025, 6, 1),
            unique_ips=3,
            unique_endpoints=5,
        )
    )
    ctx = _make_ctx(org_id=org_id)
    db = AsyncMock()

    result = await api_keys_endpoint.read_api_key_usage_stats(db=db, id=key_id, ctx=ctx)

    assert result.total_requests == 42
    assert result.unique_ips == 3
