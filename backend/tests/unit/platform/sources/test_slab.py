"""Unit tests for the Slab source connector."""

from unittest.mock import AsyncMock

import httpx
import pytest

from airweave.platform.configs.auth import SlabAuthConfig
from airweave.platform.entities.slab import SlabPostEntity, SlabTopicEntity
from airweave.platform.sources.slab import SlabSource

# Request tied to responses so httpx.Response.raise_for_status() does not fail
_SLAB_REQUEST = httpx.Request("POST", "https://api.slab.com/v1/graphql")


def _response(status_code: int, **kwargs) -> httpx.Response:
    """Build an httpx.Response with request set so raise_for_status() works."""
    return httpx.Response(status_code, request=_SLAB_REQUEST, **kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def slab_auth_config():
    """Valid Slab auth config for tests."""
    return SlabAuthConfig(api_key="test_slab_api_token_12345")


async def make_slab_source(credentials):
    """Create Slab source (async)."""
    return await SlabSource.create(credentials)


def make_mock_client(*, post_responses=None):
    """Build a mock httpx.AsyncClient that returns given responses for post()."""
    post_responses = list(post_responses or [])

    async def post(*args, **kwargs):
        if not post_responses:
            return _response(200, json={"data": {}})
        resp = post_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=post)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def mock_http_factory(source, mock_client):
    """Return a factory that yields mock_client."""

    class Ctx:
        async def __aenter__(self):
            return mock_client

        async def __aexit__(self, *args):
            pass

    def factory(**kwargs):
        return Ctx()

    return factory


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slab_source_create_with_auth_config(slab_auth_config):
    """SlabSource.create sets api_key from SlabAuthConfig."""
    source = await make_slab_source(slab_auth_config)
    assert source.api_key == "test_slab_api_token_12345"


@pytest.mark.asyncio
async def test_slab_source_create_with_string_token():
    """SlabSource.create accepts raw API token string (e.g. token injection)."""
    source = await make_slab_source("my_raw_token")
    assert source.api_key == "my_raw_token"


@pytest.mark.asyncio
async def test_slab_source_create_rejects_empty_string():
    """SlabSource.create raises when credentials are empty string."""
    with pytest.raises(ValueError, match="non-empty API token"):
        await make_slab_source("")


@pytest.mark.asyncio
async def test_slab_source_create_rejects_invalid_type():
    """SlabSource.create raises when credentials are wrong type."""
    with pytest.raises(ValueError, match="SlabAuthConfig"):
        await make_slab_source(123)


# ---------------------------------------------------------------------------
# Helpers: Quill delta and JSON description
# ---------------------------------------------------------------------------


def test_quill_delta_to_plain_text():
    """_quill_delta_to_plain_text concatenates insert strings."""
    content = [
        {"insert": "Hello "},
        {"insert": "World", "attributes": {"bold": True}},
    ]
    assert SlabSource._quill_delta_to_plain_text(content) == "Hello World"


def test_quill_delta_to_plain_text_empty():
    """_quill_delta_to_plain_text returns empty for None or empty list."""
    assert SlabSource._quill_delta_to_plain_text(None) == ""
    assert SlabSource._quill_delta_to_plain_text([]) == ""


def test_quill_delta_to_plain_text_string_passthrough():
    """_quill_delta_to_plain_text returns string as-is."""
    assert SlabSource._quill_delta_to_plain_text("already text") == "already text"


def test_quill_delta_to_plain_text_embed():
    """_quill_delta_to_plain_text replaces image/embed inserts with labels."""
    content = [{"insert": {"image": "https://example.com/x.png"}}]
    assert SlabSource._quill_delta_to_plain_text(content) == "[image]"


def test_json_description_to_string():
    """_json_description_to_string handles str, list, dict, None."""
    assert SlabSource._json_description_to_string("hello") == "hello"
    assert SlabSource._json_description_to_string(None) is None
    assert (
        SlabSource._json_description_to_string(["a", "b"])
        == "a b"
    )
    assert (
        SlabSource._json_description_to_string({"text": "desc"})
        == "desc"
    )


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success(slab_auth_config):
    """validate returns True when organization query succeeds."""
    org_response = _response(
        200,
        json={
            "data": {
                "organization": {
                    "id": "org_1",
                    "name": "Test Org",
                    "host": "myteam.slab.com",
                }
            }
        },
    )
    mock_client = make_mock_client(post_responses=[org_response])
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    result = await source.validate()
    assert result is True


@pytest.mark.asyncio
async def test_validate_failure_no_org(slab_auth_config):
    """validate returns False when organization is null."""
    org_response = _response(200, json={"data": {"organization": None}})
    mock_client = make_mock_client(post_responses=[org_response])
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    result = await source.validate()
    assert result is False


@pytest.mark.asyncio
async def test_validate_failure_http_error(slab_auth_config):
    """validate returns False when API returns error."""
    mock_client = make_mock_client(
        post_responses=[_response(401, json={"error": "Unauthorized"})]
    )
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    result = await source.validate()
    assert result is False


@pytest.mark.asyncio
async def test_validate_failure_organization_null_graphql_error(slab_auth_config):
    """validate returns False when GraphQL returns organization null error."""
    resp = _response(
        200,
        json={
            "data": None,
            "errors": [
                {
                    "message": "Cannot return null for non-nullable field",
                    "path": ["organization"],
                }
            ],
        },
    )
    mock_client = make_mock_client(post_responses=[resp])
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    result = await source.validate()
    assert result is False


# ---------------------------------------------------------------------------
# Generate entities (mocked API)
# ---------------------------------------------------------------------------


def _org_response(host="myteam.slab.com"):
    return _response(
        200,
        json={
            "data": {
                "organization": {
                    "id": "org_1",
                    "name": "Org",
                    "host": host,
                }
            }
        },
    )


def _search_response(topic_ids=None, post_ids=None, has_next_page=False, end_cursor="c1"):
    topic_ids = topic_ids or []
    post_ids = post_ids or []
    edges = []
    for tid in topic_ids:
        edges.append({"node": {"topic": {"id": tid}}})
    for pid in post_ids:
        edges.append({"node": {"post": {"id": pid}}})
    return _response(
        200,
        json={
            "data": {
                "search": {
                    "pageInfo": {"hasNextPage": has_next_page, "endCursor": end_cursor},
                    "edges": edges,
                }
            }
        },
    )


def _topics_response(topics):
    return _response(200, json={"data": {"topics": topics}})


def _posts_response(posts):
    return _response(200, json={"data": {"posts": posts}})


@pytest.mark.asyncio
async def test_generate_entities_yields_topics_and_posts(slab_auth_config):
    """generate_entities yields SlabTopicEntity and SlabPostEntity via org + search + topics(ids) + posts(ids)."""
    org_resp = _org_response()
    search_resp = _search_response(topic_ids=["topic_1"], post_ids=["post_1"])
    topics_resp = _topics_response([
        {
            "id": "topic_1",
            "name": "Engineering",
            "description": "Eng docs",
            "insertedAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-02T00:00:00Z",
        }
    ])
    posts_resp = _posts_response([
        {
            "id": "post_1",
            "title": "Getting Started",
            "content": [{"insert": "Hello world"}],
            "insertedAt": "2024-01-03T00:00:00Z",
            "updatedAt": "2024-01-04T00:00:00Z",
            "archivedAt": None,
            "publishedAt": "2024-01-03T00:00:00Z",
            "linkAccess": "INTERNAL",
            "owner": {
                "id": "user_1",
                "name": "Alice",
                "email": "alice@example.com",
            },
            "topics": [{"id": "topic_1", "name": "Engineering"}],
            "banner": {"original": None},
        }
    ])
    mock_client = make_mock_client(
        post_responses=[org_resp, search_resp, topics_resp, posts_resp]
    )
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    entities = []
    async for e in source.generate_entities():
        entities.append(e)

    topics = [e for e in entities if isinstance(e, SlabTopicEntity)]
    posts = [e for e in entities if isinstance(e, SlabPostEntity)]
    assert len(topics) == 1
    assert topics[0].entity_id == "topic_1"
    assert topics[0].name == "Engineering"
    assert topics[0].description == "Eng docs"
    assert "myteam.slab.com" in (topics[0].web_url_value or "")

    assert len(posts) == 1
    assert posts[0].entity_id == "post_1"
    assert posts[0].title == "Getting Started"
    assert posts[0].content == "Hello world"
    assert posts[0].topic_id == "topic_1"
    assert posts[0].topic_name == "Engineering"
    assert posts[0].author == {
        "id": "user_1",
        "name": "Alice",
        "email": "alice@example.com",
    }
    assert len(posts[0].breadcrumbs) == 1
    assert posts[0].breadcrumbs[0].entity_id == "topic_1"
    assert posts[0].breadcrumbs[0].name == "Engineering"


@pytest.mark.asyncio
async def test_generate_entities_empty_search(slab_auth_config):
    """generate_entities yields nothing when search returns no topics or posts."""
    org_resp = _org_response()
    search_resp = _search_response(topic_ids=[], post_ids=[])
    mock_client = make_mock_client(post_responses=[org_resp, search_resp])
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    entities = []
    async for e in source.generate_entities():
        entities.append(e)

    assert len(entities) == 0


@pytest.mark.asyncio
async def test_generate_entities_post_without_topic(slab_auth_config):
    """Post with no topic has empty breadcrumbs and unknown topic name."""
    org_resp = _org_response()
    search_resp = _search_response(topic_ids=[], post_ids=["post_1"])
    posts_resp = _posts_response([
        {
            "id": "post_1",
            "title": "Orphan",
            "content": [{"insert": "Text"}],
            "insertedAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
            "archivedAt": None,
            "publishedAt": None,
            "linkAccess": "INTERNAL",
            "owner": None,
            "topics": [],
            "banner": {"original": None},
        }
    ])
    mock_client = make_mock_client(
        post_responses=[org_resp, search_resp, posts_resp]
    )
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    entities = []
    async for e in source.generate_entities():
        entities.append(e)

    posts = [e for e in entities if isinstance(e, SlabPostEntity)]
    assert len(posts) == 1
    assert posts[0].breadcrumbs == []
    assert posts[0].topic_name == "Unknown topic"
    assert posts[0].author is None


@pytest.mark.asyncio
async def test_generate_entities_raises_on_api_error(slab_auth_config):
    """generate_entities propagates exception when API returns error."""
    mock_client = make_mock_client(
        post_responses=[_response(500, text="Server Error")]
    )
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    with pytest.raises(Exception):
        async for _ in source.generate_entities():
            pass


# ---------------------------------------------------------------------------
# Create with config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slab_source_create_with_config_host(slab_auth_config):
    """SlabSource.create sets host from config."""
    source = await SlabSource.create(slab_auth_config, config={"host": "custom.slab.com"})
    assert source.host == "custom.slab.com"


@pytest.mark.asyncio
async def test_slab_source_create_default_host(slab_auth_config):
    """SlabSource.create uses app.slab.com when config has no host."""
    source = await SlabSource.create(slab_auth_config, config={})
    assert source.host == "app.slab.com"


# ---------------------------------------------------------------------------
# _post_graphql: organization null path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_graphql_returns_org_null_on_organization_null_error(slab_auth_config):
    """When GraphQL errors indicate organization null, _post_graphql returns {organization: None}."""
    resp = _response(
        200,
        json={
            "data": None,
            "errors": [
                {
                    "message": "Cannot return null for non-nullable field",
                    "path": ["organization"],
                }
            ],
        },
    )
    mock_client = make_mock_client(post_responses=[resp])
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    async with source.http_client() as client:
        result = await source._post_graphql(
            client,
            "query($host: String!) { organization(host: $host) { id } }",
            variables={"host": "app.slab.com"},
        )

    assert result == {"organization": None}


@pytest.mark.asyncio
async def test_post_graphql_raises_on_other_graphql_error(slab_auth_config):
    """_post_graphql raises when GraphQL errors are not organization-null."""
    resp = _response(
        200,
        json={
            "data": None,
            "errors": [{"message": "Something else failed", "path": ["other"]}],
        },
    )
    mock_client = make_mock_client(post_responses=[resp])
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    with pytest.raises(httpx.HTTPStatusError, match="Something else failed"):
        async with source.http_client() as client:
            await source._post_graphql(client, "query { x }")


# ---------------------------------------------------------------------------
# _parse_datetime (instance method)
# ---------------------------------------------------------------------------


def test_parse_datetime_none():
    """_parse_datetime returns None for None."""
    source = SlabSource()
    assert source._parse_datetime(None) is None


def test_parse_datetime_valid_iso():
    """_parse_datetime parses ISO string and returns naive UTC."""
    source = SlabSource()
    dt = source._parse_datetime("2024-01-15T10:30:00Z")
    assert dt is not None
    assert dt.year == 2024 and dt.month == 1 and dt.day == 15
    assert dt.hour == 10 and dt.minute == 30


def test_parse_datetime_invalid_returns_none():
    """_parse_datetime returns None for invalid string."""
    source = SlabSource()
    assert source._parse_datetime("not-a-date") is None


# ---------------------------------------------------------------------------
# URL builders (instance methods)
# ---------------------------------------------------------------------------


def test_build_post_url():
    """_build_post_url adds https when host has no scheme."""
    source = SlabSource()
    url = source._build_post_url("myteam.slab.com", "post_123")
    assert url == "https://myteam.slab.com/posts/post_123"


def test_build_post_url_with_http():
    """_build_post_url keeps existing scheme."""
    source = SlabSource()
    url = source._build_post_url("https://myteam.slab.com", "post_123")
    assert url == "https://myteam.slab.com/posts/post_123"


def test_build_topic_url():
    """_build_topic_url produces /t/ path."""
    source = SlabSource()
    url = source._build_topic_url("myteam.slab.com", "topic_456")
    assert url == "https://myteam.slab.com/t/topic_456"


# ---------------------------------------------------------------------------
# _fetch_organization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_organization(slab_auth_config):
    """_fetch_organization returns org dict with host."""
    org_resp = _org_response("workspace.slab.com")
    mock_client = make_mock_client(post_responses=[org_resp])
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    async with source.http_client() as client:
        org = await source._fetch_organization(client)

    assert org["host"] == "workspace.slab.com"
    assert org["id"] == "org_1"


# ---------------------------------------------------------------------------
# _fetch_topic_and_post_ids_via_search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_topic_and_post_ids_empty(slab_auth_config):
    """_fetch_topic_and_post_ids_via_search returns empty lists when no edges."""
    search_resp = _search_response()
    mock_client = make_mock_client(post_responses=[search_resp])
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    async with source.http_client() as client:
        topic_ids, post_ids, comments = await source._fetch_topic_and_post_ids_via_search(client)

    assert topic_ids == []
    assert post_ids == []
    assert comments == []


@pytest.mark.asyncio
async def test_fetch_topic_and_post_ids_pagination(slab_auth_config):
    """_fetch_topic_and_post_ids_via_search follows hasNextPage and endCursor."""
    search_page1 = _search_response(
        topic_ids=["t1"], post_ids=["p1"], has_next_page=True, end_cursor="c1"
    )
    search_page2 = _search_response(
        topic_ids=["t2"], post_ids=[], has_next_page=False
    )
    mock_client = make_mock_client(post_responses=[search_page1, search_page2])
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    async with source.http_client() as client:
        topic_ids, post_ids, comments = await source._fetch_topic_and_post_ids_via_search(client)

    assert topic_ids == ["t1", "t2"]
    assert post_ids == ["p1"]
    assert comments == []


# ---------------------------------------------------------------------------
# _fetch_topics_batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_topics_batch_empty(slab_auth_config):
    """_fetch_topics_batch returns [] for empty topic_ids."""
    mock_client = make_mock_client()
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    async with source.http_client() as client:
        topics = await source._fetch_topics_batch(client, [])

    assert topics == []


@pytest.mark.asyncio
async def test_fetch_topics_batch(slab_auth_config):
    """_fetch_topics_batch returns topics from API."""
    resp = _topics_response([
        {"id": "t1", "name": "A", "description": None, "insertedAt": None, "updatedAt": None},
    ])
    mock_client = make_mock_client(post_responses=[resp])
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    async with source.http_client() as client:
        topics = await source._fetch_topics_batch(client, ["t1"])

    assert len(topics) == 1
    assert topics[0]["id"] == "t1" and topics[0]["name"] == "A"


# ---------------------------------------------------------------------------
# _fetch_posts_batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_posts_batch_empty(slab_auth_config):
    """_fetch_posts_batch returns [] for empty post_ids."""
    mock_client = make_mock_client()
    source = await make_slab_source(slab_auth_config)
    source.set_http_client_factory(mock_http_factory(source, mock_client))

    async with source.http_client() as client:
        posts = await source._fetch_posts_batch(client, [])

    assert posts == []


# ---------------------------------------------------------------------------
# _json_description_to_string edge cases
# ---------------------------------------------------------------------------


def test_json_description_to_string_dict_content():
    """_json_description_to_string uses 'content' key when 'text' missing."""
    assert SlabSource._json_description_to_string({"content": "desc"}) == "desc"


def test_json_description_to_string_dict_fallback():
    """_json_description_to_string falls back to str(description) for dict without text/content."""
    result = SlabSource._json_description_to_string({"foo": "bar"})
    assert "foo" in result or "bar" in result


def test_json_description_to_string_list_with_none():
    """_json_description_to_string skips None in list."""
    assert SlabSource._json_description_to_string(["a", None, "b"]) == "a b"


# ---------------------------------------------------------------------------
# _quill_delta_to_plain_text edge case
# ---------------------------------------------------------------------------


def test_quill_delta_to_plain_text_embed_non_image():
    """_quill_delta_to_plain_text uses [embed] for non-image embed inserts."""
    content = [{"insert": {"video": "https://example.com/v.mp4"}}]
    assert SlabSource._quill_delta_to_plain_text(content) == "[embed]"


def test_quill_delta_to_plain_text_non_dict_op_skipped():
    """_quill_delta_to_plain_text skips non-dict ops."""
    content = [{"insert": "Hi"}, "not a dict"]
    assert SlabSource._quill_delta_to_plain_text(content) == "Hi"
