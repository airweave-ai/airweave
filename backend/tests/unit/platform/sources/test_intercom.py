"""Unit tests for the Intercom source connector."""

from urllib.parse import urlparse
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.domains.sources.exceptions import SourceEntityNotFoundError
from airweave.platform.configs.config import IntercomConfig
from airweave.platform.entities.intercom import (
    IntercomConversationEntity,
    IntercomConversationMessageEntity,
    IntercomTicketEntity,
)
from airweave.platform.entities.intercom import (
    _parse_intercom_ts as _parse_timestamp,
    _strip_html,
)
from airweave.platform.sources.intercom import IntercomSource


def _mock_auth(token="token-123"):
    auth = AsyncMock()
    auth.get_token = AsyncMock(return_value=token)
    auth.supports_refresh = True
    auth.provider_kind = "oauth"
    return auth


def _mock_logger():
    return MagicMock()


def _mock_http_client():
    return AsyncMock()


async def _make_intercom_source(config: IntercomConfig | None = None):
    cfg = config if config is not None else IntercomConfig()
    return await IntercomSource.create(
        auth=_mock_auth(),
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=cfg,
    )


def _now():
    """Replacement for removed helper — UTC now."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_stores_token_and_config():
    """create() should set _exclude_closed from IntercomConfig."""
    source = await IntercomSource.create(
        auth=_mock_auth("token-123"),
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=IntercomConfig(exclude_closed_conversations=True),
    )
    assert source._exclude_closed is True


@pytest.mark.asyncio
async def test_create_defaults_exclude_closed():
    """create() with default config should set _exclude_closed to False."""
    source = await _make_intercom_source(IntercomConfig())
    assert source._exclude_closed is False
    source2 = await _make_intercom_source(IntercomConfig(exclude_closed_conversations=False))
    assert source2._exclude_closed is False


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
# _build_conversation_url, _build_ticket_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_conversation_url():
    """_build_conversation_url should return Intercom app URL."""
    source = await _make_intercom_source()
    url = source._build_conversation_url("12345")
    parsed = urlparse(url)
    assert parsed.hostname == "app.intercom.com"
    assert parsed.scheme == "https"
    assert "conversation" in parsed.path
    assert "12345" in parsed.path


@pytest.mark.asyncio
async def test_build_ticket_url():
    """_build_ticket_url should return Intercom tickets URL."""
    source = await _make_intercom_source()
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
    """validate() should complete when GET /me returns 200."""
    source = await _make_intercom_source()

    with patch.object(source, "_get", new_callable=AsyncMock, return_value={}) as mock_get:
        await source.validate()
    mock_get.assert_awaited_once()
    assert mock_get.call_args[0][0] == "https://api.intercom.io/me"


# ---------------------------------------------------------------------------
# _generate_conversations (entity mapping)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_conversations_maps_api_to_entity():
    """Conversation list payload should map to IntercomConversationEntity."""
    source = await _make_intercom_source()
    source._exclude_closed = False

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

    async def fake_get(url, params=None):
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
    with patch.object(source, "_get", side_effect=fake_get):
        async for entity in source._generate_conversations():
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
    source = await _make_intercom_source(
        IntercomConfig(exclude_closed_conversations=True),
    )

    list_response = {
        "conversations": [
            {"id": "1", "state": "closed", "source": {}, "created_at": 1539897198, "updated_at": 1539897198},
            {"id": "2", "state": "open", "source": {"body": "Open"}, "created_at": 1539897198, "updated_at": 1539897198},
        ],
        "pages": {},
    }

    call_count = 0

    async def fake_get(url, params=None):
        nonlocal call_count
        if "conversations?" in url or url.rstrip("/").endswith("conversations"):
            return list_response
        if "/conversations/2" in url:
            call_count += 1
            return {"id": "2", "conversation_parts": {"conversation_parts": []}}
        return {"conversation_parts": {"conversation_parts": []}}

    entities = []
    with patch.object(source, "_get", side_effect=fake_get):
        async for entity in source._generate_conversations():
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
    source = await _make_intercom_source()

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

    async def fake_post(url, json_body):
        assert "tickets/search" in url
        return search_response

    entities = []
    with patch.object(source, "_post", side_effect=fake_post), patch.object(
        source, "_get_ticket_parts", new_callable=AsyncMock, return_value=[]
    ):
        async for entity in source._generate_tickets():
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
    source = await _make_intercom_source()

    async def fake_post_404(url, json_body):
        raise SourceEntityNotFoundError("Not found (404)", source_short_name="intercom")

    entities = []
    with patch.object(source, "_post", side_effect=fake_post_404):
        async for entity in source._generate_tickets():
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
