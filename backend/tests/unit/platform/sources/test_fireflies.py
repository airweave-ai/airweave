"""Tests for the Fireflies source — v2 contract, GraphQL, entities."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from airweave.domains.sources.exceptions import SourceAuthError, SourceError
from airweave.domains.sources.token_providers.credential import DirectCredentialProvider
from airweave.domains.sources.token_providers.protocol import AuthProviderKind
from airweave.platform.configs.auth import FirefliesAuthConfig
from airweave.platform.configs.config import FirefliesConfig
from airweave.platform.entities.fireflies import (
    FirefliesTranscriptEntity,
    _normalize_action_items,
    _parse_epoch_ms,
)
from airweave.platform.sources.fireflies import FIREFLIES_GRAPHQL_URL, FirefliesSource


def _mock_auth(api_key: str = "test-key"):
    """Mock DirectCredentialProvider with Fireflies API key credentials."""
    creds = FirefliesAuthConfig(api_key=api_key)
    return DirectCredentialProvider(creds, source_short_name="fireflies")


def _mock_http_client():
    return AsyncMock()


def _mock_logger():
    return MagicMock()


def _http_json_response(
    status_code: int,
    data: dict,
    *,
    url: str = FIREFLIES_GRAPHQL_URL,
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(data).encode(),
        request=httpx.Request("POST", url),
    )


async def _make_source(api_key: str = "test-key", http_client=None):
    return await FirefliesSource.create(
        auth=_mock_auth(api_key=api_key),
        logger=_mock_logger(),
        http_client=http_client or _mock_http_client(),
        config=FirefliesConfig(),
    )


# ------------------------------------------------------------------
# create()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_success():
    source = await _make_source(api_key="test-key")

    assert isinstance(source, FirefliesSource)
    assert source._api_key == "test-key"


@pytest.mark.asyncio
async def test_create_uses_get_token_when_not_credential_provider():
    """Non-credential auth loads the token via get_token()."""
    auth = AsyncMock()
    auth.provider_kind = AuthProviderKind.OAUTH
    auth.supports_refresh = False
    auth.get_token = AsyncMock(return_value="oauth-token")

    source = await FirefliesSource.create(
        auth=auth,
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=FirefliesConfig(),
    )

    assert source._api_key == "oauth-token"
    auth.get_token.assert_awaited_once()


# ------------------------------------------------------------------
# _parse_epoch_ms (entity helper)
# ------------------------------------------------------------------


def test_parse_epoch_ms_valid():
    ms = 1700000000000
    dt = _parse_epoch_ms(ms)

    assert isinstance(dt, datetime)


def test_parse_epoch_ms_none():
    assert _parse_epoch_ms(None) is None


def test_parse_epoch_ms_invalid():
    assert _parse_epoch_ms(-999999999999999999999) is None


# ------------------------------------------------------------------
# _normalize_action_items()
# ------------------------------------------------------------------


def test_normalize_action_items_from_list():
    value = ["  task1  ", "task2", ""]
    result = _normalize_action_items(value)

    assert result == ["task1", "task2"]


def test_normalize_action_items_from_string():
    value = "task1\n\ntask2\n"
    result = _normalize_action_items(value)

    assert result == ["task1", "task2"]


def test_normalize_action_items_none():
    assert _normalize_action_items(None) is None


# ------------------------------------------------------------------
# _graphql()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graphql_success():
    mock_http = _mock_http_client()
    mock_http.post = AsyncMock(
        return_value=_http_json_response(200, {"data": {"ok": True}})
    )

    source = await _make_source(http_client=mock_http)

    result = await source._graphql(" query { ok } ")

    assert result == {"data": {"ok": True}}
    mock_http.post.assert_awaited_once()
    call_kw = mock_http.post.await_args
    assert call_kw[0][0] == FIREFLIES_GRAPHQL_URL
    assert call_kw[1]["headers"]["Authorization"] == "Bearer test-key"


@pytest.mark.asyncio
async def test_graphql_401_raises_source_auth_error():
    mock_http = _mock_http_client()
    mock_http.post = AsyncMock(
        return_value=_http_json_response(
            401,
            {"errors": [{"message": "Invalid API key"}]},
        )
    )

    source = await _make_source(http_client=mock_http)

    with pytest.raises(SourceAuthError, match="Unauthorized"):
        await source._graphql("query {}")


@pytest.mark.asyncio
async def test_graphql_graphql_error_inside_200():
    mock_http = _mock_http_client()
    mock_http.post = AsyncMock(
        return_value=_http_json_response(
            200,
            {"errors": [{"message": "Some GraphQL error"}]},
        )
    )

    source = await _make_source(http_client=mock_http)

    with pytest.raises(SourceError, match="Some GraphQL error"):
        await source._graphql("query {}")


# ------------------------------------------------------------------
# FirefliesTranscriptEntity.from_api()
# ------------------------------------------------------------------


def test_transcript_to_entity_basic_mapping():
    transcript = {
        "id": "123",
        "title": "Weekly Sync",
        "date": 1700000000000,
        "summary": {
            "overview": "Overview text",
            "keywords": ["sync", "team"],
            "action_items": ["Task 1", "Task 2"],
        },
        "sentences": [
            {"raw_text": "Hello world"},
            {"text": "Second line"},
        ],
    }

    entity = FirefliesTranscriptEntity.from_api(transcript)

    assert entity.entity_id == "123"
    assert entity.name == "Weekly Sync"
    assert entity.summary_overview == "Overview text"
    assert entity.summary_keywords == ["sync", "team"]
    assert entity.summary_action_items == ["Task 1", "Task 2"]
    assert entity.content == "Hello world\nSecond line"
    assert entity.created_at is not None


# ------------------------------------------------------------------
# generate_entities() pagination
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_entities_pagination():
    source = await _make_source()

    first_page = {"data": {"transcripts": [{"id": "1", "title": "A", "sentences": []}]}}
    second_page = {"data": {"transcripts": []}}

    source._graphql = AsyncMock(side_effect=[first_page, second_page])

    results = []
    async for entity in source.generate_entities():
        results.append(entity)

    assert len(results) == 1
    assert results[0].entity_id == "1"


# ------------------------------------------------------------------
# validate()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success():
    source = await _make_source()
    source._graphql = AsyncMock(return_value={"data": {}})

    await source.validate()


@pytest.mark.asyncio
async def test_validate_failure():
    source = await _make_source()
    source._graphql = AsyncMock(
        side_effect=SourceAuthError(
            "Unauthorized",
            source_short_name="fireflies",
            status_code=401,
            token_provider_kind=AuthProviderKind.CREDENTIAL,
        )
    )

    with pytest.raises(SourceAuthError):
        await source.validate()
