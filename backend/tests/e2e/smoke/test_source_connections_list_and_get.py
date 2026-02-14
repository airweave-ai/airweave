"""
Async test module for source connection list and get operations.

Tests GET /source-connections and GET /source-connections/{id} response shapes.
These are regression tests for the code blue refactor to ensure
the response builder produces identical output pre/post migration.
"""

import pytest
import httpx
from typing import Dict


class TestListEndpoint:
    """Test GET /source-connections response shape and filtering."""

    @pytest.mark.asyncio
    async def test_list_empty_returns_empty_array(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """List with no connections returns empty array."""
        response = await api_client.get(
            "/source-connections", params={"collection": collection["readable_id"]}
        )
        response.raise_for_status()
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_returns_created_connection(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Created connection appears in list with correct shape."""
        payload = {
            "name": "List Test Connection",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }
        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # List and verify shape
        response = await api_client.get(
            "/source-connections", params={"collection": collection["readable_id"]}
        )
        response.raise_for_status()
        items = response.json()
        assert len(items) >= 1

        item = next(i for i in items if i["id"] == connection["id"])
        # Verify list item has expected fields
        assert "id" in item
        assert "name" in item
        assert "short_name" in item
        assert "status" in item
        assert "readable_collection_id" in item

        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_list_pagination(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """List respects skip and limit parameters."""
        # Create 3 connections
        connection_ids = []
        for i in range(3):
            payload = {
                "name": f"Pagination Test {i}",
                "short_name": "stripe",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
                "sync_immediately": False,
            }
            response = await api_client.post("/source-connections", json=payload)
            response.raise_for_status()
            connection_ids.append(response.json()["id"])

        # Page 1: limit=2
        response = await api_client.get(
            "/source-connections",
            params={"collection": collection["readable_id"], "limit": 2, "skip": 0},
        )
        response.raise_for_status()
        assert len(response.json()) == 2

        # Page 2: skip=2, limit=2
        response = await api_client.get(
            "/source-connections",
            params={"collection": collection["readable_id"], "limit": 2, "skip": 2},
        )
        response.raise_for_status()
        assert len(response.json()) >= 1

        # Cleanup
        for cid in connection_ids:
            await api_client.delete(f"/source-connections/{cid}")


class TestGetEndpoint:
    """Test GET /source-connections/{id} response shape."""

    @pytest.mark.asyncio
    async def test_get_returns_full_response_shape(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """GET single connection returns complete response with all sections."""
        payload = {
            "name": "Response Shape Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": "0 */6 * * *"},
            "sync_immediately": False,
        }
        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # GET and verify complete shape
        response = await api_client.get(f"/source-connections/{connection['id']}")
        response.raise_for_status()
        data = response.json()

        # Top-level fields
        assert data["id"] == connection["id"]
        assert data["name"] == "Response Shape Test"
        assert data["short_name"] == "stripe"
        assert data["readable_collection_id"] == collection["readable_id"]
        assert "status" in data
        assert "created_at" in data
        assert "modified_at" in data

        # Auth section
        assert "auth" in data
        assert data["auth"]["method"] == "direct"
        assert data["auth"]["authenticated"] is True

        # Schedule section
        assert "schedule" in data
        assert data["schedule"]["cron"] == "0 */6 * * *"

        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, api_client: httpx.AsyncClient):
        """GET non-existent connection returns 404."""
        response = await api_client.get(
            "/source-connections/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_after_delete_returns_404(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """GET returns 404 after connection is deleted."""
        payload = {
            "name": "Delete Then Get",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }
        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        await api_client.delete(f"/source-connections/{connection['id']}")

        response = await api_client.get(f"/source-connections/{connection['id']}")
        assert response.status_code == 404
