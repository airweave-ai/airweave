"""Unit tests for the Calendly source connector."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from airweave.platform.entities.calendly import (
    CalendlyEventTypeEntity,
    CalendlyUserEntity,
)
from airweave.platform.sources.calendly import CalendlySource


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_stores_token():
    """create() should set access_token and rate limit state."""
    source = await CalendlySource.create("test-token", None)
    assert source.access_token == "test-token"
    assert hasattr(source, "_last_request_time")
    assert source._rate_limit_lock is not None


@pytest.mark.asyncio
async def test_create_accepts_config():
    """create() should accept optional config without raising."""
    source = await CalendlySource.create("token", {})
    assert source.access_token == "token"


# ---------------------------------------------------------------------------
# _parse_datetime()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_datetime_valid_iso_z():
    """_parse_datetime should parse ISO 8601 with Z suffix."""
    source = await CalendlySource.create("t", None)
    dt = source._parse_datetime("2023-01-15T12:00:00.000000Z")
    assert isinstance(dt, datetime)
    assert dt.year == 2023
    assert dt.month == 1
    assert dt.day == 15
    assert dt.hour == 12
    assert dt.tzinfo is not None


@pytest.mark.asyncio
async def test_parse_datetime_none():
    """_parse_datetime should return None for None or empty."""
    source = await CalendlySource.create("t", None)
    assert source._parse_datetime(None) is None
    assert source._parse_datetime("") is None


@pytest.mark.asyncio
async def test_parse_datetime_invalid():
    """_parse_datetime should return None for invalid strings."""
    source = await CalendlySource.create("t", None)
    assert source._parse_datetime("not-a-date") is None


# ---------------------------------------------------------------------------
# _normalize_uri()
# ---------------------------------------------------------------------------


def test_normalize_uri_strips_trailing_slash():
    """_normalize_uri should strip trailing slashes."""
    uri = "https://api.calendly.com/event_types/abc123/"
    assert CalendlySource._normalize_uri(uri) == "https://api.calendly.com/event_types/abc123"


def test_normalize_uri_empty_and_none():
    """_normalize_uri should return empty string for None or empty."""
    assert CalendlySource._normalize_uri(None) == ""
    assert CalendlySource._normalize_uri("") == ""


def test_normalize_uri_unchanged_when_no_trailing_slash():
    """_normalize_uri should leave URIs without trailing slash unchanged."""
    uri = "https://api.calendly.com/users/me"
    assert CalendlySource._normalize_uri(uri) == uri


# ---------------------------------------------------------------------------
# _get_paginated()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_paginated_single_page():
    """_get_paginated should yield all items from a single page."""
    source = await CalendlySource.create("token", None)
    mock_client = AsyncMock()
    source._get_with_auth = AsyncMock(
        return_value={
            "collection": [{"uri": "https://api.calendly.com/event_types/1", "name": "Type A"}],
            "pagination": {},
        }
    )
    items = []
    async for item in source._get_paginated(mock_client, "https://api.calendly.com/event_types"):
        items.append(item)
    assert len(items) == 1
    assert items[0]["uri"] == "https://api.calendly.com/event_types/1"
    assert items[0]["name"] == "Type A"
    source._get_with_auth.assert_called_once()


@pytest.mark.asyncio
async def test_get_paginated_two_pages():
    """_get_paginated should follow next_page_token and yield all pages."""
    source = await CalendlySource.create("token", None)
    mock_client = AsyncMock()
    source._get_with_auth = AsyncMock(
        side_effect=[
            {
                "collection": [{"uri": "https://api.calendly.com/event_types/1", "name": "A"}],
                "pagination": {"next_page_token": "token2"},
            },
            {
                "collection": [{"uri": "https://api.calendly.com/event_types/2", "name": "B"}],
                "pagination": {},
            },
        ]
    )
    items = []
    async for item in source._get_paginated(mock_client, "https://api.calendly.com/event_types"):
        items.append(item)
    assert len(items) == 2
    assert items[0]["name"] == "A"
    assert items[1]["name"] == "B"
    assert source._get_with_auth.await_count == 2


# ---------------------------------------------------------------------------
# _generate_user_entity()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_user_entity_success():
    """_generate_user_entity should return CalendlyUserEntity from /users/me response."""
    source = await CalendlySource.create("token", None)
    mock_client = AsyncMock()
    source._get_with_auth = AsyncMock(
        return_value={
            "resource": {
                "uri": "https://api.calendly.com/users/USER_UUID",
                "name": "Test User",
                "email": "user@example.com",
                "scheduling_url": "https://calendly.com/test",
                "timezone": "America/New_York",
            }
        }
    )
    entity = await source._generate_user_entity(mock_client)
    assert entity is not None
    assert isinstance(entity, CalendlyUserEntity)
    assert entity.uri == "https://api.calendly.com/users/USER_UUID"
    assert entity.name == "Test User"
    assert entity.email == "user@example.com"


@pytest.mark.asyncio
async def test_generate_user_entity_empty_resource_returns_none():
    """_generate_user_entity should return None when resource is missing."""
    source = await CalendlySource.create("token", None)
    mock_client = AsyncMock()
    source._get_with_auth = AsyncMock(return_value={})
    entity = await source._generate_user_entity(mock_client)
    assert entity is None


# ---------------------------------------------------------------------------
# generate_entities() with mocked API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_entities_yields_user_and_event_types():
    """generate_entities should yield user and event type entities when API returns them."""
    source = await CalendlySource.create("test-token", None)
    user_me = {
        "resource": {
            "uri": "https://api.calendly.com/users/USER_UUID",
            "name": "Test User",
            "current_organization": "https://api.calendly.com/organizations/ORG_UUID",
        }
    }
    event_types_list = {
        "collection": [
            {
                "uri": "https://api.calendly.com/event_types/ET_UUID",
                "name": "30 Min Meeting",
                "active": True,
                "slug": "30min",
            }
        ],
        "pagination": {},
    }
    event_type_detail = {
        "resource": {
            "uri": "https://api.calendly.com/event_types/ET_UUID",
            "name": "30 Min Meeting",
            "active": True,
            "slug": "30min",
            "description_plain": "A short meeting",
            "duration": 30,
        }
    }
    scheduled_events_empty = {"collection": [], "pagination": {}}

    call_count = 0

    async def mock_get_with_auth(client, url, params=None):
        nonlocal call_count
        call_count += 1
        if "users/me" in url:
            return user_me
        if "event_types" in url and "ET_UUID" not in url:
            return event_types_list
        if "event_types/ET_UUID" in url:
            return event_type_detail
        if "scheduled_events" in url and "invitees" not in url:
            return scheduled_events_empty
        return {}

    source._get_with_auth = AsyncMock(side_effect=mock_get_with_auth)
    mock_cm = AsyncMock()
    mock_client = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None
    source.http_client = MagicMock(return_value=mock_cm)

    entities = []
    async for entity in source.generate_entities():
        entities.append(entity)

    assert len(entities) >= 1
    user_entities = [e for e in entities if isinstance(e, CalendlyUserEntity)]
    event_type_entities = [e for e in entities if isinstance(e, CalendlyEventTypeEntity)]
    assert len(user_entities) == 1
    assert user_entities[0].name == "Test User"
    assert len(event_type_entities) == 1
    assert event_type_entities[0].uri == "https://api.calendly.com/event_types/ET_UUID"
    assert event_type_entities[0].name == "30 Min Meeting"


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success():
    """validate() should return True when OAuth ping succeeds."""
    source = await CalendlySource.create("token", None)
    source._validate_oauth2 = AsyncMock(return_value=True)
    assert await source.validate() is True


@pytest.mark.asyncio
async def test_validate_failure():
    """validate() should return False when OAuth ping fails."""
    source = await CalendlySource.create("token", None)
    source._validate_oauth2 = AsyncMock(return_value=False)
    assert await source.validate() is False
