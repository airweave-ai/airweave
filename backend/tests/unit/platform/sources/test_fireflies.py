import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from airweave.platform.sources.fireflies import FirefliesSource
from airweave.platform.configs.auth import FirefliesAuthConfig


pytestmark = pytest.mark.asyncio

from airweave.platform.sources.fireflies import FirefliesSource


# ------------------------------------------------------------------
# create()
# ------------------------------------------------------------------

async def test_create_success():
    credentials = FirefliesAuthConfig(api_key="  test-key  ")
    source = await FirefliesSource.create(credentials)

    assert isinstance(source, FirefliesSource)
    assert source.api_key == "test-key"


async def test_create_raises_if_missing_api_key():
    credentials = FirefliesAuthConfig(api_key="  ")

    with pytest.raises(ValueError, match="API key is required"):
        await FirefliesSource.create(credentials)


# ------------------------------------------------------------------
# _parse_date()
# ------------------------------------------------------------------

def test_parse_date_valid():
    ms = 1700000000000
    dt = FirefliesSource._parse_date(ms)

    assert isinstance(dt, datetime)


def test_parse_date_none():
    assert FirefliesSource._parse_date(None) is None


def test_parse_date_invalid():
    assert FirefliesSource._parse_date(-999999999999999999999) is None


# ------------------------------------------------------------------
# _normalize_action_items()
# ------------------------------------------------------------------

def test_normalize_action_items_from_list():
    value = ["  task1  ", "task2", ""]
    result = FirefliesSource._normalize_action_items(value)

    assert result == ["task1", "task2"]


def test_normalize_action_items_from_string():
    value = "task1\n\ntask2\n"
    result = FirefliesSource._normalize_action_items(value)

    assert result == ["task1", "task2"]


def test_normalize_action_items_none():
    assert FirefliesSource._normalize_action_items(None) is None


# ------------------------------------------------------------------
# _graphql()
# ------------------------------------------------------------------

async def test_graphql_success():
    source = FirefliesSource()
    source.api_key = "test-key"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"ok": True}}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    result = await source._graphql(mock_client, " query { ok } ")

    assert result == {"data": {"ok": True}}
    mock_client.post.assert_called_once()


async def test_graphql_http_error_with_graphql_errors():
    source = FirefliesSource()
    source.api_key = "test-key"

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.json.return_value = {
        "errors": [{"message": "Invalid API key"}]
    }
    mock_response.request = httpx.Request("POST", "http://test")

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    with pytest.raises(httpx.HTTPStatusError, match="Invalid API key"):
        await source._graphql(mock_client, "query {}")


async def test_graphql_graphql_error_inside_200():
    source = FirefliesSource()
    source.api_key = "test-key"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "errors": [{"message": "Some GraphQL error"}]
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    with pytest.raises(ValueError, match="Some GraphQL error"):
        await source._graphql(mock_client, "query {}")


# ------------------------------------------------------------------
# _transcript_to_entity()
# ------------------------------------------------------------------

def test_transcript_to_entity_basic_mapping():
    source = FirefliesSource()
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

    entity = source._transcript_to_entity(transcript)

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

async def test_generate_entities_pagination():
    source = FirefliesSource()
    source.api_key = "test-key"

    first_page = {
        "data": {
            "transcripts": [{"id": "1", "title": "A", "sentences": []}]
        }
    }
    second_page = {
        "data": {
            "transcripts": []
        }
    }

    source._graphql = AsyncMock(side_effect=[first_page, second_page])

    mock_client = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None

    source.http_client = MagicMock(return_value=mock_cm)

    results = []
    async for entity in source.generate_entities():
        results.append(entity)

    assert len(results) == 1
    assert results[0].entity_id == "1"


# ------------------------------------------------------------------
# validate()
# ------------------------------------------------------------------

async def test_validate_success():
    source = FirefliesSource()
    source.api_key = "test-key"

    source._graphql = AsyncMock(return_value={"data": {}})

    mock_client = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None
    source.http_client = MagicMock(return_value=mock_cm)

    assert await source.validate() is True


async def test_validate_failure():
    source = FirefliesSource()
    source.api_key = "test-key"

    source._graphql = AsyncMock(side_effect=httpx.HTTPStatusError(
        "Error",
        request=httpx.Request("POST", "http://test"),
        response=MagicMock(),
    ))

    mock_client = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None
    source.http_client = MagicMock(return_value=mock_cm)

    assert await source.validate() is False
