"""Unit tests for CRUDAPIKey.get_by_key constant-time comparison logic.

Tests cover:
- Happy path: valid key returns the APIKey
- Expired key raises PermissionException
- Wrong key raises NotFoundException
- InvalidToken during decrypt is skipped
- ValueError during decrypt is skipped
- Malformed payload (missing "key") falls back to empty string
- No keys in DB raises NotFoundException
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import InvalidToken

from airweave.core.exceptions import NotFoundException, PermissionException
from airweave.crud.crud_api_key import CRUDAPIKey
from airweave.models.api_key import APIKey


def _make_api_key(encrypted_key: str = "enc", expiration_date: datetime | None = None):
    """Build a stub APIKey with the given encrypted_key and expiration_date."""
    stub = MagicMock(spec=APIKey)
    stub.encrypted_key = encrypted_key
    stub.expiration_date = expiration_date or datetime(2099, 1, 1)
    return stub


def _mock_db(api_keys: list):
    """Return an AsyncMock db whose execute() yields the given api_keys."""
    db = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = api_keys
    result = MagicMock()
    result.scalars.return_value = scalars
    db.execute.return_value = result
    return db


@pytest.fixture
def crud():
    return CRUDAPIKey(APIKey)


NOW = datetime(2025, 6, 15, 12, 0, 0)


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_valid_key_returns_api_key(mock_creds, _mock_now, crud):
    """A matching, non-expired key is returned."""
    api_key = _make_api_key(expiration_date=datetime(2099, 1, 1))
    mock_creds.decrypt.return_value = {"key": "the-secret"}
    db = _mock_db([api_key])

    result = await crud.get_by_key(db, key="the-secret")

    assert result is api_key


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_expired_key_raises_permission_exception(mock_creds, _mock_now, crud):
    """A matching but expired key raises PermissionException."""
    api_key = _make_api_key(expiration_date=datetime(2020, 1, 1))
    mock_creds.decrypt.return_value = {"key": "the-secret"}
    db = _mock_db([api_key])

    with pytest.raises(PermissionException, match="expired"):
        await crud.get_by_key(db, key="the-secret")


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_wrong_key_raises_not_found(mock_creds, _mock_now, crud):
    """No key matches → NotFoundException."""
    api_key = _make_api_key()
    mock_creds.decrypt.return_value = {"key": "other-key"}
    db = _mock_db([api_key])

    with pytest.raises(NotFoundException):
        await crud.get_by_key(db, key="the-secret")


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_invalid_token_during_decrypt_is_skipped(mock_creds, _mock_now, crud):
    """InvalidToken from Fernet decrypt is caught; search continues."""
    good_key = _make_api_key(expiration_date=datetime(2099, 1, 1))
    bad_key = _make_api_key(encrypted_key="corrupt")

    mock_creds.decrypt.side_effect = [InvalidToken(), {"key": "the-secret"}]
    db = _mock_db([bad_key, good_key])

    result = await crud.get_by_key(db, key="the-secret")

    assert result is good_key
    assert mock_creds.decrypt.call_count == 2


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_value_error_during_decrypt_is_skipped(mock_creds, _mock_now, crud):
    """ValueError (e.g. JSONDecodeError) from decrypt is caught; search continues."""
    good_key = _make_api_key(expiration_date=datetime(2099, 1, 1))
    bad_key = _make_api_key(encrypted_key="bad-json")

    mock_creds.decrypt.side_effect = [ValueError("bad"), {"key": "the-secret"}]
    db = _mock_db([bad_key, good_key])

    result = await crud.get_by_key(db, key="the-secret")

    assert result is good_key


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_malformed_payload_missing_key_field(mock_creds, _mock_now, crud):
    """Decrypted payload missing "key" falls back to empty string → no match."""
    api_key = _make_api_key()
    mock_creds.decrypt.return_value = {"not_key": "value"}
    db = _mock_db([api_key])

    with pytest.raises(NotFoundException):
        await crud.get_by_key(db, key="the-secret")


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_non_dict_payload_is_skipped(mock_creds, _mock_now, crud):
    """Decrypted payload that is not a dict (e.g. a list) is skipped."""
    bad_key = _make_api_key()
    good_key = _make_api_key(expiration_date=datetime(2099, 1, 1))

    mock_creds.decrypt.side_effect = [["not", "a", "dict"], {"key": "the-secret"}]
    db = _mock_db([bad_key, good_key])

    result = await crud.get_by_key(db, key="the-secret")

    assert result is good_key
    assert mock_creds.decrypt.call_count == 2


@pytest.mark.asyncio
@patch("airweave.crud.crud_api_key.utc_now_naive", return_value=NOW)
@patch("airweave.crud.crud_api_key.credentials")
async def test_no_keys_in_db_raises_not_found(mock_creds, _mock_now, crud):
    """Empty DB table raises NotFoundException immediately."""
    db = _mock_db([])

    with pytest.raises(NotFoundException):
        await crud.get_by_key(db, key="the-secret")

    mock_creds.decrypt.assert_not_called()
