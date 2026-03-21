"""Unit tests for the Slab source connector."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from airweave.domains.sources.exceptions import SourceAuthError, SourceServerError
from airweave.domains.sources.token_providers.credential import DirectCredentialProvider
from airweave.domains.sources.token_providers.protocol import AuthProviderKind
from airweave.platform.configs.auth import SlabAuthConfig
from airweave.platform.configs.config import SlabConfig
from airweave.platform.entities.slab import (
    SlabPostEntity,
    SlabTopicEntity,
    _build_post_url,
    _build_topic_url,
    _json_description_to_string,
    _parse_dt,
    _quill_delta_to_plain_text,
)
from airweave.platform.sources.slab import SlabSource

# Request tied to responses so httpx.Response.raise_for_status() does not fail
_SLAB_REQUEST = httpx.Request("POST", "https://api.slab.com/v1/graphql")


def _response(status_code: int, **kwargs) -> httpx.Response:
    """Build an httpx.Response with request set so raise_for_status() works."""
    return httpx.Response(status_code, request=_SLAB_REQUEST, **kwargs)


def _mock_logger():
    return MagicMock()


def _mock_http_client_with_post_queue(post_responses=None):
    """Async mock with ``post`` that returns queued httpx responses in order."""
    post_responses = list(post_responses or [])

    async def post_side_effect(*args, **kwargs):
        if not post_responses:
            return _response(200, json={"data": {}})
        resp = post_responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    client = AsyncMock()
    client.post = AsyncMock(side_effect=post_side_effect)
    return client


async def make_slab_source(
    slab_auth_config: SlabAuthConfig | None = None,
    *,
    http_client=None,
    config: SlabConfig | None = None,
):
    """Create Slab source (v2 contract)."""
    auth_config = slab_auth_config or SlabAuthConfig(api_key="test_slab_api_token_12345")
    return await SlabSource.create(
        auth=DirectCredentialProvider(auth_config, source_short_name="slab"),
        logger=_mock_logger(),
        http_client=http_client if http_client is not None else AsyncMock(),
        config=config if config is not None else SlabConfig(),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def slab_auth_config():
    """Valid Slab auth config for tests."""
    return SlabAuthConfig(api_key="test_slab_api_token_12345")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slab_source_create_with_auth_config(slab_auth_config):
    """SlabSource.create sets _api_key from SlabAuthConfig via DirectCredentialProvider."""
    source = await make_slab_source(slab_auth_config)
    assert source._api_key == "test_slab_api_token_12345"


@pytest.mark.asyncio
async def test_create_uses_get_token_when_oauth():
    """Non-credential auth loads the token via get_token()."""
    auth = AsyncMock()
    auth.provider_kind = AuthProviderKind.OAUTH
    auth.supports_refresh = False
    auth.get_token = AsyncMock(return_value="oauth-token")

    source = await SlabSource.create(
        auth=auth,
        logger=_mock_logger(),
        http_client=AsyncMock(),
        config=SlabConfig(),
    )

    assert source._api_key == "oauth-token"
    auth.get_token.assert_awaited_once()


# ---------------------------------------------------------------------------
# Helpers: Quill delta and JSON description (entity module)
# ---------------------------------------------------------------------------


def test_quill_delta_to_plain_text():
    """_quill_delta_to_plain_text concatenates insert strings."""
    content = [
        {"insert": "Hello "},
        {"insert": "World", "attributes": {"bold": True}},
    ]
    assert _quill_delta_to_plain_text(content) == "Hello World"


def test_quill_delta_to_plain_text_empty():
    """_quill_delta_to_plain_text returns empty for None or empty list."""
    assert _quill_delta_to_plain_text(None) == ""
    assert _quill_delta_to_plain_text([]) == ""


def test_quill_delta_to_plain_text_string_passthrough():
    """_quill_delta_to_plain_text returns string as-is."""
    assert _quill_delta_to_plain_text("already text") == "already text"


def test_quill_delta_to_plain_text_embed():
    """_quill_delta_to_plain_text replaces image/embed inserts with labels."""
    content = [{"insert": {"image": "https://example.com/x.png"}}]
    assert _quill_delta_to_plain_text(content) == "[image]"


def test_json_description_to_string():
    """_json_description_to_string handles str, list, dict, None."""
    assert _json_description_to_string("hello") == "hello"
    assert _json_description_to_string(None) is None
    assert _json_description_to_string(["a", "b"]) == "a b"
    assert _json_description_to_string({"text": "desc"}) == "desc"


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success(slab_auth_config):
    """validate completes when organization query succeeds."""
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
    http_client = _mock_http_client_with_post_queue([org_response])
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    await source.validate()


@pytest.mark.asyncio
async def test_validate_succeeds_when_organization_null_in_response(slab_auth_config):
    """_post returns data without organization; validate does not assert on shape."""
    org_response = _response(200, json={"data": {"organization": None}})
    http_client = _mock_http_client_with_post_queue([org_response])
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    await source.validate()


@pytest.mark.asyncio
async def test_validate_failure_http_error(slab_auth_config):
    """validate propagates SourceServerError on non-auth HTTP errors (e.g. 5xx)."""
    err_500 = _response(500, json={"error": "Server Error"})
    # _post is wrapped with tenacity (5 attempts); each retry calls post again.
    http_client = _mock_http_client_with_post_queue([err_500] * 5)
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    with pytest.raises(SourceServerError):
        await source.validate()


@pytest.mark.asyncio
async def test_validate_raises_source_auth_error_on_401(slab_auth_config):
    """validate propagates SourceAuthError on 401."""
    http_client = _mock_http_client_with_post_queue(
        [_response(401, json={"error": "Unauthorized"})]
    )
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    with pytest.raises(SourceAuthError):
        await source.validate()


@pytest.mark.asyncio
async def test_validate_succeeds_when_graphql_org_null_non_nullable_handled_by_post(
    slab_auth_config,
):
    """_post maps org-null GraphQL errors to organization None without raising."""
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
    http_client = _mock_http_client_with_post_queue([resp])
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    await source.validate()


@pytest.mark.asyncio
async def test_validate_propagates_graphql_errors_from_post(slab_auth_config):
    """Non–org-null GraphQL errors raise from _post and propagate through validate."""
    resp = _response(
        200,
        json={
            "data": None,
            "errors": [{"message": "Rate limit exceeded"}],
        },
    )
    http_client = _mock_http_client_with_post_queue([resp])
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    with pytest.raises(ValueError, match="GraphQL errors"):
        await source.validate()


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
    topics_resp = _topics_response(
        [
            {
                "id": "topic_1",
                "name": "Engineering",
                "description": "Eng docs",
                "insertedAt": "2024-01-01T00:00:00Z",
                "updatedAt": "2024-01-02T00:00:00Z",
            }
        ]
    )
    posts_resp = _posts_response(
        [
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
        ]
    )
    http_client = _mock_http_client_with_post_queue(
        [org_resp, search_resp, topics_resp, posts_resp]
    )
    source = await make_slab_source(slab_auth_config, http_client=http_client)

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
    http_client = _mock_http_client_with_post_queue([org_resp, search_resp])
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    entities = []
    async for e in source.generate_entities():
        entities.append(e)

    assert len(entities) == 0


@pytest.mark.asyncio
async def test_generate_entities_post_without_topic(slab_auth_config):
    """Post with no topic has empty breadcrumbs and unknown topic name."""
    org_resp = _org_response()
    search_resp = _search_response(topic_ids=[], post_ids=["post_1"])
    posts_resp = _posts_response(
        [
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
        ]
    )
    http_client = _mock_http_client_with_post_queue([org_resp, search_resp, posts_resp])
    source = await make_slab_source(slab_auth_config, http_client=http_client)

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
    """generate_entities propagates exception when API returns error (retries use same failing response)."""
    http_client = AsyncMock()
    http_client.post = AsyncMock(return_value=_response(500, text="Server Error"))
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    with pytest.raises(SourceServerError):
        async for _ in source.generate_entities():
            pass


# ---------------------------------------------------------------------------
# Create with config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slab_source_create_with_config_host(slab_auth_config):
    """SlabSource.create sets _host from SlabConfig."""
    source = await make_slab_source(
        slab_auth_config,
        config=SlabConfig(host="custom.slab.com"),
    )
    assert source._host == "custom.slab.com"


@pytest.mark.asyncio
async def test_slab_source_create_default_host(slab_auth_config):
    """SlabSource.create uses app.slab.com when config has default host."""
    source = await make_slab_source(slab_auth_config, config=SlabConfig())
    assert source._host == "app.slab.com"


# ---------------------------------------------------------------------------
# _post: organization null path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_returns_org_null_on_organization_null_error(slab_auth_config):
    """When GraphQL errors indicate organization null, _post returns {organization: None}."""
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
    http_client = _mock_http_client_with_post_queue([resp])
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    result = await source._post("query { organization { id name host } }")

    assert result == {"organization": None}


@pytest.mark.asyncio
async def test_post_raises_on_other_graphql_error(slab_auth_config):
    """_post raises ValueError when GraphQL errors are not organization-null."""
    resp = _response(
        200,
        json={
            "data": None,
            "errors": [{"message": "Something else failed", "path": ["other"]}],
        },
    )
    http_client = _mock_http_client_with_post_queue([resp])
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    with pytest.raises(ValueError, match="Something else failed"):
        await source._post("query { x }")


# ---------------------------------------------------------------------------
# _parse_dt (entity helper)
# ---------------------------------------------------------------------------


def test_parse_dt_none():
    """_parse_dt returns None for None."""
    assert _parse_dt(None) is None


def test_parse_dt_valid_iso():
    """_parse_dt parses ISO string and returns naive UTC."""
    dt = _parse_dt("2024-01-15T10:30:00Z")
    assert dt is not None
    assert dt.year == 2024 and dt.month == 1 and dt.day == 15
    assert dt.hour == 10 and dt.minute == 30


def test_parse_dt_invalid_returns_none():
    """_parse_dt returns None for invalid string."""
    assert _parse_dt("not-a-date") is None


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------


def test_build_post_url():
    """_build_post_url adds https when host has no scheme."""
    url = _build_post_url("myteam.slab.com", "post_123")
    assert url == "https://myteam.slab.com/posts/post_123"


def test_build_post_url_with_http():
    """_build_post_url keeps existing scheme."""
    url = _build_post_url("https://myteam.slab.com", "post_123")
    assert url == "https://myteam.slab.com/posts/post_123"


def test_build_topic_url():
    """_build_topic_url produces /t/ path."""
    url = _build_topic_url("myteam.slab.com", "topic_456")
    assert url == "https://myteam.slab.com/t/topic_456"


# ---------------------------------------------------------------------------
# _fetch_organization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_organization(slab_auth_config):
    """_fetch_organization returns org dict with host."""
    org_resp = _org_response("workspace.slab.com")
    http_client = _mock_http_client_with_post_queue([org_resp])
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    org = await source._fetch_organization()

    assert org["host"] == "workspace.slab.com"
    assert org["id"] == "org_1"


# ---------------------------------------------------------------------------
# _fetch_topic_and_post_ids_via_search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_topic_and_post_ids_empty(slab_auth_config):
    """_fetch_topic_and_post_ids_via_search returns empty lists when no edges."""
    search_resp = _search_response()
    http_client = _mock_http_client_with_post_queue([search_resp])
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    topic_ids, post_ids, comments = await source._fetch_topic_and_post_ids_via_search()

    assert topic_ids == []
    assert post_ids == []
    assert comments == []


@pytest.mark.asyncio
async def test_fetch_topic_and_post_ids_pagination(slab_auth_config):
    """_fetch_topic_and_post_ids_via_search follows hasNextPage and endCursor."""
    search_page1 = _search_response(
        topic_ids=["t1"], post_ids=["p1"], has_next_page=True, end_cursor="c1"
    )
    search_page2 = _search_response(topic_ids=["t2"], post_ids=[], has_next_page=False)
    http_client = _mock_http_client_with_post_queue([search_page1, search_page2])
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    topic_ids, post_ids, comments = await source._fetch_topic_and_post_ids_via_search()

    assert topic_ids == ["t1", "t2"]
    assert post_ids == ["p1"]
    assert comments == []


# ---------------------------------------------------------------------------
# _fetch_topics_batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_topics_batch_empty(slab_auth_config):
    """_fetch_topics_batch returns [] for empty topic_ids."""
    http_client = _mock_http_client_with_post_queue()
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    topics = await source._fetch_topics_batch([])

    assert topics == []


@pytest.mark.asyncio
async def test_fetch_topics_batch(slab_auth_config):
    """_fetch_topics_batch returns topics from API."""
    resp = _topics_response(
        [{"id": "t1", "name": "A", "description": None, "insertedAt": None, "updatedAt": None}]
    )
    http_client = _mock_http_client_with_post_queue([resp])
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    topics = await source._fetch_topics_batch(["t1"])

    assert len(topics) == 1
    assert topics[0]["id"] == "t1" and topics[0]["name"] == "A"


# ---------------------------------------------------------------------------
# _fetch_posts_batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_posts_batch_empty(slab_auth_config):
    """_fetch_posts_batch returns [] for empty post_ids."""
    http_client = _mock_http_client_with_post_queue()
    source = await make_slab_source(slab_auth_config, http_client=http_client)

    posts = await source._fetch_posts_batch([])

    assert posts == []


# ---------------------------------------------------------------------------
# _json_description_to_string edge cases
# ---------------------------------------------------------------------------


def test_json_description_to_string_dict_content():
    """_json_description_to_string uses 'content' key when 'text' missing."""
    assert _json_description_to_string({"content": "desc"}) == "desc"


def test_json_description_to_string_dict_fallback():
    """_json_description_to_string falls back to str(description) for dict without text/content."""
    result = _json_description_to_string({"foo": "bar"})
    assert "foo" in result or "bar" in result


def test_json_description_to_string_list_with_none():
    """_json_description_to_string skips None in list."""
    assert _json_description_to_string(["a", None, "b"]) == "a b"


# ---------------------------------------------------------------------------
# _quill_delta_to_plain_text edge case
# ---------------------------------------------------------------------------


def test_quill_delta_to_plain_text_embed_non_image():
    """_quill_delta_to_plain_text uses [embed] for non-image embed inserts."""
    content = [{"insert": {"video": "https://example.com/v.mp4"}}]
    assert _quill_delta_to_plain_text(content) == "[embed]"


def test_quill_delta_to_plain_text_non_dict_op_skipped():
    """_quill_delta_to_plain_text skips non-dict ops."""
    content = [{"insert": "Hi"}, "not a dict"]
    assert _quill_delta_to_plain_text(content) == "Hi"
