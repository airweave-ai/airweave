"""Unit tests for api_keys endpoint coroutines — direct invocation.

Calls the endpoint functions with mocked db/ctx/CRUD so coverage
instrumentation traces every branch (404 guards, audit logging, return paths).
Integration tests in test_role_gating.py cover these via HTTP.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.api.context import ApiContext
from airweave.api.v1.endpoints.api_keys import (
    delete_api_key,
    read_api_key,
    read_api_keys,
    rotate_api_key,
)
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.schemas.organization import Organization

TEST_ORG_ID = uuid4()


def _ctx() -> ApiContext:
    now = datetime.now(timezone.utc)
    org = Organization(
        id=TEST_ORG_ID,
        name="Test Organization",
        created_at=now,
        modified_at=now,
    )
    return ApiContext(
        request_id="unit-test",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        user=None,
        logger=logger.with_context(request_id="unit-test"),
    )


def _make_fake_api_key_obj() -> MagicMock:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    key = MagicMock()
    key.id = uuid4()
    key.organization_id = TEST_ORG_ID
    key.created_at = now
    key.modified_at = now
    key.last_used_date = None
    key.expiration_date = now + timedelta(days=90)
    key.created_by_email = "testuser@example.com"
    key.modified_by_email = "testuser@example.com"
    key.encrypted_key = b"encrypted"
    key.status = "active"
    key.key_prefix = "ak_te"
    key.description = None
    key.last_used_ip = None
    key.decrypted_key = None
    key.revoked_at = None
    return key


class TestReadApiKey:
    @pytest.mark.asyncio
    async def test_not_found_raises_404(self):
        ctx = _ctx()
        db = AsyncMock()
        with patch(
            "airweave.crud.api_key.get",
            new_callable=AsyncMock,
            side_effect=NotFoundException("ApiKey not found"),
        ):
            with pytest.raises(NotFoundException):
                await read_api_key(db=db, id=uuid4(), ctx=ctx)

    @pytest.mark.asyncio
    async def test_found_returns_key(self):
        ctx = _ctx()
        db = AsyncMock()
        fake_key = _make_fake_api_key_obj()
        with patch("airweave.crud.api_key.get", new_callable=AsyncMock, return_value=fake_key):
            result = await read_api_key(db=db, id=fake_key.id, ctx=ctx)
        assert result.id == fake_key.id
        assert result.decrypted_key is None


class TestReadApiKeys:
    @pytest.mark.asyncio
    async def test_empty_list(self):
        ctx = _ctx()
        db = AsyncMock()
        with patch(
            "airweave.crud.api_key.get_multi",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await read_api_keys(db=db, skip=0, limit=100, ctx=ctx)
        assert result == []


class TestRotateApiKey:
    @pytest.mark.asyncio
    async def test_not_found_raises_404(self):
        ctx = _ctx()
        db = AsyncMock()
        with patch(
            "airweave.crud.api_key.get",
            new_callable=AsyncMock,
            side_effect=NotFoundException("ApiKey not found"),
        ):
            with pytest.raises(NotFoundException):
                await rotate_api_key(db=db, id=uuid4(), ctx=ctx)


class TestDeleteApiKey:
    @pytest.mark.asyncio
    async def test_not_found_raises_404(self):
        ctx = _ctx()
        db = AsyncMock()
        with patch(
            "airweave.crud.api_key.get",
            new_callable=AsyncMock,
            side_effect=NotFoundException("ApiKey not found"),
        ):
            with pytest.raises(NotFoundException):
                await delete_api_key(db=db, id=uuid4(), ctx=ctx)
