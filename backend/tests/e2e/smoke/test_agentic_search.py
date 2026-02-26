"""
Async test module for Agentic Search functionality.

Tests the agentic search endpoint:
- Thinking mode (default, multi-step search)
- Fast mode (single-pass search)
- Response structure validation
- Input validation (empty query, invalid mode)
- SSE streaming endpoint
"""

import json
from typing import Dict

import httpx
import pytest


class TestAgenticSearch:
    """Test suite for agentic search functionality.

    Uses a module-scoped Stripe source connection that's loaded once and shared
    across all tests in this module for efficiency.

    Query selection: Stripe test data contains invoices, customers, payments,
    balance transactions, etc. We use simple, broad queries like "invoices" or
    "payments" that reliably match Stripe entities on the first search pass,
    avoiding queries that would trigger unnecessary consolidation rounds.
    """

    # ------------------------------------------------------------------
    # Mode tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_agentic_search_thinking_mode(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test agentic search with default thinking mode.

        Thinking mode runs a multi-step plan-search-evaluate loop.
        Uses a broad query that will match Stripe data on the first iteration.
        Validates 200 response with results + answer.
        """
        payload = {
            "query": "invoices and payments",
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}"
            "/agentic-search",
            json=payload,
            timeout=120,
        )

        assert response.status_code == 200, f"Agentic search failed: {response.text}"

        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) > 0, "Thinking mode should return results from Stripe data"
        assert "answer" in data
        assert isinstance(data["answer"], dict)
        assert "text" in data["answer"]
        assert "citations" in data["answer"]

    @pytest.mark.asyncio
    async def test_agentic_search_fast_mode(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test agentic search with explicit fast mode.

        Fast mode performs a single search pass without the evaluate loop.
        Should still return results + answer.
        """
        payload = {
            "query": "invoices",
            "mode": "fast",
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}"
            "/agentic-search",
            json=payload,
            timeout=90,
        )

        assert response.status_code == 200, f"Fast mode search failed: {response.text}"

        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) > 0, "Fast mode should return results from Stripe data"
        assert "answer" in data
        assert "text" in data["answer"]
        assert "citations" in data["answer"]

    # ------------------------------------------------------------------
    # Response structure validation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_agentic_search_response_structure(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Deep validation of agentic search response structure.

        Each result should have: entity_id, name, relevance_score,
        airweave_system_metadata (with source_name, entity_type).
        Answer should have: text (str), citations (list of dicts with entity_id).
        """
        payload = {
            "query": "customers and transactions",
            "mode": "fast",
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}"
            "/agentic-search",
            json=payload,
            timeout=90,
        )

        assert response.status_code == 200, f"Search failed: {response.text}"

        data = response.json()

        # Validate results structure
        assert "results" in data
        assert len(data["results"]) > 0, "Expected results for structure validation"

        first_result = data["results"][0]
        assert "entity_id" in first_result
        assert "name" in first_result
        assert "relevance_score" in first_result
        assert isinstance(first_result["relevance_score"], (int, float))
        assert "airweave_system_metadata" in first_result

        sys_meta = first_result["airweave_system_metadata"]
        assert "source_name" in sys_meta
        assert "entity_type" in sys_meta

        # Optional but expected fields
        assert "breadcrumbs" in first_result
        assert isinstance(first_result["breadcrumbs"], list)
        assert "textual_representation" in first_result
        assert "web_url" in first_result

        # Validate answer structure
        assert "answer" in data
        answer = data["answer"]
        assert "text" in answer
        assert isinstance(answer["text"], str)
        assert len(answer["text"]) > 0, "Answer text should not be empty"
        assert "citations" in answer
        assert isinstance(answer["citations"], list)

        # If there are citations, validate their structure
        if answer["citations"]:
            first_citation = answer["citations"][0]
            assert "entity_id" in first_citation

    @pytest.mark.asyncio
    async def test_agentic_search_returns_results_from_synced_data(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test that agentic search returns results from synced Stripe data.

        Since module_source_connection_stripe syncs on creation and waits for
        completion, we should have data available for searching.
        """
        payload = {
            "query": "balance transactions",
            "mode": "fast",
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}"
            "/agentic-search",
            json=payload,
            timeout=90,
        )

        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert len(data["results"]) > 0, "Expected results from synced Stripe data"

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_agentic_search_empty_query_returns_422(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that an empty query string returns 422 Unprocessable Entity.

        Uses a lightweight empty collection since Pydantic validation rejects the
        request before any search is executed.
        """
        payload = {"query": ""}

        response = await api_client.post(
            f"/collections/{collection['readable_id']}/agentic-search",
            json=payload,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_agentic_search_invalid_mode_returns_422(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that an invalid mode value returns 422 Unprocessable Entity.

        Uses a lightweight empty collection since Pydantic validation rejects the
        request before any search is executed.
        """
        payload = {
            "query": "test query",
            "mode": "invalid_mode",
        }

        response = await api_client.post(
            f"/collections/{collection['readable_id']}/agentic-search",
            json=payload,
        )

        assert response.status_code == 422

    # ------------------------------------------------------------------
    # Limit parameter tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_agentic_search_limit_truncates_results(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test that the limit parameter truncates results.

        First performs an unlimited search to establish a baseline, then performs
        the same search with a small limit and verifies the result count is capped.
        Uses fast mode for speed since limit is applied post-search.
        """
        # Baseline: search without limit
        baseline_payload = {
            "query": "invoices and payments",
            "mode": "fast",
        }

        baseline_response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}"
            "/agentic-search",
            json=baseline_payload,
            timeout=90,
        )

        assert baseline_response.status_code == 200, (
            f"Baseline search failed: {baseline_response.text}"
        )

        baseline_data = baseline_response.json()
        baseline_count = len(baseline_data["results"])
        assert baseline_count > 0, "Baseline should return results from Stripe data"

        # Limited search: use a limit smaller than baseline count
        limit = min(2, baseline_count)
        limited_payload = {
            "query": "invoices and payments",
            "mode": "fast",
            "limit": limit,
        }

        limited_response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}"
            "/agentic-search",
            json=limited_payload,
            timeout=90,
        )

        assert limited_response.status_code == 200, (
            f"Limited search failed: {limited_response.text}"
        )

        limited_data = limited_response.json()
        assert len(limited_data["results"]) <= limit, (
            f"Expected at most {limit} results, got {len(limited_data['results'])}"
        )
        # Answer should still be present regardless of limit
        assert "answer" in limited_data
        assert "text" in limited_data["answer"]

    @pytest.mark.asyncio
    async def test_agentic_search_limit_without_value_returns_all(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test that omitting the limit parameter returns all results.

        When limit is not set (None), the agent's results should be returned
        without any truncation.
        """
        payload = {
            "query": "invoices",
            "mode": "fast",
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}"
            "/agentic-search",
            json=payload,
            timeout=90,
        )

        assert response.status_code == 200, f"Search failed: {response.text}"

        data = response.json()
        assert "results" in data
        assert len(data["results"]) > 0, "Expected results without limit"

    @pytest.mark.asyncio
    async def test_agentic_search_limit_larger_than_results_returns_all(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test that a limit larger than available results returns all results.

        If the agent returns fewer results than the user's limit, we don't
        pad or fetch more — we just return what the agent found.
        """
        payload = {
            "query": "invoices",
            "mode": "fast",
            "limit": 10000,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}"
            "/agentic-search",
            json=payload,
            timeout=90,
        )

        assert response.status_code == 200, f"Search failed: {response.text}"

        data = response.json()
        assert "results" in data
        # Should return results normally — no error from a large limit
        assert len(data["results"]) > 0, "Expected results with large limit"

    @pytest.mark.asyncio
    async def test_agentic_search_limit_invalid_zero_returns_422(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that limit=0 returns 422 Unprocessable Entity.

        Limit must be >= 1 per the schema validation.
        """
        payload = {
            "query": "test query",
            "limit": 0,
        }

        response = await api_client.post(
            f"/collections/{collection['readable_id']}/agentic-search",
            json=payload,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_agentic_search_limit_invalid_negative_returns_422(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that a negative limit returns 422 Unprocessable Entity.

        Limit must be >= 1 per the schema validation.
        """
        payload = {
            "query": "test query",
            "limit": -5,
        }

        response = await api_client.post(
            f"/collections/{collection['readable_id']}/agentic-search",
            json=payload,
        )

        assert response.status_code == 422

    # ------------------------------------------------------------------
    # Streaming endpoint tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_agentic_search_stream_returns_sse_events(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test that the streaming endpoint returns SSE events.

        Uses httpx async streaming to consume Server-Sent Events.
        Verifies we receive a 'done' event with a proper response payload
        containing results and answer.

        Transient LLM provider errors (503, rate limits) are tolerated since
        the test validates our streaming infrastructure, not the LLM provider.
        """
        payload = {
            "query": "invoices and payments",
        }

        url = (
            f"/collections/{module_source_connection_stripe['readable_collection_id']}"
            "/agentic-search/stream"
        )

        events = []
        async with api_client.stream("POST", url, json=payload, timeout=120) as stream:
            assert stream.status_code == 200, f"Stream failed: status {stream.status_code}"

            async for line in stream.aiter_lines():
                if not line.startswith("data: "):
                    continue

                raw = line[len("data: "):]
                try:
                    event = json.loads(raw)
                    events.append(event)

                    # Stop reading once we get the terminal event
                    if event.get("type") in ("done", "error"):
                        break
                except json.JSONDecodeError:
                    continue

        # We should have received at least one event
        assert len(events) > 0, "No SSE events received"

        event_types = [e.get("type") for e in events]

        # The stream must terminate with either 'done' or 'error'
        assert event_types[-1] in ("done", "error"), (
            f"Stream did not terminate properly. Event types: {event_types}"
        )

        # If we got an error, check if it's a transient LLM provider issue (acceptable
        # for a smoke test) vs a real bug in our code
        if "error" in event_types and "done" not in event_types:
            error_event = next(e for e in events if e.get("type") == "error")
            error_msg = error_event.get("message", "").lower()
            transient_indicators = ["503", "rate", "too_many_requests", "queue_exceeded"]
            is_transient = any(indicator in error_msg for indicator in transient_indicators)
            if not is_transient:
                pytest.fail(
                    f"Stream ended with non-transient error: {error_event.get('message')}"
                )
            pytest.skip(f"Skipped due to transient LLM provider error: {error_msg[:100]}")

        # Validate the done event payload
        done_event = next(e for e in events if e.get("type") == "done")
        assert "response" in done_event
        assert "results" in done_event["response"]
        assert "answer" in done_event["response"]
        assert "text" in done_event["response"]["answer"]
        assert "citations" in done_event["response"]["answer"]

    @pytest.mark.asyncio
    async def test_agentic_search_stream_fast_mode(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test streaming endpoint in fast mode.

        Fast mode should still stream events and end with a 'done' event,
        but without the iterative planning/evaluating cycle.
        """
        payload = {
            "query": "invoices",
            "mode": "fast",
        }

        url = (
            f"/collections/{module_source_connection_stripe['readable_collection_id']}"
            "/agentic-search/stream"
        )

        events = []
        async with api_client.stream("POST", url, json=payload, timeout=90) as stream:
            assert stream.status_code == 200, f"Stream failed: status {stream.status_code}"

            async for line in stream.aiter_lines():
                if not line.startswith("data: "):
                    continue

                raw = line[len("data: "):]
                try:
                    event = json.loads(raw)
                    events.append(event)

                    if event.get("type") in ("done", "error"):
                        break
                except json.JSONDecodeError:
                    continue

        assert len(events) > 0, "No SSE events received"

        event_types = [e.get("type") for e in events]
        assert "done" in event_types, f"No 'done' event received. Event types: {event_types}"

        # Fast mode should have planning + searching events but no evaluating
        # (it breaks after the first search without evaluation)
        assert "planning" in event_types, (
            f"Expected 'planning' event in direct mode. Got: {event_types}"
        )
        assert "searching" in event_types, (
            f"Expected 'searching' event in direct mode. Got: {event_types}"
        )

        done_event = next(e for e in events if e.get("type") == "done")
        assert "response" in done_event
        assert "results" in done_event["response"]
        assert "answer" in done_event["response"]
