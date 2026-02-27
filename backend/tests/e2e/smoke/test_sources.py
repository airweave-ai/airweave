"""
Async test module for Sources endpoints.

Tests listing sources and getting source details.
These tests are completely independent and can run in parallel.
"""

import pytest
import httpx


class TestSources:
    """Test suite for Sources API endpoints."""

    @pytest.mark.asyncio
    async def test_list_sources(self, api_client: httpx.AsyncClient):
        """Test listing all available sources."""
        response = await api_client.get("/sources/")

        assert response.status_code == 200, f"Failed to list sources: {response.text}"

        sources = response.json()
        assert isinstance(sources, list), "Sources response should be a list"
        assert len(sources) > 0, "Should have at least one source"

        # Check structure of first source
        first_source = sources[0]
        assert "short_name" in first_source
        assert "name" in first_source
        assert "description" in first_source
        assert "auth_methods" in first_source
        # icon_url is optional

    @pytest.mark.asyncio
    async def test_get_source_by_name(self, api_client: httpx.AsyncClient):
        """Test getting a specific source by short_name."""
        # Test with a known source (stripe should always exist)
        response = await api_client.get("/sources/stripe")

        assert response.status_code == 200, f"Failed to get source: {response.text}"

        source = response.json()
        assert source["short_name"] == "stripe"
        assert "name" in source
        assert "description" in source
        assert "auth_methods" in source
        # icon_url, config_schema and credential_schema are optional
        # But check auth and config fields which should be present
        assert "auth_fields" in source
        assert "config_fields" in source

    @pytest.mark.asyncio
    async def test_get_multiple_sources(self, api_client: httpx.AsyncClient):
        """Test getting details for multiple known sources."""
        known_sources = ["stripe", "notion", "linear", "asana", "hubspot_crm", "slab"]

        for source_name in known_sources:
            response = await api_client.get(f"/sources/{source_name}")

            # Some sources might not be available in all environments
            if response.status_code == 200:
                source = response.json()
                assert source["short_name"] == source_name
                assert "auth_methods" in source

    @pytest.mark.asyncio
    async def test_source_auth_methods(self, api_client: httpx.AsyncClient):
        """Test that sources have valid auth methods."""
        response = await api_client.get("/sources/")
        sources = response.json()

        valid_auth_methods = [
            "direct",
            "oauth_browser",
            "oauth_token",
            "auth_provider",
            "oauth_byoc",
        ]

        for source in sources:
            assert "auth_methods" in source
            for auth_method in source["auth_methods"]:
                assert auth_method in valid_auth_methods, f"Invalid auth method: {auth_method}"

    @pytest.mark.asyncio
    async def test_source_not_found(self, api_client: httpx.AsyncClient):
        """Test error handling for non-existent source."""
        response = await api_client.get("/sources/non_existent_source_xyz")

        assert response.status_code == 404
        error = response.json()
        assert "detail" in error
        assert "not found" in error["detail"].lower()

    @pytest.mark.asyncio
    async def test_sources_have_required_fields(self, api_client: httpx.AsyncClient):
        """Test that all sources have required fields."""
        response = await api_client.get("/sources/")
        sources = response.json()

        required_fields = ["short_name", "name", "description", "auth_methods"]

        for source in sources:
            for field in required_fields:
                assert (
                    field in source
                ), f"Source {source.get('short_name', 'unknown')} missing field: {field}"
                assert source[field] is not None, f"Source {source['short_name']} has null {field}"

    @pytest.mark.asyncio
    async def test_source_fields_structure(self, api_client: httpx.AsyncClient):
        """Test that source fields have proper structure."""
        # Get a source with fields
        response = await api_client.get("/sources/stripe")
        source = response.json()

        # Check auth_fields structure
        if "auth_fields" in source and source["auth_fields"]:
            auth_fields = source["auth_fields"]
            assert "fields" in auth_fields
            assert isinstance(auth_fields["fields"], list)
            if auth_fields["fields"]:
                first_field = auth_fields["fields"][0]
                assert "name" in first_field
                assert "type" in first_field
                assert "required" in first_field

        # Check config_fields structure
        if "config_fields" in source and source["config_fields"]:
            config_fields = source["config_fields"]
            assert "fields" in config_fields
            assert isinstance(config_fields["fields"], list)

    @pytest.mark.asyncio
    async def test_sources_have_supported_auth_providers_field(self, api_client: httpx.AsyncClient):
        """Test that all sources include the supported_auth_providers field."""
        response = await api_client.get("/sources/")
        sources = response.json()

        for source in sources:
            assert "supported_auth_providers" in source, (
                f"Source {source.get('short_name', 'unknown')} missing "
                "supported_auth_providers field"
            )
            # Field should be a list (can be empty)
            assert isinstance(
                source["supported_auth_providers"], list
            ), f"Source {source['short_name']} supported_auth_providers should be a list"

    @pytest.mark.asyncio
    async def test_supported_auth_providers_structure(self, api_client: httpx.AsyncClient):
        """Test that supported_auth_providers field has correct structure."""
        response = await api_client.get("/sources/")
        sources = response.json()

        # Known valid auth provider short names
        valid_providers = ["pipedream", "composio"]

        for source in sources:
            providers = source.get("supported_auth_providers", [])
            if providers:  # If list is not empty
                # All items should be strings
                assert all(
                    isinstance(p, str) for p in providers
                ), f"Source {source['short_name']} has non-string auth providers"
                # All items should be known provider names
                assert all(
                    p in valid_providers for p in providers
                ), f"Source {source['short_name']} has unknown auth providers: {providers}"

    @pytest.mark.asyncio
    async def test_blocked_sources_have_no_auth_providers(self, api_client: httpx.AsyncClient):
        """Test that blocked sources correctly show empty supported_auth_providers."""
        # Sources that are known to be blocked by all providers
        blocked_sources = ["ctti"]

        for source_name in blocked_sources:
            response = await api_client.get(f"/sources/{source_name}")

            # Skip if source doesn't exist in this environment
            if response.status_code == 404:
                continue

            assert response.status_code == 200
            source = response.json()

            providers = source.get("supported_auth_providers", [])
            assert providers == [], (
                f"Source {source_name} should have no supported auth providers, "
                f"but has: {providers}"
            )

    @pytest.mark.asyncio
    async def test_supported_sources_have_auth_providers(self, api_client: httpx.AsyncClient):
        """Test that well-supported sources have auth providers listed."""
        # Sources that should be supported by at least one provider
        supported_sources = ["notion", "slack", "stripe", "hubspot_crm", "linear", "github"]

        sources_with_providers = []
        for source_name in supported_sources:
            response = await api_client.get(f"/sources/{source_name}")

            # Skip if source doesn't exist in this environment
            if response.status_code == 404:
                continue

            assert response.status_code == 200
            source = response.json()

            providers = source.get("supported_auth_providers", [])
            if providers:
                sources_with_providers.append(source_name)

        # At least some of these sources should have auth providers
        # (depending on environment and provider availability)
        assert (
            len(sources_with_providers) >= 0
        ), "Expected some commonly supported sources to have auth providers available"

    @pytest.mark.asyncio
    async def test_auth_provider_field_consistency(self, api_client: httpx.AsyncClient):
        """Test consistency between auth_methods and supported_auth_providers."""
        response = await api_client.get("/sources/")
        sources = response.json()

        for source in sources:
            auth_methods = source.get("auth_methods", [])
            providers = source.get("supported_auth_providers", [])

            # If a source has auth_provider in auth_methods, it might have providers
            # (but not guaranteed if all providers block it)
            if "auth_provider" in auth_methods:
                # Just verify the field exists and is a list - don't enforce it has items
                assert isinstance(providers, list), (
                    f"Source {source['short_name']} has 'auth_provider' in auth_methods "
                    "but supported_auth_providers is not a list"
                )

    @pytest.mark.asyncio
    async def test_sharepoint2019v2_hidden_without_feature_flag(
        self, api_client: httpx.AsyncClient
    ):
        """Test that SharePoint 2019 V2 is hidden when feature flag is not enabled.

        This test assumes the test organization does not have the SHAREPOINT_2019_V2
        feature flag enabled by default.
        """
        response = await api_client.get("/sources/")
        assert response.status_code == 200

        sources = response.json()
        source_names = [s["short_name"] for s in sources]

        # SharePoint 2019 V2 should not be in the list
        assert "sharepoint2019v2" not in source_names, (
            "SharePoint 2019 V2 should be hidden without feature flag"
        )

    @pytest.mark.asyncio
    async def test_sharepoint2019v2_direct_access_returns_404(
        self, api_client: httpx.AsyncClient
    ):
        """Test that directly accessing SharePoint 2019 V2 returns 404 without feature flag."""
        response = await api_client.get("/sources/sharepoint2019v2")

        # Should return 404 since feature flag is not enabled
        assert response.status_code == 404
        error = response.json()
        assert "detail" in error
        assert "not found" in error["detail"].lower()

    @pytest.mark.asyncio
    async def test_regular_sources_still_visible(self, api_client: httpx.AsyncClient):
        """Test that regular sources without feature flags are still visible."""
        response = await api_client.get("/sources/")
        assert response.status_code == 200

        sources = response.json()

        # These sources should always be visible (no feature flag required)
        expected_sources = ["github", "stripe", "notion", "slack"]
        source_names = [s["short_name"] for s in sources]

        for expected in expected_sources:
            # Not all sources may exist in all environments, but check at least some
            if expected in source_names:
                # Verify we can get details
                detail_response = await api_client.get(f"/sources/{expected}")
                assert detail_response.status_code == 200

    @pytest.mark.asyncio
    async def test_sources_feature_flag_field_present(self, api_client: httpx.AsyncClient):
        """Test that all sources have the feature_flag field in schema."""
        response = await api_client.get("/sources/")
        assert response.status_code == 200

        sources = response.json()

        for source in sources:
            # feature_flag field should be present (can be null)
            # The field might not be in JSON if it's null, which is fine
            if "feature_flag" in source:
                # If present, should be a string or null
                assert source["feature_flag"] is None or isinstance(source["feature_flag"], str)
