"""Unit tests for the query-then-delete-by-ID fast delete path.

Covers:
- _parse_vespa_document_id (ID parsing from Vespa's full document URI)
- _query_doc_ids_by_parent_ids (indexed YQL query to resolve doc IDs)
- _delete_by_doc_ids (parallel direct deletes by document ID)
- delete_by_parent_ids (end-to-end with fallback)

Uses table-driven tests where possible, mocks for Vespa I/O.
"""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import httpx
import pytest

from airweave.platform.destinations.vespa.client import VespaClient


COLLECTION_ID = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def client():
    """VespaClient with mocked pyvespa app."""
    app = MagicMock()
    app.query = MagicMock()
    return VespaClient(app=app)


# ---------------------------------------------------------------------------
# _parse_vespa_document_id
# ---------------------------------------------------------------------------


@dataclass
class ParseIdCase:
    desc: str
    full_id: str
    expected_schema: Optional[str]
    expected_doc_id: Optional[str]


PARSE_ID_CASES = [
    ParseIdCase(
        "standard chunk doc",
        "id:airweave:file_entity::file_entity_slack_msg_123__chunk_0",
        "file_entity",
        "file_entity_slack_msg_123__chunk_0",
    ),
    ParseIdCase(
        "base_entity schema",
        "id:airweave:base_entity::base_entity_doc_456__chunk_2",
        "base_entity",
        "base_entity_doc_456__chunk_2",
    ),
    ParseIdCase(
        "code_file_entity schema",
        "id:airweave:code_file_entity::code_file_entity_repo_main_py__chunk_0",
        "code_file_entity",
        "code_file_entity_repo_main_py__chunk_0",
    ),
    ParseIdCase(
        "missing id: prefix",
        "airweave:base_entity::some_id",
        None,
        None,
    ),
    ParseIdCase(
        "no :: separator",
        "id:airweave:base_entity:some_id",
        None,
        None,
    ),
    ParseIdCase(
        "empty string",
        "",
        None,
        None,
    ),
    ParseIdCase(
        "only prefix, no content after ::",
        "id:airweave:base_entity::",
        "base_entity",
        "",
    ),
]


@pytest.mark.parametrize("case", PARSE_ID_CASES, ids=lambda c: c.desc)
def test_parse_vespa_document_id(case: ParseIdCase):
    schema, doc_id = VespaClient._parse_vespa_document_id(case.full_id)
    assert schema == case.expected_schema
    assert doc_id == case.expected_doc_id


# ---------------------------------------------------------------------------
# _query_doc_ids_by_parent_ids
# ---------------------------------------------------------------------------


class TestQueryDocIdsByParentIds:

    @pytest.mark.asyncio
    async def test_resolves_hits_to_schema_doc_id_tuples(self, client):
        """Successful query returns parsed (schema, doc_id) tuples."""
        mock_response = MagicMock()
        mock_response.is_successful.return_value = True
        mock_response.hits = [
            {"id": "id:airweave:file_entity::file_entity_abc__chunk_0"},
            {"id": "id:airweave:file_entity::file_entity_abc__chunk_1"},
            {"id": "id:airweave:base_entity::base_entity_def__chunk_0"},
        ]
        client.app.query = MagicMock(return_value=mock_response)

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = mock_response
            result = await client._query_doc_ids_by_parent_ids(["abc", "def"], COLLECTION_ID)

        assert len(result) == 3
        assert result[0] == ("file_entity", "file_entity_abc__chunk_0")
        assert result[1] == ("file_entity", "file_entity_abc__chunk_1")
        assert result[2] == ("base_entity", "base_entity_def__chunk_0")

    @pytest.mark.asyncio
    async def test_empty_hits_returns_empty(self, client):
        """No matching chunks returns empty list."""
        mock_response = MagicMock()
        mock_response.is_successful.return_value = True
        mock_response.hits = []
        client.app.query = MagicMock(return_value=mock_response)

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = mock_response
            result = await client._query_doc_ids_by_parent_ids(["nonexistent"], COLLECTION_ID)

        assert result == []

    @pytest.mark.asyncio
    async def test_query_failure_raises(self, client):
        """Failed Vespa query raises RuntimeError."""
        mock_response = MagicMock()
        mock_response.is_successful.return_value = False
        mock_response.json = {"root": {"errors": [{"message": "bad query"}]}}

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = mock_response
            with pytest.raises(RuntimeError, match="Doc ID query failed"):
                await client._query_doc_ids_by_parent_ids(["x"], COLLECTION_ID)

    @pytest.mark.asyncio
    async def test_skips_unparseable_ids(self, client):
        """Hits with malformed document IDs are silently skipped."""
        mock_response = MagicMock()
        mock_response.is_successful.return_value = True
        mock_response.hits = [
            {"id": "id:airweave:base_entity::base_entity_ok__chunk_0"},
            {"id": "garbage"},
            {"id": "id:airweave:base_entity::base_entity_ok2__chunk_0"},
        ]

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = mock_response
            result = await client._query_doc_ids_by_parent_ids(["ok", "ok2"], COLLECTION_ID)

        assert len(result) == 2


# ---------------------------------------------------------------------------
# _delete_by_doc_ids
# ---------------------------------------------------------------------------


class TestDeleteByDocIds:

    @pytest.mark.asyncio
    async def test_deletes_all_docs_in_parallel(self, client):
        """All docs deleted returns correct count."""
        doc_ids = [
            ("file_entity", "file_entity_abc__chunk_0"),
            ("file_entity", "file_entity_abc__chunk_1"),
            ("base_entity", "base_entity_def__chunk_0"),
        ]

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_async_client = AsyncMock()
            mock_async_client.delete = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_async_client

            count = await client._delete_by_doc_ids(doc_ids)

        assert count == 3
        assert mock_async_client.delete.call_count == 3

    @pytest.mark.asyncio
    async def test_counts_partial_failures(self, client):
        """Some failures are counted separately from successes."""
        doc_ids = [
            ("file_entity", "doc_a"),
            ("file_entity", "doc_b"),
        ]

        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        fail_resp = MagicMock(spec=httpx.Response)
        fail_resp.status_code = 404

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_async_client = AsyncMock()
            mock_async_client.delete = AsyncMock(side_effect=[success_resp, fail_resp])
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_async_client

            count = await client._delete_by_doc_ids(doc_ids)

        assert count == 1

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero(self, client):
        """Empty doc_ids list returns 0 without making requests."""
        count = await client._delete_by_doc_ids([])
        assert count == 0


# ---------------------------------------------------------------------------
# delete_by_parent_ids (end-to-end composition)
# ---------------------------------------------------------------------------


class TestDeleteByParentIds:

    @pytest.mark.asyncio
    async def test_happy_path_query_then_delete(self, client):
        """Normal flow: query resolves IDs, direct delete removes them."""
        resolved = [
            ("file_entity", "file_entity_p1__chunk_0"),
            ("file_entity", "file_entity_p1__chunk_1"),
        ]

        with (
            patch.object(
                client, "_query_doc_ids_by_parent_ids", new_callable=AsyncMock
            ) as mock_query,
            patch.object(client, "_delete_by_doc_ids", new_callable=AsyncMock) as mock_delete,
        ):
            mock_query.return_value = resolved
            mock_delete.return_value = 2

            results = await client.delete_by_parent_ids(["p1"], COLLECTION_ID)

        assert len(results) == 1
        assert results[0].deleted_count == 2
        mock_query.assert_awaited_once()
        mock_delete.assert_awaited_once_with(resolved)

    @pytest.mark.asyncio
    async def test_empty_parent_ids(self, client):
        """Empty input returns empty results without any calls."""
        results = await client.delete_by_parent_ids([], COLLECTION_ID)
        assert results == []

    @pytest.mark.asyncio
    async def test_no_chunks_found(self, client):
        """Parent IDs with no chunks in Vespa result in 0 deleted."""
        with patch.object(
            client, "_query_doc_ids_by_parent_ids", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = []

            results = await client.delete_by_parent_ids(["orphan"], COLLECTION_ID)

        assert results[0].deleted_count == 0

    @pytest.mark.asyncio
    async def test_falls_back_on_query_failure(self, client):
        """Query failure triggers fallback to selection-based delete."""
        with (
            patch.object(
                client, "_query_doc_ids_by_parent_ids", new_callable=AsyncMock
            ) as mock_query,
            patch.object(
                client, "_delete_by_parent_ids_selection", new_callable=AsyncMock
            ) as mock_fallback,
        ):
            mock_query.side_effect = RuntimeError("query boom")
            mock_fallback.return_value = 3

            results = await client.delete_by_parent_ids(["p1"], COLLECTION_ID)

        assert results[0].deleted_count == 3
        mock_fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_batches_large_parent_id_lists(self, client):
        """Parent IDs exceeding batch_size are split into multiple queries."""
        parent_ids = [f"p{i}" for i in range(5)]

        with (
            patch.object(
                client, "_query_doc_ids_by_parent_ids", new_callable=AsyncMock
            ) as mock_query,
            patch.object(client, "_delete_by_doc_ids", new_callable=AsyncMock) as mock_delete,
        ):
            mock_query.return_value = [("base_entity", "base_entity_px__chunk_0")]
            mock_delete.return_value = 1

            results = await client.delete_by_parent_ids(
                parent_ids, COLLECTION_ID, batch_size=2
            )

        # ceil(5/2) = 3 batches
        assert mock_query.call_count == 3
        assert results[0].deleted_count == 3
