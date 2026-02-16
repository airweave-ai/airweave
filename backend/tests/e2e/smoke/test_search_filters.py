"""
E2E smoke tests for search filtering with Vespa.

Uses the stub source to generate deterministic data, then validates that
various filter types correctly filter search results.

This test suite fills the gap in E2E filter testing by:
1. Creating a collection with known stub data (deterministic via seed)
2. Optionally adding Stripe data for multi-source filtering tests
3. Waiting for sync to complete
4. Firing searches with various filters
5. Validating that results match filter criteria
"""

import asyncio
import atexit
import time
import pytest
import pytest_asyncio
import httpx
import json
from collections import Counter
from typing import AsyncGenerator, Dict, List, Optional


def _cleanup_cached_collection():
    """Cleanup cached collection on process exit.

    This runs when the pytest worker process exits, ensuring we don't leave
    orphaned collections in the test environment.
    """
    global _cached_filter_collection, _cached_collection_readable_id

    if _cached_filter_collection is None:
        return

    try:
        from config import settings

        # Use synchronous cleanup since we're in atexit
        import httpx as httpx_sync

        with httpx_sync.Client(
            base_url=settings.api_url,
            headers=settings.api_headers,
            timeout=30,
        ) as client:
            # Cleanup connections first
            for conn_id in _cached_filter_collection.get("_connections_to_cleanup", []):
                try:
                    client.delete(f"/source-connections/{conn_id}")
                except Exception:
                    pass

            # Cleanup collection
            if _cached_collection_readable_id:
                try:
                    client.delete(f"/collections/{_cached_collection_readable_id}")
                except Exception:
                    pass
    except Exception:
        pass  # Best effort cleanup


# Register cleanup handler
atexit.register(_cleanup_cached_collection)


def print_results_summary(results: dict, test_name: str, filter_dict: dict = None):
    """Print detailed summary of search results for debugging."""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")

    if filter_dict:
        print(f"\nFILTER APPLIED:")
        print(json.dumps(filter_dict, indent=2))
    else:
        print("\nNO FILTER APPLIED")

    result_list = results.get("results", [])
    print(f"\nTOTAL RESULTS (CHUNKS) RETURNED: {len(result_list)}")

    if not result_list:
        print("  (no results)")
        return

    # Count by entity_type
    entity_types = Counter()
    source_names = Counter()
    entity_ids = []

    for r in result_list:
        sys_meta = r.get("system_metadata", {})
        entity_types[sys_meta.get("entity_type", "UNKNOWN")] += 1
        source_names[sys_meta.get("source_name", "UNKNOWN")] += 1
        entity_ids.append(r.get("entity_id", "UNKNOWN"))

    print(f"\nCHUNKS BY ENTITY TYPE:")
    for et, count in sorted(entity_types.items()):
        print(f"  {et}: {count} chunks")

    print(f"\nCHUNKS BY SOURCE NAME:")
    for sn, count in sorted(source_names.items()):
        print(f"  {sn}: {count} chunks")

    # Show unique parent entities (before chunking)
    parent_entities = Counter()
    parent_to_type = {}
    for r in result_list:
        eid = r.get("entity_id", "UNKNOWN")
        parent = eid.split("__chunk_")[0] if "__chunk_" in eid else eid
        parent_entities[parent] += 1
        if parent not in parent_to_type:
            parent_to_type[parent] = r.get("system_metadata", {}).get("entity_type", "UNKNOWN")

    print(f"\nUNIQUE PARENT ENTITIES: {len(parent_entities)}")
    print(f"  (remember: search returns CHUNKS, each entity can have multiple chunks)")

    # Group parent entities by type
    type_to_parents = {}
    for parent, et in parent_to_type.items():
        if et not in type_to_parents:
            type_to_parents[et] = []
        type_to_parents[et].append((parent, parent_entities[parent]))

    print(f"\nPARENT ENTITIES BY TYPE (with chunk counts):")
    for et in sorted(type_to_parents.keys()):
        parents = type_to_parents[et]
        print(f"  {et}: {len(parents)} entities")
        for parent, chunk_count in parents:
            print(f"    - {parent}: {chunk_count} chunk(s)")

    print(f"\nFIRST 10 RESULTS (entity_id, entity_type, source_name, name):")
    for i, r in enumerate(result_list[:10]):
        sys_meta = r.get("system_metadata", {})
        print(f"  {i+1}. {r.get('entity_id')}")
        print(f"      type: {sys_meta.get('entity_type')}")
        print(f"      source: {sys_meta.get('source_name')}")
        print(f"      name: {r.get('name', 'N/A')[:50]}")

    if len(result_list) > 10:
        print(f"  ... and {len(result_list) - 10} more results")

    print(f"{'='*80}\n")


@pytest_asyncio.fixture(scope="function")
async def stub_filter_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create HTTP client for filter tests.

    Note: Using function scope to avoid event loop lifecycle issues with pytest-xdist.
    The httpx client must be closed before the event loop closes, which can be
    problematic with module-scoped fixtures and parallel test execution.
    """
    from config import settings

    async with httpx.AsyncClient(
        base_url=settings.api_url,
        headers=settings.api_headers,
        timeout=httpx.Timeout(60),
        follow_redirects=True,
    ) as client:
        yield client


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


# Module-level cache for collection data (per-worker in pytest-xdist)
# This avoids recreating collections for each test while using function-scoped fixtures
_cached_filter_collection: Optional[Dict] = None
_cached_collection_readable_id: Optional[str] = None


async def _create_filter_collection(client: httpx.AsyncClient) -> Dict:
    """Create a collection with stub + optional Stripe data for filter testing.

    - Stub source: seed=42, 20 entities (deterministic)
    - Stripe source: added if TEST_STRIPE_API_KEY is available

    Having two sources enables proper multi-source filtering tests.
    """
    from config import settings

    connections_to_cleanup: List[str] = []

    # Create collection
    collection_data = {"name": f"Filter Test Collection {int(time.time())}"}
    response = await client.post("/collections/", json=collection_data)

    if response.status_code != 200:
        pytest.fail(f"Failed to create collection: {response.text}")

    collection = response.json()
    readable_id = collection["readable_id"]

    # --------------------------------------------------------------------------
    # Source 1: Stub (always created)
    # --------------------------------------------------------------------------
    stub_connection_data = {
        "name": f"Stub Filter Test {int(time.time())}",
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

    # Verify stub data is actually searchable (not just sync status = active).
    # Under parallel test load, indexing can lag behind sync completion.
    stub_verified = False
    for attempt in range(12):  # up to ~55s (first 5 at 3s, rest at 5s)
        wait_secs = 3 if attempt < 5 else 5
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
                print(f"✓ Stub sync verified: {len(verify_data['results'])} chunks found (attempt {attempt + 1})")
                break
        print(f"  [stub verify] attempt {attempt + 1}: no results yet, retrying...")

    if not stub_verified:
        pytest.fail("Stub sync completed but data not searchable after retries")

    # --------------------------------------------------------------------------
    # Source 2: Stripe (optional - only if credentials available)
    # --------------------------------------------------------------------------
    stripe_connection: Optional[Dict] = None
    has_stripe = False

    stripe_api_key = getattr(settings, "TEST_STRIPE_API_KEY", None)
    if stripe_api_key and stripe_api_key != "sk_test_dummy":
        stripe_connection_data = {
            "name": f"Stripe Filter Test {int(time.time())}",
            "short_name": "stripe",
            "readable_collection_id": readable_id,
            "authentication": {"credentials": {"api_key": stripe_api_key}},
            "sync_immediately": True,
        }

        response = await client.post("/source-connections", json=stripe_connection_data)

        if response.status_code == 200:
            stripe_connection = response.json()
            connections_to_cleanup.append(stripe_connection["id"])

            # Wait for stripe sync
            if await wait_for_sync(client, stripe_connection["id"], max_wait_time=300):
                # Verify Stripe data is actually searchable (retry loop)
                for attempt in range(6):
                    await asyncio.sleep(5)
                    verify_response = await client.post(
                        f"/collections/{readable_id}/search",
                        json={
                            "query": "customer OR invoice OR payment OR product",
                            "expand_query": False,
                            "interpret_filters": False,
                            "rerank": False,
                            "generate_answer": False,
                            "filter": {"must": [{"key": "source_name", "match": {"value": "stripe"}}]},
                        },
                        timeout=60,
                    )
                    if verify_response.status_code == 200:
                        verify_data = verify_response.json()
                        if verify_data.get("results") and len(verify_data["results"]) > 0:
                            has_stripe = True
                            print(f"✓ Stripe sync verified: {len(verify_data['results'])} chunks found (attempt {attempt + 1})")
                            break
                    print(f"  [stripe verify] attempt {attempt + 1}: no results yet, retrying...")

                if not has_stripe:
                    print("⚠ Stripe sync completed but no data indexed (empty test account?)")
            else:
                # Stripe sync timed out, but we can still run stub-only tests
                print("⚠ Stripe sync timed out")

    result = {
        "collection": collection,
        "stub_connection": stub_connection,
        "stripe_connection": stripe_connection,
        "has_stripe": has_stripe,
        "readable_id": readable_id,
        "sources": ["stub"] + (["stripe"] if has_stripe else []),
        "_connections_to_cleanup": connections_to_cleanup,
    }

    # Print expected entity distribution for debugging
    print("\n" + "="*80)
    print("STUB SOURCE CONFIGURATION (seed=42, entity_count=20)")
    print("="*80)
    print("""
WEIGHTS (% of 20 entities):
  - small_entity_weight: 25%  -> ~5 SmallStubEntity
  - medium_entity_weight: 25% -> ~5 MediumStubEntity
  - large_entity_weight: 20%  -> ~4 LargeStubEntity
  - small_file_weight: 10%    -> ~2 SmallStubFileEntity (not always generated)
  - large_file_weight: 10%    -> ~2 LargeStubFileEntity
  - code_file_weight: 10%     -> ~2 CodeStubFileEntity
  + 1 StubContainerEntity (always created as parent)

IMPORTANT: Search returns CHUNKS, not entities!
  - Small entities: ~1 chunk each
  - Medium entities: ~2 chunks each
  - Large entities: ~2 chunks each
  - Large files: ~12 chunks (big text file)
  - Code files: ~1 chunk each

So total chunks ≈ 42 (not 20 entities!)
""")
    print(f"Sources available: {result['sources']}")
    print("="*80 + "\n")

    return result


@pytest_asyncio.fixture(scope="function")
async def stub_filter_collection(
    stub_filter_client: httpx.AsyncClient,
) -> AsyncGenerator[Dict, None]:
    """Provide collection with stub + optional Stripe data for filter testing.

    Uses a module-level cache to avoid recreating collections for each test,
    while maintaining function-scoped fixtures for proper event loop management
    with pytest-xdist.
    """
    global _cached_filter_collection, _cached_collection_readable_id

    client = stub_filter_client

    # Check if we have a cached collection that still exists
    if _cached_filter_collection is not None and _cached_collection_readable_id is not None:
        # Verify the collection still exists
        check_response = await client.get(f"/collections/{_cached_collection_readable_id}")
        if check_response.status_code == 200:
            # Collection still exists, reuse it
            yield _cached_filter_collection
            return

    # Create new collection and cache it
    _cached_filter_collection = await _create_filter_collection(client)
    _cached_collection_readable_id = _cached_filter_collection["readable_id"]

    yield _cached_filter_collection

    # Note: We don't cleanup here - let the last test or pytest session cleanup handle it
    # This allows the collection to be reused across tests in the same worker


async def do_search(
    client: httpx.AsyncClient,
    readable_id: str,
    query: str,
    filter_dict: dict = None,

) -> dict:
    """Execute a search with optional filter."""
    payload = {
        "query": query,
        "expand_query": False,
        "interpret_filters": False,
        "rerank": False,
        "generate_answer": False,
        "limit": 100,
    }
    if filter_dict:
        payload["filter"] = filter_dict

    response = await client.post(
        f"/collections/{readable_id}/search",
        json=payload,
        timeout=60,
    )

    if response.status_code != 200:
        pytest.fail(f"Search failed: {response.text}")

    return response.json()


# =============================================================================
# BASELINE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_search_without_filter_returns_results(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Baseline: search without filter returns results."""
    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub"
    )

    print_results_summary(results, "test_search_without_filter_returns_results")

    assert "results" in results
    assert len(results["results"]) > 0, "Expected results from stub data"


# =============================================================================
# ENTITY TYPE FILTER TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_by_entity_type_exact_match(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test filtering by exact entity_type."""
    filter_dict = {
        "must": [{"key": "entity_type", "match": {"value": "MediumStubEntity"}}]
    }

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub", filter_dict
    )

    print_results_summary(results, "test_filter_by_entity_type_exact_match", filter_dict)

    assert "results" in results

    for result in results["results"]:
        entity_type = result.get("system_metadata", {}).get("entity_type")
        assert entity_type == "MediumStubEntity", (
            f"Expected MediumStubEntity, got {entity_type}"
        )


@pytest.mark.asyncio
async def test_filter_by_entity_type_any(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test filtering by entity_type with 'any' (IN) operator.

    NOTE: The stub source creates 20 ENTITIES with these weights:
    - small_entity_weight: 25%  -> ~5 SmallStubEntity
    - medium_entity_weight: 25% -> ~5 MediumStubEntity
    - large_entity_weight: 20%  -> ~4 LargeStubEntity
    - small_file_weight: 10%    -> ~2 small files
    - large_file_weight: 10%    -> ~2 large files
    - code_file_weight: 10%     -> ~2 code files

    Each entity is CHUNKED, so large entities may produce multiple chunks.
    The search returns CHUNKS, not entities. So if we have:
    - 6 SmallStubEntity (1 chunk each) = 6 chunks
    - 4 LargeStubEntity (2 chunks each) = 8 chunks
    Total = 14 chunks (not 50!)
    """
    filter_dict = {
        "must": [
            {"key": "entity_type", "match": {"any": ["SmallStubEntity", "LargeStubEntity"]}}
        ]
    }

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub", filter_dict
    )

    print_results_summary(results, "test_filter_by_entity_type_any", filter_dict)

    assert "results" in results

    valid_types = {"SmallStubEntity", "LargeStubEntity"}
    for result in results["results"]:
        entity_type = result.get("system_metadata", {}).get("entity_type")
        assert entity_type in valid_types, (
            f"Expected one of {valid_types}, got {entity_type}"
        )


@pytest.mark.asyncio
async def test_filter_by_source_name_nonexistent_returns_empty(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test filtering by source_name that doesn't exist returns no results.

    Filtering for a non-existent source should return 0 results. This proves
    the filter is actually being applied (not just returning everything).
    """
    filter_dict = {"must": [{"key": "source_name", "match": {"value": "slack"}}]}

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "test", filter_dict
    )

    print_results_summary(results, "test_filter_by_source_name_nonexistent_returns_empty", filter_dict)

    assert "results" in results
    assert len(results["results"]) == 0, (
        f"Expected 0 results for non-existent source, got {len(results['results'])}"
    )


@pytest.mark.asyncio
async def test_filter_by_source_name_stub_only(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test filtering for stub source returns only stub entities."""
    filter_dict = {"must": [{"key": "source_name", "match": {"value": "stub"}}]}

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "test", filter_dict
    )

    print_results_summary(results, "test_filter_by_source_name_stub_only", filter_dict)

    assert "results" in results
    assert len(results["results"]) > 0, "Expected results for stub source"

    for result in results["results"]:
        source_name = result.get("system_metadata", {}).get("source_name")
        assert source_name == "stub", f"Expected stub, got {source_name}"


@pytest.mark.asyncio
async def test_filter_by_source_name_any(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test filtering by source_name with 'any' (IN) operator.

    This mirrors production filter format:
    {"must": [{"key": "source_name", "match": {"any": ["github"]}}]}

    Using stub source for testing since it's always available.
    """
    filter_dict = {"must": [{"key": "source_name", "match": {"any": ["stub"]}}]}

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "test", filter_dict
    )

    print_results_summary(results, "test_filter_by_source_name_any", filter_dict)

    assert "results" in results
    assert len(results["results"]) > 0, "Expected results for stub source with match.any"

    for result in results["results"]:
        source_name = result.get("system_metadata", {}).get("source_name")
        assert source_name == "stub", f"Expected stub, got {source_name}"


@pytest.mark.asyncio
async def test_filter_by_source_name_stripe_only(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test filtering for stripe source returns only stripe entities.

    This test only runs if Stripe credentials are available AND Stripe has indexed data.
    The fixture verifies data exists before setting has_stripe=True.
    """
    if not stub_filter_collection.get("has_stripe"):
        pytest.skip("Stripe source not available or has no data")

    filter_dict = {"must": [{"key": "source_name", "match": {"value": "stripe"}}]}

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "data", filter_dict
    )

    print_results_summary(results, "test_filter_by_source_name_stripe_only", filter_dict)

    assert "results" in results
    assert len(results["results"]) > 0, "Expected results for stripe source (has_stripe=True)"

    for result in results["results"]:
        source_name = result.get("system_metadata", {}).get("source_name")
        assert source_name == "stripe", f"Expected stripe, got {source_name}"


@pytest.mark.asyncio
async def test_filter_multi_source_excludes_correctly(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test that filtering by one source excludes the other source's data.

    This is the strongest test of source filtering - with two sources,
    we verify that filtering for stub returns 0 stripe results and vice versa.
    """
    if not stub_filter_collection.get("has_stripe"):
        pytest.skip("Multi-source test requires Stripe (no TEST_STRIPE_API_KEY)")

    # First, get unfiltered count to verify we have data from both sources
    unfiltered = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "test"
    )

    print_results_summary(unfiltered, "test_filter_multi_source_excludes_correctly (UNFILTERED)")

    # Check we have both sources in unfiltered results
    sources_found = set()
    for result in unfiltered.get("results", []):
        sources_found.add(result.get("system_metadata", {}).get("source_name"))

    if not {"stub", "stripe"}.issubset(sources_found):
        pytest.skip(f"Need both stub and stripe data, found: {sources_found}")

    # Now filter for stub only
    stub_filter = {"must": [{"key": "source_name", "match": {"value": "stub"}}]}
    stub_results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "test", stub_filter
    )

    print_results_summary(stub_results, "test_filter_multi_source_excludes_correctly (STUB FILTER)", stub_filter)

    # Verify NO stripe results in stub-filtered results
    for result in stub_results.get("results", []):
        source_name = result.get("system_metadata", {}).get("source_name")
        assert source_name == "stub", f"Stripe data leaked through stub filter: {source_name}"

    # Now filter for stripe only
    stripe_filter = {"must": [{"key": "source_name", "match": {"value": "stripe"}}]}
    stripe_results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "test", stripe_filter
    )

    print_results_summary(stripe_results, "test_filter_multi_source_excludes_correctly (STRIPE FILTER)", stripe_filter)

    # Verify NO stub results in stripe-filtered results
    for result in stripe_results.get("results", []):
        source_name = result.get("system_metadata", {}).get("source_name")
        assert source_name == "stripe", f"Stub data leaked through stripe filter: {source_name}"

    # Verify we actually got results from both filtered searches
    # (the important filter assertions above already verified correctness)
    assert len(stub_results["results"]) > 0, "Stub filter should return some results"
    assert len(stripe_results["results"]) > 0, "Stripe filter should return some results"

    # With 42 stub chunks and limit=100, stub filter should return all 42
    # This verifies the filter is actually restricting results, not just returning everything
    assert len(stub_results["results"]) <= 42, (
        f"Stub filter returned {len(stub_results['results'])} results, expected <=42 stub chunks"
    )


# =============================================================================
# MUST NOT (EXCLUSION) TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_must_not_excludes_entity_type(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test must_not excludes specified entity types."""
    filter_dict = {
        "must_not": [{"key": "entity_type", "match": {"value": "StubContainerEntity"}}]
    }

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub", filter_dict
    )

    print_results_summary(results, "test_filter_must_not_excludes_entity_type", filter_dict)

    assert "results" in results

    for result in results["results"]:
        entity_type = result.get("system_metadata", {}).get("entity_type")
        assert entity_type != "StubContainerEntity", "StubContainerEntity should be excluded"


@pytest.mark.asyncio
async def test_filter_match_except(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test match.except excludes multiple values."""
    filter_dict = {
        "must": [
            {
                "key": "entity_type",
                "match": {"except": ["StubContainerEntity", "CodeStubFileEntity"]},
            }
        ]
    }

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub", filter_dict
    )

    print_results_summary(results, "test_filter_match_except", filter_dict)

    assert "results" in results

    excluded_types = {"StubContainerEntity", "CodeStubFileEntity"}
    for result in results["results"]:
        entity_type = result.get("system_metadata", {}).get("entity_type")
        assert entity_type not in excluded_types, f"{entity_type} should be excluded"


# =============================================================================
# SHOULD (OR) TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_should_or_logic(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test should clause provides OR logic."""
    filter_dict = {
        "should": [
            {"key": "entity_type", "match": {"value": "SmallStubEntity"}},
            {"key": "entity_type", "match": {"value": "MediumStubEntity"}},
        ]
    }

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub", filter_dict
    )

    print_results_summary(results, "test_filter_should_or_logic", filter_dict)

    assert "results" in results

    valid_types = {"SmallStubEntity", "MediumStubEntity"}
    for result in results["results"]:
        entity_type = result.get("system_metadata", {}).get("entity_type")
        assert entity_type in valid_types, f"Expected one of {valid_types}, got {entity_type}"


# =============================================================================
# COMBINED FILTER TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_combined_must_and_must_not(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test combining must and must_not."""
    filter_dict = {
        "must": [{"key": "source_name", "match": {"value": "stub"}}],
        "must_not": [{"key": "entity_type", "match": {"value": "StubContainerEntity"}}],
    }

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "test", filter_dict
    )

    print_results_summary(results, "test_filter_combined_must_and_must_not", filter_dict)

    assert "results" in results

    for result in results["results"]:
        source_name = result.get("system_metadata", {}).get("source_name")
        entity_type = result.get("system_metadata", {}).get("entity_type")
        assert source_name == "stub"
        assert entity_type != "StubContainerEntity"


# =============================================================================
# HAS_ID FILTER TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_has_id_single(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test has_id filter with a known entity ID."""
    # First get results to find a valid entity_id
    all_results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub"
    )

    print_results_summary(all_results, "test_filter_has_id_single (ALL RESULTS)")

    if not all_results.get("results"):
        pytest.skip("No results to test has_id filter")

    target_id = all_results["results"][0]["entity_id"]
    print(f"\nTARGET ID: {target_id}")

    # Search with has_id filter
    filter_dict = {"must": [{"has_id": [target_id]}]}

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub", filter_dict
    )

    print_results_summary(results, "test_filter_has_id_single (FILTERED)", filter_dict)

    assert "results" in results
    assert len(results["results"]) >= 1

    # All results should match (accounting for chunking)
    for result in results["results"]:
        result_id = result["entity_id"]
        base_id = result_id.split("__chunk_")[0] if "__chunk_" in result_id else result_id
        target_base = target_id.split("__chunk_")[0] if "__chunk_" in target_id else target_id
        assert base_id == target_base


@pytest.mark.asyncio
async def test_filter_has_id_multiple(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test has_id filter with multiple entity IDs."""
    all_results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub"
    )

    print_results_summary(all_results, "test_filter_has_id_multiple (ALL RESULTS)")

    if len(all_results.get("results", [])) < 3:
        pytest.skip("Not enough results for multiple has_id test")

    target_ids = [r["entity_id"] for r in all_results["results"][:3]]
    print(f"\nTARGET IDS: {target_ids}")

    filter_dict = {"must": [{"has_id": target_ids}]}

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub", filter_dict
    )

    print_results_summary(results, "test_filter_has_id_multiple (FILTERED)", filter_dict)

    assert "results" in results

    target_base_ids = {
        tid.split("__chunk_")[0] if "__chunk_" in tid else tid for tid in target_ids
    }

    for result in results["results"]:
        result_id = result["entity_id"]
        base_id = result_id.split("__chunk_")[0] if "__chunk_" in result_id else result_id
        assert base_id in target_base_ids


# =============================================================================
# FILTER EFFECTIVENESS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_reduces_result_count(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test that applying a filter actually reduces result count.

    Critical validation that filters work - a restrictive filter should
    return fewer results than no filter.
    """
    # Search without filter
    unfiltered = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub"
    )

    print_results_summary(unfiltered, "test_filter_reduces_result_count (UNFILTERED)")

    # Search with filter for only container entities
    filter_dict = {
        "must": [{"key": "entity_type", "match": {"value": "StubContainerEntity"}}]
    }
    filtered = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub", filter_dict
    )

    print_results_summary(filtered, "test_filter_reduces_result_count (FILTERED)", filter_dict)

    unfiltered_count = len(unfiltered.get("results", []))
    filtered_count = len(filtered.get("results", []))

    print(f"\n>>> COMPARISON: unfiltered={unfiltered_count}, filtered={filtered_count}")

    assert filtered_count < unfiltered_count, (
        f"Filter should reduce results: unfiltered={unfiltered_count}, filtered={filtered_count}"
    )
    assert filtered_count >= 1, "Should have at least 1 container entity"


@pytest.mark.asyncio
async def test_filter_impossible_condition_returns_no_results(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test that an impossible filter condition returns no results.

    Validates filters actually work and don't just return all results.
    """
    filter_dict = {
        "must": [{"key": "source_name", "match": {"value": "nonexistent_source_xyz"}}]
    }

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "test", filter_dict
    )

    print_results_summary(results, "test_filter_impossible_condition_returns_no_results", filter_dict)

    assert "results" in results
    assert len(results["results"]) == 0, (
        f"Expected 0 results for impossible filter, got {len(results['results'])}"
    )


# =============================================================================
# COMPLEX NESTED FILTER TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_nested_boolean_logic(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test complex nested boolean filter logic."""
    filter_dict = {
        "must": [
            {
                "should": [
                    {"key": "entity_type", "match": {"value": "SmallStubEntity"}},
                    {"key": "entity_type", "match": {"value": "MediumStubEntity"}},
                ]
            }
        ],
        "must_not": [{"key": "entity_type", "match": {"value": "StubContainerEntity"}}],
    }

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub", filter_dict
    )

    print_results_summary(results, "test_filter_nested_boolean_logic", filter_dict)

    assert "results" in results

    valid_types = {"SmallStubEntity", "MediumStubEntity"}
    for result in results["results"]:
        entity_type = result.get("system_metadata", {}).get("entity_type")
        assert entity_type in valid_types
        assert entity_type != "StubContainerEntity"


# =============================================================================
# EDGE CASES
# =============================================================================


@pytest.mark.asyncio
async def test_filter_empty_must_array(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test that empty must array doesn't break search."""
    filter_dict = {"must": []}

    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "stub", filter_dict
    )

    print_results_summary(results, "test_filter_empty_must_array", filter_dict)

    assert "results" in results
    assert len(results["results"]) > 0


@pytest.mark.asyncio
async def test_filter_special_characters_in_value(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test filter with special characters that need escaping."""
    filter_dict = {
        "must": [{"key": "entity_type", "match": {"value": 'Test "quoted" value'}}]
    }

    # Should not crash
    results = await do_search(
        stub_filter_client, stub_filter_collection["readable_id"], "test", filter_dict
    )

    print_results_summary(results, "test_filter_special_characters_in_value", filter_dict)

    assert "results" in results
    assert len(results["results"]) == 0  # No such entity type exists


# =============================================================================
# INVALID FILTER FORMAT TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filter_bare_field_condition_returns_error(
    stub_filter_client: httpx.AsyncClient,
    stub_filter_collection: Dict,
):
    """Test that a bare FieldCondition (without must/should/must_not) returns an error.

    This format is NOT valid according to Qdrant filter spec:
    { "key": "source_name", "match": { "value": "stub" } }

    The correct format is:
    { "must": [{ "key": "source_name", "match": { "value": "stub" } }] }
    """
    # Invalid bare FieldCondition format
    invalid_filter = {"key": "source_name", "match": {"value": "stub"}}

    payload = {
        "query": "test",
        "expand_query": False,
        "interpret_filters": False,
        "rerank": False,
        "generate_answer": False,
        "limit": 100,
        "filter": invalid_filter,
    }

    response = await stub_filter_client.post(
        f"/collections/{stub_filter_collection['readable_id']}/search",
        json=payload,
        timeout=60,
    )

    print(f"\n{'='*80}")
    print("TEST: test_filter_bare_field_condition_returns_error")
    print(f"{'='*80}")
    print(f"INVALID FILTER SENT: {invalid_filter}")
    print(f"RESPONSE STATUS: {response.status_code}")
    print(f"RESPONSE BODY: {response.text[:500]}")
    print(f"{'='*80}\n")

    # Should return 422 Unprocessable Entity for invalid filter structure
    assert response.status_code == 422, (
        f"Expected 422 Unprocessable Entity for invalid filter, got {response.status_code}. "
        f"Response: {response.text[:500]}"
    )

    # Check that error message mentions the issue
    response_text = response.text.lower()
    assert "filter" in response_text and "must" in response_text, (
        f"Expected error message to mention filter format and 'must' wrapper: {response.text}"
    )
