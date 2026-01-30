"""Unit tests for OAuth CRUD operations."""

import pytest

from airweave import crud


class TestOAuthClientCRUD:
    """Test OAuth client CRUD methods (non-database)."""

    def test_validate_redirect_uri_logic(self):
        """Test redirect URI validation logic."""
        # Create a mock client object
        class MockClient:
            redirect_uris = [
                "http://localhost:3000/callback",
                "http://localhost:3000/other-callback",
            ]
        
        mock_client = MockClient()
        
        # Valid URIs should pass
        assert crud.oauth_client.validate_redirect_uri(
            mock_client, "http://localhost:3000/callback"
        ) is True
        assert crud.oauth_client.validate_redirect_uri(
            mock_client, "http://localhost:3000/other-callback"
        ) is True
        
        # Invalid URI should fail
        assert crud.oauth_client.validate_redirect_uri(
            mock_client, "http://evil.com/callback"
        ) is False


# Note: Database-dependent CRUD tests (create, get_by_id, etc.) are in
# tests/e2e/test_oauth_flow.py where they can use real database fixtures
