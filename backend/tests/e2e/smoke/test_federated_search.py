"""
Async test module for Federated Search functionality.

Tests search against federated sources (Slack via Composio) that query external
APIs at search time instead of syncing data to the vector DB.

Covers:
- Federated-only collections (no vector data, all results from Slack API)
- Mixed collections (Stripe synced + Slack federated, RRF-merged results)
- Feature combinations (rerank, answer generation, query expansion)
- Source connection lifecycle for federated sources
"""

import uuid

import httpx
import pytest


# ---------------------------------------------------------------------------
# Tests: federated-only collection (Slack only)
# ---------------------------------------------------------------------------


class TestFederatedSearchSlackOnly:
    """Test federated search with a Slack-only collection (no vector data)."""

    @pytest.mark.asyncio
    @pytest.mark.requires_composio
    async def test_slack_source_connection_creation(
        self,
        api_client: httpx.AsyncClient,
        source_connection_slack_federated: dict,
    ):
        """Verify Slack source connection is created correctly via Composio."""
        conn = source_connection_slack_federated
        assert conn["id"]
        assert conn["auth"]["method"] == "auth_provider"
        assert conn["auth"]["authenticated"] is True
        assert conn["status"] == "active"
        assert conn["sync"] is None

    @pytest.mark.asyncio
    @pytest.mark.requires_composio
    async def test_federated_search_returns_results(
        self,
        api_client: httpx.AsyncClient,
        source_connection_slack_federated: dict,
    ):
        """Search a federated-only collection — results come from Slack API."""
        readable_id = source_connection_slack_federated["readable_collection_id"]

        response = await api_client.post(
            f"/collections/{readable_id}/search",
            json={
                "query": "hello",
                "expand_query": False,
                "interpret_filters": False,
                "rerank": False,
                "generate_answer": False,
            },
            timeout=90,
        )

        assert response.status_code == 200, f"Search failed: {response.text}"
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)

    @pytest.mark.asyncio
    @pytest.mark.requires_composio
    async def test_federated_search_with_query_expansion(
        self,
        api_client: httpx.AsyncClient,
        source_connection_slack_federated: dict,
    ):
        """Federated search with query expansion enabled."""
        readable_id = source_connection_slack_federated["readable_collection_id"]

        response = await api_client.post(
            f"/collections/{readable_id}/search",
            json={
                "query": "project updates",
                "expand_query": True,
                "interpret_filters": False,
                "rerank": False,
                "generate_answer": False,
            },
            timeout=90,
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    @pytest.mark.asyncio
    @pytest.mark.requires_composio
    async def test_federated_search_with_reranking(
        self,
        api_client: httpx.AsyncClient,
        source_connection_slack_federated: dict,
    ):
        """Federated search with LLM reranking enabled."""
        readable_id = source_connection_slack_federated["readable_collection_id"]

        response = await api_client.post(
            f"/collections/{readable_id}/search",
            json={
                "query": "important announcements",
                "expand_query": False,
                "interpret_filters": False,
                "rerank": True,
                "generate_answer": False,
            },
            timeout=90,
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    @pytest.mark.asyncio
    @pytest.mark.requires_composio
    async def test_federated_search_with_answer_generation(
        self,
        api_client: httpx.AsyncClient,
        source_connection_slack_federated: dict,
    ):
        """Federated search with AI answer generation."""
        readable_id = source_connection_slack_federated["readable_collection_id"]

        response = await api_client.post(
            f"/collections/{readable_id}/search",
            json={
                "query": "What are people discussing?",
                "expand_query": False,
                "interpret_filters": False,
                "rerank": False,
                "generate_answer": True,
            },
            timeout=90,
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        if data.get("results"):
            assert "completion" in data

    @pytest.mark.asyncio
    @pytest.mark.requires_composio
    async def test_federated_search_all_features(
        self,
        api_client: httpx.AsyncClient,
        source_connection_slack_federated: dict,
    ):
        """Federated search with all features enabled together."""
        readable_id = source_connection_slack_federated["readable_collection_id"]

        response = await api_client.post(
            f"/collections/{readable_id}/search",
            json={
                "query": "team meeting notes",
                "expand_query": True,
                "interpret_filters": False,
                "rerank": True,
                "generate_answer": True,
                "limit": 10,
            },
            timeout=120,
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    @pytest.mark.asyncio
    @pytest.mark.requires_composio
    async def test_federated_search_result_structure(
        self,
        api_client: httpx.AsyncClient,
        source_connection_slack_federated: dict,
    ):
        """Verify federated search results have the expected fields."""
        readable_id = source_connection_slack_federated["readable_collection_id"]

        response = await api_client.post(
            f"/collections/{readable_id}/search",
            json={
                "query": "test",
                "expand_query": False,
                "interpret_filters": False,
                "rerank": False,
                "generate_answer": False,
            },
            timeout=90,
        )

        assert response.status_code == 200
        data = response.json()

        if data.get("results"):
            result = data["results"][0]
            assert "entity_id" in result
            assert "score" in result
            assert "name" in result


# ---------------------------------------------------------------------------
# Tests: mixed collection (Stripe synced + Slack federated)
# ---------------------------------------------------------------------------


class TestFederatedSearchMixedCollection:
    """Test federated search in a collection with both synced and federated sources.

    Uses the module_source_connection_stripe fixture (Stripe already synced and
    searchable), then adds Slack as a federated source to the same collection.
    All mixed-collection assertions are in a single test to avoid repeated
    Stripe sync overhead.
    """

    @pytest.mark.asyncio
    @pytest.mark.requires_composio
    async def test_mixed_collection_search(
        self,
        api_client: httpx.AsyncClient,
        module_source_connection_stripe: dict,
        composio_auth_provider: dict,
        config,
    ):
        """Search a mixed Stripe+Slack collection — basic, all-features, and all strategies."""
        if not config.TEST_COMPOSIO_SLACK_AUTH_CONFIG_ID or not config.TEST_COMPOSIO_SLACK_ACCOUNT_ID:
            pytest.skip("Slack Composio configuration not available")

        readable_id = module_source_connection_stripe["readable_collection_id"]

        # Add Slack (federated) source to the existing Stripe collection
        resp = await api_client.post(
            "/source-connections",
            json={
                "name": f"Slack Mixed {uuid.uuid4().hex[:8]}",
                "short_name": "slack",
                "readable_collection_id": readable_id,
                "authentication": {
                    "provider_readable_id": composio_auth_provider["readable_id"],
                    "provider_config": {
                        "auth_config_id": config.TEST_COMPOSIO_SLACK_AUTH_CONFIG_ID,
                        "account_id": config.TEST_COMPOSIO_SLACK_ACCOUNT_ID,
                    },
                },
                "sync_immediately": False,
            },
        )
        assert resp.status_code == 200, f"Slack connection failed: {resp.text}"
        slack_conn = resp.json()

        try:
            # 1. Basic mixed search — should return results from both sources
            response = await api_client.post(
                f"/collections/{readable_id}/search",
                json={
                    "query": "invoice OR message",
                    "expand_query": False,
                    "interpret_filters": False,
                    "rerank": False,
                    "generate_answer": False,
                },
                timeout=90,
            )
            assert response.status_code == 200, f"Mixed search failed: {response.text}"
            data = response.json()
            assert "results" in data
            assert isinstance(data["results"], list)
            assert len(data["results"]) > 0, "Expected results from mixed collection"

            # 2. All features enabled
            response = await api_client.post(
                f"/collections/{readable_id}/search",
                json={
                    "query": "payment updates",
                    "expand_query": True,
                    "interpret_filters": False,
                    "rerank": True,
                    "generate_answer": True,
                    "limit": 20,
                },
                timeout=120,
            )
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            if data.get("results"):
                assert "completion" in data

            # 3. All retrieval strategies
            for strategy in ("hybrid", "neural", "keyword"):
                response = await api_client.post(
                    f"/collections/{readable_id}/search",
                    json={
                        "query": "customer",
                        "retrieval_strategy": strategy,
                        "expand_query": False,
                        "interpret_filters": False,
                        "rerank": False,
                        "generate_answer": False,
                    },
                    timeout=90,
                )
                assert response.status_code == 200, (
                    f"Strategy '{strategy}' failed: {response.text}"
                )
                assert "results" in response.json()
        finally:
            try:
                await api_client.delete(f"/source-connections/{slack_conn['id']}")
            except Exception:
                pass
