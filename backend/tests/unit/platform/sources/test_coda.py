"""Unit tests for Coda source connector (v2 contract)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceEntityForbiddenError,
    SourceRateLimitError,
)
from airweave.domains.sources.token_providers.credential import DirectCredentialProvider
from airweave.domains.sources.token_providers.protocol import AuthProviderKind
from airweave.platform.configs.auth import CodaAuthConfig
from airweave.platform.configs.config import CodaConfig
from airweave.platform.entities.coda import (
    CodaDocEntity,
    CodaPageEntity,
    CodaRowEntity,
    CodaTableEntity,
    _parse_dt,
)
from airweave.platform.sources.coda import CODA_API_BASE, CodaSource


def _mock_auth(api_key: str = "test-token-coda"):
    """Direct credential auth matching Coda create() / _get token resolution."""
    creds = CodaAuthConfig(api_key=api_key)
    return DirectCredentialProvider(creds, source_short_name="coda")


def _mock_http_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


def _mock_logger():
    return MagicMock()


async def _make_coda_source(*, config: CodaConfig | None = None, api_key: str = "test-token-coda"):
    return await CodaSource.create(
        auth=_mock_auth(api_key=api_key),
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=config if config is not None else CodaConfig(),
    )


@pytest_asyncio.fixture
async def coda_source():
    """Coda source with default test credentials."""
    return await _make_coda_source()


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_sets_config():
    """create() should set optional doc_id / folder_id filters on the instance."""
    source = await CodaSource.create(
        auth=_mock_auth(api_key="my-token-coda"),
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=CodaConfig(doc_id="doc-1", folder_id="fl-1"),
    )
    assert source.auth.credentials.api_key == "my-token-coda"
    assert source._doc_id_filter == "doc-1"
    assert source._folder_id_filter == "fl-1"


@pytest.mark.asyncio
async def test_create_empty_config():
    """create() with default config should set empty filters."""
    source = await _make_coda_source(config=CodaConfig())
    assert source._doc_id_filter == ""
    assert source._folder_id_filter == ""


@pytest.mark.asyncio
async def test_create_with_coda_auth_config():
    """create() stores API key on auth and applies doc_id from config."""
    source = await CodaSource.create(
        auth=_mock_auth(api_key="config-token-12345"),
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=CodaConfig(doc_id="d1"),
    )
    assert source.auth.credentials.api_key == "config-token-12345"
    assert source._doc_id_filter == "d1"


# ---------------------------------------------------------------------------
# validate / generate_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success(coda_source):
    """validate() should complete when whoami returns 200."""
    with patch.object(
        coda_source, "_get", new_callable=AsyncMock, return_value={}
    ) as mock_get:
        await coda_source.validate()
        mock_get.assert_awaited_once()
        assert mock_get.call_args[0][0] == "/whoami"


@pytest.mark.asyncio
async def test_validate_failure(coda_source):
    """validate() should propagate when whoami fails."""
    with patch.object(
        coda_source, "_get", new_callable=AsyncMock, side_effect=RuntimeError("nope")
    ):
        with pytest.raises(RuntimeError, match="nope"):
            await coda_source.validate()


@pytest.mark.asyncio
async def test_generate_entities_yields_doc_page_table_row(coda_source):
    """generate_entities() should yield Doc, Page, Table, Row entities with correct breadcrumbs."""
    docs_response = {
        "items": [
            {
                "id": "doc-1",
                "name": "Test Doc",
                "browserLink": "https://coda.io/d/_ddoc1",
                "owner": "u@x.com",
                "ownerName": "User",
                "createdAt": "2024-01-01T00:00:00Z",
                "updatedAt": "2024-01-02T00:00:00Z",
                "workspace": {"name": "WS1"},
                "folder": {"name": "Folder1"},
            }
        ],
    }
    pages_response = {
        "items": [
            {
                "id": "page-1",
                "name": "Page One",
                "subtitle": "Sub",
                "browserLink": "https://coda.io/d/_ddoc1/Page-One_xyz",
                "contentType": "canvas",
                "createdAt": "2024-01-01T00:00:00Z",
                "updatedAt": "2024-01-02T00:00:00Z",
                "isHidden": False,
                "isEffectivelyHidden": False,
            }
        ],
    }
    page_content_response = {"items": []}
    tables_response = {
        "items": [
            {
                "id": "grid-1",
                "name": "Table One",
                "tableType": "table",
                "browserLink": "https://coda.io/d/_ddoc1#Table-One_t1",
                "parent": {"name": "Page One"},
            }
        ],
    }
    table_detail_response = {
        "id": "grid-1",
        "name": "Table One",
        "rowCount": 1,
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-02T00:00:00Z",
    }
    rows_response = {
        "items": [
            {
                "id": "i-row1",
                "name": "Row One",
                "values": {"c-col1": "A", "c-col2": "B"},
                "browserLink": "https://coda.io/d/_ddoc1#_rui-row1",
                "createdAt": "2024-01-01T00:00:00Z",
                "updatedAt": "2024-01-02T00:00:00Z",
            }
        ],
    }

    async def fake_get(path, params=None):
        params = params or {}
        if path == "/docs":
            return docs_response
        if "/docs/doc-1/pages" in path and "/content" not in path:
            return pages_response
        if "/docs/doc-1/pages/page-1/content" in path:
            return page_content_response
        if path == "/docs/doc-1/tables":
            return tables_response
        if path == "/docs/doc-1/tables/grid-1":
            return table_detail_response
        if "/docs/doc-1/tables/grid-1/rows" in path:
            return rows_response
        if path == "/whoami":
            return {"name": "Test", "loginId": "u@x.com"}
        raise ValueError(f"Unexpected path: {path}")

    with patch.object(coda_source, "_get", side_effect=fake_get):
        entities = []
        async for e in coda_source.generate_entities():
            entities.append(e)

        assert len(entities) >= 1
        doc_entities = [e for e in entities if isinstance(e, CodaDocEntity)]
        page_entities = [e for e in entities if isinstance(e, CodaPageEntity)]
        table_entities = [e for e in entities if isinstance(e, CodaTableEntity)]
        row_entities = [e for e in entities if isinstance(e, CodaRowEntity)]

        assert len(doc_entities) == 1
        assert doc_entities[0].entity_id == "doc-1"
        assert doc_entities[0].name == "Test Doc"
        assert doc_entities[0].breadcrumbs == []

        assert len(page_entities) == 1
        assert page_entities[0].entity_id == "page-1"
        assert page_entities[0].name == "Page One"
        assert len(page_entities[0].breadcrumbs) == 1
        assert page_entities[0].breadcrumbs[0].entity_id == "doc-1"
        assert page_entities[0].breadcrumbs[0].name == "Test Doc"

        assert len(table_entities) == 1
        assert table_entities[0].entity_id == "grid-1"
        assert table_entities[0].name == "Table One"
        assert len(table_entities[0].breadcrumbs) == 1

        assert len(row_entities) == 1
        assert row_entities[0].entity_id == "i-row1"
        assert row_entities[0].name == "Row One"
        assert len(row_entities[0].breadcrumbs) == 2
        assert row_entities[0].breadcrumbs[0].entity_type == "CodaDocEntity"
        assert row_entities[0].breadcrumbs[1].entity_type == "CodaTableEntity"


def test_parse_dt():
    """_parse_dt should return timezone-naive UTC datetime or None."""
    assert _parse_dt(None) is None
    assert _parse_dt("") is None
    dt = _parse_dt("2024-06-15T12:00:00Z")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 6
    assert dt.day == 15


@pytest.mark.asyncio
async def test_row_values_to_text(coda_source):
    """_row_values_to_text should concatenate simple and array values."""
    assert coda_source._row_values_to_text({}) == ""
    assert coda_source._row_values_to_text({"c1": "a", "c2": "b"}) == "a | b"
    assert coda_source._row_values_to_text({"c1": [1, 2]}) == "1 2"
    assert coda_source._row_values_to_text({"c1": "a", "c2": None}) == "a"


def test_parse_dt_invalid_returns_none():
    """_parse_dt returns None for invalid or non-iso strings."""
    assert _parse_dt("not-a-date") is None
    assert _parse_dt("2024-13-45T00:00:00Z") is None


@pytest.mark.asyncio
async def test_get_unauthorized_raises_source_auth_error(coda_source):
    """_get raises SourceAuthError when the API returns 401."""
    req = httpx.Request("GET", f"{CODA_API_BASE}/docs")
    mock_resp = httpx.Response(401, request=req)
    coda_source.http_client.get = AsyncMock(return_value=mock_resp)

    with pytest.raises(SourceAuthError):
        await coda_source._get("/docs")


@pytest.mark.asyncio
async def test_get_429_raises_rate_limit_error(coda_source):
    """_get raises SourceRateLimitError when API returns 429 (after retries)."""
    req = httpx.Request("GET", f"{CODA_API_BASE}/docs")
    mock_resp = httpx.Response(429, request=req)
    coda_source.http_client.get = AsyncMock(return_value=mock_resp)

    # Tenacity's async retrier sleeps between attempts via asyncio.sleep.
    with patch.object(asyncio, "sleep", new_callable=AsyncMock):
        with pytest.raises(SourceRateLimitError):
            await coda_source._get("/docs")


@pytest.mark.asyncio
async def test_get_success_returns_json(coda_source):
    """_get with valid token and 200 returns response json."""
    req = httpx.Request("GET", f"{CODA_API_BASE}/docs")
    mock_resp = httpx.Response(200, json={"items": []}, request=req)
    coda_source.http_client.get = AsyncMock(return_value=mock_resp)

    result = await coda_source._get("/docs", params={"limit": 25})
    assert result == {"items": []}
    coda_source.http_client.get.assert_awaited()
    call_kw = coda_source.http_client.get.call_args[1]
    assert "Bearer" in call_kw["headers"]["Authorization"]
    assert call_kw["params"] == {"limit": 25}


@pytest.mark.asyncio
async def test_list_docs_with_folder_filter(coda_source):
    """_list_docs includes folderId in params when _folder_id_filter is set."""
    coda_source._folder_id_filter = "fl-123"
    seen_params = []

    async def capture_get(path, params=None):
        if path == "/docs":
            seen_params.append(params or {})
            return {"items": [{"id": "d1", "name": "Doc1"}], "nextPageToken": None}
        raise ValueError(path)

    with patch.object(coda_source, "_get", side_effect=capture_get):
        docs = []
        async for d in coda_source._list_docs():
            docs.append(d)
    assert len(docs) == 1
    assert seen_params[0].get("folderId") == "fl-123"


@pytest.mark.asyncio
async def test_list_docs_pagination(coda_source):
    """_list_docs follows nextPageToken and merges items."""
    call_count = 0

    async def paginated_get(path, params=None):
        nonlocal call_count
        if path == "/docs":
            call_count += 1
            if call_count == 1:
                return {"items": [{"id": "d1", "name": "First"}], "nextPageToken": "p2"}
            return {"items": [{"id": "d2", "name": "Second"}], "nextPageToken": None}
        raise ValueError(path)

    with patch.object(coda_source, "_get", side_effect=paginated_get):
        docs = []
        async for d in coda_source._list_docs():
            docs.append(d)
    assert len(docs) == 2
    assert docs[0]["name"] == "First"
    assert docs[1]["name"] == "Second"


@pytest.mark.asyncio
async def test_list_pages_pagination(coda_source):
    """_list_pages follows nextPageToken."""
    call_count = 0

    async def paginated_get(path, params=None):
        nonlocal call_count
        if "/docs/d1/pages" in path and "/content" not in path:
            call_count += 1
            if call_count == 1:
                return {"items": [{"id": "p1", "name": "P1"}], "nextPageToken": "nx"}
            return {"items": [{"id": "p2", "name": "P2"}], "nextPageToken": None}
        raise ValueError(path)

    with patch.object(coda_source, "_get", side_effect=paginated_get):
        pages = []
        async for p in coda_source._list_pages("d1"):
            pages.append(p)
    assert len(pages) == 2
    assert pages[0]["name"] == "P1"
    assert pages[1]["name"] == "P2"


@pytest.mark.asyncio
async def test_get_page_content_forbidden_returns_empty(coda_source):
    """_get_page_content returns empty string when _get raises entity forbidden."""
    with patch.object(
        coda_source,
        "_get",
        side_effect=SourceEntityForbiddenError("no access", source_short_name="coda"),
    ):
        result = await coda_source._get_page_content("doc-1", "page-1")
    assert result == ""


@pytest.mark.asyncio
async def test_list_tables_and_list_rows(coda_source):
    """_list_tables and _list_rows yield items from _get."""

    async def fake_get(path, params=None):
        if path == "/docs/d1/tables":
            return {"items": [{"id": "t1", "name": "T1"}], "nextPageToken": None}
        if "/docs/d1/tables/t1/rows" in path:
            return {
                "items": [{"id": "r1", "name": "R1", "values": {"c1": "v1"}}],
                "nextPageToken": None,
            }
        raise ValueError(path)

    with patch.object(coda_source, "_get", side_effect=fake_get):
        tables = []
        async for t in coda_source._list_tables("d1"):
            tables.append(t)
        rows = []
        async for r in coda_source._list_rows("d1", "t1"):
            rows.append(r)
    assert len(tables) == 1 and tables[0]["id"] == "t1"
    assert len(rows) == 1 and rows[0]["id"] == "r1"


@pytest.mark.asyncio
async def test_generate_entities_table_fetch_fails_continues(coda_source):
    """When table detail _get fails, generate_entities uses defaults and continues."""
    docs_resp = {
        "items": [
            {
                "id": "doc-1",
                "name": "Doc",
                "browserLink": "https://x",
                "workspace": {},
                "folder": {},
            }
        ],
        "nextPageToken": None,
    }
    pages_resp = {"items": []}
    tables_resp = {
        "items": [{"id": "grid-1", "name": "T1", "browserLink": "https://x", "parent": {}}]
    }
    rows_resp = {
        "items": [
            {
                "id": "r1",
                "name": "R1",
                "values": {"c1": "a"},
                "browserLink": "https://x",
                "createdAt": None,
                "updatedAt": None,
            }
        ]
    }

    async def fake_get(path, params=None):
        if path == "/docs":
            return docs_resp
        if "/docs/doc-1/pages" in path and "/content" not in path:
            return pages_resp
        if path == "/docs/doc-1/tables":
            return tables_resp
        if path == "/docs/doc-1/tables/grid-1":
            raise RuntimeError("Table detail failed")
        if "/docs/doc-1/tables/grid-1/rows" in path:
            return rows_resp
        raise ValueError(path)

    with patch.object(coda_source, "_get", side_effect=fake_get):
        entities = []
        async for e in coda_source.generate_entities():
            entities.append(e)
    row_entities = [e for e in entities if isinstance(e, CodaRowEntity)]
    assert len(row_entities) == 1
    assert row_entities[0].entity_id == "r1"
    table_entities = [e for e in entities if isinstance(e, CodaTableEntity)]
    assert len(table_entities) == 1
    assert table_entities[0].row_count == 0


@pytest.mark.asyncio
async def test_get_uses_oauth_token_when_not_credential_provider():
    """OAuth-style auth resolves token via get_token()."""
    auth = AsyncMock()
    auth.provider_kind = AuthProviderKind.OAUTH
    auth.supports_refresh = False
    auth.get_token = AsyncMock(return_value="oauth-coda-token")

    source = await CodaSource.create(
        auth=auth,
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=CodaConfig(),
    )

    req = httpx.Request("GET", f"{CODA_API_BASE}/docs")
    mock_resp = httpx.Response(200, json={"items": []}, request=req)
    source.http_client.get = AsyncMock(return_value=mock_resp)

    await source._get("/docs")
    call_kw = source.http_client.get.call_args[1]
    assert "Bearer oauth-coda-token" in call_kw["headers"]["Authorization"]
    auth.get_token.assert_awaited_once()
