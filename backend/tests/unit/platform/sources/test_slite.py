"""Unit tests for the Slite source connector."""

from unittest.mock import AsyncMock

import httpx
import pytest

from airweave.platform.configs.auth import SliteAuthConfig
from airweave.platform.entities.slite import SliteNoteEntity
from airweave.platform.sources.slite import SliteSource
from airweave.schemas.source_connection import AuthenticationMethod

SLITE_BASE = "https://api.slite.com/v1"


def _response(
    status_code: int,
    json_body: dict | None = None,
    method: str = "GET",
    url: str = f"{SLITE_BASE}/notes",
):
    """Build an httpx.Response with request set so raise_for_status() works."""
    return httpx.Response(
        status_code=status_code,
        json=json_body if json_body is not None else {},
        request=httpx.Request(method, url),
    )


@pytest.fixture
def slite_credentials():
    """Valid Slite auth config for tests."""
    return SliteAuthConfig(api_key="test_slite_api_key_xyz")


async def _make_slite_source(credentials: SliteAuthConfig, config: dict | None = None) -> SliteSource:
    """Create Slite source (async)."""
    return await SliteSource.create(credentials, config=config)


def _make_mock_client(*, get_responses=None):
    """Build a mock httpx.AsyncClient that returns given responses for get."""
    get_responses = list(get_responses or [])

    async def get(*args, **kwargs):
        if not get_responses:
            return _response(200, {})
        resp = get_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=get)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _mock_http_factory(source: SliteSource, mock_client):
    """Return an async context manager that yields mock_client."""

    class Ctx:
        async def __aenter__(self):
            return mock_client

        async def __aexit__(self, *args):
            pass

    def factory(**kwargs):
        return Ctx()

    return factory


# ---------------------------------------------------------------------------
# Create & headers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slite_source_create(slite_credentials):
    """SliteSource.create sets api_key and include_archived from credentials and config."""
    source = await _make_slite_source(slite_credentials)
    assert source.api_key == "test_slite_api_key_xyz"
    assert source.include_archived is False

    source2 = await _make_slite_source(slite_credentials, config={"include_archived": True})
    assert source2.include_archived is True


@pytest.mark.asyncio
async def test_slite_source_headers(slite_credentials):
    """_headers includes x-slite-api-key and Content-Type."""
    source = await _make_slite_source(slite_credentials)
    headers = source._headers()
    assert headers.get("x-slite-api-key") == "test_slite_api_key_xyz"
    assert "application/json" in headers.get("Content-Type", "")
    assert "application/json" in headers.get("Accept", "")


# ---------------------------------------------------------------------------
# List notes page
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_notes_page_returns_notes(slite_credentials):
    """_list_notes_page returns parsed response with notes and pagination."""
    page_payload = {
        "notes": [
            {
                "id": "note1",
                "title": "First note",
                "parentNoteId": None,
                "url": "https://slite.slite.com/api/s/note1/First-note",
                "lastEditedAt": "2024-01-01T00:00:00.000Z",
                "updatedAt": "2024-01-01T00:00:00.000Z",
                "archivedAt": None,
            }
        ],
        "total": 1,
        "hasNextPage": False,
        "nextCursor": None,
    }
    mock_client = _make_mock_client(get_responses=[_response(200, page_payload)])
    source = await _make_slite_source(slite_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    async with source.http_client() as client:
        page = await source._list_notes_page(client)

    assert page["notes"] == page_payload["notes"]
    assert page["hasNextPage"] is False
    assert page["total"] == 1


# ---------------------------------------------------------------------------
# Get note by id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_note_by_id_returns_note_with_content(slite_credentials):
    """_get_note_by_id returns full note with content."""
    full_note = {
        "id": "note1",
        "title": "My doc",
        "parentNoteId": None,
        "url": "https://slite.slite.com/api/s/note1/My-doc",
        "content": "# Hello\n\nMarkdown content.",
        "lastEditedAt": "2024-01-02T00:00:00.000Z",
        "updatedAt": "2024-01-02T00:00:00.000Z",
        "archivedAt": None,
    }
    mock_client = _make_mock_client(
        get_responses=[_response(200, full_note, url=f"{SLITE_BASE}/notes/note1")]
    )
    source = await _make_slite_source(slite_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    async with source.http_client() as client:
        note = await source._get_note_by_id(client, "note1")

    assert note["id"] == "note1"
    assert note["title"] == "My doc"
    assert note["content"] == "# Hello\n\nMarkdown content."


# ---------------------------------------------------------------------------
# Entity generation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_note_entities_yields_slite_note_entity(slite_credentials):
    """_generate_note_entities maps API responses to SliteNoteEntity."""
    list_page = {
        "notes": [
            {
                "id": "n1",
                "title": "Doc One",
                "parentNoteId": None,
                "url": "https://slite.slite.com/api/s/n1/Doc-One",
                "lastEditedAt": "2024-01-01T00:00:00.000Z",
                "updatedAt": "2024-01-01T00:00:00.000Z",
                "archivedAt": None,
            }
        ],
        "total": 1,
        "hasNextPage": False,
        "nextCursor": None,
    }
    full_note = {
        "id": "n1",
        "title": "Doc One",
        "parentNoteId": None,
        "url": "https://slite.slite.com/api/s/n1/Doc-One",
        "content": "Body text",
        "lastEditedAt": "2024-01-01T00:00:00.000Z",
        "updatedAt": "2024-01-01T00:00:00.000Z",
        "archivedAt": None,
    }
    mock_client = _make_mock_client(
        get_responses=[
            _response(200, list_page),
            _response(200, full_note, url=f"{SLITE_BASE}/notes/n1"),
        ]
    )
    source = await _make_slite_source(slite_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    entities = []
    async with source.http_client() as client:
        async for e in source._generate_note_entities(client):
            entities.append(e)

    assert len(entities) == 1
    ent = entities[0]
    assert isinstance(ent, SliteNoteEntity)
    assert ent.entity_id == "n1"
    assert ent.note_id == "n1"
    assert ent.name == "Doc One"
    assert ent.content == "Body text"
    assert ent.web_url_value == "https://slite.slite.com/api/s/n1/Doc-One"
    assert ent.breadcrumbs == []


@pytest.mark.asyncio
async def test_generate_note_entities_skips_archived_when_not_included(slite_credentials):
    """When include_archived is False, archived notes are skipped."""
    list_page = {
        "notes": [
            {
                "id": "archived1",
                "title": "Archived doc",
                "parentNoteId": None,
                "url": "https://slite.slite.com/api/s/archived1/Archived-doc",
                "lastEditedAt": "2024-01-01T00:00:00.000Z",
                "updatedAt": "2024-01-01T00:00:00.000Z",
                "archivedAt": "2024-01-15T00:00:00.000Z",
            }
        ],
        "total": 1,
        "hasNextPage": False,
        "nextCursor": None,
    }
    mock_client = _make_mock_client(get_responses=[_response(200, list_page)])
    source = await _make_slite_source(slite_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    entities = []
    async with source.http_client() as client:
        async for e in source._generate_note_entities(client):
            entities.append(e)

    assert len(entities) == 0


# ---------------------------------------------------------------------------
# generate_entities (full flow)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_entities_yields_notes(slite_credentials):
    """generate_entities yields SliteNoteEntity from list + get flow."""
    list_page = {
        "notes": [
            {
                "id": "n1",
                "title": "Only note",
                "parentNoteId": None,
                "url": "https://slite.slite.com/api/s/n1/Only-note",
                "lastEditedAt": "2024-01-01T00:00:00.000Z",
                "updatedAt": "2024-01-01T00:00:00.000Z",
                "archivedAt": None,
            }
        ],
        "total": 1,
        "hasNextPage": False,
        "nextCursor": None,
    }
    full_note = {
        "id": "n1",
        "title": "Only note",
        "parentNoteId": None,
        "url": "https://slite.slite.com/api/s/n1/Only-note",
        "content": "Content here",
        "lastEditedAt": "2024-01-01T00:00:00.000Z",
        "updatedAt": "2024-01-01T00:00:00.000Z",
        "archivedAt": None,
    }
    mock_client = _make_mock_client(
        get_responses=[
            _response(200, list_page),
            _response(200, full_note, url=f"{SLITE_BASE}/notes/n1"),
        ]
    )
    source = await _make_slite_source(slite_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    entities = []
    async for e in source.generate_entities():
        entities.append(e)

    assert len(entities) == 1
    assert entities[0].name == "Only note"
    assert entities[0].content == "Content here"


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success(slite_credentials):
    """validate returns True when list notes returns notes key."""
    mock_client = _make_mock_client(
        get_responses=[_response(200, {"notes": [], "total": 0, "hasNextPage": False, "nextCursor": None})]
    )
    source = await _make_slite_source(slite_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    result = await source.validate()
    assert result is True


@pytest.mark.asyncio
async def test_validate_failure_missing_notes_key(slite_credentials):
    """validate returns False when response does not contain notes key."""
    mock_client = _make_mock_client(get_responses=[_response(200, {"data": []})])
    source = await _make_slite_source(slite_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    result = await source.validate()
    assert result is False


@pytest.mark.asyncio
async def test_validate_failure_http_error(slite_credentials):
    """validate returns False when API returns 401."""
    mock_client = _make_mock_client(get_responses=[_response(401, {"message": "Invalid apiKey"})])
    source = await _make_slite_source(slite_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    result = await source.validate()
    assert result is False


# ---------------------------------------------------------------------------
# Source class metadata
# ---------------------------------------------------------------------------


def test_slite_source_class_metadata():
    """Slite source has expected short_name and auth methods."""
    assert SliteSource.short_name == "slite"
    assert SliteSource.source_name == "Slite"
    assert AuthenticationMethod.DIRECT in SliteSource.auth_methods
    assert AuthenticationMethod.AUTH_PROVIDER in SliteSource.auth_methods
