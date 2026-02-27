"""Unit tests for the Apollo source connector.

Tests assume the API token is a master token (sequences and email activities
endpoints are authorized).
"""

from unittest.mock import AsyncMock

import httpx
import pytest

from airweave.platform.configs.auth import ApolloAuthConfig
from airweave.schemas.source_connection import AuthenticationMethod
from airweave.platform.entities.apollo import (
    ApolloAccountEntity,
    ApolloContactEntity,
    ApolloEmailActivityEntity,
    ApolloSequenceEntity,
)
from airweave.platform.sources.apollo import ApolloSource

# Base URL used by Apollo source; responses need a request set for raise_for_status().
_APOLLO_URL = "https://api.apollo.io/api/v1/accounts/search"


def _response(status_code: int, json_body: dict = None, method: str = "POST", url: str = _APOLLO_URL):
    """Build an httpx.Response with request set so raise_for_status() works."""
    return httpx.Response(
        status_code=status_code,
        json=json_body if json_body is not None else {},
        request=httpx.Request(method, url),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def apollo_credentials():
    """Valid Apollo auth config for tests (master token)."""
    return ApolloAuthConfig(api_key="test_apollo_api_key_12345")


async def _make_apollo_source(credentials: ApolloAuthConfig) -> ApolloSource:
    """Create Apollo source (async)."""
    return await ApolloSource.create(credentials)


def _make_mock_client(
    *,
    post_responses=None,
    get_responses=None,
):
    """Build a mock httpx.AsyncClient that returns given responses for post/get."""
    post_responses = list(post_responses or [])
    get_responses = list(get_responses or [])

    async def post(*args, **kwargs):
        if not post_responses:
            return _response(200, {})
        resp = post_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    async def get(*args, **kwargs):
        if not get_responses:
            return _response(200, {})
        resp = get_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=post)
    client.get = AsyncMock(side_effect=get)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _mock_http_factory(source: ApolloSource, mock_client):
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
async def test_apollo_source_create(apollo_credentials):
    """ApolloSource.create sets api_key from credentials."""
    source = await _make_apollo_source(apollo_credentials)
    assert source.api_key == "test_apollo_api_key_12345"


@pytest.mark.asyncio
async def test_apollo_source_headers(apollo_credentials):
    """_headers includes x-api-key and Content-Type."""
    source = await _make_apollo_source(apollo_credentials)
    headers = source._headers()
    assert headers.get("x-api-key") == "test_apollo_api_key_12345"
    assert "application/json" in headers.get("Content-Type", "")
    assert "application/json" in headers.get("Accept", "")


# ---------------------------------------------------------------------------
# Entity generation: accounts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_accounts_yields_entity(apollo_credentials):
    """_generate_accounts maps API response to ApolloAccountEntity."""
    account_payload = {
        "accounts": [
            {
                "id": "acc_abc",
                "name": "Acme Corp",
                "domain": "acme.com",
                "created_at": "2024-01-15T10:00:00Z",
                "num_contacts": 5,
            }
        ],
        "pagination": {"total_pages": 1},
    }
    mock_client = _make_mock_client(
        post_responses=[_response(200, account_payload)],
    )
    source = await _make_apollo_source(apollo_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    entities = []
    async with source.http_client() as client:
        async for e in source._generate_accounts(client):
            entities.append(e)

    assert len(entities) == 1
    ent = entities[0]
    assert isinstance(ent, ApolloAccountEntity)
    assert ent.entity_id == "acc_abc"
    assert ent.name == "Acme Corp"
    assert ent.account_id == "acc_abc"
    assert ent.domain == "acme.com"
    assert ent.num_contacts == 5
    assert ent.web_url_value == "https://app.apollo.io/accounts/acc_abc"


@pytest.mark.asyncio
async def test_generate_accounts_skips_items_without_id(apollo_credentials):
    """_generate_accounts skips account objects that have no id."""
    account_payload = {
        "accounts": [
            {"name": "No Id", "domain": "x.com"},
            {"id": "acc_only", "name": "With Id"},
        ],
        "pagination": {"total_pages": 1},
    }
    mock_client = _make_mock_client(
        post_responses=[_response(200, account_payload)],
    )
    source = await _make_apollo_source(apollo_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    entities = []
    async with source.http_client() as client:
        async for e in source._generate_accounts(client):
            entities.append(e)

    assert len(entities) == 1
    assert entities[0].entity_id == "acc_only"


# ---------------------------------------------------------------------------
# Entity generation: contacts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_contacts_yields_entity_with_breadcrumb(apollo_credentials):
    """_generate_contacts maps API response and adds account breadcrumb."""
    contact_payload = {
        "contacts": [
            {
                "id": "con_123",
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@acme.com",
                "account_id": "acc_abc",
                "account": {"name": "Acme Corp"},
            }
        ],
        "pagination": {"total_pages": 1},
    }
    mock_client = _make_mock_client(
        post_responses=[_response(200, contact_payload)],
    )
    source = await _make_apollo_source(apollo_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    entities = []
    async with source.http_client() as client:
        async for e in source._generate_contacts(client):
            entities.append(e)

    assert len(entities) == 1
    ent = entities[0]
    assert isinstance(ent, ApolloContactEntity)
    assert ent.entity_id == "con_123"
    assert ent.name == "Jane Doe"
    assert ent.contact_id == "con_123"
    assert ent.email == "jane@acme.com"
    assert ent.account_id == "acc_abc"
    assert ent.account_name == "Acme Corp"
    assert len(ent.breadcrumbs) == 1
    assert ent.breadcrumbs[0].entity_id == "acc_abc"
    assert ent.breadcrumbs[0].name == "Acme Corp"
    assert ent.breadcrumbs[0].entity_type == "ApolloAccountEntity"


# ---------------------------------------------------------------------------
# Entity generation: sequences (403 handling)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_sequences_403_skips_without_raise(apollo_credentials):
    """On 403 from sequences endpoint, no entities yielded and no exception."""
    mock_client = _make_mock_client(
        post_responses=[_response(403, {"error": "Forbidden"})],
    )
    source = await _make_apollo_source(apollo_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    entities = []
    async with source.http_client() as client:
        async for e in source._generate_sequences(client):
            entities.append(e)

    assert len(entities) == 0


@pytest.mark.asyncio
async def test_generate_sequences_yields_entity_when_authorized(apollo_credentials):
    """_generate_sequences yields ApolloSequenceEntity when API returns 200."""
    seq_payload = {
        "emailer_campaigns": [
            {
                "id": "seq_xyz",
                "name": "Outreach Q1",
                "active": True,
                "num_steps": 3,
            }
        ],
        "pagination": {"total_pages": 1},
    }
    mock_client = _make_mock_client(
        post_responses=[_response(200, seq_payload)],
    )
    source = await _make_apollo_source(apollo_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    entities = []
    async with source.http_client() as client:
        async for e in source._generate_sequences(client):
            entities.append(e)

    assert len(entities) == 1
    ent = entities[0]
    assert isinstance(ent, ApolloSequenceEntity)
    assert ent.entity_id == "seq_xyz"
    assert ent.name == "Outreach Q1"
    assert ent.sequence_id == "seq_xyz"
    assert ent.active is True
    assert ent.num_steps == 3


# ---------------------------------------------------------------------------
# Entity generation: email activities (403 handling)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_email_activities_403_skips_without_raise(apollo_credentials):
    """On 403 from email activities endpoint, no entities yielded and no exception."""
    mock_client = _make_mock_client(
        get_responses=[_response(403, {"error": "Forbidden"})],
    )
    source = await _make_apollo_source(apollo_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    entities = []
    async with source.http_client() as client:
        async for e in source._generate_email_activities(client):
            entities.append(e)

    assert len(entities) == 0


@pytest.mark.asyncio
async def test_generate_email_activities_yields_entity_when_authorized(apollo_credentials):
    """_generate_email_activities yields ApolloEmailActivityEntity when API returns 200."""
    msg_payload = {
        "emailer_messages": [
            {
                "id": "msg_1",
                "subject": "Intro",
                "to_email": "jane@acme.com",
                "to_name": "Jane",
                "emailer_campaign_id": "seq_xyz",
                "campaign_name": "Outreach Q1",
                "contact_id": "con_123",
                "status": "delivered",
            }
        ],
        "pagination": {"total_pages": 1},
    }
    mock_client = _make_mock_client(
        get_responses=[_response(200, msg_payload, method="GET")],
    )
    source = await _make_apollo_source(apollo_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    entities = []
    async with source.http_client() as client:
        async for e in source._generate_email_activities(client):
            entities.append(e)

    assert len(entities) == 1
    ent = entities[0]
    assert isinstance(ent, ApolloEmailActivityEntity)
    assert ent.entity_id == "msg_1"
    assert "Intro" in ent.name
    assert ent.message_id == "msg_1"
    assert ent.subject == "Intro"
    assert ent.to_email == "jane@acme.com"
    assert ent.campaign_name == "Outreach Q1"
    assert ent.emailer_campaign_id == "seq_xyz"
    assert ent.contact_id == "con_123"
    assert len(ent.breadcrumbs) == 2  # sequence + contact


# ---------------------------------------------------------------------------
# generate_entities (full flow)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_entities_order_and_403_handling(apollo_credentials):
    """generate_entities yields accounts, then contacts; 403 on sequences/activities skips them."""
    account_payload = {
        "accounts": [{"id": "acc_1", "name": "A"}],
        "pagination": {"total_pages": 1},
    }
    contact_payload = {
        "contacts": [{"id": "con_1", "email": "c@a.com", "account_id": "acc_1"}],
        "pagination": {"total_pages": 1},
    }
    mock_client = _make_mock_client(
        post_responses=[
            _response(200, account_payload),
            _response(200, contact_payload),
            _response(403, {"error": "Forbidden"}),  # sequences
        ],
        get_responses=[_response(403, {"error": "Forbidden"})],  # email activities
    )
    source = await _make_apollo_source(apollo_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    entities = []
    async for e in source.generate_entities():
        entities.append(e)

    assert len(entities) == 2
    assert isinstance(entities[0], ApolloAccountEntity)
    assert entities[0].entity_id == "acc_1"
    assert isinstance(entities[1], ApolloContactEntity)
    assert entities[1].entity_id == "con_1"


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success(apollo_credentials):
    """validate returns True when accounts/search returns accounts key."""
    mock_client = _make_mock_client(
        post_responses=[_response(200, {"accounts": [], "pagination": {"total_pages": 0}})],
    )
    source = await _make_apollo_source(apollo_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    result = await source.validate()
    assert result is True


@pytest.mark.asyncio
async def test_validate_failure_missing_accounts_key(apollo_credentials):
    """validate returns False when response does not contain accounts key."""
    mock_client = _make_mock_client(
        post_responses=[_response(200, {"data": []})],
    )
    source = await _make_apollo_source(apollo_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    result = await source.validate()
    assert result is False


@pytest.mark.asyncio
async def test_validate_failure_http_error(apollo_credentials):
    """validate returns False when API returns 401."""
    mock_client = _make_mock_client(
        post_responses=[_response(401, {"error": "Unauthorized"})],
    )
    source = await _make_apollo_source(apollo_credentials)
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    result = await source.validate()
    assert result is False


# ---------------------------------------------------------------------------
# Source class metadata
# ---------------------------------------------------------------------------


def test_apollo_source_class_metadata():
    """Apollo source has expected short_name and auth methods."""
    assert ApolloSource.short_name == "apollo"
    assert ApolloSource.source_name == "Apollo"
    assert AuthenticationMethod.DIRECT in ApolloSource.auth_methods
    assert AuthenticationMethod.AUTH_PROVIDER in ApolloSource.auth_methods
