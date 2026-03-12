"""Unit tests for the Creatio CRM source connector.

Tests cover create(), _generate_entity, validate, token refresh,
and class metadata — all with mocked HTTP responses.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from airweave.platform.configs.auth import CreatioAuthConfig
from airweave.platform.entities.creatio import CreatioContactEntity
from airweave.platform.sources.creatio import CreatioEntity, CreatioSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _response(
    status_code: int,
    json_body: dict = None,
    method: str = "GET",
    url: str = "https://example.creatio.com/0/odata/Contact",
) -> httpx.Response:
    """Build an httpx.Response with request set so raise_for_status() works."""
    return httpx.Response(
        status_code=status_code,
        json=json_body if json_body is not None else {},
        request=httpx.Request(method, url),
    )


def _make_mock_client(*, get_responses=None):
    """Build a mock httpx.AsyncClient that returns given responses for GET."""
    get_responses = list(get_responses or [])

    async def get(*args, **kwargs):
        if not get_responses:
            return _response(200, {"value": []})
        resp = get_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=get)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _mock_http_factory(source: CreatioSource, mock_client):
    """Return an async context manager that yields mock_client."""

    class Ctx:
        async def __aenter__(self):
            return mock_client

        async def __aexit__(self, *args):
            pass

    def factory(**kwargs):
        return Ctx()

    return factory


async def _make_creatio_source(
    creatio_credentials: CreatioAuthConfig,
    creatio_config: dict[str, str],
) -> CreatioSource:
    """Create a CreatioSource with mocked token exchange."""
    with patch.object(
        CreatioSource, "_get_access_token", return_value="fake-token-123"
    ):
        return await CreatioSource.create(creatio_credentials, creatio_config)


_CONTACT_RECORD = {
    "Id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "Name": "John Doe",
    "CreatedOn": "2025-01-01T00:00:00Z",
    "ModifiedOn": "2025-06-01T00:00:00Z",
    "Email": "john@example.com",
    "Phone": "+1234567890",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def creatio_config() -> dict[str, str]:
    """Creatio source configuration for tests."""
    return {"instance_url": "183119-crm-bundle.creatio.com"}


@pytest.fixture
def creatio_credentials() -> CreatioAuthConfig:
    """Creatio auth config for tests."""
    return CreatioAuthConfig(
        client_id="fake-client-id",
        client_secret="fake-client-secret",
    )


# ---------------------------------------------------------------------------
# Create & static helpers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_sets_fields(creatio_config, creatio_credentials):
    """CreatioSource.create sets fields from credentials and config."""
    source = await _make_creatio_source(creatio_credentials, creatio_config)

    assert source.client_id == "fake-client-id"
    assert source.client_secret == "fake-client-secret"
    assert source.instance_url == "183119-crm-bundle.creatio.com"
    assert source.access_token == "fake-token-123"


@pytest.mark.asyncio
async def test_create_missing_instance_url(creatio_credentials):
    """create() should raise ValueError when instance_url is missing."""
    with pytest.raises(ValueError, match="instance_url"):
        await _make_creatio_source(creatio_credentials, {})


def test_normalize_instance_url():
    """_normalize_instance_url strips protocol and trailing slash."""
    assert CreatioSource._normalize_instance_url("https://Foo.creatio.com/") == "foo.creatio.com"
    assert CreatioSource._normalize_instance_url("http://Bar.creatio.com") == "bar.creatio.com"


def test_identity_service_url_derivation():
    """_identity_service_url_from_instance replaces .creatio.com with -is.creatio.com."""
    result = CreatioSource._identity_service_url_from_instance(
        instance_url="183119-crm-bundle.creatio.com"
    )
    assert result == "183119-crm-bundle-is.creatio.com"


# ---------------------------------------------------------------------------
# Entity generation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_entity_yields_contacts(creatio_config, creatio_credentials):
    """_generate_entity maps OData response to CreatioContactEntity."""
    source = await _make_creatio_source(creatio_credentials, creatio_config)

    mock_client = _make_mock_client(get_responses=[
        _response(200, {"value": [_CONTACT_RECORD]}),
    ])

    entities = []
    async for e in source._generate_entity(
        client=mock_client,
        creatio_entity=CreatioEntity.CONTACT,
    ):
        entities.append(e)

    assert len(entities) == 1
    assert isinstance(entities[0], CreatioContactEntity)
    assert entities[0].contact_id == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert entities[0].display_name == "John Doe"
    assert entities[0].email == "john@example.com"


@pytest.mark.asyncio
async def test_generate_entity_paginates(creatio_config, creatio_credentials):
    """_generate_entity follows pagination when a full page is returned."""
    source = await _make_creatio_source(creatio_credentials, creatio_config)

    full_page = [
        {**_CONTACT_RECORD, "Id": f"id-{i}", "Name": f"Contact {i}"}
        for i in range(source.ODATA_PAGE_SIZE)
    ]
    partial_page = [
        {**_CONTACT_RECORD, "Id": "id-last", "Name": "Last Contact"}
    ]

    mock_client = _make_mock_client(get_responses=[
        _response(200, {"value": full_page}),
        _response(200, {"value": partial_page}),
    ])

    entities = []
    async for e in source._generate_entity(
        client=mock_client,
        creatio_entity=CreatioEntity.CONTACT,
    ):
        entities.append(e)

    assert len(entities) == source.ODATA_PAGE_SIZE + 1
    assert mock_client.get.call_count == 2


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success(creatio_config, creatio_credentials):
    """validate() returns True when the API responds successfully."""
    source = await _make_creatio_source(creatio_credentials, creatio_config)

    mock_client = _make_mock_client(get_responses=[
        _response(200, {"value": [_CONTACT_RECORD]}),
    ])
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    result = await source.validate()
    assert result is True


@pytest.mark.asyncio
async def test_validate_failure_http_error(creatio_config, creatio_credentials):
    """validate() returns False when the API returns an HTTP error."""
    source = await _make_creatio_source(creatio_credentials, creatio_config)

    mock_client = _make_mock_client()
    source.set_http_client_factory(_mock_http_factory(source, mock_client))

    with patch.object(
        source,
        "_get_with_auth",
        side_effect=httpx.HTTPStatusError(
            "Forbidden",
            request=httpx.Request("GET", "https://example.com"),
            response=httpx.Response(403),
        ),
    ):
        result = await source.validate()

    assert result is False


@pytest.mark.asyncio
async def test_validate_missing_credentials():
    """validate() returns False when credentials are not set."""
    source = CreatioSource()
    result = await source.validate()
    assert result is False


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_refresh_on_401(creatio_config, creatio_credentials):
    """_get_with_auth refreshes the token and retries on 401."""
    source = await _make_creatio_source(creatio_credentials, creatio_config)

    mock_client = _make_mock_client(get_responses=[
        _response(401, {"error": "Unauthorized"}),
        _response(200, {"value": [_CONTACT_RECORD]}),
    ])

    with patch.object(
        source, "_get_access_token", return_value="refreshed-token"
    ):
        result = await source._get_with_auth(
            mock_client,
            "https://183119-crm-bundle.creatio.com/0/odata/Contact?$top=1",
        )

    assert result == {"value": [_CONTACT_RECORD]}
    assert source.access_token == "refreshed-token"


# ---------------------------------------------------------------------------
# Enum metadata
# ---------------------------------------------------------------------------


def test_creatio_entity_enum():
    """CreatioEntity enum maps OData names to entity classes."""
    assert CreatioEntity.CONTACT.odata_name == "Contact"
    assert CreatioEntity.CONTACT.type == CreatioContactEntity
    assert len(list(CreatioEntity)) == 6
