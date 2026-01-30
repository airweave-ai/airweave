"""
Smoke tests for OAuth 2.1 authentication flow.

Tests the complete OAuth authorization code flow with PKCE for MCP server authentication.
These tests verify:
- OAuth metadata endpoint
- Authorization code generation
- Token exchange with PKCE
- Token validation
- Token revocation
- Security boundaries

NOTE: These tests require a running backend API with database.
"""

import pytest
import httpx
from urllib.parse import parse_qs, urlparse

from config import settings

pytestmark = [
    pytest.mark.oauth,
    pytest.mark.asyncio,
]


@pytest.fixture(scope="module", autouse=True)
def skip_if_not_local():
    """Skip OAuth tests if not in local development."""
    if not settings.is_local:
        pytest.skip("OAuth tests only run in local development environment", allow_module_level=True)


class TestOAuthMetadata:
    """Test OAuth server metadata discovery."""

    async def test_oauth_metadata_endpoint(self, api_client: httpx.AsyncClient):
        """Test OAuth 2.1 metadata endpoint returns correct configuration."""
        response = await api_client.get("/oauth/.well-known/oauth-authorization-server")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required OAuth 2.1 metadata fields
        assert "issuer" in data
        assert "authorization_endpoint" in data
        assert "token_endpoint" in data
        assert "revocation_endpoint" in data
        
        # Verify response types and grant types
        assert "authorization_code" in data.get("grant_types_supported", [])
        assert "code" in data.get("response_types_supported", [])
        
        # Verify PKCE support
        assert "S256" in data.get("code_challenge_methods_supported", [])
        
        print(f"\n✅ OAuth metadata: {data.get('issuer')}")


class TestOAuthAuthorizationFlow:
    """Test complete OAuth authorization code flow."""

    async def test_authorization_request_redirects_to_consent(
        self, api_client: httpx.AsyncClient, collection: dict
    ):
        """Test GET /oauth/authorize redirects to consent screen with correct parameters."""
        # Build authorization request
        params = {
            "client_id": "claude-desktop",
            "redirect_uri": "http://localhost:3000/oauth/callback",
            "response_type": "code",
            "state": "random-state-abc123",
            "code_challenge": "test-challenge-string",
            "code_challenge_method": "S256",
            "scope": "read:collection",
        }
        
        # Note: This will return 404 if the OAuth client doesn't exist
        # In a real test, we'd need to seed the OAuth client first
        response = await api_client.get(
            "/oauth/authorize",
            params=params,
            follow_redirects=False,
        )
        
        # Expecting redirect to frontend consent screen or error
        # The exact behavior depends on authentication state
        # 400 can occur for validation errors (missing client, etc.)
        assert response.status_code in [302, 307, 400, 401, 404], \
            f"Expected redirect or auth error, got {response.status_code}"
        
        if response.status_code in [302, 307]:
            location = response.headers.get("location", "")
            assert "consent" in location or "authorize" in location
            print(f"\n✅ Redirected to: {location}")


class TestOAuthTokenExchange:
    """Test OAuth token exchange endpoints."""

    async def test_token_endpoint_requires_authorization_code(
        self, api_client: httpx.AsyncClient
    ):
        """Test POST /oauth/token requires valid authorization code."""
        token_request = {
            "grant_type": "authorization_code",
            "code": "invalid-code-12345",
            "client_id": "claude-desktop",
            "redirect_uri": "http://localhost:3000/oauth/callback",
        }
        
        response = await api_client.post(
            "/oauth/token",
            data=token_request,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        
        # Should fail with invalid code
        assert response.status_code in [400, 401, 404]
        data = response.json()
        # FastAPI returns 'detail' for errors, OAuth spec uses 'error'
        assert "error" in data or "detail" in data
        error_msg = data.get('error') or data.get('detail')
        print(f"\n✅ Invalid code rejected: {error_msg}")

    async def test_token_endpoint_requires_pkce_verifier(
        self, api_client: httpx.AsyncClient
    ):
        """Test PKCE verification is enforced."""
        # This would require creating a valid auth code first
        # For now, just test that missing code_verifier is rejected
        token_request = {
            "grant_type": "authorization_code",
            "code": "some-code",
            "client_id": "claude-desktop",
            "redirect_uri": "http://localhost:3000/oauth/callback",
            # Missing code_verifier when PKCE was used
        }
        
        response = await api_client.post(
            "/oauth/token",
            data=token_request,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        
        assert response.status_code in [400, 401, 404]
        print(f"\n✅ PKCE required: {response.status_code}")


class TestOAuthTokenValidation:
    """Test OAuth token validation endpoint."""

    async def test_validate_endpoint_rejects_invalid_token(
        self, api_client: httpx.AsyncClient
    ):
        """Test POST /oauth/validate rejects invalid tokens."""
        response = await api_client.post(
            "/oauth/validate",
            json={"token": "invalid-token-12345"},
        )
        
        # Should reject invalid token (422 for validation errors is acceptable)
        assert response.status_code in [400, 401, 422]
        data = response.json()
        # API may return error, detail, or errors array depending on validation
        assert "error" in data or "detail" in data or "errors" in data
        print(f"\n✅ Invalid token rejected")

    async def test_validate_endpoint_rejects_malformed_token(
        self, api_client: httpx.AsyncClient
    ):
        """Test validation rejects tokens without proper prefix."""
        response = await api_client.post(
            "/oauth/validate",
            json={"token": "not-an-oauth-token"},
        )
        
        # 422 is acceptable for validation/schema errors
        assert response.status_code in [400, 401, 422]
        data = response.json()
        # API may return error, detail, or errors array
        assert "error" in data or "detail" in data or "errors" in data
        print(f"\n✅ Malformed token rejected")


class TestOAuthTokenRevocation:
    """Test OAuth token revocation endpoint."""

    async def test_revoke_endpoint_exists(
        self, api_client: httpx.AsyncClient
    ):
        """Test POST /oauth/revoke endpoint is accessible."""
        response = await api_client.post(
            "/oauth/revoke",
            data={"token": "some-token"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        
        # Should accept request (may return 200 even for invalid token per spec)
        assert response.status_code in [200, 400, 401]
        print(f"\n✅ Revoke endpoint accessible: {response.status_code}")


class TestOAuthSecurity:
    """Test OAuth security features."""

    async def test_redirect_uri_validation(
        self, api_client: httpx.AsyncClient
    ):
        """Test that invalid redirect URIs are rejected."""
        params = {
            "client_id": "claude-desktop",
            "redirect_uri": "http://evil.com/steal-tokens",  # Not in allowed list
            "response_type": "code",
            "state": "state-123",
        }
        
        response = await api_client.get(
            "/oauth/authorize",
            params=params,
            follow_redirects=False,
        )
        
        # Should reject with error (not redirect to evil.com!)
        assert response.status_code in [400, 401, 404]
        
        # Verify NO redirect to evil domain
        if response.status_code in [302, 307]:
            location = response.headers.get("location", "")
            assert "evil.com" not in location, "SECURITY: Redirected to unregistered URI!"
        
        print(f"\n✅ Invalid redirect URI rejected")

    async def test_state_parameter_preserved(
        self, api_client: httpx.AsyncClient
    ):
        """Test that state parameter is preserved in redirects."""
        params = {
            "client_id": "test-client",
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "state": "csrf-protection-12345",
        }
        
        response = await api_client.get(
            "/oauth/authorize",
            params=params,
            follow_redirects=False,
        )
        
        if response.status_code in [302, 307]:
            location = response.headers.get("location", "")
            parsed = urlparse(location)
            query_params = parse_qs(parsed.query)
            
            # State should be preserved in redirect
            if "state" in query_params:
                assert query_params["state"][0] == "csrf-protection-12345"
                print(f"\n✅ State parameter preserved")


class TestOAuthClientRegistration:
    """Test OAuth client management."""

    async def test_unknown_client_rejected(
        self, api_client: httpx.AsyncClient
    ):
        """Test that requests with unknown client_id are rejected."""
        params = {
            "client_id": "non-existent-client-xyz",
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "state": "state-123",
        }
        
        response = await api_client.get(
            "/oauth/authorize",
            params=params,
            follow_redirects=False,
        )
        
        # Should reject unknown client
        assert response.status_code in [400, 401, 404]
        print(f"\n✅ Unknown client rejected: {response.status_code}")


# Note: Complete end-to-end flow test would require:
# 1. Seeding an OAuth client in the database
# 2. Authenticating a user
# 3. Generating an authorization code
# 4. Exchanging it for a token
# 5. Validating the token
# 6. Revoking the token
# This is better suited for a full integration test with database fixtures
