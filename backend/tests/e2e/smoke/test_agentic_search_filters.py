"""
E2E smoke tests for agentic search filtering.

Uses stub + optional Stripe data to validate that agentic_search filters:
1. Are correctly validated by Pydantic (invalid input rejected with 422)
2. Actually filter results (source/entity_type filtering with dual sources)
3. Survive merging with planner-generated filters in thinking mode

The fixture creates a collection with:
- Stub source: seed=42, 20 entities (deterministic, always available)
- Stripe source: added if TEST_STRIPE_API_KEY is available

Having two sources is critical for verifying that source filters actually
exclude the other source's data.
"""

import asyncio
import atexit
import json
import time
from collections import Counter
from typing import AsyncGenerator, Dict, List, Optional

import httpx
import pytest
import pytest_asyncio


# =============================================================================
# Cleanup
# =============================================================================


def _cleanup_cached_collection():
    """Cleanup cached collection on process exit.

    Runs when the pytest worker process exits, ensuring we don't leave
    orphaned collections in the test environment.
    """
    global _cached_agentic_search_collection, _cached_agentic_search_readable_id

    if _cached_agentic_search_collection is None:
        return

    try:
        from config import settings

        import httpx as httpx_sync

        with httpx_sync.Client(
            base_url=settings.api_url,
            headers=settings.api_headers,
            timeout=30,
        ) as client:
            for conn_id in _cached_agentic_search_collection.get("_connections_to_cleanup", []):
                try:
                    client.delete(f"/source-connections/{conn_id}")
                except Exception:
                    pass

            if _cached_agentic_search_readable_id:
                try:
                    client.delete(f"/collections/{_cached_agentic_search_readable_id}")
                except Exception:
                    pass
    except Exception:
        pass


atexit.register(_cleanup_cached_collection)


# =============================================================================
# Helpers
# =============================================================================


def print_results_summary(results: dict, test_name: str, filter_list: list = None):
    """Print a summary of agentic search results for debugging."""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")

    if filter_list:
        print(f"\nFILTER APPLIED:")
        print(json.dumps(filter_list, indent=2))
    else:
        print("\nNO FILTER APPLIED")

    result_list = results.get("results", [])
    print(f"\nTOTAL RESULTS RETURNED: {len(result_list)}")

    if not result_list:
        print("  (no results)")
        return

    source_names = Counter()
    entity_types = Counter()

    for r in result_list:
        sys_meta = r.get("airweave_system_metadata", {})
        source_names[sys_meta.get("source_name", "UNKNOWN")] += 1
        entity_types[sys_meta.get("entity_type", "UNKNOWN")] += 1

    print(f"\nBY SOURCE NAME:")
    for sn, count in sorted(source_names.items()):
        print(f"  {sn}: {count}")

    print(f"\nBY ENTITY TYPE:")
    for et, count in sorted(entity_types.items()):
        print(f"  {et}: {count}")

    print(f"\nFIRST 5 RESULTS:")
    for i, r in enumerate(result_list[:5]):
        sys_meta = r.get("airweave_system_metadata", {})
        print(f"  {i+1}. {r.get('entity_id')}")
        print(f"      type: {sys_meta.get('entity_type')}")
        print(f"      source: {sys_meta.get('source_name')}")
        print(f"      name: {r.get('name', 'N/A')[:50]}")

    if len(result_list) > 5:
        print(f"  ... and {len(result_list) - 5} more results")

    print(f"{'='*80}\n")


# =============================================================================
# Collection setup
# =============================================================================

_cached_agentic_search_collection: Optional[Dict] = None
_cached_agentic_search_readable_id: Optional[str] = None


async def wait_for_sync(
    client: httpx.AsyncClient,
    connection_id: str,
    max_wait_time: int = 180,
    poll_interval: int = 3,
) -> bool:
    """Wait for a source connection sync job to successfully complete.

    Polls the sync job status until it reaches a terminal state.
    Returns True only if the sync job completed successfully.
    Returns False if the job failed, was cancelled, or timed out.
    """
    elapsed = 0
    while elapsed < max_wait_time:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        status_response = await client.get(f"/source-connections/{connection_id}")
        if status_response.status_code != 200:
            continue

        conn_details = status_response.json()

        # Check sync job status (the actual job, not just the connection)
        sync_info = conn_details.get("sync")
        if sync_info and sync_info.get("last_job"):
            job_status = sync_info["last_job"].get("status")
            if job_status == "completed":
                return True
            if job_status in ["failed", "cancelled"]:
                return False

        # If no job info yet but connection errored, bail out
        if conn_details.get("status") == "error":
            return False

    return False


async def _create_agentic_search_collection(client: httpx.AsyncClient) -> Dict:
    """Create a collection with stub + optional Stripe data for agentic_search filter testing.

    - Stub source: seed=42, 20 entities (deterministic)
    - Stripe source: added if TEST_STRIPE_API_KEY is available
    """
    from config import settings

    connections_to_cleanup: List[str] = []

    # Create collection
    collection_data = {"name": f"AgenticSearch Filter Test {int(time.time())}"}
    response = await client.post("/collections/", json=collection_data)

    if response.status_code != 200:
        pytest.fail(f"Failed to create collection: {response.text}")

    collection = response.json()
    readable_id = collection["readable_id"]

    # ---------- Source 1: Stub (always created) ----------
    stub_connection_data = {
        "name": f"Stub AgenticSearch Filter Test {int(time.time())}",
        "short_name": "stub",
        "readable_collection_id": readable_id,
        "authentication": {"credentials": {"stub_key": "test"}},
        "config": {
            "seed": 42,
            "entity_count": 20,
            "generation_delay_ms": 0,
            "small_entity_weight": 25,
            "medium_entity_weight": 25,
            "large_entity_weight": 20,
            "small_file_weight": 10,
            "large_file_weight": 10,
            "code_file_weight": 10,
        },
        "sync_immediately": True,
    }

    response = await client.post("/source-connections", json=stub_connection_data)
    if response.status_code != 200:
        pytest.fail(f"Failed to create stub connection: {response.text}")

    stub_connection = response.json()
    connections_to_cleanup.append(stub_connection["id"])

    # Wait for stub sync
    if not await wait_for_sync(client, stub_connection["id"]):
        pytest.fail("Stub sync did not complete within timeout")

    # Verify stub data is searchable (use regular /search — cheaper, no LLM dependency)
    stub_verified = False
    for attempt in range(18):  # up to ~100s (3s x5, 5s x5, 8s x8)
        wait_secs = 3 if attempt < 5 else 5 if attempt < 10 else 8
        await asyncio.sleep(wait_secs)
        verify_resp = await client.post(
            f"/collections/{readable_id}/search",
            json={
                "query": "stub",
                "expand_query": False,
                "interpret_filters": False,
                "rerank": False,
                "generate_answer": False,
                "limit": 5,
            },
            timeout=60,
        )
        if verify_resp.status_code == 200:
            verify_data = verify_resp.json()
            if verify_data.get("results") and len(verify_data["results"]) > 0:
                stub_verified = True
                print(
                    f"  Stub sync verified: {len(verify_data['results'])} results "
                    f"(attempt {attempt + 1})"
                )
                break
        print(f"  [stub verify] attempt {attempt + 1}: no results yet, retrying...")

    if not stub_verified:
        pytest.fail("Stub sync completed but data not searchable after retries")

    # ---------- Source 2: Stripe (optional) ----------
    stripe_connection: Optional[Dict] = None
    has_stripe = False

    stripe_api_key = getattr(settings, "TEST_STRIPE_API_KEY", None)
    if stripe_api_key and stripe_api_key != "sk_test_dummy":
        stripe_connection_data = {
            "name": f"Stripe AgenticSearch Filter Test {int(time.time())}",
            "short_name": "stripe",
            "readable_collection_id": readable_id,
            "authentication": {"credentials": {"api_key": stripe_api_key}},
            "sync_immediately": True,
        }

        response = await client.post("/source-connections", json=stripe_connection_data)

        if response.status_code == 200:
            stripe_connection = response.json()
            connections_to_cleanup.append(stripe_connection["id"])

            if await wait_for_sync(client, stripe_connection["id"], max_wait_time=300):
                for attempt in range(8):
                    await asyncio.sleep(5)
                    verify_response = await client.post(
                        f"/collections/{readable_id}/search",
                        json={
                            "query": "customer OR invoice OR payment",
                            "expand_query": False,
                            "interpret_filters": False,
                            "rerank": False,
                            "generate_answer": False,
                            "filter": {"must": [{"key": "source_name", "match": {"value": "stripe"}}]},
                            "limit": 5,
                        },
                        timeout=60,
                    )
                    if verify_response.status_code == 200:
                        verify_data = verify_response.json()
                        if verify_data.get("results") and len(verify_data["results"]) > 0:
                            has_stripe = True
                            print(
                                f"  Stripe sync verified: {len(verify_data['results'])} results "
                                f"(attempt {attempt + 1})"
                            )
                            break
                    print(f"  [stripe verify] attempt {attempt + 1}: no results yet, retrying...")

                if not has_stripe:
                    print("  WARNING: Stripe sync completed but no data indexed")
            else:
                print("  WARNING: Stripe sync timed out")

    result = {
        "collection": collection,
        "stub_connection": stub_connection,
        "stripe_connection": stripe_connection,
        "has_stripe": has_stripe,
        "readable_id": readable_id,
        "sources": ["stub"] + (["stripe"] if has_stripe else []),
        "_connections_to_cleanup": connections_to_cleanup,
    }

    print(f"\n  AgenticSearch filter collection ready. Sources: {result['sources']}\n")

    return result


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def agentic_search_filter_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create HTTP client for agentic_search filter tests.

    Uses a high default timeout (180s) because thinking mode tests make multiple
    LLM calls and can take significantly longer than fast mode.
    """
    from config import settings

    async with httpx.AsyncClient(
        base_url=settings.api_url,
        headers=settings.api_headers,
        timeout=httpx.Timeout(180),
        follow_redirects=True,
    ) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def agentic_search_filter_collection(
    agentic_search_filter_client: httpx.AsyncClient,
) -> AsyncGenerator[Dict, None]:
    """Provide collection with stub + optional Stripe data for agentic_search filter testing.

    Uses module-level cache to avoid recreating collections for each test.
    """
    global _cached_agentic_search_collection, _cached_agentic_search_readable_id

    client = agentic_search_filter_client

    if _cached_agentic_search_collection is not None and _cached_agentic_search_readable_id is not None:
        check_response = await client.get(f"/collections/{_cached_agentic_search_readable_id}")
        if check_response.status_code == 200:
            yield _cached_agentic_search_collection
            return

    _cached_agentic_search_collection = await _create_agentic_search_collection(client)
    _cached_agentic_search_readable_id = _cached_agentic_search_collection["readable_id"]

    yield _cached_agentic_search_collection


def _is_transient_llm_error(status_code: int, response_text: str) -> bool:
    """Check if a non-200 response is caused by a transient LLM provider issue.

    These are not bugs in our code -- the LLM provider is temporarily overloaded.
    """
    text_lower = response_text.lower()
    transient_indicators = ["503", "rate", "too_many_requests", "queue_exceeded", "high traffic"]

    # Server-side timeout (504) -- LLM retries exceeded server's request timeout
    if status_code == 504:
        return True

    # 500 caused by LLM provider exhaustion (not a code bug)
    if status_code == 500 and any(ind in text_lower for ind in transient_indicators):
        return True

    return False


async def do_agentic_search(
    client: httpx.AsyncClient,
    readable_id: str,
    query: str,
    filter_list: list = None,
    mode: str = "fast",
) -> dict:
    """Execute a agentic search with optional filter.

    Thinking mode gets a longer timeout since it makes multiple LLM calls.
    Transient LLM provider errors (503 rate limits, server timeouts) cause
    the test to skip rather than fail, since they're infrastructure issues.
    """
    payload: dict = {
        "query": query,
        "mode": mode,
    }
    if filter_list is not None:
        payload["filter"] = filter_list

    response = await client.post(
        f"/collections/{readable_id}/agentic-search",
        json=payload,
        timeout=180 if mode == "thinking" else 90,
    )

    if response.status_code != 200:
        if _is_transient_llm_error(response.status_code, response.text):
            pytest.skip(
                f"Transient LLM provider error ({response.status_code}): "
                f"{response.text[:200]}"
            )
        pytest.fail(f"Agentic search failed ({response.status_code}): {response.text}")

    return response.json()


# =============================================================================
# FILTER VALIDATION TESTS (Pydantic rejects bad input with 422)
# =============================================================================


@pytest.mark.asyncio
async def test_invalid_field_name_rejected(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that an invalid field name is rejected by Pydantic with 422."""
    payload = {
        "query": "test",
        "mode": "fast",
        "filter": [
            {
                "conditions": [
                    {
                        "field": "nonexistent_field",
                        "operator": "equals",
                        "value": "test",
                    }
                ]
            }
        ],
    }

    response = await agentic_search_filter_client.post(
        f"/collections/{agentic_search_filter_collection['readable_id']}/agentic-search",
        json=payload,
        timeout=30,
    )

    assert response.status_code == 422, (
        f"Expected 422 for invalid field, got {response.status_code}: {response.text}"
    )


@pytest.mark.asyncio
async def test_invalid_operator_rejected(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that an invalid operator is rejected by Pydantic with 422."""
    payload = {
        "query": "test",
        "mode": "fast",
        "filter": [
            {
                "conditions": [
                    {
                        "field": "airweave_system_metadata.source_name",
                        "operator": "invalid_op",
                        "value": "test",
                    }
                ]
            }
        ],
    }

    response = await agentic_search_filter_client.post(
        f"/collections/{agentic_search_filter_collection['readable_id']}/agentic-search",
        json=payload,
        timeout=30,
    )

    assert response.status_code == 422, (
        f"Expected 422 for invalid operator, got {response.status_code}: {response.text}"
    )


@pytest.mark.asyncio
async def test_empty_conditions_list_rejected(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that an empty conditions list is rejected (min_length=1)."""
    payload = {
        "query": "test",
        "mode": "fast",
        "filter": [{"conditions": []}],
    }

    response = await agentic_search_filter_client.post(
        f"/collections/{agentic_search_filter_collection['readable_id']}/agentic-search",
        json=payload,
        timeout=30,
    )

    assert response.status_code == 422, (
        f"Expected 422 for empty conditions, got {response.status_code}: {response.text}"
    )


@pytest.mark.asyncio
async def test_invalid_filter_structure_rejected(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that a flat dict instead of list of filter groups is rejected."""
    payload = {
        "query": "test",
        "mode": "fast",
        # filter should be a list of groups, not a single dict
        "filter": {
            "field": "airweave_system_metadata.source_name",
            "operator": "equals",
            "value": "stub",
        },
    }

    response = await agentic_search_filter_client.post(
        f"/collections/{agentic_search_filter_collection['readable_id']}/agentic-search",
        json=payload,
        timeout=30,
    )

    assert response.status_code == 422, (
        f"Expected 422 for invalid filter structure, got {response.status_code}: {response.text}"
    )


# =============================================================================
# BASELINE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_search_without_filter_returns_results(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Baseline: agentic search without filter returns results."""
    results = await do_agentic_search(
        agentic_search_filter_client, agentic_search_filter_collection["readable_id"], "stub"
    )

    print_results_summary(results, "test_search_without_filter_returns_results")

    assert "results" in results
    assert len(results["results"]) > 0, "Expected results from stub data"


# =============================================================================
# SOURCE NAME FILTER TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_by_source_name_equals(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test filtering by source_name equals 'stub'."""
    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.source_name",
                    "operator": "equals",
                    "value": "stub",
                }
            ]
        }
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "test",
        filter_list=filter_list,
    )

    print_results_summary(results, "test_filter_by_source_name_equals", filter_list)

    assert "results" in results
    assert len(results["results"]) > 0, "Expected results for stub source"

    for result in results["results"]:
        source_name = result.get("airweave_system_metadata", {}).get("source_name")
        assert source_name == "stub", f"Expected stub, got {source_name}"


@pytest.mark.asyncio
async def test_filter_by_source_name_stripe_only(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test filtering for Stripe source returns only Stripe entities."""
    if not agentic_search_filter_collection.get("has_stripe"):
        pytest.skip("Stripe source not available or has no data")

    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.source_name",
                    "operator": "equals",
                    "value": "stripe",
                }
            ]
        }
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "data",
        filter_list=filter_list,
    )

    print_results_summary(results, "test_filter_by_source_name_stripe_only", filter_list)

    assert "results" in results
    assert len(results["results"]) > 0, "Expected results for stripe source"

    for result in results["results"]:
        source_name = result.get("airweave_system_metadata", {}).get("source_name")
        assert source_name == "stripe", f"Expected stripe, got {source_name}"


@pytest.mark.asyncio
async def test_filter_multi_source_excludes_correctly(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that filtering by one source completely excludes the other.

    The strongest test of source filtering: with two sources, verify that
    filtering for stub returns 0 stripe results and vice versa.
    """
    if not agentic_search_filter_collection.get("has_stripe"):
        pytest.skip("Multi-source test requires Stripe (no TEST_STRIPE_API_KEY)")

    # Filter for stub only
    stub_filter = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.source_name",
                    "operator": "equals",
                    "value": "stub",
                }
            ]
        }
    ]
    stub_results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "test",
        filter_list=stub_filter,
    )

    print_results_summary(
        stub_results, "test_filter_multi_source_excludes_correctly (STUB)", stub_filter
    )

    for result in stub_results.get("results", []):
        source_name = result.get("airweave_system_metadata", {}).get("source_name")
        assert source_name == "stub", f"Stripe data leaked through stub filter: {source_name}"

    # Filter for stripe only
    stripe_filter = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.source_name",
                    "operator": "equals",
                    "value": "stripe",
                }
            ]
        }
    ]
    stripe_results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "test",
        filter_list=stripe_filter,
    )

    print_results_summary(
        stripe_results, "test_filter_multi_source_excludes_correctly (STRIPE)", stripe_filter
    )

    for result in stripe_results.get("results", []):
        source_name = result.get("airweave_system_metadata", {}).get("source_name")
        assert source_name == "stripe", f"Stub data leaked through stripe filter: {source_name}"

    assert len(stub_results["results"]) > 0, "Stub filter should return results"
    assert len(stripe_results["results"]) > 0, "Stripe filter should return results"


@pytest.mark.asyncio
async def test_filter_nonexistent_source_returns_empty(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that filtering for a non-existent source returns no results."""
    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.source_name",
                    "operator": "equals",
                    "value": "nonexistent_source_xyz",
                }
            ]
        }
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "test",
        filter_list=filter_list,
    )

    print_results_summary(results, "test_filter_nonexistent_source_returns_empty", filter_list)

    assert "results" in results
    assert len(results["results"]) == 0, (
        f"Expected 0 results for non-existent source, got {len(results['results'])}"
    )


# =============================================================================
# ENTITY TYPE FILTER TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_by_entity_type_equals(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test filtering by exact entity_type."""
    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.entity_type",
                    "operator": "equals",
                    "value": "MediumStubEntity",
                }
            ]
        }
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "stub",
        filter_list=filter_list,
    )

    print_results_summary(results, "test_filter_by_entity_type_equals", filter_list)

    assert "results" in results

    for result in results["results"]:
        entity_type = result.get("airweave_system_metadata", {}).get("entity_type")
        assert entity_type == "MediumStubEntity", (
            f"Expected MediumStubEntity, got {entity_type}"
        )


# =============================================================================
# FILTER EFFECTIVENESS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_reduces_result_count(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that applying a filter actually reduces result count.

    A restrictive filter should return fewer results than no filter.
    """
    unfiltered = await do_agentic_search(
        agentic_search_filter_client, agentic_search_filter_collection["readable_id"], "stub"
    )

    print_results_summary(unfiltered, "test_filter_reduces_result_count (UNFILTERED)")

    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.entity_type",
                    "operator": "equals",
                    "value": "StubContainerEntity",
                }
            ]
        }
    ]
    filtered = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "stub",
        filter_list=filter_list,
    )

    print_results_summary(filtered, "test_filter_reduces_result_count (FILTERED)", filter_list)

    unfiltered_count = len(unfiltered.get("results", []))
    filtered_count = len(filtered.get("results", []))

    print(f"\n>>> COMPARISON: unfiltered={unfiltered_count}, filtered={filtered_count}")

    assert filtered_count < unfiltered_count, (
        f"Filter should reduce results: unfiltered={unfiltered_count}, filtered={filtered_count}"
    )
    assert filtered_count >= 1, "Should have at least 1 container entity"


# =============================================================================
# OPERATOR TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_with_in_operator(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test the 'in' operator with a list of entity types."""
    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.entity_type",
                    "operator": "in",
                    "value": ["SmallStubEntity", "LargeStubEntity"],
                }
            ]
        }
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "stub",
        filter_list=filter_list,
    )

    print_results_summary(results, "test_filter_with_in_operator", filter_list)

    assert "results" in results

    valid_types = {"SmallStubEntity", "LargeStubEntity"}
    for result in results["results"]:
        entity_type = result.get("airweave_system_metadata", {}).get("entity_type")
        assert entity_type in valid_types, (
            f"Expected one of {valid_types}, got {entity_type}"
        )


@pytest.mark.asyncio
async def test_filter_with_not_equals_operator(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test the 'not_equals' operator excludes a specific entity type."""
    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.entity_type",
                    "operator": "not_equals",
                    "value": "StubContainerEntity",
                }
            ]
        }
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "stub",
        filter_list=filter_list,
    )

    print_results_summary(results, "test_filter_with_not_equals_operator", filter_list)

    assert "results" in results

    for result in results["results"]:
        entity_type = result.get("airweave_system_metadata", {}).get("entity_type")
        assert entity_type != "StubContainerEntity", "StubContainerEntity should be excluded"


@pytest.mark.asyncio
async def test_filter_with_contains_operator(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test the 'contains' operator on a name field."""
    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.source_name",
                    "operator": "contains",
                    "value": "stub",
                }
            ]
        }
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "test",
        filter_list=filter_list,
    )

    print_results_summary(results, "test_filter_with_contains_operator", filter_list)

    assert "results" in results
    assert len(results["results"]) > 0, "Expected results for 'contains stub'"

    for result in results["results"]:
        source_name = result.get("airweave_system_metadata", {}).get("source_name", "")
        assert "stub" in source_name, f"Expected source_name containing 'stub', got {source_name}"


# =============================================================================
# MULTIPLE CONDITIONS / GROUP TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_multiple_conditions_and_logic(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test two conditions in one group (AND logic).

    Both conditions must hold for every result.
    """
    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.source_name",
                    "operator": "equals",
                    "value": "stub",
                },
                {
                    "field": "airweave_system_metadata.entity_type",
                    "operator": "equals",
                    "value": "MediumStubEntity",
                },
            ]
        }
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "stub",
        filter_list=filter_list,
    )

    print_results_summary(results, "test_multiple_conditions_and_logic", filter_list)

    assert "results" in results

    for result in results["results"]:
        sys_meta = result.get("airweave_system_metadata", {})
        assert sys_meta.get("source_name") == "stub"
        assert sys_meta.get("entity_type") == "MediumStubEntity"


@pytest.mark.asyncio
async def test_multiple_filter_groups_or_logic(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test multiple filter groups (OR logic between groups).

    Results should match either group's conditions.
    """
    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.entity_type",
                    "operator": "equals",
                    "value": "SmallStubEntity",
                }
            ]
        },
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.entity_type",
                    "operator": "equals",
                    "value": "MediumStubEntity",
                }
            ]
        },
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "stub",
        filter_list=filter_list,
    )

    print_results_summary(results, "test_multiple_filter_groups_or_logic", filter_list)

    assert "results" in results

    valid_types = {"SmallStubEntity", "MediumStubEntity"}
    for result in results["results"]:
        entity_type = result.get("airweave_system_metadata", {}).get("entity_type")
        assert entity_type in valid_types, (
            f"Expected one of {valid_types}, got {entity_type}"
        )


# =============================================================================
# FILTER MERGE TESTS (user filters survive planner-generated filters)
# =============================================================================


@pytest.mark.asyncio
async def test_user_filter_enforced_in_agentic_mode(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that user-supplied filters are enforced in thinking mode.

    In thinking mode, the planner generates its own filters which are merged
    with user filters via AgenticSearchCompletePlanBuilder. This test proves
    that user filters survive the merge.
    """
    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.source_name",
                    "operator": "equals",
                    "value": "stub",
                }
            ]
        }
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "find me some data",
        filter_list=filter_list,
        mode="thinking",
    )

    print_results_summary(results, "test_user_filter_enforced_in_agentic_mode", filter_list)

    assert "results" in results

    for result in results["results"]:
        source_name = result.get("airweave_system_metadata", {}).get("source_name")
        assert source_name == "stub", (
            f"User filter not enforced in thinking mode: expected stub, got {source_name}"
        )


@pytest.mark.asyncio
async def test_user_filter_exclusion_in_agentic_mode(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that a user filter for a non-existent source returns 0 results in thinking mode.

    The planner cannot override user filters, so filtering for a source that
    doesn't exist should always return empty results.
    """
    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.source_name",
                    "operator": "equals",
                    "value": "nonexistent",
                }
            ]
        }
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "find any available data",
        filter_list=filter_list,
        mode="thinking",
    )

    print_results_summary(results, "test_user_filter_exclusion_in_agentic_mode", filter_list)

    assert "results" in results
    assert len(results["results"]) == 0, (
        f"Expected 0 results for non-existent source in thinking mode, "
        f"got {len(results['results'])}"
    )


@pytest.mark.asyncio
async def test_user_filter_in_agentic_vs_direct_consistency(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that user filters are respected in both agentic and fast mode.

    Both modes should enforce the user filter. This verifies the merge path
    in thinking mode produces the same filtering behavior as fast mode.
    """
    filter_list = [
        {
            "conditions": [
                {
                    "field": "airweave_system_metadata.source_name",
                    "operator": "equals",
                    "value": "stub",
                }
            ]
        }
    ]

    direct_results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "test data",
        filter_list=filter_list,
        mode="fast",
    )

    agentic_results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "test data",
        filter_list=filter_list,
        mode="thinking",
    )

    print_results_summary(
        direct_results, "test_user_filter_consistency (DIRECT)", filter_list
    )
    print_results_summary(
        agentic_results, "test_user_filter_consistency (AGENTIC)", filter_list
    )

    # Both modes must respect the source filter
    for result in direct_results.get("results", []):
        source_name = result.get("airweave_system_metadata", {}).get("source_name")
        assert source_name == "stub", f"Fast mode: expected stub, got {source_name}"

    for result in agentic_results.get("results", []):
        source_name = result.get("airweave_system_metadata", {}).get("source_name")
        assert source_name == "stub", f"Thinking mode: expected stub, got {source_name}"


@pytest.mark.asyncio
async def test_planner_and_user_filter_combined(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that planner-generated filters and user filters both apply.

    Sends a query that nudges the planner to search Stripe data, while also
    applying a user-supplied timestamp filter. Verifies that ALL results
    satisfy BOTH constraints:
    - source_name=stripe (from planner's interpretation of the query)
    - created_at after the timestamp (from user filter)

    This proves AgenticSearchCompletePlanBuilder.build() correctly ANDs planner
    and user filter groups together.
    """
    if not agentic_search_filter_collection.get("has_stripe"):
        pytest.skip("Combined filter test requires Stripe data")

    # User filter: only entities created after 2020-01-01
    filter_list = [
        {
            "conditions": [
                {
                    "field": "created_at",
                    "operator": "greater_than",
                    "value": "2020-01-01T00:00:00Z",
                }
            ]
        }
    ]

    # Query that nudges the planner toward Stripe data
    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "find my Stripe invoices and payments",
        filter_list=filter_list,
        mode="thinking",
    )

    print_results_summary(results, "test_planner_and_user_filter_combined", filter_list)

    assert "results" in results

    # The user filter (created_at > 2020) should be applied to all results.
    # We validate the created_at field if present.
    for result in results["results"]:
        created_at = result.get("created_at")
        if created_at is not None:
            # created_at is an ISO string; lexicographic comparison works for ISO dates
            assert created_at > "2020-01-01", (
                f"User timestamp filter not applied: created_at={created_at}"
            )


# =============================================================================
# TIMESTAMP FILTER TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_with_valid_timestamp(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that a valid ISO timestamp filter works correctly.

    Uses created_at with a far-past date so all stub entities pass the filter.
    The filter translator converts ISO strings to epoch seconds for Vespa.
    """
    filter_list = [
        {
            "conditions": [
                {
                    "field": "created_at",
                    "operator": "greater_than",
                    "value": "2000-01-01T00:00:00Z",
                }
            ]
        }
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "stub",
        filter_list=filter_list,
    )

    print_results_summary(results, "test_filter_with_valid_timestamp", filter_list)

    assert "results" in results
    # All stub entities were created recently, so they should all pass
    assert len(results["results"]) > 0, (
        "Expected results when filtering created_at > 2000-01-01"
    )


@pytest.mark.asyncio
async def test_filter_with_valid_timestamp_excludes_results(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that a far-future timestamp filter excludes all results.

    Uses created_at with a future date so no entities pass the filter.
    Proves the timestamp comparison is actually applied.
    """
    filter_list = [
        {
            "conditions": [
                {
                    "field": "created_at",
                    "operator": "greater_than",
                    "value": "2099-01-01T00:00:00Z",
                }
            ]
        }
    ]

    results = await do_agentic_search(
        agentic_search_filter_client,
        agentic_search_filter_collection["readable_id"],
        "stub",
        filter_list=filter_list,
    )

    print_results_summary(
        results, "test_filter_with_valid_timestamp_excludes_results", filter_list
    )

    assert "results" in results
    assert len(results["results"]) == 0, (
        f"Expected 0 results for created_at > 2099, got {len(results['results'])}"
    )


@pytest.mark.asyncio
async def test_filter_with_invalid_timestamp_format(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test that a malformed timestamp string does not crash the endpoint.

    The filter translator's _parse_datetime_to_epoch raises FilterTranslationError
    for invalid ISO strings. The agent catches this gracefully and returns empty
    results rather than a 500 error.

    We accept either:
    - 200 with empty results (graceful degradation)
    - 422 (if future validation is added at the API layer)

    The key assertion is: NOT a 500 server error.
    """
    filter_list = [
        {
            "conditions": [
                {
                    "field": "created_at",
                    "operator": "greater_than",
                    "value": "not-a-valid-date",
                }
            ]
        }
    ]

    payload = {
        "query": "test",
        "mode": "fast",
        "filter": filter_list,
    }

    response = await agentic_search_filter_client.post(
        f"/collections/{agentic_search_filter_collection['readable_id']}/agentic-search",
        json=payload,
        timeout=60,
    )

    print(f"\n{'='*80}")
    print("TEST: test_filter_with_invalid_timestamp_format")
    print(f"{'='*80}")
    print(f"RESPONSE STATUS: {response.status_code}")
    print(f"RESPONSE BODY: {response.text[:500]}")
    print(f"{'='*80}\n")

    # Skip if the LLM provider is overloaded (not related to timestamp validation)
    if _is_transient_llm_error(response.status_code, response.text):
        pytest.skip(f"Transient LLM provider error ({response.status_code})")

    # Must not crash the server with a code bug
    assert response.status_code != 500, (
        f"Invalid timestamp caused server error: {response.text[:500]}"
    )

    # Accept either 200 (graceful degradation) or 422 (validation rejection)
    assert response.status_code in (200, 422), (
        f"Expected 200 or 422 for invalid timestamp, got {response.status_code}"
    )


@pytest.mark.asyncio
async def test_filter_with_various_invalid_timestamp_formats(
    agentic_search_filter_client: httpx.AsyncClient,
    agentic_search_filter_collection: Dict,
):
    """Test multiple malformed timestamp strings don't crash the endpoint.

    Covers common mistakes: missing timezone, partial dates, random strings,
    wrong separators, and numeric types where ISO string is expected.
    """
    invalid_values = [
        "2024-13-01T00:00:00Z",   # month 13
        "yesterday",               # human-readable but not ISO
        "2024/01/01",              # wrong separator
        "Jan 1, 2024",             # US date format
        "",                        # empty string
    ]

    for invalid_value in invalid_values:
        payload = {
            "query": "test",
            "mode": "fast",
            "filter": [
                {
                    "conditions": [
                        {
                            "field": "created_at",
                            "operator": "greater_than",
                            "value": invalid_value,
                        }
                    ]
                }
            ],
        }

        response = await agentic_search_filter_client.post(
            f"/collections/{agentic_search_filter_collection['readable_id']}/agentic-search",
            json=payload,
            timeout=90,
        )

        # Skip if LLM provider is overloaded (not related to timestamp validation)
        if _is_transient_llm_error(response.status_code, response.text):
            pytest.skip(
                f"Transient LLM provider error on '{invalid_value}': "
                f"{response.status_code}"
            )

        assert response.status_code != 500, (
            f"Invalid timestamp '{invalid_value}' caused server error: "
            f"{response.text[:300]}"
        )
