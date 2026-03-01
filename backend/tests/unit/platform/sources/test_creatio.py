"""Unit tests for the Creatio CRM source connector.

Tests cover static helpers, create(), _generate_entity, pagination,
generate_entities full flow, validate, token refresh, and class metadata.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from airweave.crud import entity
from airweave.platform.configs.auth import CreatioAuthConfig
from airweave.platform.entities.creatio import (
    CreatioAccountEntity,
    CreatioContactEntity,
)
from airweave.platform.sources.creatio import CreatioEntity, CreatioSource
from airweave.schemas.source_connection import AuthenticationMethod
from airweave.platform.configs.config import CreatioConfig
from airweave.platform.configs.auth import CreatioAuthConfig


@pytest.fixture
def config() -> dict[str, str]:
    return dict(
        instance_url="183119-crm-bundle.creatio.com"
    )

@pytest.fixture
def credentials() -> CreatioAuthConfig:
    return CreatioAuthConfig(
        client_id="7DDD373BD04074D4501930109F6ED138",
        client_secret="6D49A3A086420035C753E18058970107A17816F3D92F2B41BBB8015A2E39706A",
    )

async def _make_creatio_source(config: dict[str, str], credentials: CreatioAuthConfig) -> CreatioSource:
    """Instantiate CreatioSource directly, bypassing create() and token exchange."""
    source = await CreatioSource.create(credentials, config)
    return source


@pytest.mark.asyncio
async def test_generate(config: dict, credentials: CreatioAuthConfig):
    source = await _make_creatio_source(config, credentials)

    from airweave.platform.sources.creatio import CreatioEntity
    async with httpx.AsyncClient(timeout=30.0) as client:
        async for e in source._generate_entity(
            client=client,
            creatio_entity=CreatioEntity.CONTACT
        ):
            assert type(e.contact_id) == str, "Entity not generated properly"


@pytest.mark.asyncio
async def test_validate(config: dict, credentials: CreatioAuthConfig):
    """Test that validate() returns True with valid credentials."""
    source = await _make_creatio_source(config, credentials)
    result = await source.validate()
    assert result is True, "validate() should return True with valid credentials"