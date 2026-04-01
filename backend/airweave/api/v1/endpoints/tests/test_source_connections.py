"""API tests for source connections endpoints.

Focused coverage for Google Drive connection-scoped native search:
POST /source-connections/{source_connection_id}/native-search
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from airweave.api.conftest import TEST_ORG_ID
from airweave.models.source_connection import SourceConnection


def _make_source_connection(
    *,
    id: UUID,
    short_name: str = "google_drive",
) -> SourceConnection:
    return SourceConnection(
        id=id,
        organization_id=TEST_ORG_ID,
        name="Test Connection",
        description=None,
        short_name=short_name,
        config_fields={},
        readable_auth_provider_id=None,
        auth_provider_config=None,
        sync_id=None,
        readable_collection_id=None,
        connection_id=None,
        connection_init_session_id=None,
        is_authenticated=True,
        created_by_email="test@airweave.ai",
        modified_by_email="test@airweave.ai",
    )


class _FakeGoogleDriveSource:
    class _HttpClientStub:
        async def aclose(self) -> None:
            return None

    def __init__(self, results):
        self._results = results
        self.calls = []
        self.http_client = self._HttpClientStub()

    async def native_search(self, query: str, *, limit: int):
        self.calls.append({"query": query, "limit": limit})
        return list(self._results)


class _FakeNoNativeSearchSource:
    class _HttpClientStub:
        async def aclose(self) -> None:
            return None

    def __init__(self):
        self.http_client = self._HttpClientStub()


class TestSourceConnectionsNativeSearch:
    """Tests for POST /source-connections/{id}/native-search."""

    @pytest.mark.asyncio
    async def test_native_search_happy_path_returns_results(
        self,
        client,
        fake_source_connection_service,
        fake_source_lifecycle_service,
    ):
        source_connection_id = uuid4()
        fake_source_connection_service.seed(
            source_connection_id,
            _make_source_connection(id=source_connection_id, short_name="google_drive"),
        )

        fake_source = _FakeGoogleDriveSource(results=[])
        fake_source_lifecycle_service.seed_source(source_connection_id, fake_source)

        response = await client.post(
            f"/source-connections/{source_connection_id}/native-search",
            json={"query": "hello world", "limit": 5},
        )

        assert response.status_code == 200
        assert response.json() == {"results": []}
        assert fake_source.calls == [{"query": "hello world", "limit": 5}]

    @pytest.mark.asyncio
    async def test_native_search_rejects_non_google_drive_connection(
        self,
        client,
        fake_source_connection_service,
    ):
        source_connection_id = uuid4()
        fake_source_connection_service.seed(
            source_connection_id,
            _make_source_connection(id=source_connection_id, short_name="slack"),
        )

        response = await client.post(
            f"/source-connections/{source_connection_id}/native-search",
            json={"query": "hello world", "limit": 5},
        )

        assert response.status_code == 400
        assert (
            response.json()["detail"]
            == "native-search is only supported for google_drive source connections"
        )

    @pytest.mark.asyncio
    async def test_native_search_returns_500_if_source_missing_native_search(
        self,
        client,
        fake_source_connection_service,
        fake_source_lifecycle_service,
    ):
        source_connection_id = uuid4()
        fake_source_connection_service.seed(
            source_connection_id,
            _make_source_connection(id=source_connection_id, short_name="google_drive"),
        )

        fake_source_lifecycle_service.seed_source(source_connection_id, _FakeNoNativeSearchSource())

        response = await client.post(
            f"/source-connections/{source_connection_id}/native-search",
            json={"query": "hello world", "limit": 5},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "google_drive source does not implement native_search()"

    @pytest.mark.asyncio
    async def test_native_search_validates_query_not_empty(self, client):
        response = await client.post(
            f"/source-connections/{uuid4()}/native-search",
            json={"query": "   ", "limit": 5},
        )

        assert response.status_code == 422
