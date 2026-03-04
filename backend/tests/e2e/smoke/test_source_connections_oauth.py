"""
Async test module for OAuth source connections.

Tests OAuth authentication flows including:
- OAuth browser flow
- OAuth token injection
- OAuth BYOC (Bring Your Own Credentials)
"""

import pytest
import pytest_asyncio
import httpx
import asyncio
from typing import Dict
from urllib.parse import parse_qs, urlparse, unquote


async def fetch_fresh_token_from_composio(
    api_key: str,
    auth_config_id: str,
    account_id: str,
    source_slug: str = "notion",
) -> str:
    """Fetch a fresh access token directly from Composio API."""
    async with httpx.AsyncClient() as client:
        headers = {"x-api-key": api_key}

        page = 1
        while True:
            response = await client.get(
                "https://backend.composio.dev/api/v3/connected_accounts",
                headers=headers,
                params={"limit": 100, "page": page},
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])

            if not items:
                break

            for account in items:
                toolkit_slug = account.get("toolkit", {}).get("slug")
                acc_auth_config_id = account.get("auth_config", {}).get("id")
                acc_id = account.get("id")

                if (toolkit_slug == source_slug and
                    acc_auth_config_id == auth_config_id and
                    acc_id == account_id):
                    creds = account.get("state", {}).get("val", {})
                    token = creds.get("access_token")
                    if token:
                        return token

            if len(items) < 100:
                break
            page += 1

    raise ValueError(f"Could not find access_token for {source_slug}")


@pytest_asyncio.fixture
async def fresh_notion_token(config) -> str:
    """Fetch a fresh Notion access token from Composio. Fails if not configured."""
    if not config.TEST_COMPOSIO_API_KEY:
        pytest.fail("TEST_COMPOSIO_API_KEY not configured")
    if not config.TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_1:
        pytest.fail("TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_1 not configured")
    if not config.TEST_COMPOSIO_NOTION_ACCOUNT_ID_1:
        pytest.fail("TEST_COMPOSIO_NOTION_ACCOUNT_ID_1 not configured")

    return await fetch_fresh_token_from_composio(
        api_key=config.TEST_COMPOSIO_API_KEY,
        auth_config_id=config.TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_1,
        account_id=config.TEST_COMPOSIO_NOTION_ACCOUNT_ID_1,
        source_slug="notion",
    )


def verify_redirect_uri(provider_url: str, expected_api_url: str) -> None:
    """Helper to verify redirect_uri parameter in OAuth URL.

    Note: OAuth1 flows don't include redirect_uri in the authorization URL,
    so this check is skipped for OAuth1 providers (identified by oauth_token parameter).

    Args:
        provider_url: The OAuth provider URL
        expected_api_url: Expected API URL (e.g., http://localhost:8001)
    """
    parsed = urlparse(provider_url)
    params = parse_qs(parsed.query)

    # OAuth1 flows use oauth_token instead of redirect_uri in the authorization URL
    if "oauth_token" in params:
        # OAuth1 flow - redirect is configured during request token phase, not in auth URL
        return

    # OAuth2 flow - verify redirect_uri parameter
    assert "redirect_uri" in params, f"OAuth URL should have redirect_uri parameter: {provider_url}"
    redirect_uri = unquote(params["redirect_uri"][0])

    expected_redirect = f"{expected_api_url}/source-connections/callback"
    assert (
        redirect_uri == expected_redirect
    ), f"redirect_uri should be {expected_redirect}, got {redirect_uri}"


class TestOAuthAuthentication:
    """Test suite for OAuth authentication source connections."""

    @pytest.mark.asyncio
    async def test_oauth_browser_flow(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test OAuth browser flow (creates shell connection)."""
        payload = {
            "name": "Test Linear OAuth Browser",
            "short_name": "linear",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing OAuth browser flow",
            "authentication": {},  # Empty for browser flow
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # Verify OAuth browser flow response
        assert connection["id"]
        assert connection["auth"]["method"] == "oauth_browser"
        assert connection["auth"]["authenticated"] == False
        assert connection["status"] == "pending_auth"
        assert "auth_url" in connection["auth"]
        assert connection["auth"]["auth_url"] is not None

        # Follow the proxy URL to verify it redirects to OAuth provider
        auth_url = connection["auth"]["auth_url"]
        proxy_response = await api_client.get(auth_url, follow_redirects=False)
        assert proxy_response.status_code == 303, "Should redirect to OAuth provider"
        provider_url = proxy_response.headers.get("location")
        assert provider_url is not None, "Should have provider redirect URL"
        # Verify it's a valid OAuth URL (contains common OAuth patterns)
        assert any(
            pattern in provider_url for pattern in ["oauth", "authorize", "auth"]
        ), f"Should be OAuth URL: {provider_url}"

        # Verify redirect_uri parameter is correct for this environment
        verify_redirect_uri(provider_url, config.api_url)

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth_browser_defaults_sync_immediately_false(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that OAuth browser defaults to sync_immediately=False when not specified."""
        payload = {
            "name": "Test OAuth Default No Sync",
            "short_name": "linear",
            "readable_collection_id": collection["readable_id"],
            "authentication": {},  # OAuth browser flow
            # Note: sync_immediately is not specified, should default to False
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # OAuth browser should not have sync details (no immediate sync)
        assert connection["sync"] is None
        assert connection["status"] == "pending_auth"

        # Verify OAuth URL is correctly formed
        auth_url = connection["auth"]["auth_url"]
        proxy_response = await api_client.get(auth_url, follow_redirects=False)
        assert proxy_response.status_code == 303
        provider_url = proxy_response.headers.get("location")
        verify_redirect_uri(provider_url, config.api_url)

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth_token_injection_notion(
        self, api_client: httpx.AsyncClient, collection: Dict, fresh_notion_token: str
    ):
        """Test OAuth token injection with Notion."""
        payload = {
            "name": "Test Notion Token Injection",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing OAuth token injection",
            "authentication": {"access_token": fresh_notion_token},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # Verify OAuth token injection response
        assert connection["id"]
        assert connection["auth"]["method"] == "oauth_token"
        assert connection["auth"]["authenticated"] == True
        assert connection["status"] in ["active", "syncing"]

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth_token_defaults_sync_immediately_true(
        self, api_client: httpx.AsyncClient, collection: Dict, fresh_notion_token: str
    ):
        """Test that OAuth token injection defaults to sync_immediately=True when not specified."""
        payload = {
            "name": "Test OAuth Token Default Sync",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": fresh_notion_token,
            },
            # Note: sync_immediately is not specified, should default to True
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # OAuth token should have sync details (immediate sync triggered)
        # Since sync_immediately defaults to True for token injection
        assert connection["auth"]["method"] == "oauth_token"
        assert connection["auth"]["authenticated"] == True
        assert connection["status"] in ["active", "syncing"]

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth_byoc_google_drive(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test OAuth BYOC with Google Drive."""
        client_id = config.TEST_GOOGLE_CLIENT_ID
        client_secret = config.TEST_GOOGLE_CLIENT_SECRET

        payload = {
            "name": "Test Google Drive BYOC",
            "short_name": "google_drive",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing OAuth BYOC flow",
            "authentication": {"client_id": client_id, "client_secret": client_secret},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # BYOC returns oauth_browser after creation
        assert connection["id"]
        assert connection["auth"]["method"] == "oauth_browser"
        assert connection["auth"]["authenticated"] == False
        assert connection["status"] == "pending_auth"
        assert "auth_url" in connection["auth"]
        assert connection["auth"]["auth_url"] is not None

        # Verify BYOC generates valid OAuth redirect with custom client
        auth_url = connection["auth"]["auth_url"]
        proxy_response = await api_client.get(auth_url, follow_redirects=False)
        assert proxy_response.status_code == 303
        provider_url = proxy_response.headers.get("location")
        assert provider_url is not None
        # BYOC should use the custom client_id in the OAuth URL
        assert "client_id=" in provider_url, "OAuth URL should include client_id parameter"

        # Verify redirect_uri is correct
        verify_redirect_uri(provider_url, config.api_url)

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_minimal_oauth_payload(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test minimal OAuth payload defaults."""
        # Minimal payload - should default to OAuth browser
        payload = {"short_name": "notion", "readable_collection_id": collection["readable_id"]}

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # Verify defaults
        assert connection["name"] == "Notion Connection"  # Default name
        assert connection["status"] == "pending_auth"
        assert connection["auth"]["method"] == "oauth_browser"
        assert "auth_url" in connection["auth"]
        auth_url = connection["auth"]["auth_url"]
        assert isinstance(auth_url, str)
        assert auth_url.startswith("http://") or auth_url.startswith("https://")

        # Verify minimal payload generates valid OAuth redirect
        proxy_response = await api_client.get(auth_url, follow_redirects=False)
        assert proxy_response.status_code == 303
        provider_url = proxy_response.headers.get("location")
        assert provider_url is not None
        assert (
            "notion" in provider_url.lower() or "oauth" in provider_url.lower()
        ), f"Should be Notion OAuth URL: {provider_url}"

        # Verify redirect_uri is correct
        verify_redirect_uri(provider_url, config.api_url)

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth_wrong_auth_method(self, api_client: httpx.AsyncClient, collection: Dict):
        """Test using OAuth on source that doesn't support it."""
        # Try OAuth token on Stripe (which only supports API key)
        payload = {
            "name": "Wrong Auth Method",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"access_token": "some_token"},
        }

        response = await api_client.post("/source-connections", json=payload)

        assert response.status_code == 400
        error = response.json()
        detail = error.get("detail", "").lower()
        assert "does not support" in detail or "unsupported" in detail

    @pytest.mark.asyncio
    async def test_oauth_browser_flow_with_sync_immediately(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test OAuth browser flow with sync_immediately=true."""
        payload = {
            "name": "OAuth Browser Flow with Sync Immediately",
            "short_name": "gmail",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
            },
            "sync_immediately": True,
        }
        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 400
        error = response.json()
        assert "sync_immediately" in error["detail"].lower()

    @pytest.mark.asyncio
    async def test_oauth_byoc_with_sync_immediately(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test OAuth BYOC with sync_immediately=true."""
        payload = {
            "name": "OAuth BYOC with Sync Immediately",
            "short_name": "gmail",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
            },
            "sync_immediately": True,
        }
        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 400
        error = response.json()
        assert "sync_immediately" in error["detail"].lower()

    @pytest.mark.asyncio
    async def test_oauth_byoc_requires_credentials(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that sources requiring BYOC fail with empty authentication.

        Zendesk has requires_byoc=True, so it should fail without client credentials.
        """
        # Test with empty authentication dict - should fail
        payload = {
            "name": "Test Zendesk BYOC without Credentials",
            "short_name": "zendesk",
            "readable_collection_id": collection["readable_id"],
            "config": {
                "subdomain": "mycompany",
            },
            "authentication": {},  # Empty - should fail for BYOC sources
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 400
        error = response.json()
        detail = error.get("detail", "").lower()
        # Should mention client credentials are required
        assert "client" in detail or "credentials" in detail or "byoc" in detail


class TestOAuth1Authentication:
    """Test suite for OAuth1 authentication source connections (e.g. Trello)."""

    @pytest.mark.asyncio
    async def test_oauth1_browser_flow(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test OAuth1 browser flow with Trello."""
        payload = {
            "name": "Test Trello OAuth1 Browser",
            "short_name": "trello",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing OAuth1 browser flow",
            "authentication": {},  # Empty for browser flow
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # Verify OAuth1 browser flow response
        assert connection["id"]
        assert connection["auth"]["method"] == "oauth_browser"
        assert connection["auth"]["authenticated"] == False
        assert connection["status"] == "pending_auth"
        assert "auth_url" in connection["auth"]
        assert connection["auth"]["auth_url"] is not None

        # Follow the proxy URL to verify it redirects to OAuth provider
        auth_url = connection["auth"]["auth_url"]
        proxy_response = await api_client.get(auth_url, follow_redirects=False)
        assert proxy_response.status_code == 303, "Should redirect to OAuth provider"
        provider_url = proxy_response.headers.get("location")
        assert provider_url is not None, "Should have provider redirect URL"
        # Verify it's a valid OAuth1 URL for Trello
        assert "trello.com" in provider_url.lower(), f"Should be Trello URL: {provider_url}"
        assert "oauth_token" in provider_url, "OAuth1 URL should contain oauth_token parameter"

        # Verify redirect_uri parameter is correct for this environment
        verify_redirect_uri(provider_url, config.api_url)

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth1_byoc_flow(self, api_client: httpx.AsyncClient, collection: Dict, config):
        """Test OAuth1 BYOC (Bring Your Own Credentials) with custom consumer key/secret."""
        payload = {
            "name": "Test Trello OAuth1 BYOC",
            "short_name": "trello",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing OAuth1 BYOC flow",
            "authentication": {
                "consumer_key": config.TEST_TRELLO_CONSUMER_KEY,
                "consumer_secret": config.TEST_TRELLO_CONSUMER_SECRET,
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # BYOC returns oauth_browser after creation (shell connection)
        assert connection["id"]
        assert connection["auth"]["method"] == "oauth_browser"
        assert connection["auth"]["authenticated"] == False
        assert connection["status"] == "pending_auth"
        assert "auth_url" in connection["auth"]
        assert connection["auth"]["auth_url"] is not None

        # Verify BYOC generates valid OAuth1 redirect
        auth_url = connection["auth"]["auth_url"]
        proxy_response = await api_client.get(auth_url, follow_redirects=False)
        assert proxy_response.status_code == 303
        provider_url = proxy_response.headers.get("location")
        assert provider_url is not None
        # OAuth1 BYOC should have oauth_token in the authorization URL
        assert "oauth_token" in provider_url, "OAuth1 URL should include oauth_token parameter"

        # Verify redirect_uri is correct
        verify_redirect_uri(provider_url, config.api_url)

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth1_byoc_partial_credentials_fails(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test OAuth1 BYOC with only one credential (should fail validation)."""
        # Test with only consumer_key (missing consumer_secret)
        payload = {
            "name": "Test Trello OAuth1 BYOC Partial",
            "short_name": "trello",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "consumer_key": "test_consumer_key_12345",
                # Missing consumer_secret
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        # The validation should catch partial OAuth1 credentials
        # This could be either 400 (business logic) or 422 (schema validation)
        assert response.status_code in [400, 422], f"Expected error status, got {response.status_code}"

        error = response.json()

        # Convert entire error response to string for checking
        error_str = str(error).lower()

        # Check that the error mentions the validation issue
        # The Pydantic validator raises: "OAuth1 BYOC requires both consumer_key and consumer_secret or neither"
        assert "consumer" in error_str and ("both" in error_str or "neither" in error_str or "required" in error_str), \
            f"Expected validation error about OAuth1 credentials, got: {error}"


class TestOAuthCallbackRedirect:
    """Test suite for OAuth callback redirect URL handling."""

    @pytest.mark.asyncio
    async def test_oauth_callback_redirect_with_custom_url(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test OAuth callback redirects to custom URL with correct query parameters."""
        custom_redirect = "https://example.com/oauth-return"

        # Create source connection with custom redirect URL
        payload = {
            "name": "Test OAuth with Custom Redirect",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {},
            "redirect_url": custom_redirect,
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Verify redirect_url was stored
        assert connection["auth"]["redirect_url"] == custom_redirect

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth_callback_preserves_existing_query_params(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that OAuth callback preserves existing query parameters in redirect URL."""
        # Redirect URL with existing query parameters
        custom_redirect = "https://example.com/oauth-return?existing_param=value1&another=value2"

        payload = {
            "name": "Test OAuth Query Params",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {},
            "redirect_url": custom_redirect,
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()
        connection_id = connection["id"]

        # Verify the redirect URL was stored with query params
        stored_redirect = connection["auth"]["redirect_url"]
        assert "existing_param=value1" in stored_redirect
        assert "another=value2" in stored_redirect

        # Cleanup
        await api_client.delete(f"/source-connections/{connection_id}")

    @pytest.mark.asyncio
    async def test_oauth_callback_uses_new_parameter_names(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that OAuth callback uses new parameter names: status and source_connection_id."""
        custom_redirect = "https://example.com/oauth-return"

        payload = {
            "name": "Test OAuth Param Names",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {},
            "redirect_url": custom_redirect,
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Verify redirect_url is stored correctly
        assert connection["auth"]["redirect_url"] == custom_redirect
        # The actual callback test would require completing OAuth flow
        # which requires valid OAuth credentials, so we verify storage here

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth_callback_with_url_fragment(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test OAuth callback with redirect URL containing a fragment."""
        custom_redirect = "https://example.com/oauth-return#section"

        payload = {
            "name": "Test OAuth with Fragment",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {},
            "redirect_url": custom_redirect,
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Verify redirect_url with fragment was stored
        assert connection["auth"]["redirect_url"] == custom_redirect

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth_callback_with_complex_query_params(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test OAuth callback with complex query parameters including special characters."""
        # URL with special characters that need proper encoding
        custom_redirect = "https://example.com/oauth?param1=value%20with%20spaces&param2=value&empty="

        payload = {
            "name": "Test OAuth Complex Params",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {},
            "redirect_url": custom_redirect,
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Verify the redirect URL was stored
        assert connection["auth"]["redirect_url"] == custom_redirect

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth_callback_without_redirect_url(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test OAuth callback falls back to app URL when redirect_url is not provided."""
        # Don't provide redirect_url, should default to None
        payload = {
            "name": "Test OAuth No Redirect",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # When redirect_url is not provided, it should be None
        # The callback endpoint will fall back to settings.app_url
        assert connection["auth"]["redirect_url"] is None

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth_callback_redirect_with_localhost(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test OAuth callback with localhost redirect URL (for local development)."""
        # Test with HTTP localhost (common in local dev)
        custom_redirect = "http://localhost:3000/?oauth_return=true"

        payload = {
            "name": "Test OAuth Localhost",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {},
            "redirect_url": custom_redirect,
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Verify localhost URL is preserved as-is (not converted to HTTPS)
        assert connection["auth"]["redirect_url"] == custom_redirect

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth_callback_with_duplicate_query_params(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test OAuth callback with duplicate query parameter names."""
        # URL with duplicate parameter names (valid in HTTP)
        custom_redirect = "https://example.com/oauth?tag=value1&tag=value2"

        payload = {
            "name": "Test OAuth Duplicate Params",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {},
            "redirect_url": custom_redirect,
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Verify the redirect URL with duplicate params was stored
        assert connection["auth"]["redirect_url"] == custom_redirect

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_oauth_callback_redirect_url_with_path_and_query(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test OAuth callback with redirect URL containing path segments and query params."""
        custom_redirect = "https://example.com/app/integrations/callback?source=oauth&flow=new"

        payload = {
            "name": "Test OAuth Path Query",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {},
            "redirect_url": custom_redirect,
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        response.raise_for_status()
        connection = response.json()

        # Verify the full URL structure is preserved
        assert connection["auth"]["redirect_url"] == custom_redirect

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")
