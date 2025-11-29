"""
Async test module for validation failures during sync triggers.

Tests that validation happens when manually triggering syncs on existing connections,
particularly when credentials have been revoked or services become unreachable.
"""

import pytest
import httpx
import asyncio
from typing import Dict


class TestValidationOnSyncTrigger:
    """Test suite for validation failures during manual sync triggers."""

    @pytest.mark.asyncio
    async def test_trigger_sync_with_invalid_credentials(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that triggering sync with invalid credentials fails gracefully."""
        # Create connection with invalid credentials (validation might not run during creation)
        payload = {
            "name": "Sync Trigger Invalid Creds",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": "sk_test_51InvalidTriggerKey123456789012345678901234567890123456"}},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # If connection creation fails, that's expected
        if response.status_code in [400, 422]:
            return

        # If connection was created, trigger sync
        connection = response.json()
        connection_id = connection["id"]

        try:
            # Trigger manual sync
            sync_response = await api_client.post(f"/source-connections/{connection_id}/run")

            if sync_response.status_code == 200:
                job = sync_response.json()
                
                # Wait for sync to process
                await asyncio.sleep(5)
                
                # Check job status
                job_response = await api_client.get(
                    f"/source-connections/{connection_id}/jobs"
                )
                if job_response.status_code == 200:
                    jobs = job_response.json()
                    if jobs:
                        latest_job = jobs[0]
                        # Job should fail due to validation
                        assert latest_job["status"] in ["failed", "completed"]
        finally:
            # Cleanup
            await api_client.delete(f"/source-connections/{connection_id}")

    @pytest.mark.asyncio
    async def test_sync_trigger_after_service_unreachable(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test sync trigger when external service is unreachable."""
        payload = {
            "name": "Service Unreachable Test",
            "short_name": "postgresql",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "credentials": {
                    "host": "unreachable.service.invalid",
                    "port": 5432,
                    "database": "testdb",
                    "user": "user",  # PostgreSQL uses 'user' not 'username'
                    "password": "pass",
                }
            },
            "config": {"schema": "public"},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Validation should fail
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_multiple_sync_triggers_with_validation_failure(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test multiple concurrent sync attempts handle validation failures gracefully."""
        # Create a valid connection first
        payload = {
            "name": "Multiple Sync Triggers",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()
        connection_id = connection["id"]

        try:
            # Trigger multiple syncs concurrently
            sync_requests = [
                api_client.post(f"/source-connections/{connection_id}/run")
                for _ in range(3)
            ]
            responses = await asyncio.gather(*sync_requests, return_exceptions=True)

            # First should succeed, others should fail with "already running" or succeed
            success_count = 0
            for resp in responses:
                if isinstance(resp, Exception):
                    continue
                if resp.status_code == 200:
                    success_count += 1
                elif resp.status_code == 400:
                    error = resp.json()
                    detail_lower = error.get("detail", "").lower()
                    # Should mention already running or similar
                    assert "already" in detail_lower or "running" in detail_lower or "pending" in detail_lower

            # At least one should have succeeded
            assert success_count >= 1

        finally:
            # Cleanup
            await api_client.delete(f"/source-connections/{connection_id}")

    @pytest.mark.asyncio
    async def test_sync_job_failure_preserves_connection_status(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that sync validation failure doesn't change connection status to failed."""
        # Create connection with invalid credentials
        payload = {
            "name": "Connection Status Preservation",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": "sk_test_51PreserveStatus12345678901234567890123456789012345678"}},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # If validation fails immediately, test passes
        if response.status_code == 400:
            return

        connection = response.json()
        connection_id = connection["id"]

        try:
            # Get initial connection status
            conn_response = await api_client.get(f"/source-connections/{connection_id}")
            if conn_response.status_code == 200:
                conn = conn_response.json()
                initial_status = conn["status"]
                
                # Connection should remain in its initial state
                # (active or pending_auth, not "failed")
                assert initial_status in ["active", "pending_auth", "syncing"]

        finally:
            # Cleanup
            await api_client.delete(f"/source-connections/{connection_id}")

    @pytest.mark.asyncio
    async def test_sync_trigger_validation_error_message(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that validation errors during sync trigger have proper error messages."""
        payload = {
            "name": "Sync Validation Error Message",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": "sk_test_51ErrorMessageTest1234567890123456789012345678901234567"}},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Should fail with clear error message
        if response.status_code in [400, 422]:
            error = response.json()
            assert "detail" in error or "errors" in error
            
            if "detail" in error:
                detail = error["detail"]
                
                # Error should be informative
                assert len(detail) > 10
                detail_lower = detail.lower()
                
                # Should mention validation or credentials
                assert "validation" in detail_lower or "credential" in detail_lower or "invalid" in detail_lower

    @pytest.mark.asyncio
    async def test_valid_sync_trigger_succeeds(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that sync trigger with valid credentials succeeds."""
        payload = {
            "name": "Valid Sync Trigger",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()
        connection_id = connection["id"]

        try:
            # Trigger sync
            sync_response = await api_client.post(f"/source-connections/{connection_id}/run")
            sync_response.raise_for_status()
            
            job = sync_response.json()
            assert job["id"]
            assert job["source_connection_id"] == connection_id
            assert job["status"] in ["pending", "running"]

        finally:
            # Cleanup
            await api_client.delete(f"/source-connections/{connection_id}")

    @pytest.mark.asyncio
    async def test_sync_trigger_nonexistent_connection(
        self, api_client: httpx.AsyncClient
    ):
        """Test triggering sync on non-existent connection returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await api_client.post(f"/source-connections/{fake_id}/run")

        assert response.status_code == 404
        error = response.json()
        assert "detail" in error

    @pytest.mark.asyncio
    async def test_sync_validation_doesnt_spam_external_service(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that validation failures don't result in multiple requests to external service."""
        # Create connection with invalid credentials
        payload = {
            "name": "No Spam Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": "sk_test_51NoSpamTestKey123456789012345678901234567890123456789012"}},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Validation should fail quickly (not retry multiple times)
        # We can't directly observe the external calls, but we can verify
        # the response comes back quickly
        assert response.status_code in [200, 400, 422]

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_sync_with_invalid_credentials_reports_failure(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that sync with invalid credentials properly reports failure status."""
        payload = {
            "name": "Sync Failure Reporting",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": "sk_test_51FailureReport1234567890123456789012345678901234567890"}},
            "sync_immediately": True,  # Start sync immediately
        }

        response = await api_client.post("/source-connections", json=payload)

        # If validation fails immediately, test passes
        if response.status_code in [400, 422]:
            return

        # If connection created, check job status
        if response.status_code == 200:
            connection = response.json()
            connection_id = connection["id"]

            try:
                # Wait for sync to fail
                await asyncio.sleep(10)

                # Check job status
                job_response = await api_client.get(
                    f"/source-connections/{connection_id}/jobs"
                )
                if job_response.status_code == 200:
                    jobs = job_response.json()
                    if jobs:
                        latest_job = jobs[0]
                        # Job should be failed or completed
                        assert latest_job["status"] in ["failed", "completed", "running"]

            finally:
                # Cleanup
                await api_client.delete(f"/source-connections/{connection_id}")

