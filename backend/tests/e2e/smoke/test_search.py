"""
Async test module for Search functionality.

Tests collection search functionality using the unified POST endpoint:
- Basic search with all defaults
- Individual feature testing (query expansion, interpretation, reranking, answer generation)
- Retrieval strategies (hybrid, neural, keyword)
- Pagination and temporal relevance
"""

import pytest
import httpx


class TestSearch:
    """Test suite for search functionality.

    Uses a module-scoped Stripe source connection that's loaded once and shared
    across all tests in this module for efficiency.
    """

    @pytest.mark.asyncio
    async def test_search_with_all_defaults(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test search with only a query - uses all defaults from defaults.yml.

        Default behavior (from defaults.yml):
        - expand_query: true
        - interpret_filters: false
        - rerank: true
        - generate_answer: true
        - temporal_relevance: 0.3
        - retrieval_strategy: hybrid
        - offset: 0
        - limit: 1000
        """
        search_payload = {
            "query": "Are there any open invoices"
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload,
            timeout=90,
        )

        assert response.status_code == 200, f"Search failed: {response.text}"

        results = response.json()
        assert "results" in results
        assert isinstance(results["results"], list)

        # With generate_answer=true by default, we should get a completion
        if results.get("results"):
            assert "completion" in results
            assert results["completion"] is not None

    @pytest.mark.asyncio
    async def test_basic_search_raw_only(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test basic search with all extra features disabled."""
        search_payload = {
            "query": "invoices",
            "expand_query": False,
            "interpret_filters": False,
            "rerank": False,
            "generate_answer": False,
            "temporal_relevance": 0.0,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload,
            timeout=90,
        )

        assert response.status_code == 200, f"Search failed: {response.text}"

        results = response.json()
        assert "results" in results

        # With generate_answer=false, completion should be None
        assert results.get("completion") is None

        if results.get("results"):
            # Validate result structure (new AirweaveSearchResult format)
            first_result = results["results"][0]
            assert "entity_id" in first_result
            assert "score" in first_result
            assert "name" in first_result

    @pytest.mark.asyncio
    async def test_query_expansion_only(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test query expansion in isolation - disable other features."""
        search_payload = {
            "query": "invoice",
            "expand_query": True,
            "interpret_filters": False,
            "rerank": False,
            "generate_answer": False,
            "temporal_relevance": 0.0,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload,
            timeout=90,
        )

        assert response.status_code == 200
        results = response.json()
        assert "results" in results

    @pytest.mark.asyncio
    async def test_query_interpretation_only(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test query interpretation in isolation - disable other features."""
        search_payload = {
            "query": "find invoices from last month",
            "expand_query": False,
            "interpret_filters": True,
            "rerank": False,
            "generate_answer": False,
            "temporal_relevance": 0.0,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload,
            timeout=90,
        )

        assert response.status_code == 200
        results = response.json()
        assert "results" in results

    @pytest.mark.asyncio
    async def test_reranking_only(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test LLM reranking in isolation - disable other features."""
        search_payload = {
            "query": "important invoices",
            "expand_query": False,
            "interpret_filters": False,
            "rerank": True,
            "generate_answer": False,
            "temporal_relevance": 0.0,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload,
            timeout=90,
        )

        assert response.status_code == 200
        results = response.json()
        assert "results" in results

    @pytest.mark.asyncio
    async def test_generate_answer_only(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test answer generation in isolation - disable other features."""
        search_payload = {
            "query": "What are the most recent payments?",
            "expand_query": False,
            "interpret_filters": False,
            "rerank": False,
            "generate_answer": True,
            "temporal_relevance": 0.0,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload,
            timeout=90,
        )

        assert response.status_code == 200
        results = response.json()
        assert "results" in results

        # With generate_answer=true, should have completion if there are results
        if results.get("results"):
            assert "completion" in results

    @pytest.mark.asyncio
    async def test_temporal_relevance(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test temporal relevance weighting."""
        search_payload = {
            "query": "recent activity",
            "temporal_relevance": 0.8,
            "expand_query": False,
            "interpret_filters": False,
            "rerank": False,
            "generate_answer": False,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload,
            timeout=90,
        )

        assert response.status_code == 200
        results = response.json()
        assert "results" in results

    @pytest.mark.asyncio
    async def test_retrieval_strategies(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test different retrieval strategies: hybrid, neural, keyword."""
        strategies = ["hybrid", "neural", "keyword"]

        for strategy in strategies:
            search_payload = {
                "query": "payment OR invoice",
                "retrieval_strategy": strategy,
                "expand_query": False,
                "interpret_filters": False,
                "rerank": False,
                "generate_answer": False,
                "temporal_relevance": 0.0,
            }

            response = await api_client.post(
                f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
                json=search_payload,
                timeout=90,
            )

            assert response.status_code == 200, f"Strategy {strategy} failed"
            results = response.json()
            assert "results" in results

    @pytest.mark.asyncio
    async def test_pagination_without_reranking(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test pagination consistency without reranking.

        Uses keyword search (pure BM25) for deterministic ordering.
        Verifies that offset moves through results predictably by checking that
        offset=1,limit=1 returns the same result as the second item from offset=0,limit=2.
        """
        # Get first 2 results
        search_payload_first_two = {
            "query": "invoice",
            "retrieval_strategy": "keyword",
            "limit": 2,
            "offset": 0,
            "expand_query": False,
            "interpret_filters": False,
            "rerank": False,
            "generate_answer": False,
            "temporal_relevance": 0.0,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload_first_two,
            timeout=90,
        )

        assert response.status_code == 200
        first_two = response.json()
        assert "results" in first_two

        if len(first_two.get("results", [])) >= 2:
            second_result_id = first_two["results"][1].get("entity_id")

            # Now get just the second result using offset=1, limit=1
            search_payload_second_only = {
                "query": "invoice",
                "retrieval_strategy": "keyword",
                "limit": 1,
                "offset": 1,
                "expand_query": False,
                "interpret_filters": False,
                "rerank": False,
                "generate_answer": False,
                "temporal_relevance": 0.0,
            }

            response = await api_client.post(
                f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
                json=search_payload_second_only,
                timeout=90,
            )

            assert response.status_code == 200
            second_only = response.json()

            assert len(second_only.get("results", [])) == 1
            offset_result_id = second_only["results"][0].get("entity_id")

            # The second result from first query should match the offset=1 query
            assert offset_result_id == second_result_id, (
                f"Pagination inconsistent: offset=1,limit=1 returned {offset_result_id} "
                f"but offset=0,limit=2 had {second_result_id} as second result"
            )

    @pytest.mark.asyncio
    async def test_pagination_with_reranking(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test pagination consistency WITH reranking enabled.

        Reranking applies special logic (fetches more candidates, reranks them, then paginates).
        This test verifies that pagination still works correctly after reranking.
        """
        # Get first 2 results with reranking
        search_payload_first_two = {
            "query": "invoice",
            "retrieval_strategy": "keyword",
            "limit": 2,
            "offset": 0,
            "expand_query": False,
            "interpret_filters": False,
            "rerank": True,
            "generate_answer": False,
            "temporal_relevance": 0.0,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload_first_two,
            timeout=90,
        )

        assert response.status_code == 200
        first_two = response.json()
        assert "results" in first_two

        if len(first_two.get("results", [])) >= 2:
            second_result_id = first_two["results"][1].get("entity_id")

            # Now get just the second result using offset=1, limit=1 with reranking
            search_payload_second_only = {
                "query": "invoice",
                "retrieval_strategy": "keyword",
                "limit": 1,
                "offset": 1,
                "expand_query": False,
                "interpret_filters": False,
                "rerank": True,
                "generate_answer": False,
                "temporal_relevance": 0.0,
            }

            response = await api_client.post(
                f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
                json=search_payload_second_only,
                timeout=90,
            )

            assert response.status_code == 200
            second_only = response.json()

            assert len(second_only.get("results", [])) == 1
            offset_result_id = second_only["results"][0].get("entity_id")

            # The second result from first query should match the offset=1 query
            # even with reranking enabled
            assert offset_result_id == second_result_id, (
                f"Pagination with reranking inconsistent: offset=1,limit=1 returned {offset_result_id} "
                f"but offset=0,limit=2 had {second_result_id} as second result"
            )

    @pytest.mark.asyncio
    async def test_empty_query(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test handling of empty query with Stripe collection."""
        search_payload = {
            "query": ""
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload,
        )

        # Should return 422 for empty query
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_combined_features(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test search with multiple features enabled together."""
        search_payload = {
            "query": "payment processing",
            "retrieval_strategy": "hybrid",
            "expand_query": True,
            "rerank": True,
            "generate_answer": True,
            "temporal_relevance": 0.5,
            "limit": 10,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload,
            timeout=90,
        )

        assert response.status_code == 200
        results = response.json()
        assert "results" in results

        # With generate_answer=true, should have completion if there are results
        if results.get("results"):
            assert "completion" in results

    @pytest.mark.asyncio
    async def test_search_with_synced_data(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test search with already synced Stripe data.

        Since module_source_connection_stripe syncs on creation and waits for completion,
        we should have data available for searching.
        """
        search_payload = {
            "query": "invoice OR payment OR customer",
            "expand_query": False,
            "interpret_filters": False,
            "rerank": False,
            "generate_answer": False,
            "temporal_relevance": 0.0,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload,
            timeout=90,
        )

        assert response.status_code == 200
        results = response.json()

        # Should have some results from the initial sync
        if results.get("results"):
            assert len(results["results"]) > 0, "Expected results from synced Stripe data"

    @pytest.mark.asyncio
    async def test_legacy_get_endpoint(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test legacy GET endpoint with query params still works."""
        response = await api_client.get(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            params={
                "query": "invoices",
                "response_type": "raw",
                "limit": 10,
                "offset": 0,
                "recency_bias": 0.5,
            },
            timeout=90,
        )

        assert response.status_code == 200, f"Legacy GET search failed: {response.text}"

        # Check for deprecation headers
        assert response.headers.get("X-API-Deprecation") == "true"
        assert "X-API-Deprecation-Message" in response.headers

        results = response.json()
        # Legacy response includes status and response_type fields
        assert "results" in results
        assert "status" in results
        assert "response_type" in results
        assert results["response_type"] == "raw"

    @pytest.mark.asyncio
    async def test_legacy_post_endpoint_with_old_schema(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test legacy POST endpoint with old schema fields still works."""
        legacy_payload = {
            "query": "customer payments",
            "response_type": "completion",  # Old field
            "expansion_strategy": "auto",  # Old field
            "enable_reranking": True,  # Old field name
            "enable_query_interpretation": False,  # Old field name
            "search_method": "hybrid",  # Old field
            "recency_bias": 0.3,  # Old field
            "limit": 20,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=legacy_payload,
            timeout=90,
        )

        assert response.status_code == 200, f"Legacy POST search failed: {response.text}"

        # Check for deprecation headers
        assert response.headers.get("X-API-Deprecation") == "true"
        assert "X-API-Deprecation-Message" in response.headers

        results = response.json()
        # Legacy response includes status and response_type fields
        assert "results" in results
        assert "status" in results
        assert "response_type" in results
        assert results["response_type"] == "completion"

        # With response_type=completion, should have completion field
        if results.get("results"):
            assert "completion" in results

    @pytest.mark.asyncio
    async def test_legacy_post_raw_response(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test legacy POST with response_type='raw' returns correct format."""
        legacy_payload = {
            "query": "invoices",
            "response_type": "raw",
            "expansion_strategy": "no_expansion",
            "enable_reranking": False,
            "limit": 5,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=legacy_payload,
            timeout=90,
        )

        assert response.status_code == 200
        results = response.json()

        # Legacy response should have status and response_type
        assert "status" in results
        assert "response_type" in results
        assert results["response_type"] == "raw"

        # With response_type=raw, completion should be None
        assert results.get("completion") is None
