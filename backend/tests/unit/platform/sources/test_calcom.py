"""Unit tests for Cal.com (calcom) source, auth config, and connector config."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from airweave.platform.configs.auth import CalComAuthConfig
from airweave.platform.configs.config import CalComConfig
from airweave.platform.sources.calcom import (
    CAL_BOOKINGS_API_VERSION,
    CAL_EVENT_TYPES_API_VERSION,
    DEFAULT_CAL_API_BASE,
    CalSource,
)


def _mock_auth(api_key="cal_test_1234567890"):
    auth = AsyncMock()
    auth.get_token = AsyncMock(return_value=api_key)
    auth.supports_refresh = False
    auth.provider_kind = "credential"
    auth.credentials = MagicMock()
    auth.credentials.api_key = api_key
    return auth


def _mock_http_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


async def _cal_source(*, config: CalComConfig | None = None, api_key: str = "cal_test_1234567890"):
    return await CalSource.create(
        auth=_mock_auth(api_key=api_key),
        logger=MagicMock(),
        http_client=_mock_http_client(),
        config=config if config is not None else CalComConfig(),
    )


@pytest.mark.asyncio
async def test_create_sets_default_base_url():
    source = await _cal_source()
    assert source._base_url == DEFAULT_CAL_API_BASE


@pytest.mark.asyncio
async def test_create_normalizes_host_and_accepts_host_without_scheme():
    source = await _cal_source(config=CalComConfig(host="cal.example.com/"))
    assert source._base_url == "https://cal.example.com"


@pytest.mark.asyncio
async def test_get_uses_configured_base_url():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"ok": True})

    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_response)

    source = await CalSource.create(
        auth=_mock_auth(),
        logger=MagicMock(),
        http_client=client,
        config=CalComConfig(host="https://cal.example.com"),
    )

    result = await source._get("/v2/bookings", params={"take": 1})
    assert result == {"ok": True}
    client.get.assert_awaited_once()
    called_url = client.get.call_args.args[0]
    assert called_url == "https://cal.example.com/v2/bookings"

    called_headers = client.get.call_args.kwargs["headers"]
    assert called_headers["Authorization"].startswith("Bearer ")


@pytest.mark.asyncio
async def test_list_bookings_requests_all_statuses():
    source = await _cal_source(config=CalComConfig(host="https://cal.example.com"))

    async def fake_get(path, params=None, headers=None):
        # Return no items to stop pagination.
        return {"data": [], "pagination": {"hasNextPage": False, "returnedItems": 0}}

    with patch.object(source, "_get", new=AsyncMock(side_effect=fake_get)) as m:
        async for _ in source._list_bookings(after_updated_at="2026-01-01T00:00:00Z"):
            raise AssertionError("Expected no yielded items")

        assert m.await_count == 1
        _, kwargs = m.call_args
        params = kwargs["params"]
        assert params["status"] == "upcoming,recurring,past,cancelled,unconfirmed"
        assert params["afterUpdatedAt"] == "2026-01-01T00:00:00Z"
        assert kwargs["headers"]["cal-api-version"] == CAL_BOOKINGS_API_VERSION


@pytest.mark.asyncio
async def test_list_bookings_pagination_yields_all_pages():
    """Pagination advances skip and requests next page until hasNextPage is false."""
    source = await _cal_source(config=CalComConfig(host="https://cal.example.com"))

    page1 = [
        {"uid": "b1", "id": 1, "title": "Booking 1", "updatedAt": "2026-01-01T00:00:00Z"},
        {"uid": "b2", "id": 2, "title": "Booking 2", "updatedAt": "2026-01-01T00:00:00Z"},
    ]
    page2 = [
        {"uid": "b3", "id": 3, "title": "Booking 3", "updatedAt": "2026-01-01T00:00:00Z"},
    ]

    # Source mutates params in place; capture a copy at call time to assert later.
    params_snapshot: list = []

    async def fake_get(path, params=None, headers=None):
        params_snapshot.append(dict(params) if params else {})
        if path != "/v2/bookings":
            return {"data": [], "pagination": {"hasNextPage": False, "returnedItems": 0}}
        skip = (params or {}).get("skip", 0)
        if skip == 0:
            return {
                "data": page1,
                "pagination": {"hasNextPage": True, "returnedItems": len(page1)},
            }
        if skip == 2:
            return {
                "data": page2,
                "pagination": {"hasNextPage": False, "returnedItems": len(page2)},
            }
        return {"data": [], "pagination": {"hasNextPage": False, "returnedItems": 0}}

    with patch.object(source, "_get", new=AsyncMock(side_effect=fake_get)) as m:
        items = []
        async for b in source._list_bookings():
            items.append(b)

        assert len(items) == 3
        assert items[0]["uid"] == "b1"
        assert items[1]["uid"] == "b2"
        assert items[2]["uid"] == "b3"

        assert m.await_count == 2
        assert params_snapshot[0]["skip"] == 0
        assert params_snapshot[0]["take"] == 100
        assert params_snapshot[1]["skip"] == 2
        assert params_snapshot[1]["take"] == 100


@pytest.mark.asyncio
async def test_list_bookings_pagination_stops_when_no_items_returned():
    """Pagination stops when returnedItems is 0 even if hasNextPage is true (defensive)."""
    source = await _cal_source(config=CalComConfig(host="https://cal.example.com"))

    async def fake_get(path, params=None, headers=None):
        return {"data": [], "pagination": {"hasNextPage": True, "returnedItems": 0}}

    with patch.object(source, "_get", new=AsyncMock(side_effect=fake_get)) as m:
        items = []
        async for b in source._list_bookings():
            items.append(b)
        assert len(items) == 0
        assert m.await_count == 1


@pytest.mark.asyncio
async def test_list_event_types_pagination_yields_all_pages():
    """Event types pagination advances skip and requests next page until hasNextPage is false."""
    source = await _cal_source(config=CalComConfig(host="https://cal.example.com"))

    page1 = [
        {"id": 1, "title": "Type 1", "slug": "type-1", "lengthInMinutes": 30},
        {"id": 2, "title": "Type 2", "slug": "type-2", "lengthInMinutes": 60},
    ]
    page2 = [
        {"id": 3, "title": "Type 3", "slug": "type-3", "lengthInMinutes": 90},
    ]

    # Source mutates params in place; capture a copy at call time to assert later.
    params_snapshot: list = []

    async def fake_get(path, params=None, headers=None):
        params_snapshot.append(dict(params) if params else {})
        if path != "/v2/event-types":
            return {"data": [], "pagination": {"hasNextPage": False, "returnedItems": 0}}
        skip = (params or {}).get("skip", 0)
        if skip == 0:
            return {
                "data": page1,
                "pagination": {"hasNextPage": True, "returnedItems": len(page1)},
            }
        if skip == 2:
            return {
                "data": page2,
                "pagination": {"hasNextPage": False, "returnedItems": len(page2)},
            }
        return {"data": [], "pagination": {"hasNextPage": False, "returnedItems": 0}}

    with patch.object(source, "_get", new=AsyncMock(side_effect=fake_get)) as m:
        items = []
        async for et in source._list_event_types():
            items.append(et)

        assert len(items) == 3
        assert items[0]["id"] == 1 and items[0]["slug"] == "type-1"
        assert items[1]["id"] == 2 and items[1]["slug"] == "type-2"
        assert items[2]["id"] == 3 and items[2]["slug"] == "type-3"

        assert m.await_count == 2
        assert params_snapshot[0]["skip"] == 0
        assert params_snapshot[0]["take"] == 100
        assert params_snapshot[1]["skip"] == 2
        assert params_snapshot[1]["take"] == 100
        assert m.call_args_list[0].kwargs["headers"]["cal-api-version"] == CAL_EVENT_TYPES_API_VERSION


@pytest.mark.asyncio
async def test_list_event_types_single_page_when_no_pagination():
    """Event types with no pagination in response yield one page and stop (backward compatible)."""
    source = await _cal_source(config=CalComConfig(host="https://cal.example.com"))

    single_page = [
        {"id": 10, "title": "Only", "slug": "only", "lengthInMinutes": 15},
    ]

    async def fake_get(path, params=None, headers=None):
        # No pagination key - simulates API that doesn't return pagination.
        return {"data": single_page}

    with patch.object(source, "_get", new=AsyncMock(side_effect=fake_get)) as m:
        items = []
        async for et in source._list_event_types():
            items.append(et)
        assert len(items) == 1
        assert items[0]["id"] == 10
        assert m.await_count == 1


@pytest.mark.asyncio
async def test_validate_uses_configured_host_in_ping_url():
    source = await _cal_source(config=CalComConfig(host="https://cal.example.com"))

    with patch.object(source, "_get", new=AsyncMock(return_value={"data": []})) as m:
        await source.validate()
        m.assert_awaited_once()
        assert m.call_args[0][0] == "/v2/bookings"
        assert m.call_args.kwargs["params"] == {"take": 1, "skip": 0}
        assert m.call_args.kwargs["headers"]["cal-api-version"] == CAL_BOOKINGS_API_VERSION


# ---------------------------------------------------------------------------
# CalComAuthConfig (auth.py coverage)
# ---------------------------------------------------------------------------


def test_calcom_auth_config_rejects_empty_api_key():
    """CalComAuthConfig.validate_api_key raises when api_key is empty."""
    with pytest.raises(ValidationError):
        CalComAuthConfig(api_key="")


def test_calcom_auth_config_rejects_whitespace_only_api_key():
    """CalComAuthConfig.validate_api_key raises when api_key is only whitespace."""
    with pytest.raises(ValidationError):
        CalComAuthConfig(api_key="   \t  ")


# ---------------------------------------------------------------------------
# CalComConfig.normalize_host (config.py coverage)
# ---------------------------------------------------------------------------


def test_calcom_config_default_host():
    """CalComConfig uses default host when not provided."""
    cfg = CalComConfig()
    assert cfg.host == "https://api.cal.com"


def test_calcom_config_normalize_host_none():
    """normalize_host returns default when host is None."""
    cfg = CalComConfig(host=None)
    assert cfg.host == "https://api.cal.com"


def test_calcom_config_normalize_host_non_string_raises():
    """normalize_host raises when host is not a string."""
    with pytest.raises(ValidationError):
        CalComConfig(host=123)


def test_calcom_config_normalize_host_empty_string_returns_default():
    """normalize_host returns default when host is empty or whitespace."""
    cfg = CalComConfig(host="   ")
    assert cfg.host == "https://api.cal.com"


def test_calcom_config_normalize_host_adds_https_when_no_scheme():
    """normalize_host adds https:// when host has no scheme."""
    cfg = CalComConfig(host="cal.example.com")
    assert cfg.host == "https://cal.example.com"


def test_calcom_config_normalize_host_strips_trailing_slash():
    """normalize_host strips trailing slash."""
    cfg = CalComConfig(host="https://cal.example.com/api/")
    assert cfg.host == "https://cal.example.com/api"
