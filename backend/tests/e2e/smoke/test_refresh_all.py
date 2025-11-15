"""Test suite for refresh_all endpoint - Issue #1037 fix verification."""

import pytest
import httpx
from typing import Dict


class TestRefreshAll:
    """Test the /collections/{readable_id}/refresh_all endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_all_with_no_connections(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test refresh_all on a collection with no source connections.
        
        This verifies the fix for issue - the endpoint should work
        without throwing AttributeError about get_source_connections_by_collection.
        """
        response = await api_client.post(
            f"/collections/{collection['readable_id']}/refresh_all"
        )

        assert response.status_code == 200, f"Failed: {response.text}"
        jobs = response.json()
        assert isinstance(jobs, list)
        assert len(jobs) == 0  # No connections = no jobs

    @pytest.mark.asyncio 
    async def test_refresh_all_collection_not_found(self, api_client: httpx.AsyncClient):
        """Test refresh_all on a non-existent collection."""
        response = await api_client.post("/collections/non-existent-xyz/refresh_all")

        assert response.status_code == 404
        error = response.json()
        assert "detail" in error
