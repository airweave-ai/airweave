"""
Async test module for source connection update operations.

Tests PATCH /source-connections/{id} for name, description, schedule,
and config updates. These are regression tests for the code blue refactor.
"""

import pytest
import httpx
from typing import Dict


class TestUpdateName:
    """Test updating connection name and description."""

    @pytest.mark.asyncio
    async def test_update_name(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Update name on a direct auth connection."""
        payload = {
            "name": "Original Name",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }
        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Update name
        response = await api_client.patch(
            f"/source-connections/{connection['id']}",
            json={"name": "Updated Name"},
        )
        response.raise_for_status()
        updated = response.json()
        assert updated["name"] == "Updated Name"

        # Verify GET reflects the change
        response = await api_client.get(f"/source-connections/{connection['id']}")
        response.raise_for_status()
        assert response.json()["name"] == "Updated Name"

        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_update_description(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Update description on a direct auth connection."""
        payload = {
            "name": "Description Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }
        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        response = await api_client.patch(
            f"/source-connections/{connection['id']}",
            json={"description": "New description"},
        )
        response.raise_for_status()
        assert response.json()["description"] == "New description"

        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_update_name_too_short_rejected(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Name shorter than 4 chars should be rejected (422)."""
        payload = {
            "name": "Name Validation Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }
        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        response = await api_client.patch(
            f"/source-connections/{connection['id']}",
            json={"name": "ab"},
        )
        assert response.status_code == 422

        await api_client.delete(f"/source-connections/{connection['id']}")


class TestUpdateSchedule:
    """Test updating sync schedule."""

    @pytest.mark.asyncio
    async def test_add_schedule_to_connection(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Add a cron schedule to a connection that didn't have one."""
        payload = {
            "name": "Schedule Add Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }
        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Add schedule
        response = await api_client.patch(
            f"/source-connections/{connection['id']}",
            json={"schedule": {"cron": "0 */12 * * *"}},
        )
        response.raise_for_status()
        updated = response.json()
        assert updated["schedule"]["cron"] == "0 */12 * * *"

        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_update_existing_schedule(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Change cron schedule on an existing connection."""
        payload = {
            "name": "Schedule Update Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": "0 */6 * * *"},
            "sync_immediately": False,
        }
        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()
        assert connection["schedule"]["cron"] == "0 */6 * * *"

        # Update schedule
        response = await api_client.patch(
            f"/source-connections/{connection['id']}",
            json={"schedule": {"cron": "0 0 * * *"}},
        )
        response.raise_for_status()
        updated = response.json()
        assert updated["schedule"]["cron"] == "0 0 * * *"

        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_remove_schedule(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Remove schedule by setting cron to null."""
        payload = {
            "name": "Schedule Remove Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": "0 */6 * * *"},
            "sync_immediately": False,
        }
        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Remove schedule
        response = await api_client.patch(
            f"/source-connections/{connection['id']}",
            json={"schedule": {"cron": None}},
        )
        response.raise_for_status()
        updated = response.json()
        assert updated["schedule"]["cron"] is None

        await api_client.delete(f"/source-connections/{connection['id']}")


class TestUpdateNegative:
    """Test update error cases."""

    @pytest.mark.asyncio
    async def test_update_nonexistent_connection_returns_404(
        self, api_client: httpx.AsyncClient
    ):
        """PATCH on non-existent connection returns 404."""
        response = await api_client.patch(
            "/source-connections/00000000-0000-0000-0000-000000000000",
            json={"name": "Does Not Exist"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_empty_body_rejected(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Empty update body should be rejected (422)."""
        payload = {
            "name": "Empty Update Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }
        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        response = await api_client.patch(
            f"/source-connections/{connection['id']}",
            json={},
        )
        assert response.status_code == 422

        await api_client.delete(f"/source-connections/{connection['id']}")
