"""Unit tests for the Freshdesk source connector."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from airweave.platform.configs.auth import FreshdeskAuthConfig
from airweave.platform.configs.config import FreshdeskConfig
from airweave.platform.entities.freshdesk import (
    FreshdeskCompanyEntity,
    FreshdeskContactEntity,
    FreshdeskConversationEntity,
    FreshdeskSolutionArticleEntity,
    FreshdeskTicketEntity,
)
from airweave.platform.sources.freshdesk import (
    FreshdeskSource,
    _parse_datetime,
    _now,
)


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_stores_api_key_and_domain():
    """create() should set api_key from auth_config and domain from config."""
    auth = FreshdeskAuthConfig(api_key="test-key-123")
    config = {"domain": "mycompany"}
    source = await FreshdeskSource.create(auth, config)
    assert source.api_key == "test-key-123"
    assert source.domain == "mycompany"


@pytest.mark.asyncio
async def test_create_domain_defaults_to_empty():
    """create() with no config or empty config should set domain to empty string."""
    auth = FreshdeskAuthConfig(api_key="key")
    source = await FreshdeskSource.create(auth, None)
    assert source.domain == ""
    source2 = await FreshdeskSource.create(auth, {})
    assert source2.domain == ""


# ---------------------------------------------------------------------------
# _base_url, URL builders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_base_url():
    """_base_url() should return correct Freshdesk API base URL."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "acme"})
    assert source._base_url() == "https://acme.freshdesk.com/api/v2"
    assert source._build_ticket_url(42) == "https://acme.freshdesk.com/a/tickets/42"
    assert source._build_contact_url(1) == "https://acme.freshdesk.com/a/contacts/1"
    assert source._build_company_url(2) == "https://acme.freshdesk.com/a/companies/2"
    assert "solutions/articles/99" in source._build_article_url(99)


# ---------------------------------------------------------------------------
# _parse_link_header()
# ---------------------------------------------------------------------------


def test_parse_link_header_returns_next_url():
    """_parse_link_header should extract next page URL from Link header."""
    source = FreshdeskSource()
    source.api_key = "k"
    source.domain = "d"
    link = '<https://d.freshdesk.com/api/v2/tickets?page=2>; rel="next"'
    assert source._parse_link_header(link) == "https://d.freshdesk.com/api/v2/tickets?page=2"


def test_parse_link_header_returns_none_when_empty():
    """_parse_link_header should return None for None or empty."""
    source = FreshdeskSource()
    source.api_key = "k"
    source.domain = "d"
    assert source._parse_link_header(None) is None
    assert source._parse_link_header("") is None


def test_parse_link_header_returns_none_when_no_next():
    """_parse_link_header should return None when rel=next is absent."""
    source = FreshdeskSource()
    source.api_key = "k"
    source.domain = "d"
    link = '<https://example.com/prev>; rel="prev"'
    assert source._parse_link_header(link) is None


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success():
    """validate() should return True when GET /agents/me returns 200."""
    auth = FreshdeskAuthConfig(api_key="valid-key")
    source = await FreshdeskSource.create(auth, {"domain": "test"})

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch.object(source, "http_client") as mock_http_client:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_http_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_http_client.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch.object(source, "_get_with_auth", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await source.validate()
    assert result is True
    mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_validate_fails_when_missing_api_key():
    """validate() should return False when api_key is missing."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "d"})
    source.api_key = None
    result = await source.validate()
    assert result is False


@pytest.mark.asyncio
async def test_validate_fails_when_missing_domain():
    """validate() should return False when domain is missing."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "d"})
    source.domain = None
    result = await source.validate()
    assert result is False


@pytest.mark.asyncio
async def test_validate_fails_on_http_error():
    """validate() should return False when API returns non-2xx."""
    auth = FreshdeskAuthConfig(api_key="bad")
    source = await FreshdeskSource.create(auth, {"domain": "d"})

    with patch.object(source, "http_client") as mock_http_client:
        mock_client = AsyncMock()
        mock_http_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_http_client.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch.object(source, "_get_with_auth", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError(
                "401", request=MagicMock(), response=MagicMock(status_code=401)
            )
            result = await source.validate()
    assert result is False

# ---------------------------------------------------------------------------
# _generate_ticket_entities (entity mapping)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_ticket_entities_maps_api_to_entity():
    """Ticket API payload should map to FreshdeskTicketEntity with correct fields."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "test"})
    ticket_payload = {
        "id": 100,
        "subject": "Help with login",
        "description": "<p>Cannot log in</p>",
        "description_text": "Cannot log in",
        "status": 2,
        "priority": 1,
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T11:00:00Z",
    }

    async def fake_paginate(client, path, params=None):
        yield ticket_payload

    entities = []
    with patch.object(source, "_paginate_list", fake_paginate):
        async for entity in source._generate_ticket_entities(AsyncMock()):
            entities.append(entity)

    assert len(entities) == 1
    ent = entities[0]
    assert isinstance(ent, FreshdeskTicketEntity)
    assert ent.entity_id == "100"
    assert ent.subject == "Help with login"
    assert ent.ticket_id == 100
    assert "tickets/100" in (ent.web_url_value or "")


# ---------------------------------------------------------------------------
# _generate_company_entities (entity mapping)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_company_entities_maps_api_to_entity():
    """Company API payload should map to FreshdeskCompanyEntity."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "test"})
    company_payload = {
        "id": 5,
        "name": "Acme Corp",
        "description": "A company",
        "created_at": "2024-06-01T00:00:00Z",
        "updated_at": "2024-06-02T00:00:00Z",
    }

    async def fake_paginate(client, path, params=None):
        yield company_payload

    entities = []
    with patch.object(source, "_paginate_list", fake_paginate):
        async for entity in source._generate_company_entities(AsyncMock()):
            entities.append(entity)

    assert len(entities) == 1
    ent = entities[0]
    assert isinstance(ent, FreshdeskCompanyEntity)
    assert ent.entity_id == "5"
    assert ent.name == "Acme Corp"
    assert "companies/5" in (ent.web_url_value or "")


# ---------------------------------------------------------------------------
# FreshdeskConfig (config.py coverage)
# ---------------------------------------------------------------------------


def test_freshdesk_config_schema():
    """FreshdeskConfig has required domain field."""
    cfg = FreshdeskConfig(domain="mycompany")
    assert cfg.domain == "mycompany"


# ---------------------------------------------------------------------------
# _parse_datetime, _now
# ---------------------------------------------------------------------------


def test_parse_datetime_none_or_empty():
    """_parse_datetime returns None for None or empty."""
    assert _parse_datetime(None) is None
    assert _parse_datetime("") is None


def test_parse_datetime_valid_iso8601():
    """_parse_datetime parses Z-suffix to timezone-aware datetime."""
    result = _parse_datetime("2025-01-15T10:00:00Z")
    assert result is not None
    assert result.tzinfo is not None
    assert result.year == 2025 and result.month == 1 and result.day == 15


def test_parse_datetime_invalid_raises_returns_none():
    """_parse_datetime returns None on invalid input."""
    assert _parse_datetime("not-a-date") is None
    assert _parse_datetime("2025-13-45T00:00:00Z") is None


def test_now_returns_utc_datetime():
    """_now returns timezone-aware UTC datetime."""
    result = _now()
    assert result.tzinfo is not None


# ---------------------------------------------------------------------------
# Entity web_url fallback (when web_url_value is None)
# ---------------------------------------------------------------------------

_UTC = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_ticket_entity_web_url_fallback():
    """FreshdeskTicketEntity.web_url returns '' when web_url_value is None."""
    ent = FreshdeskTicketEntity(
        entity_id="1",
        breadcrumbs=[],
        name="t",
        created_at=_UTC,
        updated_at=_UTC,
        ticket_id=1,
        subject="t",
        created_at_value=_UTC,
        updated_at_value=_UTC,
        web_url_value=None,
    )
    assert ent.web_url == ""


def test_conversation_entity_web_url_fallback():
    """FreshdeskConversationEntity.web_url returns '' when web_url_value is None."""
    ent = FreshdeskConversationEntity(
        entity_id="1_2",
        breadcrumbs=[],
        name="conv",
        created_at=_UTC,
        updated_at=_UTC,
        conversation_id=2,
        ticket_id=1,
        ticket_subject="t",
        body_text="body",
        created_at_value=_UTC,
        updated_at_value=_UTC,
        web_url_value=None,
    )
    assert ent.web_url == ""


def test_contact_entity_web_url_fallback():
    """FreshdeskContactEntity.web_url returns '' when web_url_value is None."""
    ent = FreshdeskContactEntity(
        entity_id="1",
        breadcrumbs=[],
        name="c",
        created_at=_UTC,
        updated_at=_UTC,
        contact_id=1,
        created_at_value=_UTC,
        updated_at_value=_UTC,
        web_url_value=None,
    )
    assert ent.web_url == ""


def test_company_entity_web_url_fallback():
    """FreshdeskCompanyEntity.web_url returns '' when web_url_value is None."""
    ent = FreshdeskCompanyEntity(
        entity_id="1",
        breadcrumbs=[],
        name="co",
        created_at=_UTC,
        updated_at=_UTC,
        company_id=1,
        created_at_value=_UTC,
        updated_at_value=_UTC,
        web_url_value=None,
    )
    assert ent.web_url == ""


def test_solution_article_entity_web_url_fallback():
    """FreshdeskSolutionArticleEntity.web_url returns '' when web_url_value is None."""
    ent = FreshdeskSolutionArticleEntity(
        entity_id="1",
        breadcrumbs=[],
        name="a",
        created_at=_UTC,
        updated_at=_UTC,
        article_id=1,
        title="a",
        created_at_value=_UTC,
        updated_at_value=_UTC,
        web_url_value=None,
    )
    assert ent.web_url == ""


# ---------------------------------------------------------------------------
# _paginate_list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_paginate_list_yields_list_response():
    """_paginate_list yields items from a list JSON response."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "fd"})
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": 1}, {"id": 2}]
    mock_response.headers = {}
    mock_response.raise_for_status = MagicMock()

    with patch.object(source, "_get_with_auth", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        items = []
        async for item in source._paginate_list(mock_client, "/companies"):
            items.append(item)
    assert items == [{"id": 1}, {"id": 2}]
    assert mock_get.call_count == 1


@pytest.mark.asyncio
async def test_paginate_list_uses_results_key_when_not_list():
    """_paginate_list uses 'results' or 'records' when response is a dict."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "fd"})
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": [{"id": 10}]}
    mock_response.headers = {}
    mock_response.raise_for_status = MagicMock()

    with patch.object(source, "_get_with_auth", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        items = []
        async for item in source._paginate_list(mock_client, "/contacts"):
            items.append(item)
    assert items == [{"id": 10}]


@pytest.mark.asyncio
async def test_paginate_list_follows_link_header():
    """_paginate_list follows Link rel=next to next page."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "fd"})
    base = source._base_url()
    mock_client = AsyncMock()
    r1 = MagicMock()
    r1.json.return_value = [{"id": 1}]
    r1.headers = {"link": f'<{base}/companies?page=2>; rel="next"'}
    r1.raise_for_status = MagicMock()
    r2 = MagicMock()
    r2.json.return_value = [{"id": 2}]
    r2.headers = {}
    r2.raise_for_status = MagicMock()

    with patch.object(source, "_get_with_auth", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [r1, r2]
        items = []
        async for item in source._paginate_list(mock_client, "/companies"):
            items.append(item)
    assert items == [{"id": 1}, {"id": 2}]
    assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_paginate_list_increments_page_when_no_link():
    """_paginate_list increments page when full page and no Link next."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "fd"})
    mock_client = AsyncMock()
    full_page = [{"id": i} for i in range(100)]
    r1 = MagicMock()
    r1.json.return_value = full_page
    r1.headers = {}
    r1.raise_for_status = MagicMock()
    r2 = MagicMock()
    r2.json.return_value = [{"id": 100}]
    r2.headers = {}
    r2.raise_for_status = MagicMock()

    with patch.object(source, "_get_with_auth", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [r1, r2]
        items = []
        async for item in source._paginate_list(mock_client, "/tickets"):
            items.append(item)
    assert len(items) == 101
    assert mock_get.call_count == 2
    # Second call uses page=2 (first call reuses the same params dict which gets mutated)
    assert mock_get.call_args_list[1][1].get("params", {}).get("page") == 2


# ---------------------------------------------------------------------------
# _generate_contact_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_contact_entities_maps_api_to_entity():
    """Contact API payload maps to FreshdeskContactEntity."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "test"})
    contact_payload = {
        "id": 7,
        "name": "Jane Doe",
        "email": "jane@example.com",
        "created_at": "2024-06-01T00:00:00Z",
        "updated_at": "2024-06-02T00:00:00Z",
    }

    async def fake_paginate(client, path, params=None):
        yield contact_payload

    entities = []
    with patch.object(source, "_paginate_list", fake_paginate):
        async for entity in source._generate_contact_entities(AsyncMock()):
            entities.append(entity)
    assert len(entities) == 1
    ent = entities[0]
    assert isinstance(ent, FreshdeskContactEntity)
    assert ent.entity_id == "7"
    assert ent.name == "Jane Doe"
    assert ent.email == "jane@example.com"


# ---------------------------------------------------------------------------
# _generate_conversation_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_conversation_entities_maps_api_to_entity():
    """Conversation payload maps to FreshdeskConversationEntity."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "test"})
    ticket_payload = {"id": 10, "subject": "Help"}
    conv_payload = {
        "id": 20,
        "body_text": "Reply text",
        "created_at": "2024-06-01T00:00:00Z",
        "updated_at": "2024-06-02T00:00:00Z",
        "user_id": 1,
        "incoming": True,
        "private": False,
    }

    async def fake_paginate(client, path, params=None):
        yield ticket_payload

    mock_conv_response = MagicMock()
    mock_conv_response.json.return_value = [conv_payload]
    mock_conv_response.headers = {}

    with patch.object(source, "_paginate_list", fake_paginate), patch.object(
        source, "_get_with_auth", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = mock_conv_response
        entities = []
        async for entity in source._generate_conversation_entities(AsyncMock()):
            entities.append(entity)
    assert len(entities) == 1
    ent = entities[0]
    assert isinstance(ent, FreshdeskConversationEntity)
    assert ent.entity_id == "10_20"
    assert ent.conversation_id == 20
    assert ent.ticket_id == 10
    assert ent.body_text == "Reply text"


# ---------------------------------------------------------------------------
# _generate_solution_article_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_solution_article_entities_maps_api_to_entity():
    """Solution article payload maps to FreshdeskSolutionArticleEntity."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "test"})
    cat_response = MagicMock()
    cat_response.json.return_value = [{"id": 1, "name": "Cat1"}]
    folder_response = MagicMock()
    folder_response.json.return_value = [{"id": 2, "name": "Folder1"}]
    article_response = MagicMock()
    article_response.json.return_value = [
        {
            "id": 100,
            "title": "How to reset",
            "created_at": "2024-06-01T00:00:00Z",
            "updated_at": "2024-06-02T00:00:00Z",
        }
    ]
    article_response.headers = {}
    subfolders_response = MagicMock()
    subfolders_response.json.return_value = []  # no nested subfolders

    with patch.object(source, "_get_with_auth", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [
            cat_response,
            folder_response,
            article_response,
            subfolders_response,
        ]
        entities = []
        async for entity in source._generate_solution_article_entities(AsyncMock()):
            entities.append(entity)
    assert len(entities) == 1
    ent = entities[0]
    assert isinstance(ent, FreshdeskSolutionArticleEntity)
    assert ent.entity_id == "100"
    assert ent.title == "How to reset"
    assert ent.article_id == 100


# ---------------------------------------------------------------------------
# generate_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_entities_yields_from_all_generators():
    """generate_entities yields from companies, contacts, tickets, conversations, articles."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "test"})
    seen = []

    async def fake_company(client):
        yield FreshdeskCompanyEntity(
            entity_id="1",
            breadcrumbs=[],
            name="C",
            created_at=_UTC,
            updated_at=_UTC,
            company_id=1,
            created_at_value=_UTC,
            updated_at_value=_UTC,
            web_url_value="https://x.freshdesk.com/a/companies/1",
        )
        seen.append("company")

    async def fake_contact(client):
        yield FreshdeskContactEntity(
            entity_id="1",
            breadcrumbs=[],
            name="C",
            created_at=_UTC,
            updated_at=_UTC,
            contact_id=1,
            created_at_value=_UTC,
            updated_at_value=_UTC,
            web_url_value="https://x.freshdesk.com/a/contacts/1",
        )
        seen.append("contact")

    async def fake_ticket(client):
        yield FreshdeskTicketEntity(
            entity_id="1",
            breadcrumbs=[],
            name="T",
            created_at=_UTC,
            updated_at=_UTC,
            ticket_id=1,
            subject="T",
            created_at_value=_UTC,
            updated_at_value=_UTC,
            web_url_value="https://x.freshdesk.com/a/tickets/1",
        )
        seen.append("ticket")

    async def fake_conv(client):
        yield FreshdeskConversationEntity(
            entity_id="1_2",
            breadcrumbs=[],
            name="Conv",
            created_at=_UTC,
            updated_at=_UTC,
            conversation_id=2,
            ticket_id=1,
            ticket_subject="T",
            body_text="b",
            created_at_value=_UTC,
            updated_at_value=_UTC,
            web_url_value="https://x.freshdesk.com/a/tickets/1",
        )
        seen.append("conversation")

    async def fake_article(client):
        yield FreshdeskSolutionArticleEntity(
            entity_id="1",
            breadcrumbs=[],
            name="A",
            created_at=_UTC,
            updated_at=_UTC,
            article_id=1,
            title="A",
            created_at_value=_UTC,
            updated_at_value=_UTC,
            web_url_value="https://x.freshdesk.com/support/solutions/articles/1",
        )
        seen.append("article")

    with patch.object(source, "_generate_company_entities", fake_company), patch.object(
        source, "_generate_contact_entities", fake_contact
    ), patch.object(source, "_generate_ticket_entities", fake_ticket), patch.object(
        source, "_generate_conversation_entities", fake_conv
    ), patch.object(
        source, "_generate_solution_article_entities", fake_article
    ), patch.object(source, "http_client") as mock_http:
        mock_client = AsyncMock()
        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=None)
        out = []
        async for entity in source.generate_entities():
            out.append(entity)
    assert len(out) == 5
    assert seen == ["company", "contact", "ticket", "conversation", "article"]


# ---------------------------------------------------------------------------
# validate() - generic Exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_fails_on_generic_exception():
    """validate() returns False on unexpected exception."""
    auth = FreshdeskAuthConfig(api_key="k")
    source = await FreshdeskSource.create(auth, {"domain": "d"})
    with patch.object(source, "http_client") as mock_http_client:
        mock_http_client.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("connection failed")
        )
        mock_http_client.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await source.validate()
    assert result is False
