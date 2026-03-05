"""Unit tests for the Intercom source connector."""

from urllib.parse import urlparse
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from airweave.platform.configs.config import IntercomConfig
from airweave.platform.entities.intercom import (
    IntercomConversationEntity,
    IntercomConversationMessageEntity,
    IntercomTicketEntity,
)
from airweave.platform.sources.intercom import (
    IntercomSource,
    _now,
    _parse_timestamp,
    _strip_html,
)


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_stores_token_and_config():
    """create() should set access_token and exclude_closed_conversations from config."""
    source = await IntercomSource.create("token-123", {"exclude_closed_conversations": True})
    assert source.access_token == "token-123"
    assert source.exclude_closed_conversations is True


@pytest.mark.asyncio
async def test_create_defaults_exclude_closed():
    """create() with no config should set exclude_closed_conversations to False."""
    source = await IntercomSource.create("token", None)
    assert source.exclude_closed_conversations is False
    source2 = await IntercomSource.create("token", {})
    assert source2.exclude_closed_conversations is False


@pytest.mark.asyncio
async def test_create_raises_when_no_token():
    """create() should raise ValueError when access_token is empty."""
    with pytest.raises(ValueError, match="Access token is required"):
        await IntercomSource.create("", None)
    with pytest.raises(ValueError, match="Access token is required"):
        await IntercomSource.create(None, None)


# ---------------------------------------------------------------------------
# Helpers: _parse_timestamp, _strip_html, _now
# ---------------------------------------------------------------------------


def test_parse_timestamp_int():
    """_parse_timestamp should accept Unix int (seconds)."""
    dt = _parse_timestamp(1539897198)
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.year == 2018


def test_parse_timestamp_none():
    """_parse_timestamp should return None for None."""
    assert _parse_timestamp(None) is None


def test_parse_timestamp_string_number():
    """_parse_timestamp should accept string number."""
    dt = _parse_timestamp("1539897198")
    assert dt is not None
    assert dt.year == 2018


def test_strip_html():
    """_strip_html should remove tags and collapse whitespace."""
    assert _strip_html("<p>Hi</p>") == "Hi"
    assert _strip_html("<p>  Hello  <b>World</b>  </p>") == "Hello World"
    assert _strip_html(None) == ""
    assert _strip_html("") == ""


def test_now_returns_utc():
    """_now() should return timezone-aware UTC datetime."""
    n = _now()
    assert n.tzinfo is not None
    assert n.tzinfo.utcoffset(n) is not None


# ---------------------------------------------------------------------------
# _get_auth_headers, _build_conversation_url, _build_ticket_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_conversation_url():
    """_build_conversation_url should return Intercom app URL."""
    source = await IntercomSource.create("t", None)
    url = source._build_conversation_url("12345")
    parsed = urlparse(url)
    assert parsed.hostname == "app.intercom.com"
    assert parsed.scheme == "https"
    assert "conversation" in parsed.path
    assert "12345" in parsed.path


@pytest.mark.asyncio
async def test_build_ticket_url():
    """_build_ticket_url should return Intercom tickets URL."""
    source = await IntercomSource.create("t", None)
    url = source._build_ticket_url("ticket-99")
    parsed = urlparse(url)
    assert parsed.hostname == "app.intercom.com"
    assert parsed.scheme == "https"
    assert "tickets" in parsed.path
    assert "ticket-99" in parsed.path


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success():
    """validate() should return True when GET /me returns 200."""
    source = await IntercomSource.create("valid-token", None)

    with patch.object(source, "_validate_oauth2", new_callable=AsyncMock) as mock_validate:
        mock_validate.return_value = True
        result = await source.validate()
    assert result is True
    mock_validate.assert_called_once()
    call_kw = mock_validate.call_args[1]
    assert call_kw["ping_url"] == "https://api.intercom.io/me"
    assert "Intercom-Version" in (call_kw.get("headers") or {})


# ---------------------------------------------------------------------------
# _generate_conversations (entity mapping)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_conversations_maps_api_to_entity():
    """Conversation list payload should map to IntercomConversationEntity."""
    source = await IntercomSource.create("t", None)
    source.exclude_closed_conversations = False

    list_response = {
        "conversations": [
            {
                "id": "1911149811",
                "created_at": 1539897198,
                "updated_at": 1540393270,
                "source": {"subject": "", "body": "<p>Hi</p>"},
                "teammates": [{"id": "814860", "name": "Mark Strong", "email": "mk@acme.org"}],
                "admin_assignee_id": "814860",
                "state": "open",
                "priority": "not_priority",
                "contacts": [{"id": "5bc8f7ae2d96695c18a"}],
                "custom_attributes": {"issue_type": "Billing"},
                "tags": {"tags": [{"name": "vip"}], "type": "tag.list"},
            }
        ],
        "pages": {},
    }

    async def fake_get(client, url, params=None):
        if "/conversations?" in url or url.endswith("/conversations"):
            return list_response
        if "/conversations/1911149811" in url:
            return {
                "id": "1911149811",
                "conversation_parts": {
                    "conversation_parts": [
                        {
                            "id": "269650473",
                            "body": "Customer message",
                            "created_at": 1539897198,
                            "part_type": "comment",
                            "author": {"id": "5bc8f742", "type": "lead", "name": "Alice"},
                        }
                    ],
                    "total_count": 1,
                },
            }
        raise ValueError(f"Unexpected URL: {url}")

    entities = []
    with patch.object(source, "_get_with_auth", side_effect=fake_get):
        async for entity in source._generate_conversations(AsyncMock()):
            entities.append(entity)

    conv_entities = [e for e in entities if isinstance(e, IntercomConversationEntity)]
    msg_entities = [
        e for e in entities if isinstance(e, IntercomConversationMessageEntity)
    ]
    assert len(conv_entities) == 1
    c = conv_entities[0]
    assert c.entity_id == "1911149811"
    assert c.conversation_id == "1911149811"
    assert "Hi" in (c.subject or "")
    assert c.state == "open"
    assert c.assignee_name == "Mark Strong"
    assert len(msg_entities) == 1
    m = msg_entities[0]
    assert m.message_id == "269650473"
    assert m.conversation_id == "1911149811"
    assert m.body == "Customer message"
    assert m.author_name == "Alice"


@pytest.mark.asyncio
async def test_generate_conversations_skips_closed_when_configured():
    """When exclude_closed_conversations is True, closed conversations are skipped."""
    source = await IntercomSource.create("t", {"exclude_closed_conversations": True})

    list_response = {
        "conversations": [
            {"id": "1", "state": "closed", "source": {}, "created_at": 1539897198, "updated_at": 1539897198},
            {"id": "2", "state": "open", "source": {"body": "Open"}, "created_at": 1539897198, "updated_at": 1539897198},
        ],
        "pages": {},
    }

    call_count = 0

    async def fake_get(client, url, params=None):
        nonlocal call_count
        if "conversations?" in url or url.rstrip("/").endswith("conversations"):
            return list_response
        if "/conversations/2" in url:
            call_count += 1
            return {"id": "2", "conversation_parts": {"conversation_parts": []}}
        return {"conversation_parts": {"conversation_parts": []}}

    entities = []
    with patch.object(source, "_get_with_auth", side_effect=fake_get):
        async for entity in source._generate_conversations(AsyncMock()):
            entities.append(entity)

    conv_entities = [e for e in entities if isinstance(e, IntercomConversationEntity)]
    assert len(conv_entities) == 1
    assert conv_entities[0].entity_id == "2"
    assert conv_entities[0].state == "open"
    assert call_count == 1


# ---------------------------------------------------------------------------
# _generate_tickets (entity mapping)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_tickets_maps_api_to_entity():
    """Tickets search payload should map to IntercomTicketEntity."""
    source = await IntercomSource.create("t", None)

    search_response = {
        "tickets": [
            {
                "id": "ticket-42",
                "name": "Billing question",
                "description": "Customer asked about invoice",
                "created_at": 1609459200,
                "updated_at": 1609545600,
                "state": "open",
                "priority": "high",
                "assignee": {"id": "admin-1", "name": "Jane"},
                "contacts": [{"id": "contact-1"}],
            }
        ],
        "pages": {},
    }

    async def fake_post(client, url, json_body):
        assert "tickets/search" in url
        return search_response

    entities = []
    with patch.object(source, "_post_with_auth", side_effect=fake_post), patch.object(
        source, "_get_ticket_parts", new_callable=AsyncMock, return_value=[]
    ):
        async for entity in source._generate_tickets(AsyncMock()):
            entities.append(entity)

    assert len(entities) == 1
    t = entities[0]
    assert isinstance(t, IntercomTicketEntity)
    assert t.entity_id == "ticket-42"
    assert t.ticket_id == "ticket-42"
    assert t.name == "Billing question"
    assert t.description == "Customer asked about invoice"
    assert t.state == "open"
    assert t.assignee_name == "Jane"
    assert t.ticket_parts_text is None
    assert "ticket-42" in (t.web_url_value or "")


@pytest.mark.asyncio
async def test_generate_tickets_handles_404_gracefully():
    """_generate_tickets should not raise when tickets API returns 404 (e.g. plan)."""
    source = await IntercomSource.create("t", None)

    async def fake_post_404(client, url, json_body):
        raise httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )

    entities = []
    with patch.object(source, "_post_with_auth", side_effect=fake_post_404):
        async for entity in source._generate_tickets(AsyncMock()):
            entities.append(entity)
    assert len(entities) == 0


# ---------------------------------------------------------------------------
# IntercomConfig
# ---------------------------------------------------------------------------


def test_intercom_config_schema():
    """IntercomConfig has optional exclude_closed_conversations."""
    config = IntercomConfig()
    assert config.exclude_closed_conversations is False
    config2 = IntercomConfig(exclude_closed_conversations=True)
    assert config2.exclude_closed_conversations is True
