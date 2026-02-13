"""
Async test module for Direct Authentication source connections.

Tests source connections that use direct authentication (API keys).
"""

import pytest
import httpx
import asyncio
from typing import Dict


class TestDirectAuthentication:
    """Test suite for direct authentication source connections."""

    @pytest.mark.asyncio
    async def test_create_stripe_connection(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test creating a Stripe connection with API key."""
        payload = {
            "name": "Test Stripe Connection",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing direct authentication with API key",
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()

        connection = response.json()
        assert connection["id"]
        assert connection["name"] == "Test Stripe Connection"
        assert connection["short_name"] == "stripe"
        assert connection["auth"]["method"] == "direct"
        assert connection["auth"]["authenticated"] == True
        assert connection["status"] == "active"

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_direct_auth_defaults_sync_immediately_true(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that direct auth defaults to sync_immediately=True when not specified."""
        payload = {
            "name": "Test Direct Auth Default Sync",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            # Note: sync_immediately is not specified, should default to True
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Check that sync was triggered (would have sync details)
        assert connection["sync"] is not None

        # Wait for sync to start
        await asyncio.sleep(2)

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_create_connection_with_immediate_sync(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test creating a connection with immediate sync."""
        payload = {
            "name": "Stripe with Auto Sync",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": True,
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()
        assert connection["sync"] is not None
        assert connection["sync"]["last_job"]["status"] == "pending"

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_update_api_key(self, api_client: httpx.AsyncClient, collection: Dict, config):
        """Test updating the API key of a direct auth connection."""
        # Create connection
        payload = {
            "name": "Update API Key Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # Verify it's direct auth
        assert connection["auth"]["method"] == "direct"

        # Update with new API key (same key in test, but demonstrates the flow)
        update_payload = {
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}}
        }

        response = await api_client.patch(
            f"/source-connections/{connection['id']}", json=update_payload
        )

        response.raise_for_status()
        updated = response.json()
        assert updated["auth"]["method"] == "direct"
        assert updated["auth"]["authenticated"] == True

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_trigger_manual_sync(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test triggering a manual sync."""
        # Create connection
        payload = {
            "name": "Manual Sync Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # Trigger manual sync
        response = await api_client.post(f"/source-connections/{connection['id']}/run")

        response.raise_for_status()
        job = response.json()
        assert job["id"]
        assert job["source_connection_id"] == connection["id"]
        assert job["status"] in ["pending", "running"]

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_sync_completion(self, api_client: httpx.AsyncClient, collection: Dict, config):
        """Test that sync completes successfully."""
        # Create connection and trigger sync
        payload = {
            "name": "Sync Completion Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": True,
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # Wait for sync to complete
        await asyncio.sleep(30)  # Wait for sync to process

        response = await api_client.get(f"/source-connections/{connection['id']}")
        response.raise_for_status()
        updated_connection = response.json()

        assert updated_connection["sync"]["last_job"]["status"] in ["completed", "running"]
        # Verify individual entity metrics are tracked
        assert updated_connection["sync"]["last_job"]["entities_inserted"] >= 0
        assert updated_connection["sync"]["last_job"]["entities_updated"] >= 0

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, api_client: httpx.AsyncClient, collection: Dict):
        """Test creating connection with invalid API key."""
        payload = {
            "name": "Invalid API Key Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": "sk_test_invalid_key_12345"}},
        }

        response = await api_client.post("/source-connections", json=payload)

        # Should still create the connection (validation happens during sync)
        if response.status_code == 200:
            connection = response.json()
            # Cleanup
            await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_connection_with_schedule(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test creating connection with CRON schedule."""
        payload = {
            "name": "Scheduled Connection",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": "0 */6 * * *"},  # Every 6 hours
        }

        response = await api_client.post("/source-connections", json=payload)

        body = response.json()
        response.raise_for_status()
        connection = response.json()
        assert connection["schedule"]["cron"] == "0 */6 * * *"

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_delete_connection(self, api_client: httpx.AsyncClient, collection: Dict, config):
        """Test deleting a connection."""
        # Create connection
        payload = {
            "name": "Connection to Delete",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # Delete connection
        response = await api_client.delete(f"/source-connections/{connection['id']}")

        assert response.status_code == 200

        # Verify it's deleted
        response = await api_client.get(f"/source-connections/{connection['id']}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_concurrent_connection_creation(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test creating multiple connections concurrently."""

        async def create_connection(i: int):
            payload = {
                "name": f"Concurrent Connection {i}",
                "short_name": "stripe",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            }
            response = await api_client.post("/source-connections", json=payload)
            if response.status_code == 200:
                return response.json()
            return None

        # Create 3 connections concurrently
        results = await asyncio.gather(*[create_connection(i) for i in range(3)])
        connections = [c for c in results if c]

        assert len(connections) == 3, "Should create 3 connections"

        # Cleanup concurrently
        await asyncio.gather(
            *[api_client.delete(f"/source-connections/{c['id']}") for c in connections]
        )
