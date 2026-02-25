"""Unit tests for Coda source connector."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from airweave.platform.configs.auth import CodaAuthConfig
from airweave.platform.entities.coda import (
    CodaDocEntity,
    CodaPageEntity,
    CodaRowEntity,
    CodaTableEntity,
)
from airweave.platform.sources.coda import CodaSource, CODA_API_BASE


@pytest.fixture
def coda_source():
    """Create a Coda source instance with a test token."""
    source = CodaSource()
    source.access_token = "test-token"
    source.doc_id_filter = ""
    source.folder_id_filter = ""
    return source


@pytest.mark.asyncio
async def test_create_sets_config():
    """create() should set access_token and optional doc_id/folder_id."""
    source = await CodaSource.create("my-token", {"doc_id": "doc-1", "folder_id": "fl-1"})
    assert source.access_token == "my-token"
    assert source.doc_id_filter == "doc-1"
    assert source.folder_id_filter == "fl-1"


@pytest.mark.asyncio
async def test_create_empty_config():
    """create() with no config should set empty filters."""
    source = await CodaSource.create("token", None)
    assert source.doc_id_filter == ""
    assert source.folder_id_filter == ""


@pytest.mark.asyncio
async def test_create_with_coda_auth_config():
    """create() with CodaAuthConfig uses api_key."""
    auth_config = CodaAuthConfig(api_key="config-token-12345")
    source = await CodaSource.create(auth_config, {"doc_id": "d1"})
    assert source.access_token == "config-token-12345"
    assert source.doc_id_filter == "d1"


@pytest.mark.asyncio
async def test_create_invalid_credentials_raises():
    """create() with object that has no api_key raises ValueError."""
    class NoApiKey:
        pass
    with pytest.raises(ValueError, match="api_key"):
        await CodaSource.create(NoApiKey(), None)


@pytest.mark.asyncio
async def test_validate_success(coda_source):
    """validate() should return True when whoami returns 200."""
    with patch.object(
        coda_source, "_validate_oauth2", new_callable=AsyncMock, return_value=True
    ) as mock_validate:
        result = await coda_source.validate()
        assert result is True
        mock_validate.assert_called_once()
        call_kw = mock_validate.call_args[1]
        assert call_kw["ping_url"] == f"{CODA_API_BASE}/whoami"


@pytest.mark.asyncio
async def test_validate_failure(coda_source):
    """validate() should return False when whoami fails."""
    with patch.object(
        coda_source, "_validate_oauth2", new_callable=AsyncMock, return_value=False
    ):
        result = await coda_source.validate()
        assert result is False


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

    async def fake_get(client, path, params=None):
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

    with patch.object(coda_source, "_get", side_effect=fake_get), patch.object(
        coda_source, "http_client"
    ) as mock_http_ctx:
        mock_client = MagicMock()
        mock_http_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_http_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

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


@pytest.mark.asyncio
async def test_parse_datetime(coda_source):
    """_parse_datetime should return timezone-naive UTC datetime or None."""
    assert coda_source._parse_datetime(None) is None
    assert coda_source._parse_datetime("") is None
    dt = coda_source._parse_datetime("2024-06-15T12:00:00Z")
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


@pytest.mark.asyncio
async def test_parse_datetime_invalid_returns_none(coda_source):
    """_parse_datetime returns None for invalid or non-iso strings."""
    assert coda_source._parse_datetime("not-a-date") is None
    assert coda_source._parse_datetime("2024-13-45T00:00:00Z") is None


@pytest.mark.asyncio
async def test_get_no_token_raises(coda_source):
    """_get raises ValueError when get_access_token returns no token."""
    with patch.object(coda_source, "get_access_token", new_callable=AsyncMock, return_value=""):
        with patch.object(coda_source, "_wait_for_rate_limit", new_callable=AsyncMock):
            with patch.object(coda_source, "http_client") as mock_ctx:
                mock_client = MagicMock()
                mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)
                async with coda_source.http_client() as client:
                    with pytest.raises(ValueError, match="No access token"):
                        await coda_source._get(client, "/docs")


@pytest.mark.asyncio
async def test_get_429_raises(coda_source):
    """_get raises when API returns 429."""
    with patch.object(coda_source, "get_access_token", new_callable=AsyncMock, return_value="tok"):
        with patch.object(coda_source, "_wait_for_rate_limit", new_callable=AsyncMock):
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 429
            mock_resp.json.return_value = {}
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "429", request=MagicMock(), response=mock_resp
            )
            mock_client.get = AsyncMock(return_value=mock_resp)
            with pytest.raises(httpx.HTTPStatusError):
                await coda_source._get(mock_client, "/docs")


@pytest.mark.asyncio
async def test_get_success_returns_json(coda_source):
    """_get with valid token and 200 returns response json."""
    with patch.object(coda_source, "get_access_token", new_callable=AsyncMock, return_value="tok"):
        with patch.object(coda_source, "_wait_for_rate_limit", new_callable=AsyncMock):
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"items": []}
            mock_resp.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            result = await coda_source._get(mock_client, "/docs", params={"limit": 25})
            assert result == {"items": []}
            mock_client.get.assert_called_once()
            call_kw = mock_client.get.call_args[1]
            assert "Bearer tok" in call_kw["headers"]["Authorization"]
            assert call_kw["params"] == {"limit": 25}


@pytest.mark.asyncio
async def test_wait_for_rate_limit_sleeps_when_over_limit(coda_source):
    """_wait_for_rate_limit sleeps when request count is at limit."""
    from airweave.platform.sources import coda as coda_module

    RATE_LIMIT_REQUESTS = coda_module.RATE_LIMIT_REQUESTS
    RATE_LIMIT_PERIOD = coda_module.RATE_LIMIT_PERIOD
    with patch("asyncio.get_event_loop") as mock_loop:
        loop = MagicMock()
        mock_loop.return_value = loop
        t0 = 1000.0
        # Each _wait_for_rate_limit() calls time() 2–3 times (start, after sleep, append).
        # First 15 calls: 2 each = 30. 16th call (triggers sleep): 3 times.
        time_values = (
            [t0] * 30  # first 15 invocations
            + [t0 + 0.5, t0 + 0.5, t0 + RATE_LIMIT_PERIOD + 1]  # 16th: now, now after sleep, append
            + [t0 + RATE_LIMIT_PERIOD + 2] * 10  # spare so side_effect does not run out
        )
        loop.time.side_effect = time_values
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            for _ in range(RATE_LIMIT_REQUESTS + 1):
                await coda_source._wait_for_rate_limit()
            assert mock_sleep.called


@pytest.mark.asyncio
async def test_list_docs_with_folder_filter(coda_source):
    """_list_docs includes folderId in params when folder_id_filter is set."""
    coda_source.folder_id_filter = "fl-123"
    seen_params = []

    async def capture_get(client, path, params=None):
        if path == "/docs":
            seen_params.append(params or {})
            return {"items": [{"id": "d1", "name": "Doc1"}], "nextPageToken": None}
        raise ValueError(path)

    with patch.object(coda_source, "_get", side_effect=capture_get):
        with patch.object(coda_source, "http_client") as mock_ctx:
            mock_client = MagicMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)
            async with coda_source.http_client() as client:
                docs = []
                async for d in coda_source._list_docs(client):
                    docs.append(d)
            assert len(docs) == 1
            assert seen_params[0].get("folderId") == "fl-123"


@pytest.mark.asyncio
async def test_list_docs_pagination(coda_source):
    """_list_docs follows nextPageToken and merges items."""
    call_count = 0

    async def paginated_get(client, path, params=None):
        nonlocal call_count
        if path == "/docs":
            call_count += 1
            if call_count == 1:
                return {"items": [{"id": "d1", "name": "First"}], "nextPageToken": "p2"}
            return {"items": [{"id": "d2", "name": "Second"}], "nextPageToken": None}
        raise ValueError(path)

    with patch.object(coda_source, "_get", side_effect=paginated_get):
        with patch.object(coda_source, "http_client") as mock_ctx:
            mock_client = MagicMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)
            async with coda_source.http_client() as client:
                docs = []
                async for d in coda_source._list_docs(client):
                    docs.append(d)
            assert len(docs) == 2
            assert docs[0]["name"] == "First"
            assert docs[1]["name"] == "Second"


@pytest.mark.asyncio
async def test_list_pages_pagination(coda_source):
    """_list_pages follows nextPageToken."""
    call_count = 0

    async def paginated_get(client, path, params=None):
        nonlocal call_count
        if "/docs/d1/pages" in path and "/content" not in path:
            call_count += 1
            if call_count == 1:
                return {"items": [{"id": "p1", "name": "P1"}], "nextPageToken": "nx"}
            return {"items": [{"id": "p2", "name": "P2"}], "nextPageToken": None}
        raise ValueError(path)

    with patch.object(coda_source, "_get", side_effect=paginated_get):
        with patch.object(coda_source, "http_client") as mock_ctx:
            mock_client = MagicMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)
            async with coda_source.http_client() as client:
                pages = []
                async for p in coda_source._list_pages(client, "d1"):
                    pages.append(p)
            assert len(pages) == 2
            assert pages[0]["name"] == "P1"
            assert pages[1]["name"] == "P2"


@pytest.mark.asyncio
async def test_get_page_content_403_returns_empty(coda_source):
    """_get_page_content returns empty string when page returns 403/404/410."""
    with patch.object(coda_source, "_get", side_effect=httpx.HTTPStatusError(
        "Forbidden", request=MagicMock(), response=MagicMock(status_code=403)
    )):
        with patch.object(coda_source, "http_client") as mock_ctx:
            mock_client = MagicMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)
            async with coda_source.http_client() as client:
                result = await coda_source._get_page_content(client, "doc-1", "page-1")
            assert result == ""


@pytest.mark.asyncio
async def test_list_tables_and_list_rows(coda_source):
    """_list_tables and _list_rows yield items from _get."""
    async def fake_get(client, path, params=None):
        if path == "/docs/d1/tables":
            return {"items": [{"id": "t1", "name": "T1"}], "nextPageToken": None}
        if "/docs/d1/tables/t1/rows" in path:
            return {"items": [{"id": "r1", "name": "R1", "values": {"c1": "v1"}}], "nextPageToken": None}
        raise ValueError(path)

    with patch.object(coda_source, "_get", side_effect=fake_get):
        with patch.object(coda_source, "http_client") as mock_ctx:
            mock_client = MagicMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)
            async with coda_source.http_client() as client:
                tables = []
                async for t in coda_source._list_tables(client, "d1"):
                    tables.append(t)
                rows = []
                async for r in coda_source._list_rows(client, "d1", "t1"):
                    rows.append(r)
            assert len(tables) == 1 and tables[0]["id"] == "t1"
            assert len(rows) == 1 and rows[0]["id"] == "r1"


@pytest.mark.asyncio
async def test_generate_entities_table_fetch_fails_continues(coda_source):
    """When table detail _get fails, generate_entities uses defaults and continues."""
    docs_resp = {"items": [{"id": "doc-1", "name": "Doc", "browserLink": "https://x", "workspace": {}, "folder": {}}], "nextPageToken": None}
    pages_resp = {"items": []}
    tables_resp = {"items": [{"id": "grid-1", "name": "T1", "browserLink": "https://x", "parent": {}}]}
    rows_resp = {"items": [{"id": "r1", "name": "R1", "values": {"c1": "a"}, "browserLink": "https://x", "createdAt": None, "updatedAt": None}]}
    get_calls = []

    async def fake_get(client, path, params=None):
        get_calls.append(path)
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

    with patch.object(coda_source, "_get", side_effect=fake_get), patch.object(
        coda_source, "http_client"
    ) as mock_http_ctx:
        mock_client = MagicMock()
        mock_http_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_http_ctx.return_value.__aexit__ = AsyncMock(return_value=None)
        entities = []
        async for e in coda_source.generate_entities():
            entities.append(e)
        row_entities = [e for e in entities if isinstance(e, CodaRowEntity)]
        assert len(row_entities) == 1
        assert row_entities[0].entity_id == "r1"
        table_entities = [e for e in entities if isinstance(e, CodaTableEntity)]
        assert len(table_entities) == 1
        assert table_entities[0].row_count == 0
