"""Tests for the exception stub source."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceEntityForbiddenError,
    SourceEntityNotFoundError,
    SourceRateLimitError,
    SourceServerError,
    SourceTokenRefreshError,
)
from airweave.domains.sources.token_providers.exceptions import (
    TokenCredentialsInvalidError,
    TokenExpiredError,
    TokenProviderConfigError,
    TokenProviderServerError,
)
from airweave.platform.configs.config import ExceptionStubConfig
from airweave.platform.entities.stub import SmallStubEntity, StubContainerEntity
from airweave.platform.sources.exception_stub import ExceptionStubSource


def _mock_auth() -> MagicMock:
    return MagicMock()


def _mock_logger() -> MagicMock:
    logger = MagicMock()
    logger.info = MagicMock()
    logger.error = MagicMock()
    return logger


def _mock_http_client() -> AsyncMock:
    return AsyncMock()


async def _create_source(config: ExceptionStubConfig) -> ExceptionStubSource:
    return await ExceptionStubSource.create(
        auth=_mock_auth(),
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=config,
    )


async def _collect_entities(source: ExceptionStubSource) -> list:
    entities = []
    async for entity in source.generate_entities():
        entities.append(entity)
    return entities


@pytest.mark.unit
async def test_generates_entities_before_failure():
    """Verify correct number of entities are yielded before the exception."""
    config = ExceptionStubConfig(entity_count=10, trigger_after=5, exception_type="runtime_error")
    source = await _create_source(config)

    entities = []
    with pytest.raises(RuntimeError):
        async for entity in source.generate_entities():
            entities.append(entity)

    # 1 container + 5 data entities
    assert len(entities) == 6
    assert isinstance(entities[0], StubContainerEntity)
    assert all(isinstance(e, SmallStubEntity) for e in entities[1:])


@pytest.mark.unit
async def test_runtime_error():
    """Verify RuntimeError is raised with ExceptionStub prefix."""
    config = ExceptionStubConfig(exception_type="runtime_error", trigger_after=0)
    source = await _create_source(config)

    with pytest.raises(RuntimeError, match=r"\[ExceptionStub\]"):
        await _collect_entities(source)


@pytest.mark.unit
async def test_source_auth_error():
    """Verify SourceAuthError is raised with configured provider kind."""
    config = ExceptionStubConfig(
        exception_type="source_auth_error",
        trigger_after=0,
        auth_provider_kind="oauth",
    )
    source = await _create_source(config)

    with pytest.raises(SourceAuthError, match=r"\[ExceptionStub\]") as exc_info:
        await _collect_entities(source)

    assert exc_info.value.status_code == 401


@pytest.mark.unit
async def test_source_auth_error_static_provider():
    """Verify SourceAuthError uses the configured auth_provider_kind."""
    config = ExceptionStubConfig(
        exception_type="source_auth_error",
        trigger_after=0,
        auth_provider_kind="static",
    )
    source = await _create_source(config)

    with pytest.raises(SourceAuthError) as exc_info:
        await _collect_entities(source)

    from airweave.domains.sources.token_providers.protocol import AuthProviderKind

    assert exc_info.value.token_provider_kind == AuthProviderKind.STATIC


@pytest.mark.unit
async def test_source_token_refresh_error():
    """Verify SourceTokenRefreshError is raised."""
    config = ExceptionStubConfig(exception_type="source_token_refresh_error", trigger_after=0)
    source = await _create_source(config)

    with pytest.raises(SourceTokenRefreshError, match=r"\[ExceptionStub\]"):
        await _collect_entities(source)


@pytest.mark.unit
async def test_token_expired():
    """Verify TokenExpiredError is raised."""
    config = ExceptionStubConfig(exception_type="token_expired", trigger_after=0)
    source = await _create_source(config)

    with pytest.raises(TokenExpiredError, match=r"\[ExceptionStub\]"):
        await _collect_entities(source)


@pytest.mark.unit
async def test_token_credentials_invalid():
    """Verify TokenCredentialsInvalidError is raised."""
    config = ExceptionStubConfig(exception_type="token_credentials_invalid", trigger_after=0)
    source = await _create_source(config)

    with pytest.raises(TokenCredentialsInvalidError, match=r"\[ExceptionStub\]"):
        await _collect_entities(source)


@pytest.mark.unit
async def test_token_provider_config_error():
    """Verify TokenProviderConfigError is raised."""
    config = ExceptionStubConfig(exception_type="token_provider_config_error", trigger_after=0)
    source = await _create_source(config)

    with pytest.raises(TokenProviderConfigError, match=r"\[ExceptionStub\]"):
        await _collect_entities(source)


@pytest.mark.unit
async def test_token_provider_server_error():
    """Verify TokenProviderServerError is raised."""
    config = ExceptionStubConfig(exception_type="token_provider_server_error", trigger_after=0)
    source = await _create_source(config)

    with pytest.raises(TokenProviderServerError, match=r"\[ExceptionStub\]"):
        await _collect_entities(source)


@pytest.mark.unit
async def test_source_rate_limit_error():
    """Verify SourceRateLimitError is raised."""
    config = ExceptionStubConfig(exception_type="source_rate_limit_error", trigger_after=0)
    source = await _create_source(config)

    with pytest.raises(SourceRateLimitError):
        await _collect_entities(source)


@pytest.mark.unit
async def test_source_server_error():
    """Verify SourceServerError is raised."""
    config = ExceptionStubConfig(exception_type="source_server_error", trigger_after=0)
    source = await _create_source(config)

    with pytest.raises(SourceServerError, match=r"\[ExceptionStub\]"):
        await _collect_entities(source)


@pytest.mark.unit
async def test_source_entity_not_found():
    """Verify SourceEntityNotFoundError is raised."""
    config = ExceptionStubConfig(exception_type="source_entity_not_found", trigger_after=0)
    source = await _create_source(config)

    with pytest.raises(SourceEntityNotFoundError, match=r"\[ExceptionStub\]"):
        await _collect_entities(source)


@pytest.mark.unit
async def test_source_entity_forbidden():
    """Verify SourceEntityForbiddenError is raised."""
    config = ExceptionStubConfig(exception_type="source_entity_forbidden", trigger_after=0)
    source = await _create_source(config)

    with pytest.raises(SourceEntityForbiddenError, match=r"\[ExceptionStub\]"):
        await _collect_entities(source)


@pytest.mark.unit
async def test_timeout_error():
    """Verify asyncio.TimeoutError is raised."""
    config = ExceptionStubConfig(exception_type="timeout", trigger_after=0)
    source = await _create_source(config)

    with pytest.raises(asyncio.TimeoutError):
        await _collect_entities(source)


@pytest.mark.unit
async def test_cancelled_error():
    """Verify asyncio.CancelledError is raised."""
    config = ExceptionStubConfig(exception_type="cancelled", trigger_after=0)
    source = await _create_source(config)

    with pytest.raises(asyncio.CancelledError):
        await _collect_entities(source)


@pytest.mark.unit
async def test_immediate_failure():
    """trigger_after=0 should only yield the container before raising."""
    config = ExceptionStubConfig(entity_count=10, trigger_after=0, exception_type="runtime_error")
    source = await _create_source(config)

    entities = []
    with pytest.raises(RuntimeError):
        async for entity in source.generate_entities():
            entities.append(entity)

    assert len(entities) == 1
    assert isinstance(entities[0], StubContainerEntity)


@pytest.mark.unit
async def test_trigger_after_last_entity():
    """trigger_after=-1 should yield all entities then raise."""
    config = ExceptionStubConfig(entity_count=5, trigger_after=-1, exception_type="runtime_error")
    source = await _create_source(config)

    entities = []
    with pytest.raises(RuntimeError):
        async for entity in source.generate_entities():
            entities.append(entity)

    # 1 container + 4 data entities (entity_count - 1 because container counts)
    assert len(entities) == 5


@pytest.mark.unit
async def test_no_failure_when_trigger_exceeds_count():
    """When trigger_after >= entity_count, all entities succeed."""
    config = ExceptionStubConfig(entity_count=5, trigger_after=100, exception_type="runtime_error")
    source = await _create_source(config)

    entities = await _collect_entities(source)

    # 1 container + 4 data entities
    assert len(entities) == 5
    assert isinstance(entities[0], StubContainerEntity)


@pytest.mark.unit
async def test_fail_on_validate():
    """validate() should raise the configured exception_type when fail_on_validate=True."""
    config = ExceptionStubConfig(
        fail_on_validate=True,
        exception_type="source_auth_error",
        auth_provider_kind="oauth",
    )
    source = await _create_source(config)

    with pytest.raises(SourceAuthError, match=r"\[ExceptionStub\]"):
        await source.validate()


@pytest.mark.unit
async def test_fail_on_validate_server_error():
    """validate() can raise any configured exception type."""
    config = ExceptionStubConfig(
        fail_on_validate=True,
        exception_type="source_server_error",
    )
    source = await _create_source(config)

    with pytest.raises(SourceServerError, match=r"\[ExceptionStub\]"):
        await source.validate()


@pytest.mark.unit
async def test_validate_succeeds_by_default():
    """validate() should succeed when fail_on_validate=False."""
    config = ExceptionStubConfig(fail_on_validate=False)
    source = await _create_source(config)

    # Should not raise
    await source.validate()


@pytest.mark.unit
async def test_custom_error_message():
    """Custom error_message should appear in the raised exception."""
    custom_msg = "Custom test error for UI verification"
    config = ExceptionStubConfig(
        exception_type="runtime_error",
        trigger_after=0,
        error_message=custom_msg,
    )
    source = await _create_source(config)

    with pytest.raises(RuntimeError, match=custom_msg):
        await _collect_entities(source)


@pytest.mark.unit
async def test_custom_error_message_on_validate():
    """Custom error_message should appear in validate exception."""
    custom_msg = "Custom validation error for testing"
    config = ExceptionStubConfig(
        fail_on_validate=True,
        exception_type="runtime_error",
        error_message=custom_msg,
    )
    source = await _create_source(config)

    with pytest.raises(RuntimeError, match=custom_msg):
        await source.validate()


@pytest.mark.unit
async def test_entities_are_deterministic():
    """Same seed should produce same entities."""
    config = ExceptionStubConfig(entity_count=5, trigger_after=100, seed=123)
    source1 = await _create_source(config)
    source2 = await _create_source(config)

    entities1 = await _collect_entities(source1)
    entities2 = await _collect_entities(source2)

    for e1, e2 in zip(entities1[1:], entities2[1:], strict=True):
        assert e1.stub_id == e2.stub_id
        assert e1.title == e2.title


@pytest.mark.unit
async def test_invalid_exception_type():
    """Invalid exception_type should be rejected by Literal validation."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExceptionStubConfig(exception_type="nonexistent_error")
