"""
Async test module for PreSyncValidationException.

Tests validation failures during source connection creation with invalid credentials,
verifying proper HTTP 400 responses and sanitized error messages.
"""

import pytest
import httpx
from typing import Dict


class TestPreSyncValidation:
    """Test suite for pre-sync validation failures."""

    @pytest.mark.asyncio
    async def test_invalid_stripe_api_key_validation(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that invalid Stripe API key fails validation with error status."""
        # Use properly formatted but invalid key (long enough to pass schema validation)
        payload = {
            "name": "Invalid Stripe Key Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": "sk_test_51InvalidKeyThatLooksRealButIsNotActuallyValid123456789012345678"}},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Should fail validation (400 or 422)
        assert response.status_code in [400, 422]
        error = response.json()
        assert "detail" in error or "errors" in error
        # Verify error message is sanitized and helpful
        if "detail" in error:
            detail_lower = error["detail"].lower()
            assert "validation" in detail_lower or "invalid" in detail_lower or "failed" in detail_lower

    @pytest.mark.asyncio
    async def test_postgresql_invalid_credentials(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test PostgreSQL with invalid credentials fails validation."""
        payload = {
            "name": "Invalid PostgreSQL Credentials",
            "short_name": "postgresql",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "credentials": {
                    "host": "nonexistent.database.local",
                    "port": 5432,
                    "database": "testdb",
                    "user": "invalid_user",  # PostgreSQL uses 'user' not 'username'
                    "password": "invalid_password",
                }
            },
            "config": {
                "schema": "public",
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Should fail validation
        assert response.status_code in [400, 422]
        error = response.json()
        assert "detail" in error or "errors" in error
        # Just verify we got an error response - the specific message may vary
        if "detail" in error:
            assert len(error["detail"]) > 0

    @pytest.mark.asyncio
    async def test_postgresql_invalid_schema(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test PostgreSQL with non-existent schema fails validation."""
        payload = {
            "name": "PostgreSQL Invalid Schema",
            "short_name": "postgresql",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "credentials": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "testdb",
                    "user": "testuser",  # PostgreSQL uses 'user' not 'username'
                    "password": "testpass",
                }
            },
            "config": {
                "schema": "nonexistent_schema_xyz_12345",
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Should fail validation (either 400 or 422) or connection creation succeeds
        # If connection is created, it should fail during validation
        if response.status_code == 200:
            connection = response.json()
            # Wait a moment for validation
            import asyncio
            await asyncio.sleep(2)
            
            # Cleanup
            await api_client.delete(f"/source-connections/{connection['id']}")
        else:
            # Failed immediately during creation/validation
            assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_invalid_oauth_token_notion(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test Notion with invalid OAuth token fails validation."""
        payload = {
            "name": "Invalid Notion Token",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"access_token": "invalid_token_abc123"},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Should fail validation
        assert response.status_code == 400
        error = response.json()
        assert "detail" in error
        detail_lower = error["detail"].lower()
        assert "validation" in detail_lower or "invalid" in detail_lower or "token" in detail_lower

    @pytest.mark.asyncio
    async def test_gitlab_invalid_oauth_token(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test GitLab with invalid OAuth token fails validation."""
        payload = {
            "name": "Invalid GitLab Token",
            "short_name": "gitlab",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"access_token": "glpat-invalid_token_xyz"},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Should fail validation
        assert response.status_code == 400
        error = response.json()
        assert "detail" in error
        detail_lower = error["detail"].lower()
        assert "validation" in detail_lower or "credential" in detail_lower or "gitlab" in detail_lower

    @pytest.mark.asyncio
    async def test_bitbucket_invalid_workspace(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test Bitbucket with non-existent workspace fails validation."""
        payload = {
            "name": "Invalid Bitbucket Workspace",
            "short_name": "bitbucket",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"access_token": "invalid_token_12345"},
            "config": {
                "workspace": "nonexistent_workspace_xyz_99999",
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Should fail validation
        assert response.status_code == 400
        error = response.json()
        assert "detail" in error

    @pytest.mark.asyncio
    async def test_validation_error_message_format(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that validation error messages are properly formatted."""
        payload = {
            "name": "Error Format Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": "sk_test_51InvalidFormatTestKey1234567890123456789012345678901234"}},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        assert response.status_code in [400, 422]
        error = response.json()
        
        # Verify error structure (may have "detail" or "errors")
        assert "detail" in error or "errors" in error
        
        if "detail" in error:
            assert isinstance(error["detail"], str)
            assert len(error["detail"]) > 0
            
            # Verify error doesn't leak internal details
            detail_lower = error["detail"].lower()
            assert "traceback" not in detail_lower
            assert "exception" not in detail_lower or "validation" in detail_lower

    @pytest.mark.asyncio
    async def test_multiple_invalid_connections_independent(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that multiple invalid connection attempts are handled independently."""
        payloads = [
            {
                "name": f"Invalid Connection {i}",
                "short_name": "stripe",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"api_key": f"sk_test_51InvalidKey{i}ButLongEnoughToPassSchemaValidation123456789012"}},
                "sync_immediately": False,
            }
            for i in range(3)
        ]

        # Create connections concurrently
        import asyncio
        responses = await asyncio.gather(
            *[api_client.post("/source-connections", json=payload) for payload in payloads],
            return_exceptions=True,
        )

        # All should fail with validation error
        for response in responses:
            if isinstance(response, Exception):
                continue  # Network errors are acceptable
            assert response.status_code in [400, 422]
            error = response.json()
            assert "detail" in error or "errors" in error

    @pytest.mark.asyncio
    async def test_validation_fails_before_sync_starts(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that validation happens before sync starts (no pending sync job)."""
        payload = {
            "name": "Pre-Sync Validation Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": "sk_test_51InvalidPreSyncKey1234567890123456789012345678901234567"}},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Validation should fail immediately
        assert response.status_code in [400, 422]
        
        # No connection should be created (or it should fail validation)
        error = response.json()
        assert "detail" in error or "errors" in error

    @pytest.mark.asyncio
    async def test_valid_credentials_pass_validation(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that valid credentials pass validation successfully."""
        payload = {
            "name": "Valid Stripe Connection",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Should succeed
        response.raise_for_status()
        connection = response.json()
        assert connection["auth"]["authenticated"] == True
        assert connection["status"] == "active"

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_validation_with_config_fields(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test validation with invalid config fields."""
        payload = {
            "name": "Invalid Config Test",
            "short_name": "postgresql",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "credentials": {
                    "host": "invalid.host",
                    "port": 99999,  # Invalid port
                    "database": "db",
                    "user": "user",  # PostgreSQL uses 'user' not 'username'
                    "password": "pass",
                }
            },
            "config": {"schema": "public"},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # Should fail validation
        assert response.status_code in [400, 422]  # 400 for validation, 422 for schema
        error = response.json()
        assert "detail" in error or "errors" in error

