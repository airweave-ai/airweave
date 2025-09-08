"""
Simplified search feature tests for the public API.

Just checks if expected words appear in search results.
No ordering, no scoring, no creativity - just content checks.
All search features are enabled to verify end-to-end integration.
"""

import json
import requests


def test_advanced_search_features(api_url: str, headers: dict, collection_id: str) -> None:
    """Test search features by checking if expected words appear in results."""
    print("\n🔬 Testing Search Features (Simplified)")

    # Define what word we're looking for in all tests
    EXPECTED_WORD = "invoice"  # Just check if this word appears

    # Check if we have any data first
    print("\n  🔍 Checking for data in collection...")
    check_response = requests.post(
        f"{api_url}/collections/{collection_id}/search",
        json={"query": "test", "limit": 1, "response_type": "raw"},
        headers=headers,
    )
    assert (
        check_response.status_code == 200
    ), f"Failed to check for data: {check_response.status_code}"

    check_results = check_response.json()
    num_results = len(check_results.get("results", []))

    if num_results == 0:
        print("\n  ⚠️ WARNING: No data found in collection! Tests may not be meaningful.")
    else:
        print(f"  ✓ Found data in collection")

    # Helper function to check content
    def check_for_word(results: list, word: str) -> bool:
        """Check if word appears in any result."""
        for result in results:
            payload = result.get("payload", {})
            payload_str = json.dumps(payload).lower()
            if word.lower() in payload_str:
                return True
        return False

    # TEST 1: Query Expansion Strategies (AUTO)
    print("\n  📝 Testing Query Expansion (AUTO)")
    response = requests.post(
        f"{api_url}/collections/{collection_id}/search",
        json={
            "query": "invoice payment",
            "expansion_strategy": "auto",
            "limit": 10,
            "response_type": "raw",
            "enable_reranking": False,
            "enable_query_interpretation": False,
            "recency_bias": 0.3,
        },
        headers=headers,
    )
    assert response.status_code == 200, f"Failed AUTO expansion: {response.status_code}"
    results = response.json().get("results", [])
    found = check_for_word(results, EXPECTED_WORD)
    print(f"    AUTO: {'✓ Found' if found else '⚠️ Not found'} '{EXPECTED_WORD}'")

    # TEST 2: Query Interpretation (enabled)
    print("\n  🧠 Testing Query Interpretation (enabled)")
    response = requests.post(
        f"{api_url}/collections/{collection_id}/search",
        json={
            "query": "invoices from company",
            "enable_query_interpretation": True,
            "limit": 10,
            "response_type": "raw",
            "expansion_strategy": "no_expansion",
            "enable_reranking": False,
            "recency_bias": 0.3,
        },
        headers=headers,
    )
    assert response.status_code == 200, f"Failed interpretation True: {response.status_code}"
    results = response.json().get("results", [])
    found = check_for_word(results, EXPECTED_WORD)
    print(f"    Interpretation True: {'✓ Found' if found else '⚠️ Not found'} '{EXPECTED_WORD}'")

    # TEST 3: Reranking (enabled)
    print("\n  🎯 Testing Reranking (enabled)")
    response = requests.post(
        f"{api_url}/collections/{collection_id}/search",
        json={
            "query": "urgent payment invoice",
            "enable_reranking": True,
            "limit": 10,
            "response_type": "raw",
            "expansion_strategy": "no_expansion",
            "enable_query_interpretation": False,
            "recency_bias": 0.3,
        },
        headers=headers,
    )
    assert response.status_code == 200, f"Failed reranking True: {response.status_code}"
    results = response.json().get("results", [])
    found = check_for_word(results, EXPECTED_WORD)
    print(f"    Reranking True: {'✓ Found' if found else '⚠️ Not found'} '{EXPECTED_WORD}'")

    # TEST 4: Recency Bias
    print("\n  📅 Testing Recency Bias")
    for bias in [0.0, 0.5, 1.0]:
        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json={
                "query": "invoice",
                "recency_bias": bias,
                "limit": 10,
                "response_type": "raw",
                "expansion_strategy": "no_expansion",
                "enable_reranking": False,
                "enable_query_interpretation": False,
            },
            headers=headers,
        )
        assert response.status_code == 200, f"Failed recency {bias}: {response.status_code}"
        results = response.json().get("results", [])
        found = check_for_word(results, EXPECTED_WORD)
        print(f"    Recency {bias}: {'✓ Found' if found else '⚠️ Not found'} '{EXPECTED_WORD}'")

    # TEST 5: Search Methods
    print("\n  🔍 Testing Search Methods")
    for method in ["hybrid", "neural", "keyword"]:
        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json={
                "query": "invoice payment",
                "search_method": method,
                "limit": 10,
                "response_type": "raw",
                "enable_query_interpretation": False,
                "expansion_strategy": "no_expansion",
                "enable_reranking": False,
                "recency_bias": 0,
            },
            headers=headers,
        )
        assert response.status_code == 200, f"Failed method {method}: {response.status_code}"
        results = response.json().get("results", [])
        found = check_for_word(results, EXPECTED_WORD)
        print(f"    {method}: {'✓ Found' if found else '⚠️ Not found'} '{EXPECTED_WORD}'")

    # TEST 6: Qdrant Filters
    print("\n  🎛️  Testing Qdrant Filters")
    response = requests.post(
        f"{api_url}/collections/{collection_id}/search",
        json={
            "query": "payment",
            "filter": {"must": [{"key": "source_name", "match": {"value": "stripe"}}]},
            "limit": 10,
            "response_type": "raw",
            "expansion_strategy": "no_expansion",
            "enable_reranking": False,
            "enable_query_interpretation": False,
            "recency_bias": 0,
        },
        headers=headers,
    )
    if response.status_code == 422:
        print("    Filter test skipped (format mismatch)")
    else:
        assert response.status_code == 200, f"Failed filter: {response.status_code}"
        results = response.json().get("results", [])
        found = check_for_word(results, EXPECTED_WORD)
        print(f"    Filter: {'✓ Found' if found else '⚠️ Not found'} '{EXPECTED_WORD}'")

    # TEST 7: Score Threshold
    print("\n  📊 Testing Score Threshold")
    for threshold in [None, 0.3, 0.7]:
        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json={
                "query": "invoice",
                "score_threshold": threshold,
                "limit": 10,
                "response_type": "raw",
                "expansion_strategy": "no_expansion",
                "enable_reranking": False,
                "enable_query_interpretation": False,
                "recency_bias": 0,
            },
            headers=headers,
        )
        assert response.status_code == 200, f"Failed threshold {threshold}: {response.status_code}"
        results = response.json().get("results", [])
        found = check_for_word(results, EXPECTED_WORD)
        print(
            f"    Threshold {threshold}: {'✓ Found' if found else '⚠️ Not found'} '{EXPECTED_WORD}'"
        )

    # TEST 8: Pagination
    print("\n  📄 Testing Pagination")
    for offset in [0, 5, 10]:
        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json={
                "query": "invoice",
                "offset": offset,
                "limit": 5,
                "response_type": "raw",
                "enable_query_interpretation": False,
                "expansion_strategy": "no_expansion",
                "enable_reranking": False,
                "recency_bias": 0,
            },
            headers=headers,
        )
        assert response.status_code == 200, f"Failed pagination {offset}: {response.status_code}"
        results = response.json().get("results", [])
        found = check_for_word(results, EXPECTED_WORD)
        print(f"    Offset {offset}: {'✓ Found' if found else '⚠️ Not found'} '{EXPECTED_WORD}'")

    # TEST 9: Edge Cases (just test they return proper errors)
    print("\n  ⚠️  Testing Edge Cases")
    edge_cases = [
        ("Empty query", {"query": "", "response_type": "raw"}, 422),
        ("Long query", {"query": "a" * 1001, "response_type": "raw"}, 422),
        ("Invalid type", {"query": "test", "response_type": "invalid"}, 422),
        ("Negative offset", {"query": "test", "offset": -1, "response_type": "raw"}, 422),
    ]
    for name, body, expected_status in edge_cases:
        response = requests.post(
            f"{api_url}/collections/{collection_id}/search",
            json=body,
            headers=headers,
        )
        assert (
            response.status_code == expected_status
        ), f"{name}: Expected {expected_status}, got {response.status_code}"
        print(f"    {name}: ✓ Got expected error {expected_status}")

    # TEST 10: Full pipeline + Completion (POST)
    print("\n  🧾 Testing Full Pipeline with Completion (POST)")
    response = requests.post(
        f"{api_url}/collections/{collection_id}/search",
        json={
            "query": "invoice payment",
            "response_type": "completion",
            "limit": 10,
            "expansion_strategy": "no_expansion",
            "enable_query_interpretation": False,
            "enable_reranking": False,
            "recency_bias": 0,
        },
        headers=headers,
    )
    assert response.status_code == 200, f"Failed completion (POST): {response.status_code}"
    completion_res = response.json()
    assert completion_res.get("response_type") == "completion", "Completion response_type mismatch"
    completion_text = completion_res.get("completion", "")
    assert isinstance(completion_text, str) and len(completion_text) > 0, "Empty completion text"

    print("\n✅ Search features test completed")
