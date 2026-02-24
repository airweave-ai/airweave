"""Unit tests for ServiceNow source."""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from airweave.platform.configs.auth import ServiceNowAuthConfig
from airweave.platform.entities.servicenow import (
    ServiceNowCatalogItemEntity,
    ServiceNowChangeRequestEntity,
    ServiceNowIncidentEntity,
    ServiceNowKnowledgeArticleEntity,
    ServiceNowProblemEntity,
)
from airweave.platform.sources.servicenow import (
    PAGE_LIMIT,
    _display_value,
    _parse_bool,
    _parse_datetime,
    _raw_value,
    ServiceNowSource,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_config() -> ServiceNowAuthConfig:
    """ServiceNow auth config for tests."""
    return ServiceNowAuthConfig(
        url="https://test-instance.service-now.com",
        username="test_user",
        password="test_pass",
    )


# ---------------------------------------------------------------------------
# _parse_datetime
# ---------------------------------------------------------------------------


def test_parse_datetime_none() -> None:
    assert _parse_datetime(None) is None


def test_parse_datetime_empty() -> None:
    assert _parse_datetime("") is None


def test_parse_datetime_iso() -> None:
    got = _parse_datetime("2024-01-15T10:30:00Z")
    assert got is not None
    assert got.year == 2024 and got.month == 1 and got.day == 15


def test_parse_datetime_space_separated() -> None:
    got = _parse_datetime("2024-01-15 10:30:00")
    assert got is not None
    assert got.year == 2024 and got.month == 1 and got.day == 15


def test_parse_datetime_invalid() -> None:
    assert _parse_datetime("not-a-date") is None


def test_parse_datetime_raises_value_error() -> None:
    """Covers except (ValueError, TypeError) in _parse_datetime."""
    assert _parse_datetime("2024-02-30 99:99:99") is None  # invalid date/time


# ---------------------------------------------------------------------------
# _display_value / _raw_value
# ---------------------------------------------------------------------------


def test_display_value_key_missing() -> None:
    assert _display_value({"a": "hello"}, "b") is None


def test_display_value_string() -> None:
    assert _display_value({"a": "hello"}, "a") == "hello"


def test_display_value_dict_display_value_only() -> None:
    assert _display_value({"a": {"display_value": "Label"}}, "a") == "Label"


def test_display_value_dict() -> None:
    assert _display_value({"a": {"display_value": "Label", "value": "x"}}, "a") == "Label"
    assert _display_value({"a": {"value": "x"}}, "a") == "x"


def test_display_value_non_dict_truthy() -> None:
    assert _display_value({"a": 123}, "a") == "123"


def test_raw_value_key_missing() -> None:
    assert _raw_value({"a": "x"}, "b") is None


def test_raw_value_string() -> None:
    assert _raw_value({"a": "hello"}, "a") == "hello"


def test_raw_value_dict_value_only() -> None:
    assert _raw_value({"a": {"value": "x"}}, "a") == "x"


def test_raw_value_dict() -> None:
    assert _raw_value({"a": {"value": "x", "display_value": "Label"}}, "a") == "x"
    assert _raw_value({"a": {"display_value": "Label"}}, "a") == "Label"


# ---------------------------------------------------------------------------
# _parse_bool
# ---------------------------------------------------------------------------


def test_parse_bool_none() -> None:
    assert _parse_bool(None) is None


def test_parse_bool_bool() -> None:
    assert _parse_bool(True) is True
    assert _parse_bool(False) is False


def test_parse_bool_string_false() -> None:
    """String 'false' must be False; bool('false') is True in Python."""
    assert _parse_bool("false") is False
    assert _parse_bool("False") is False
    assert _parse_bool("  false  ") is False


def test_parse_bool_string_true() -> None:
    assert _parse_bool("true") is True
    assert _parse_bool("True") is True
    assert _parse_bool("1") is True
    assert _parse_bool("yes") is True


def test_parse_bool_string_zero_empty() -> None:
    assert _parse_bool("0") is False
    assert _parse_bool("no") is False
    assert _parse_bool("") is False


# ---------------------------------------------------------------------------
# ServiceNowAuthConfig (url vs subdomain)
# ---------------------------------------------------------------------------


def test_auth_config_from_subdomain() -> None:
    """Composio provides subdomain; url is derived."""
    creds = ServiceNowAuthConfig(
        subdomain="my-instance",
        username="u",
        password="p",
    )
    assert creds.url == "https://my-instance.service-now.com"


def test_auth_config_from_subdomain_stripped() -> None:
    """Subdomain with trailing slash or spaces is normalized."""
    creds = ServiceNowAuthConfig(
        subdomain="  dev123  ",
        username="u",
        password="p",
    )
    assert creds.url == "https://dev123.service-now.com"


def test_auth_config_url_preferred_over_subdomain() -> None:
    """When both url and subdomain are set, url is used."""
    creds = ServiceNowAuthConfig(
        url="https://custom.service-now.com",
        subdomain="other",
        username="u",
        password="p",
    )
    assert creds.url == "https://custom.service-now.com"


def test_auth_config_requires_url_or_subdomain() -> None:
    """Either url or subdomain must be provided."""
    with pytest.raises(ValueError, match="Either 'url' or 'subdomain'"):
        ServiceNowAuthConfig(username="u", password="p")


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_sets_base_url_and_auth(auth_config: ServiceNowAuthConfig) -> None:
    source = await ServiceNowSource.create(auth_config)
    assert source._base_url == "https://test-instance.service-now.com"
    assert source._auth_header.startswith("Basic ")
    decoded = __import__("base64").b64decode(source._auth_header.split()[1]).decode()
    assert decoded == "test_user:test_pass"


@pytest.mark.asyncio
async def test_create_strips_trailing_slash(auth_config: ServiceNowAuthConfig) -> None:
    auth_config.url = "https://test.service-now.com/"
    source = await ServiceNowSource.create(auth_config)
    assert source._base_url == "https://test.service-now.com"


@pytest.mark.asyncio
async def test_create_with_config(auth_config: ServiceNowAuthConfig) -> None:
    source = await ServiceNowSource.create(auth_config, config={"foo": "bar"})
    assert source._base_url == "https://test-instance.service-now.com"


@pytest.mark.asyncio
async def test_create_from_subdomain_credentials() -> None:
    """create() works when credentials use subdomain (e.g. from Composio)."""
    creds = ServiceNowAuthConfig(
        subdomain="composio-instance",
        username="u",
        password="p",
    )
    source = await ServiceNowSource.create(creds)
    assert source._base_url == "https://composio-instance.service-now.com"
    decoded = __import__("base64").b64decode(source._auth_header.split()[1]).decode()
    assert decoded == "u:p"


# ---------------------------------------------------------------------------
# _table_url / _build_record_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_table_url_and_build_record_url(auth_config: ServiceNowAuthConfig) -> None:
    source = await ServiceNowSource.create(auth_config)
    assert source._table_url("incident") == (
        "https://test-instance.service-now.com/api/now/table/incident"
    )
    url = source._build_record_url("incident", "abc123")
    assert "incident" in url and "abc123" in url


@pytest.mark.asyncio
async def test_get_with_auth_returns_json(auth_config: ServiceNowAuthConfig) -> None:
    """Covers _get_with_auth: request, raise_for_status, return response.json()."""
    source = await ServiceNowSource.create(auth_config)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"result": [{"sys_id": "x"}]}
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    result = await source._get_with_auth(mock_client, "https://test/api/incident", {"a": 1})
    assert result == {"result": [{"sys_id": "x"}]}
    mock_response.raise_for_status.assert_called_once()
    mock_client.get.assert_called_once()


# ---------------------------------------------------------------------------
# generate_entities() with mocked HTTP
# ---------------------------------------------------------------------------


def _incident_result(sys_id: str = "inc-1", number: str = "INC0010001") -> dict:
    return {
        "sys_id": sys_id,
        "number": number,
        "short_description": "Test incident",
        "description": "Description",
        "state": "1",
        "priority": "3",
        "category": "",
        "assigned_to": "",
        "caller_id": "",
        "sys_created_on": "2024-01-15 10:00:00",
        "sys_updated_on": "2024-01-15 11:00:00",
    }


@pytest.mark.asyncio
async def test_generate_entities_incidents(auth_config: ServiceNowAuthConfig) -> None:
    source = await ServiceNowSource.create(auth_config)
    incident_payload = {"result": [_incident_result()]}
    empty = {"result": []}

    call_count = 0

    async def fake_get_with_auth(client: MagicMock, url: str, params: Any = None) -> dict:
        nonlocal call_count
        call_count += 1
        if "incident" in url:
            return incident_payload
        return empty

    with patch.object(source, "_get_with_auth", side_effect=fake_get_with_auth):
        entities: list = []
        async for e in source.generate_entities():
            entities.append(e)
    incidents = [e for e in entities if isinstance(e, ServiceNowIncidentEntity)]
    assert len(incidents) == 1
    assert incidents[0].entity_id == "inc-1"
    assert incidents[0].number == "INC0010001"
    assert incidents[0].short_description == "Test incident"
    assert incidents[0].web_url_value and ("incident" in incidents[0].web_url_value or "inc-1" in incidents[0].web_url_value)


@pytest.mark.asyncio
async def test_generate_incidents_with_dict_assignee_and_caller(
    auth_config: ServiceNowAuthConfig,
) -> None:
    """Covers assigned_to/caller_id as dict (display_value/value) and non-dict branches."""
    source = await ServiceNowSource.create(auth_config)
    rec = _incident_result("inc-2", "INC0010002")
    rec["assigned_to"] = {"display_value": "Jane Doe", "value": "user-123"}
    rec["caller_id"] = {"display_value": "John Caller", "value": "user-456"}
    payload = {"result": [rec]}
    empty = {"result": []}

    async def fake_get(client: MagicMock, url: str, params: Any = None) -> dict:
        if "incident" in url:
            return payload
        return empty

    with patch.object(source, "_get_with_auth", side_effect=fake_get):
        entities = [e async for e in source.generate_entities()]
    incidents = [e for e in entities if isinstance(e, ServiceNowIncidentEntity)]
    assert len(incidents) == 1
    assert incidents[0].assigned_to_name == "Jane Doe"
    assert incidents[0].caller_id_name == "John Caller"


@pytest.mark.asyncio
async def test_fetch_table_paginated_two_pages(auth_config: ServiceNowAuthConfig) -> None:
    """Covers pagination: first page full, second page partial."""
    source = await ServiceNowSource.create(auth_config)
    full_page = {"result": [{"sys_id": f"x{i}"} for i in range(PAGE_LIMIT)]}
    second_page = {"result": [{"sys_id": "y1"}]}
    call_count = 0

    async def fake_get(client: MagicMock, url: str, params: Any = None) -> dict:
        nonlocal call_count
        call_count += 1
        offset = (params or {}).get("sysparm_offset", 0)
        if offset == 0:
            return full_page
        return second_page

    with patch.object(source, "_get_with_auth", side_effect=fake_get):
        collected = []
        async with source.http_client() as client:
            async for rec in source._fetch_table_paginated(client, "incident", ["sys_id"]):
                collected.append(rec)
    assert len(collected) == PAGE_LIMIT + 1
    assert call_count == 2


def _kb_result(sys_id: str = "kb1", number: str = "KB001") -> dict:
    return {
        "sys_id": sys_id,
        "number": number,
        "short_description": "Article title",
        "text": "Body",
        "author": {"display_value": "Author Name", "value": "author-id"},
        "kb_knowledge_base": {"display_value": "KB Base", "value": "kbb-id"},
        "category": {"display_value": "Cat", "value": "cat-id"},
        "workflow_state": "published",
        "sys_created_on": "2024-01-15 10:00:00",
        "sys_updated_on": "2024-01-15 11:00:00",
    }


def _change_request_result(sys_id: str = "chg1", number: str = "CHG001") -> dict:
    return {
        "sys_id": sys_id,
        "number": number,
        "short_description": "Change",
        "description": "Desc",
        "state": "1",
        "phase": "build",
        "priority": "3",
        "type": "normal",
        "assigned_to": {"display_value": "Assignee", "value": "a1"},
        "requested_by": {"display_value": "Requester", "value": "r1"},
        "sys_created_on": "2024-01-15 10:00:00",
        "sys_updated_on": "2024-01-15 11:00:00",
    }


def _problem_result(sys_id: str = "prb1", number: str = "PRB001") -> dict:
    return {
        "sys_id": sys_id,
        "number": number,
        "short_description": "Problem",
        "description": "Desc",
        "state": "1",
        "priority": "3",
        "category": "network",
        "assigned_to": {"display_value": "Tech", "value": "t1"},
        "sys_created_on": "2024-01-15 10:00:00",
        "sys_updated_on": "2024-01-15 11:00:00",
    }


def _catalog_item_result(sys_id: str = "cat1") -> dict:
    return {
        "sys_id": sys_id,
        "name": "Catalog Item",
        "short_description": "Short",
        "description": "Desc",
        "category": {"display_value": "Hardware", "value": "hw"},
        "price": "0",
        "active": {"value": "true"},
        "sys_created_on": "2024-01-15 10:00:00",
        "sys_updated_on": "2024-01-15 11:00:00",
    }


@pytest.mark.asyncio
async def test_generate_all_entity_types(auth_config: ServiceNowAuthConfig) -> None:
    """Runs all five generators so KB, change_request, problem, sc_cat_item are covered."""
    source = await ServiceNowSource.create(auth_config)
    empty = {"result": []}

    async def fake_get(client: MagicMock, url: str, params: Any = None) -> dict:
        if "incident" in url:
            return {"result": [_incident_result("inc-1", "INC001")]}
        if "kb_knowledge" in url:
            return {"result": [_kb_result()]}
        if "change_request" in url:
            return {"result": [_change_request_result()]}
        if "problem" in url:
            return {"result": [_problem_result()]}
        if "sc_cat_item" in url:
            return {"result": [_catalog_item_result()]}
        return empty

    with patch.object(source, "_get_with_auth", side_effect=fake_get):
        entities = [e async for e in source.generate_entities()]
    by_type = {
        ServiceNowIncidentEntity: 0,
        ServiceNowKnowledgeArticleEntity: 0,
        ServiceNowChangeRequestEntity: 0,
        ServiceNowProblemEntity: 0,
        ServiceNowCatalogItemEntity: 0,
    }
    for e in entities:
        for cls in by_type:
            if isinstance(e, cls):
                by_type[cls] += 1
                break
    assert by_type[ServiceNowIncidentEntity] == 1
    assert by_type[ServiceNowKnowledgeArticleEntity] == 1
    assert by_type[ServiceNowChangeRequestEntity] == 1
    assert by_type[ServiceNowProblemEntity] == 1
    assert by_type[ServiceNowCatalogItemEntity] == 1


@pytest.mark.asyncio
async def test_generate_catalog_items_category_and_active_branches(
    auth_config: ServiceNowAuthConfig,
) -> None:
    """Covers category as non-dict and active as dict with value."""
    source = await ServiceNowSource.create(auth_config)
    rec = _catalog_item_result("cat2")
    rec["category"] = "string_category"
    rec["active"] = {"value": "false"}
    empty = {"result": []}

    async def fake_get(client: MagicMock, url: str, params: Any = None) -> dict:
        if "sc_cat_item" in url:
            return {"result": [rec]}
        if "incident" in url or "kb_knowledge" in url or "change_request" in url or "problem" in url:
            return empty
        return empty

    with patch.object(source, "_get_with_auth", side_effect=fake_get):
        entities = [e async for e in source.generate_entities()]
    catalog = [e for e in entities if isinstance(e, ServiceNowCatalogItemEntity)]
    assert len(catalog) == 1
    assert catalog[0].category_name == "string_category"
    # active parsed from string "false" -> False (bool("false") would wrongly be True)
    assert catalog[0].active is False


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success(auth_config: ServiceNowAuthConfig) -> None:
    source = await ServiceNowSource.create(auth_config)
    with patch.object(source, "_get_with_auth", new_callable=AsyncMock, return_value={"result": []}):
        result = await source.validate()
    assert result is True


@pytest.mark.asyncio
async def test_validate_failure(auth_config: ServiceNowAuthConfig) -> None:
    source = await ServiceNowSource.create(auth_config)
    with patch.object(
        source,
        "_get_with_auth",
        new_callable=AsyncMock,
        side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock()),
    ):
        result = await source.validate()
    assert result is False


@pytest.mark.asyncio
async def test_validate_failure_generic_exception(auth_config: ServiceNowAuthConfig) -> None:
    """Covers validate() except block and logger.warning."""
    source = await ServiceNowSource.create(auth_config)
    with patch.object(
        source,
        "_get_with_auth",
        new_callable=AsyncMock,
        side_effect=RuntimeError("connection failed"),
    ):
        result = await source.validate()
    assert result is False


# ---------------------------------------------------------------------------
# Entity types
# ---------------------------------------------------------------------------


def test_servicenow_incident_entity_has_required_fields() -> None:
    e = ServiceNowIncidentEntity(
        entity_id="x",
        breadcrumbs=[],
        name="INC001",
        sys_id="x",
        number="INC001",
        short_description="Test",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 2),
    )
    assert e.web_url == "" or "x" in (e.web_url_value or "")


def test_servicenow_knowledge_article_entity_has_required_fields() -> None:
    e = ServiceNowKnowledgeArticleEntity(
        entity_id="kb1",
        breadcrumbs=[],
        name="KB001",
        sys_id="kb1",
        number="KB001",
        short_description="Article",
    )
    assert e.entity_id == "kb1"
    assert e.web_url == ""


def test_servicenow_knowledge_article_entity_web_url_with_value() -> None:
    e = ServiceNowKnowledgeArticleEntity(
        entity_id="kb1",
        breadcrumbs=[],
        name="KB001",
        sys_id="kb1",
        number="KB001",
        short_description="Article",
        web_url_value="https://instance.service-now.com/kb?id=kb1",
    )
    assert e.web_url == "https://instance.service-now.com/kb?id=kb1"


def test_servicenow_change_request_entity_has_required_fields() -> None:
    e = ServiceNowChangeRequestEntity(
        entity_id="chg1",
        breadcrumbs=[],
        name="CHG001",
        sys_id="chg1",
        number="CHG001",
    )
    assert e.entity_id == "chg1"
    assert e.web_url == ""


def test_servicenow_change_request_entity_web_url_with_value() -> None:
    e = ServiceNowChangeRequestEntity(
        entity_id="chg1",
        breadcrumbs=[],
        name="CHG001",
        sys_id="chg1",
        number="CHG001",
        web_url_value="https://instance.service-now.com/chg?id=chg1",
    )
    assert e.web_url == "https://instance.service-now.com/chg?id=chg1"


def test_servicenow_problem_entity_has_required_fields() -> None:
    e = ServiceNowProblemEntity(
        entity_id="prb1",
        breadcrumbs=[],
        name="PRB001",
        sys_id="prb1",
        number="PRB001",
    )
    assert e.entity_id == "prb1"
    assert e.web_url == ""


def test_servicenow_problem_entity_web_url_with_value() -> None:
    e = ServiceNowProblemEntity(
        entity_id="prb1",
        breadcrumbs=[],
        name="PRB001",
        sys_id="prb1",
        number="PRB001",
        web_url_value="https://instance.service-now.com/prb?id=prb1",
    )
    assert e.web_url == "https://instance.service-now.com/prb?id=prb1"


def test_servicenow_catalog_item_entity_has_required_fields() -> None:
    e = ServiceNowCatalogItemEntity(
        entity_id="cat1",
        breadcrumbs=[],
        name="Catalog Item",
        sys_id="cat1",
    )
    assert e.entity_id == "cat1"
    assert e.web_url == ""


def test_servicenow_catalog_item_entity_web_url_with_value() -> None:
    e = ServiceNowCatalogItemEntity(
        entity_id="cat1",
        breadcrumbs=[],
        name="Catalog Item",
        sys_id="cat1",
        web_url_value="https://instance.service-now.com/cat?id=cat1",
    )
    assert e.web_url == "https://instance.service-now.com/cat?id=cat1"
