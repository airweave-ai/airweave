"""API endpoint tests for /source-connections.

Uses FakeSourceConnectionService via the test_container client fixture.
"""

from uuid import uuid4

import pytest
import pytest_asyncio

from airweave.domains.source_connections.exceptions import SourceConnectionNotFoundError


class TestSourceConnectionsList:
    @pytest.mark.asyncio
    async def test_list_returns_200(self, client):
        response = await client.get("/source-connections")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestSourceConnectionsGet:
    @pytest.mark.asyncio
    async def test_get_not_found_returns_404(self, client):
        response = await client.get(f"/source-connections/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_not_found_returns_detail(self, client):
        response = await client.get(f"/source-connections/{uuid4()}")
        assert response.status_code == 404
        assert "detail" in response.json()


class TestSourceConnectionsDelete:
    @pytest.mark.asyncio
    async def test_delete_not_found_returns_404(self, client):
        response = await client.delete(f"/source-connections/{uuid4()}")
        assert response.status_code == 404


class TestSourceConnectionsJobs:
    @pytest.mark.asyncio
    async def test_jobs_unknown_id_returns_empty_list(self, client):
        """Fake service returns empty list for unknown IDs (real service would 404)."""
        response = await client.get(f"/source-connections/{uuid4()}/jobs")
        assert response.status_code == 200
        assert response.json() == []
