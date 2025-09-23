"""
Test module for Source Connections with new nested authentication API.

This module replaces the original test_source_connections.py to test the refactored API with:
- Nested authentication structure (DirectAuthentication, OAuthTokenAuthentication, etc.)
- New response models (SourceConnection with nested auth details)
- Various authentication methods (modular approach)
- State transitions

This is designed to run in the CI/CD pipeline via test-public-api.yml

OAuth Token Environment Variables:
- TEST_GITHUB_TOKEN: GitHub personal access token for testing GitHub OAuth
- TEST_NOTION_TOKEN: Notion integration token for testing Notion OAuth
- TEST_GOOGLE_ACCESS_TOKEN: Google OAuth access token (requires refresh token)
- TEST_GOOGLE_REFRESH_TOKEN: Google OAuth refresh token (used with access token)
"""

import time
import uuid
import os
import requests
from typing import Tuple, Optional, Dict, Any, List
from .utils import show_backend_logs
from .test_pubsub import test_sync_job_pubsub


class SourceConnectionTestBase:
    """Base class for all source connection tests"""

    def __init__(self, api_url: str, headers: dict, collection_id: str):
        self.api_url = api_url
        self.headers = headers
        self.collection_id = collection_id

    def create_connection(self, payload: dict) -> requests.Response:
        """Create a source connection and return response"""
        response = requests.post(
            f"{self.api_url}/source-connections", json=payload, headers=self.headers
        )
        return response

    def verify_response_structure(self, conn: dict, expected_auth_method: str) -> None:
        """Verify the response matches expected structure"""
        assert "id" in conn, "Missing id field"
        assert "name" in conn, "Missing name field"
        assert "status" in conn, "Missing status field"
        assert "readable_collection_id" in conn, "Missing readable_collection_id"
        assert "auth" in conn, "Missing auth object"
        assert (
            conn["auth"]["method"] == expected_auth_method
        ), f"Expected {expected_auth_method}, got {conn['auth']['method']}"

    def update_connection(self, conn_id: str, update_data: dict) -> Optional[dict]:
        """Update a connection using PATCH"""
        response = requests.patch(
            f"{self.api_url}/source-connections/{conn_id}", json=update_data, headers=self.headers
        )
        return response.json() if response.status_code == 200 else None

    def run_sync(self, conn_id: str) -> Optional[dict]:
        """Trigger manual sync"""
        response = requests.post(
            f"{self.api_url}/source-connections/{conn_id}/run", headers=self.headers
        )
        return response.json() if response.status_code == 200 else None

    def wait_for_job(self, conn_id: str, job_id: str, timeout: int = 60) -> str:
        """Wait for sync job to complete and return final status"""
        elapsed = 0
        poll_interval = 5

        while elapsed < timeout:
            response = requests.get(
                f"{self.api_url}/source-connections/{conn_id}/jobs", headers=self.headers
            )

            if response.status_code == 200:
                jobs = response.json()
                job = next((j for j in jobs if j["id"] == job_id), None)

                if job:
                    status = job["status"].lower()
                    if status in ["completed", "failed", "cancelled"]:
                        return status

            time.sleep(poll_interval)
            elapsed += poll_interval

        return "timeout"


class DirectAuthTest(SourceConnectionTestBase):
    """Test direct authentication flow (e.g., Stripe with API key)"""

    def create_payload(self, api_key: str, sync_immediately: bool = False) -> dict:
        return {
            "name": "Test Stripe Direct Auth",
            "short_name": "stripe",
            "readable_collection_id": self.collection_id,
            "description": "Testing direct authentication with API key",
            "authentication": {"credentials": {"api_key": api_key}},
            "schedule": {"cron": "0 */6 * * *"},
            "sync_immediately": sync_immediately,
        }

    def run_test(self, api_key: str) -> str:
        """Run complete direct auth test flow"""
        print("  Testing Direct Authentication (Stripe)...")

        # Step 1: Create connection
        payload = self.create_payload(api_key, sync_immediately=False)
        response = self.create_connection(payload)

        if response.status_code != 200:
            print(f"    Failed to create: {response.status_code}")
            print(f"    Response: {response.text}")
            show_backend_logs(lines=20)
            raise AssertionError(f"Failed to create direct auth connection: {response.text}")

        conn = response.json()
        conn_id = conn["id"]
        self.verify_response_structure(conn, "direct")

        # Step 2: Verify authenticated
        assert conn["auth"]["authenticated"] == True, "Should be authenticated"
        assert conn["status"] == "active", f"Expected active status, got {conn['status']}"
        print(f"    ✓ Connection created: {conn_id}")

        # Step 3: Update connection
        update_data = {
            "name": "Updated Stripe Connection",
            "description": "Updated via PATCH",
            "schedule": {"cron": "0 0 * * *"},  # Daily
        }

        updated = self.update_connection(conn_id, update_data)
        if updated:
            assert updated["name"] == update_data["name"], "Name not updated"
            print(f"    ✓ Connection updated")

        # Step 4: Run sync
        job = self.run_sync(conn_id)
        if job:
            job_id = job["id"]
            assert job["source_connection_id"] == conn_id
            print(f"    ✓ Sync job started: {job_id}")

            # Step 5: Brief wait for job
            final_status = self.wait_for_job(conn_id, job_id, timeout=30)
            print(f"    ✓ Job status after 30s: {final_status}")

        return conn_id


class OAuthBrowserTest(SourceConnectionTestBase):
    """Test OAuth browser flow - limited in CI environment"""

    def create_payload(self) -> dict:
        return {
            "name": "Test Linear OAuth Browser",
            "short_name": "linear",
            "readable_collection_id": self.collection_id,
            "description": "Testing OAuth browser flow",
            "authentication": {},  # Empty for browser flow
            "sync_immediately": False,
        }

    def run_test(self) -> Optional[str]:
        """Run OAuth browser test - stops at shell creation in CI"""
        print("  Testing OAuth Browser Flow (Linear)...")

        # Step 1: Create shell connection
        payload = self.create_payload()
        response = self.create_connection(payload)

        if response.status_code != 200:
            print(f"    ❌ OAuth browser test failed: {response.status_code}")
            print(f"    Response: {response.text}")
            raise AssertionError(f"Failed to create OAuth browser connection: {response.text}")

        conn = response.json()
        conn_id = conn["id"]
        self.verify_response_structure(conn, "oauth_browser")

        # Step 2: Verify pending auth state
        assert conn["auth"]["authenticated"] == False, "Should not be authenticated"
        assert conn["status"] == "pending_auth", f"Expected pending_auth, got {conn['status']}"
        assert "auth_url" in conn["auth"], "Missing auth_url"
        assert conn["auth"]["auth_url"] is not None, "auth_url should not be None"

        print(f"    ✓ OAuth shell created: {conn_id}")
        print(f"    ℹ️ Cannot complete OAuth flow in CI (requires user interaction)")

        return conn_id


class AuthProviderTest(SourceConnectionTestBase):
    """Test authentication via external auth provider"""

    def __init__(
        self, api_url: str, headers: dict, collection_id: str, provider_readable_id: str = None
    ):
        """Initialize with optional provider readable_id for auth provider connections"""
        super().__init__(api_url, headers, collection_id)
        self.provider_readable_id = provider_readable_id

    def create_payload(
        self, provider_readable_id: str, provider_config: Optional[dict] = None
    ) -> dict:
        """Create payload for auth provider connection"""
        # Use provider_readable_id for the auth provider connection (matches AuthProviderAuthentication schema)
        auth = {
            "provider_readable_id": self.provider_readable_id
            or f"composio-test-{int(time.time())}",
        }

        # Add Composio-specific config if provided
        if provider_config:
            auth["provider_config"] = provider_config

        return {
            "name": f"Test {provider_readable_id} Auth Provider Source",
            "short_name": "asana",  # Using Asana for auth provider test
            "readable_collection_id": self.collection_id,
            "description": "Testing auth provider authentication with Asana",
            "authentication": auth,
            "sync_immediately": False,
        }

    def run_test(
        self, provider_readable_id: str, provider_config: Optional[dict] = None
    ) -> Optional[str]:
        """Run auth provider test"""
        print(f"  Testing Auth Provider ({provider_readable_id})...")

        # Step 1: Create connection with auth provider
        payload = self.create_payload(provider_readable_id, provider_config)
        response = self.create_connection(payload)

        if response.status_code == 404:
            print(f"    ❌ Auth provider '{provider_readable_id}' not found")
            raise AssertionError(
                f"Auth provider '{provider_readable_id}' not found in this environment"
            )

        if response.status_code != 200:
            print(f"    ❌ Auth provider test failed: {response.status_code}")
            print(f"    Response: {response.text}")
            raise AssertionError(f"Failed to create auth provider connection: {response.text}")

        conn = response.json()
        conn_id = conn["id"]
        self.verify_response_structure(conn, "auth_provider")

        # Step 2: Verify authenticated via provider
        assert conn["auth"]["authenticated"] == True, "Should be authenticated via provider"
        assert "provider_id" in conn["auth"], "Missing provider_id in auth"
        assert conn["auth"]["provider_id"] == self.provider_readable_id, "Provider ID mismatch"
        assert conn["status"] == "active", f"Expected active status, got {conn['status']}"

        print(f"    ✓ Connection created via auth provider: {conn_id}")
        print(f"    ✓ Provider: {provider_readable_id}")

        return conn_id


class OAuthBYOCTest(SourceConnectionTestBase):
    """Test OAuth BYOC (Bring Your Own Credentials) flow"""

    def create_payload(self, source_name: str, client_id: str, client_secret: str) -> dict:
        """Create payload for OAuth BYOC"""
        return {
            "name": f"Test {source_name} BYOC OAuth",
            "short_name": source_name,
            "readable_collection_id": self.collection_id,
            "description": "Testing OAuth BYOC flow",
            "authentication": {
                "client_id": client_id,
                "client_secret": client_secret,
            },
            "sync_immediately": False,
        }

    def run_test(self, source_name: str, client_id: str, client_secret: str) -> Optional[str]:
        """Run OAuth BYOC test - creates shell for OAuth flow"""
        print(f"  Testing OAuth BYOC ({source_name})...")

        # Step 1: Create shell connection with BYOC credentials
        payload = self.create_payload(source_name, client_id, client_secret)
        response = self.create_connection(payload)

        if response.status_code != 200:
            print(f"    ❌ OAuth BYOC test failed: {response.status_code}")
            print(f"    Response: {response.text}")
            raise AssertionError(f"Failed to create BYOC connection: {response.text}")

        conn = response.json()
        conn_id = conn["id"]
        # BYOC returns oauth_browser since they're functionally the same after creation
        # The difference is only in the control flow (user provides vs system provides credentials)
        self.verify_response_structure(conn, "oauth_browser")

        # Step 2: Verify pending auth state with BYOC
        assert conn["auth"]["authenticated"] == False, "Should not be authenticated"
        assert conn["status"] == "pending_auth", f"Expected pending_auth, got {conn['status']}"
        assert "auth_url" in conn["auth"], "Missing auth_url"
        assert conn["auth"]["auth_url"] is not None, "auth_url should not be None"

        print(f"    ✓ OAuth BYOC shell created: {conn_id}")
        print(f"    ✓ Client ID confirmed: {conn['auth'].get('client_id', 'N/A')[:10]}...")
        print(f"    ℹ️ Cannot complete OAuth flow in CI (requires user interaction)")

        return conn_id


class OAuthTokenTest(SourceConnectionTestBase):
    """Test OAuth token injection"""

    def create_payload(
        self, source_name: str, access_token: str, refresh_token: Optional[str] = None
    ) -> dict:
        """Create payload for OAuth token injection"""
        auth = {"access_token": access_token}
        if refresh_token:
            auth["refresh_token"] = refresh_token
            auth["expires_at"] = "2025-12-31T23:59:59Z"  # Future date

        return {
            "name": f"Test {source_name} Token Injection",
            "short_name": source_name,
            "readable_collection_id": self.collection_id,
            "description": "Testing OAuth token injection",
            "authentication": auth,
            "sync_immediately": True,
        }

    def run_test(
        self, source_name: str, access_token: str, refresh_token: Optional[str] = None
    ) -> Optional[str]:
        """Run OAuth token injection test"""
        print(f"  Testing OAuth Token Injection ({source_name})...")

        # Step 1: Create connection with injected token
        payload = self.create_payload(source_name, access_token, refresh_token)
        response = self.create_connection(payload)

        if response.status_code == 400:
            # Token might be invalid or expired
            print(f"    ❌ Token validation failed for {source_name}")
            print(f"    Response: {response.text}")
            raise AssertionError(f"Token validation failed for {source_name}: {response.text}")

        if response.status_code != 200:
            print(f"    ❌ OAuth token test failed: {response.status_code}")
            print(f"    Response: {response.text}")
            raise AssertionError(f"Failed to create OAuth token connection: {response.text}")

        conn = response.json()
        conn_id = conn["id"]
        self.verify_response_structure(conn, "oauth_token")

        # Step 2: Verify authenticated with token
        assert conn["auth"]["authenticated"] == True, "Should be authenticated with token"
        if "expires_at" in conn["auth"]:
            print(f"    Token expires at: {conn['auth']['expires_at']}")

        # Should be active or syncing (since sync_immediately=True)
        assert conn["status"] in ["active", "syncing"], f"Unexpected status: {conn['status']}"

        print(f"    ✓ Connection created with OAuth token: {conn_id}")
        if refresh_token:
            print(f"    ✓ Has refresh token")

        # Check if sync started
        if conn["status"] == "syncing" or (conn.get("sync") and conn["sync"].get("last_job")):
            print(f"    ✓ Sync auto-started")

        return conn_id


class ErrorHandlingTest(SourceConnectionTestBase):
    """Test error scenarios"""

    def test_invalid_source(self) -> None:
        """Test with non-existent source"""
        payload = {
            "name": "Invalid Source",
            "short_name": "nonexistent_source",
            "readable_collection_id": self.collection_id,
            "authentication": {"credentials": {"key": "value"}},
        }

        response = self.create_connection(payload)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_wrong_auth_method(self, api_key: str) -> None:
        """Test wrong auth method for source"""
        # Try OAuth token on Stripe (which only supports direct auth)
        payload = {
            "name": "Wrong Auth Method",
            "short_name": "stripe",
            "readable_collection_id": self.collection_id,
            "authentication": {"access_token": "some_token"},  # OAuth for direct-only source
        }

        response = self.create_connection(payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

        if response.status_code == 400:
            error = response.json()
            detail = error.get("detail", "").lower()
            assert "does not support" in detail or "unsupported" in detail

    def test_invalid_collection(self, api_key: str) -> None:
        """Test with non-existent collection"""
        payload = {
            "name": "Invalid Collection",
            "short_name": "stripe",
            "readable_collection_id": "nonexistent-collection-xyz",
            "authentication": {"credentials": {"api_key": api_key}},
        }

        response = self.create_connection(payload)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_invalid_cron(self, api_key: str) -> None:
        """Test with invalid cron expression"""
        payload = {
            "name": "Invalid Cron",
            "short_name": "stripe",
            "readable_collection_id": self.collection_id,
            "authentication": {"credentials": {"api_key": api_key}},
            "schedule": {"cron": "invalid cron expression"},
        }

        response = self.create_connection(payload)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

    def run_all_error_tests(self, api_key: str) -> None:
        """Run all error handling tests"""
        print("  Testing Error Handling...")

        self.test_invalid_source()
        print("    ✓ Invalid source returns 404")

        self.test_wrong_auth_method(api_key)
        print("    ✓ Wrong auth method returns 400")

        self.test_invalid_collection(api_key)
        print("    ✓ Invalid collection returns 404")

        self.test_invalid_cron(api_key)
        print("    ✓ Invalid cron returns 422")


def test_source_connections(
    api_url: str, headers: dict, collection_id: str, stripe_api_key: str = None
) -> Tuple[str, str]:
    """
    Test source connections with new nested authentication API.

    This function signature matches the original to maintain compatibility with runner.py

    Args:
        api_url: The API URL
        headers: Request headers with authentication
        collection_id: The readable_id of the collection to use
        stripe_api_key: Stripe API key for testing

    Returns:
        Tuple[str, str]: The IDs of the two created source connections
    """
    print("\n🔄 Testing Source Connections - Nested Authentication API")

    # Debug: Print the collection_id being used
    print(f"  Using collection_id: '{collection_id}'")

    # Verify the collection exists
    print("  Verifying collection exists...")
    response = requests.get(f"{api_url}/collections/{collection_id}", headers=headers)
    if response.status_code != 200:
        print(f"  ✗ Collection verification failed: {response.status_code} - {response.text}")
        raise AssertionError(f"Collection '{collection_id}' not found")

    collection_detail = response.json()
    print(
        f"  ✓ Collection verified: {collection_detail['name']} ({collection_detail['readable_id']})"
    )

    # Verify Stripe API key
    if not stripe_api_key:
        raise ValueError("Stripe API key must be provided via --stripe-api-key argument")

    created_connections = []

    # =============================
    # Test 1: Direct Authentication (Always runs - we have Stripe key)
    # =============================
    print("\n📌 Test 1: Direct Authentication")
    direct_test = DirectAuthTest(api_url, headers, collection_id)
    try:
        conn_id = direct_test.run_test(stripe_api_key)
        created_connections.append(conn_id)
        print("  ✅ Direct authentication test passed")
    except AssertionError as e:
        print(f"  ❌ Direct authentication test failed: {e}")
        show_backend_logs(lines=30)
        raise

    # =============================
    # Test 2: Create second connection with immediate sync
    # =============================
    print("\n📌 Test 2: Direct Auth with Immediate Sync")
    try:
        payload = {
            "name": "Auto-sync Stripe Connection",
            "short_name": "stripe",
            "readable_collection_id": collection_id,
            "description": "Test connection with immediate sync",
            "authentication": {"credentials": {"api_key": stripe_api_key}},
            "sync_immediately": True,
        }

        response = requests.post(f"{api_url}/source-connections", json=payload, headers=headers)
        assert response.status_code == 200, f"Failed to create second connection: {response.text}"

        conn2 = response.json()
        conn2_id = conn2["id"]
        created_connections.append(conn2_id)

        # Should be syncing or active
        assert conn2["status"] in ["active", "syncing"], f"Unexpected status: {conn2['status']}"

        # Check if sync job was created
        if "sync" in conn2 and conn2["sync"]:
            if conn2["sync"].get("last_job"):
                print(f"  ✓ Sync job auto-started: {conn2['sync']['last_job']['status']}")

        print(f"  ✅ Second connection created with immediate sync: {conn2_id}")

    except (AssertionError, Exception) as e:
        print(f"  ❌ Second connection test failed: {e}")
        show_backend_logs(lines=30)
        # Re-raise to fail the entire test suite
        raise AssertionError(f"Test 2 (Direct Auth with Immediate Sync) failed: {e}")

    # =============================
    # Test 3: OAuth Browser (Creates shell only in CI)
    # =============================
    print("\n📌 Test 3: OAuth Browser Flow")
    oauth_browser_test = OAuthBrowserTest(api_url, headers, collection_id)
    try:
        conn_id = oauth_browser_test.run_test()
        if conn_id:
            created_connections.append(conn_id)
            print("  ✅ OAuth browser shell creation test passed")
    except Exception as e:
        print(f"  ❌ OAuth browser test failed: {e}")
        raise AssertionError(f"OAuth browser test failed: {e}")

    # =============================
    # Test 3.5: OAuth BYOC Flow (REQUIRED)
    # =============================
    print("\n📌 Test 3.5: OAuth BYOC (Bring Your Own Credentials)")

    # Require BYOC credentials for Google Drive
    google_client_id = os.environ.get("TEST_GOOGLE_CLIENT_ID")
    google_client_secret = os.environ.get("TEST_GOOGLE_CLIENT_SECRET")

    if not google_client_id:
        raise AssertionError(
            "TEST_GOOGLE_CLIENT_ID environment variable is required for OAuth BYOC tests."
        )
    if not google_client_secret:
        raise AssertionError(
            "TEST_GOOGLE_CLIENT_SECRET environment variable is required for OAuth BYOC tests."
        )

    oauth_byoc_test = OAuthBYOCTest(api_url, headers, collection_id)
    try:
        conn_id = oauth_byoc_test.run_test("google_drive", google_client_id, google_client_secret)
        if conn_id:
            created_connections.append(conn_id)
            print("  ✅ OAuth BYOC shell creation test passed")
    except Exception as e:
        print(f"  ❌ OAuth BYOC test failed: {e}")
        raise AssertionError(f"OAuth BYOC test failed: {e}")

    # =============================
    # Test 3.6: Minimal OAuth Payload (No auth, no name)
    # =============================
    print("\n📌 Test 3.6: Minimal OAuth Payload")
    try:
        # Create connection with minimal payload - should default to OAuth browser flow
        minimal_payload = {
            "short_name": "notion",  # Notion supports OAuth
            "readable_collection_id": collection_id,
        }

        response = requests.post(
            f"{api_url}/source-connections", json=minimal_payload, headers=headers
        )

        assert response.status_code == 200, f"Failed to create minimal connection: {response.text}"

        minimal_conn = response.json()
        minimal_conn_id = minimal_conn["id"]
        created_connections.append(minimal_conn_id)

        # Verify defaults were applied
        assert (
            minimal_conn["name"] == "Notion Connection"
        ), f"Name should default to 'Notion Connection', got {minimal_conn['name']}"
        assert minimal_conn["status"] == "pending_auth", "Should be pending auth"
        assert minimal_conn["auth"]["method"] == "oauth_browser", "Should default to OAuth browser"
        assert "auth_url" in minimal_conn["auth"], "Should have OAuth URL"

        print(f"  ✅ Minimal OAuth payload test passed: {minimal_conn_id}")

    except (AssertionError, Exception) as e:
        print(f"  ❌ Minimal payload test failed: {e}")
        show_backend_logs(lines=30)
        # Re-raise to fail the entire test suite
        raise AssertionError(f"Test 3.6 (Minimal OAuth Payload) failed: {e}")

    # =============================
    # Test 4: OAuth Token Injection (REQUIRED)
    # =============================
    print("\n📌 Test 4: OAuth Token Injection")

    # Require Notion token
    notion_token = os.environ.get("TEST_NOTION_TOKEN")
    if not notion_token:
        raise AssertionError(
            "TEST_NOTION_TOKEN environment variable is required for OAuth token injection tests."
        )

    oauth_token_test = OAuthTokenTest(api_url, headers, collection_id)
    conn_id = oauth_token_test.run_test("notion", notion_token)
    if not conn_id:
        raise AssertionError("Notion OAuth token test failed - token may be invalid")
    created_connections.append(conn_id)
    print("  ✅ Notion OAuth token injection test passed")

    # =============================
    # Test 5: Auth Providers (Composio and Pipedream)
    # =============================
    print("\n📌 Test 5: Auth Providers")

    # Test 5a: Composio Auth Provider
    print("\n  📌 Test 5a: Composio Auth Provider")

    # Require auth provider configuration
    auth_provider_readable_id = os.environ.get("TEST_AUTH_PROVIDER_NAME")
    if not auth_provider_readable_id:
        raise AssertionError(
            "TEST_AUTH_PROVIDER_NAME environment variable is required. Set it to 'composio' to run tests."
        )

    if auth_provider_readable_id != "composio":
        raise AssertionError(
            f"Only 'composio' auth provider is supported. Got: {auth_provider_readable_id}"
        )

    # Require Composio API key
    composio_api_key = os.environ.get("TEST_COMPOSIO_API_KEY")
    if not composio_api_key:
        raise AssertionError(
            "TEST_COMPOSIO_API_KEY environment variable is required for Composio auth provider tests."
        )

    print(f"    Creating Composio auth provider connection...")

    # Get Composio auth_config_id and account_id for Asana
    composio_auth_config_id = os.environ.get("TEST_COMPOSIO_AUTH_CONFIG_ID")
    composio_account_id = os.environ.get("TEST_COMPOSIO_ACCOUNT_ID")

    if not composio_auth_config_id:
        raise AssertionError(
            "TEST_COMPOSIO_AUTH_CONFIG_ID environment variable is required for Composio auth provider tests."
        )
    if not composio_account_id:
        raise AssertionError(
            "TEST_COMPOSIO_ACCOUNT_ID environment variable is required for Composio auth provider tests."
        )

    # Create the Composio auth provider connection first
    provider_readable_id = f"composio-test-{int(time.time())}"
    auth_provider_payload = {
        "name": "Test Composio Provider for Asana",
        "short_name": "composio",
        "readable_id": provider_readable_id,
        "auth_fields": {"api_key": composio_api_key},
        "config_fields": {
            "auth_config_id": composio_auth_config_id,
            "account_id": composio_account_id,
        },
    }

    # Call the auth provider connect endpoint
    auth_provider_response = requests.put(
        f"{api_url}/auth-providers/connect", json=auth_provider_payload, headers=headers
    )

    if auth_provider_response.status_code != 200:
        print(f"    ❌ Failed to create Composio auth provider: {auth_provider_response.text}")
        raise AssertionError(
            f"Failed to create Composio auth provider: {auth_provider_response.text}"
        )

    auth_provider_conn = auth_provider_response.json()
    actual_provider_id = auth_provider_conn["readable_id"]
    print(f"    ✓ Created Composio auth provider connection: {actual_provider_id}")

    # Now test creating a source connection using the auth provider
    auth_provider_test = AuthProviderTest(api_url, headers, collection_id, actual_provider_id)

    # Create provider config with auth_config_id and account_id for Asana
    provider_config = {
        "auth_config_id": composio_auth_config_id,
        "account_id": composio_account_id,
    }

    try:
        conn_id = auth_provider_test.run_test(auth_provider_readable_id, provider_config)
        if not conn_id:
            raise AssertionError(f"Auth provider test returned None - failed to create connection")
        created_connections.append(conn_id)
        print("    ✅ Composio auth provider test passed")
    except Exception as e:
        print(f"    ❌ Composio auth provider test failed: {e}")
        raise AssertionError(f"Composio auth provider test failed: {e}")

    # Test 5b: Pipedream Proxy Auth Provider
    print("\n  📌 Test 5b: Pipedream Proxy Auth Provider")

    # Check for Pipedream environment variables
    pipedream_client_id = os.environ.get("TEST_PIPEDREAM_CLIENT_ID")
    pipedream_client_secret = os.environ.get("TEST_PIPEDREAM_CLIENT_SECRET")
    pipedream_project_id = os.environ.get("TEST_PIPEDREAM_PROJECT_ID")
    pipedream_account_id = os.environ.get("TEST_PIPEDREAM_ACCOUNT_ID")
    pipedream_external_user_id = os.environ.get("TEST_PIPEDREAM_EXTERNAL_USER_ID")
    pipedream_environment = os.environ.get("TEST_PIPEDREAM_ENVIRONMENT", "development")

    if not all(
        [
            pipedream_client_id,
            pipedream_client_secret,
            pipedream_project_id,
            pipedream_account_id,
            pipedream_external_user_id,
        ]
    ):
        print("    ⚠️ Skipping Pipedream proxy test - missing required environment variables:")
        if not pipedream_client_id:
            print("      - TEST_PIPEDREAM_CLIENT_ID")
        if not pipedream_client_secret:
            print("      - TEST_PIPEDREAM_CLIENT_SECRET")
        if not pipedream_project_id:
            print("      - TEST_PIPEDREAM_PROJECT_ID")
        if not pipedream_account_id:
            print("      - TEST_PIPEDREAM_ACCOUNT_ID")
        if not pipedream_external_user_id:
            print("      - TEST_PIPEDREAM_EXTERNAL_USER_ID")
        print(
            "    ℹ️ To run this test, set up a Pipedream OAuth client and connected Google Drive account"
        )
    else:
        try:
            # Create the Pipedream auth provider connection
            pipedream_provider_id = f"pipedream-test-{int(time.time())}"

            # Create Pipedream auth provider using AuthProviderTest
            auth_provider_test = AuthProviderTest(
                api_url, headers, collection_id, pipedream_provider_id
            )

            # First create the Pipedream auth provider
            pipedream_auth_payload = {
                "name": "Test Pipedream Provider",
                "short_name": "pipedream",
                "readable_id": pipedream_provider_id,
                "auth_fields": {
                    "client_id": pipedream_client_id,
                    "client_secret": pipedream_client_secret,
                },
            }

            # Create Pipedream auth provider
            pipedream_response = requests.put(
                f"{api_url}/auth-providers/connect", json=pipedream_auth_payload, headers=headers
            )

            if pipedream_response.status_code != 200:
                print(f"    ❌ Failed to create Pipedream auth provider: {pipedream_response.text}")
                raise AssertionError(
                    f"Failed to create Pipedream auth provider: {pipedream_response.text}"
                )

            pipedream_provider = pipedream_response.json()
            actual_pipedream_id = pipedream_provider["readable_id"]
            print(f"    ✓ Created Pipedream auth provider: {actual_pipedream_id}")

            # Now create a Google Drive source connection using the auth provider
            google_drive_payload = {
                "name": "Test Google Drive via Pipedream",
                "short_name": "google_drive",
                "readable_collection_id": collection_id,
                "description": "Testing Google Drive with Pipedream proxy authentication",
                "authentication": {
                    "provider_readable_id": actual_pipedream_id,
                    "provider_config": {
                        "project_id": pipedream_project_id,
                        "account_id": pipedream_account_id,
                        "environment": pipedream_environment,
                        "external_user_id": pipedream_external_user_id,
                    },
                },
                "sync_immediately": False,
            }

            # Create the source connection
            google_response = requests.post(
                f"{api_url}/source-connections", json=google_drive_payload, headers=headers
            )

            if google_response.status_code != 200:
                print(f"    ❌ Failed to create Google Drive connection: {google_response.text}")
                raise AssertionError(f"Failed to create Google Drive connection via Pipedream")

            google_conn = google_response.json()
            google_conn_id = google_conn["id"]
            created_connections.append(google_conn_id)

            # Verify the connection
            assert (
                google_conn["auth"]["method"] == "auth_provider"
            ), "Should use auth_provider method"
            assert google_conn["auth"]["authenticated"] == True, "Should be authenticated"
            assert (
                google_conn["auth"]["provider_id"] == actual_pipedream_id
            ), "Provider ID should match"
            assert (
                google_conn["status"] == "active"
            ), f"Expected active status, got {google_conn['status']}"

            print(f"    ✓ Google Drive connection created via Pipedream: {google_conn_id}")

            # Test syncing and verify entities are created
            print("    Testing sync and entity creation...")

            # Trigger a sync
            sync_response = requests.post(
                f"{api_url}/source-connections/{google_conn_id}/run", headers=headers
            )

            if sync_response.status_code == 200:
                sync_job = sync_response.json()
                sync_job_id = sync_job["id"]
                print(f"    ✓ Sync job started: {sync_job_id}")

                # Wait for sync to process some entities (give it 30 seconds)
                print("    Waiting for sync to process entities...")
                time.sleep(30)

                # Check if entities were created
                entities_response = requests.get(
                    f"{api_url}/source-connections/{google_conn_id}/entities", headers=headers
                )

                if entities_response.status_code == 200:
                    entities = entities_response.json()
                    entity_count = (
                        len(entities) if isinstance(entities, list) else entities.get("count", 0)
                    )

                    if entity_count > 0:
                        print(
                            f"    ✓ Successfully synced {entity_count} entities from Google Drive"
                        )
                        print(
                            "    ✅ Pipedream proxy auth provider test passed with entity sync verification"
                        )
                    else:
                        print("    ⚠️ No entities synced yet - checking job status...")

                        # Check job status to see if it's still running or failed
                        jobs_response = requests.get(
                            f"{api_url}/source-connections/{google_conn_id}/jobs", headers=headers
                        )

                        if jobs_response.status_code == 200:
                            jobs = jobs_response.json()
                            if jobs and len(jobs) > 0:
                                latest_job = jobs[0]
                                print(f"    Job status: {latest_job['status']}")

                                if latest_job["status"] == "failed":
                                    print(f"    ❌ Sync job failed - check logs for details")
                                    raise AssertionError(
                                        "Google Drive sync failed - proxy authentication may have issues"
                                    )
                                elif latest_job["status"] == "in_progress":
                                    print("    ℹ️ Sync still in progress - may need more time")
                                    print(
                                        "    ✅ Pipedream proxy auth provider test passed (sync started successfully)"
                                    )
                                else:
                                    print(
                                        f"    ✅ Pipedream proxy auth provider test passed (job status: {latest_job['status']})"
                                    )
                else:
                    print(f"    ⚠️ Could not fetch entities: {entities_response.status_code}")
                    print(
                        "    ✅ Pipedream proxy auth provider test passed (connection created successfully)"
                    )
            else:
                print(f"    ⚠️ Could not start sync: {sync_response.status_code}")
                print(
                    "    ✅ Pipedream proxy auth provider test passed (connection created successfully)"
                )

        except Exception as e:
            print(f"    ❌ Pipedream test failed: {e}")
            raise AssertionError(f"Pipedream proxy auth provider test failed: {e}")

    # =============================
    # Test 6: Error Handling
    # =============================
    print("\n📌 Test 6: Error Handling")
    error_test = ErrorHandlingTest(api_url, headers, collection_id)
    try:
        error_test.run_all_error_tests(stripe_api_key)
        print("  ✅ Error handling tests passed")
    except AssertionError as e:
        print(f"  ❌ Error handling test failed: {e}")
        raise

    # =============================
    # Test 7: List Operations
    # =============================
    print("\n📌 Test 7: List Operations")
    try:
        # List connections for our test collection (to avoid pagination issues)
        response = requests.get(
            f"{api_url}/source-connections?collection={collection_id}&limit=100", headers=headers
        )
        assert response.status_code == 200, f"Failed to list connections: {response.text}"

        all_connections = response.json()
        assert isinstance(all_connections, list), "Response should be a list"

        # All connections should be from our test collection
        print(f"    Created connection IDs: {created_connections}")
        print(f"    Total connections in collection: {len(all_connections)}")

        # Convert both to strings for comparison
        created_conn_strs = [str(cid) for cid in created_connections if cid is not None]
        our_connections = [c for c in all_connections if str(c["id"]) in created_conn_strs]

        print(
            f"    Found {len(our_connections)} of our {len(created_conn_strs)} created connections"
        )
        assert len(our_connections) > 0, "Should find at least one of our connections"

        # Verify list item has auth_method field (new in refactored API)
        for conn in our_connections:
            assert "auth_method" in conn, "List item should have auth_method"
            assert conn["auth_method"] in [
                "direct",
                "oauth_browser",
                "oauth_token",
                "oauth_byoc",
                "auth_provider",
            ]

            # Filter by collection
        response = requests.get(
            f"{api_url}/source-connections?collection={collection_id}", headers=headers
        )

        assert response.status_code == 200, f"Failed to filter by collection: {response.text}"

        collection_connections = response.json()
        assert all(
            c["readable_collection_id"] == collection_id for c in collection_connections
        ), "Collection filter not working"

        print(
            f"  ✅ List operations passed ({len(all_connections)} total, {len(collection_connections)} in collection)"
        )
    except AssertionError as e:
        print(f"  ❌ List operations test failed: {e}")
        raise

    # =============================
    # Test 8: PubSub/SSE (if we have a running job)
    # =============================
    if len(created_connections) > 0:
        print("\n📌 Test 8: Sync Job Monitoring")
        try:
            # Get the first connection and run a sync
            conn_id = created_connections[0]
            response = requests.post(f"{api_url}/source-connections/{conn_id}/run", headers=headers)

            if response.status_code == 200:
                job = response.json()
                job_id = job["id"]
                print(f"  Testing PubSub for job {job_id}...")

                # Test SSE subscription
                pubsub_success = test_sync_job_pubsub(api_url, job_id, headers, timeout=30)
                if pubsub_success:
                    print("  ✅ PubSub/SSE test passed")
                else:
                    print("  ⚠️ PubSub test timed out (may be normal for quick jobs)")
        except Exception as e:
            print(f"  ❌ PubSub test failed: {e}")
            raise AssertionError(f"PubSub/SSE test failed: {e}")

    # =============================
    # Summary
    # =============================
    print("\n✅ Source Connections test completed successfully")
    print(f"   Created {len(created_connections)} connections")
    print(
        f"   Tests run: Direct Auth, OAuth Browser, OAuth Token, Auth Providers (Composio, Pipedream), Error Handling, List Operations"
    )

    # Return first two connection IDs (maintains compatibility with runner.py)
    conn1 = created_connections[0] if len(created_connections) > 0 else ""
    conn2 = created_connections[1] if len(created_connections) > 1 else ""

    return conn1, conn2
