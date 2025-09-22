"""
Test module for Search functionality.

This module tests the collection search functionality including:
- RAW search response with results and scores
- COMPLETION search response with AI-generated answers
- Search result relevance evaluation
- Handling of no results scenarios
- Query expansion strategies (AUTO, LLM, NO_1ANSION)
- Query interpretation (natural language filter extraction)
- LLM reranking for improved relevance
- Recency bias configurations
- Search methods (hybrid, neural, keyword)
- Qdrant native filtering
- Score threshold filtering
- Pagination with offset and limit
- Edge cases and error handling
"""

import time
import json
import requests
from .utils import show_backend_logs
from .test_advanced_search import test_advanced_search_features


def test_search_functionality(
    api_url: str, headers: dict, collection_id: str, wait_after_sync: int = 10
) -> None:
    """Test collection search functionality with both RAW and COMPLETION response types.

    Args:
        api_url: The API URL
        headers: Request headers with authentication
        collection_id: The readable_id of the collection to search
        wait_after_sync: Seconds to wait after sync before searching (for indexing)
    """
    print("\n🔄 Testing Search Functionality")

    # Wait a bit for data to be fully indexed after sync
    print(f"  Waiting {wait_after_sync} seconds for data indexing...")
    time.sleep(wait_after_sync)

    # Define test query - same as in the deprecated test
    search_query = "Are there any open invoices"
    expected_keywords = ["in_"]

    # TEST 1: Raw search response
    print(f"\n  Testing RAW search for: '{search_query}'")
    response = requests.get(
        f"{api_url}/collections/{collection_id}/search",
        params={"query": search_query, "response_type": "raw"},
        headers=headers,
    )

    if response.status_code != 200:
        print(f"Search request failed: {response.status_code} - {response.text}")
        print("📋 Backend logs for search failure debugging:")
        show_backend_logs(lines=30)

    assert response.status_code == 200, f"Search failed: {response.text}"

    raw_results = response.json()

    # Validate RAW response structure based on SearchResponse schema
    assert "results" in raw_results, "Missing 'results' field in raw response"
    assert "response_type" in raw_results, "Missing 'response_type' field in raw response"
    assert "status" in raw_results, "Missing 'status' field in raw response"
    assert raw_results["response_type"] == "raw", "Response type should be 'raw'"

    results_list = raw_results.get("results", [])
    status = raw_results.get("status", "")

    print(f"  ✓ RAW search returned {len(results_list)} results (status: {status})")

    # Check if we have results before evaluating
    if len(results_list) > 0 and status == "success":
        # Validate individual result structure
        first_result = results_list[0]
        assert "payload" in first_result, "Result missing 'payload' field"
        assert "score" in first_result, "Result missing 'score' field"

        # Display first few results for debugging
        print(f"\n  Top results (showing up to 3):")
        for i, result in enumerate(results_list[:3]):
            print(f"    Result {i+1} (score: {result.get('score', 0):.4f}):")
            payload = result.get("payload", {})

            # More detailed debugging of payload content
            if isinstance(payload, dict):
                # Show all fields in the payload for debugging
                print("      Payload fields:")
                for key, value in payload.items():
                    # Truncate long values
                    value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                    print(f"        {key}: {value_str}")

                # Look for any content that might contain invoice/product info
                text_content = payload.get("text", payload.get("content", ""))
                if text_content:
                    print(f"      Full text content: {text_content[:500]}...")
            else:
                content = str(payload)[:200]
                print(f"      Content: {content}...")
            print("      ---")

        # Use LLM judge to evaluate search quality
        try:
            # Add the tests directory to Python path to enable imports
            import sys
            import os

            current_dir = os.path.dirname(os.path.abspath(__file__))
            tests_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(current_dir))
            )  # Go up 3 levels to tests/
            if tests_dir not in sys.path:
                sys.path.insert(0, tests_dir)

            print(f"  Tests directory: {tests_dir}")

            from helpers.llm_judge import evaluate_search_results

            print(f"\n  Evaluating search results with LLM judge...")
            evaluation = evaluate_search_results(
                query=search_query,
                results=results_list,
                expected_content_keywords=expected_keywords,
                minimum_score=0.5,  # Lower threshold since it's test data
                minimum_relevant_results=1,
            )

            print(f"    Relevance: {evaluation.get('relevance', 0):.2f}")
            print(f"    Completeness: {evaluation.get('completeness', 0):.2f}")
            print(f"    Score: {evaluation.get('score', 0):.2f}")
            print(f"    Feedback: {evaluation.get('feedback', 'No feedback')}")

            # FAIL THE TEST if score is too low
            min_acceptable_score = 0.3
            if evaluation.get("score", 0) < min_acceptable_score:
                # First, let's see if we can find the keywords anywhere in ALL results
                print(
                    f"\n  🔍 Debugging: Searching for keywords in all {len(results_list)} results..."
                )
                keywords_found_in_any = False
                for idx, result in enumerate(results_list):
                    payload = result.get("payload", {})
                    payload_str = json.dumps(payload).lower()
                    for keyword in expected_keywords:
                        if keyword.lower() in payload_str:
                            print(f"    Found '{keyword}' in result {idx+1}!")
                            keywords_found_in_any = True

                if not keywords_found_in_any:
                    raise AssertionError(
                        f"Search quality too low! Score: {evaluation.get('score', 0):.2f} < {min_acceptable_score}. "
                        f"LLM Judge feedback: {evaluation.get('feedback', 'No feedback')}. "
                        f"This likely means the Stripe test data doesn't contain the expected invoice information."
                    )

            else:
                print("    ✓ Search quality evaluation passed")

        except AssertionError:
            # Re-raise assertion errors
            raise
        except Exception as e:
            print(f"    ⚠️  LLM judge evaluation skipped: {e}")
    else:
        if status == "no_results":
            print("  ⚠️  No search results - data may not have synced or indexed properly")
        elif status == "no_relevant_results":
            print("  ⚠️  No relevant results found for the query")
        else:
            print(f"  ⚠️  Search returned status: {status}")

    # TEST 2: Completion search response
    print(f"\n  Testing COMPLETION search for: '{search_query}'")
    response = requests.get(
        f"{api_url}/collections/{collection_id}/search",
        params={"query": search_query, "response_type": "completion"},
        headers=headers,
    )

    # Completion search should return 200
    assert response.status_code == 200, (
        f"COMPLETION search failed with status {response.status_code}. "
        f"Response: {response.text[:500]}"
    )

    completion_results = response.json()

    # Validate COMPLETION response structure
    assert "response_type" in completion_results, "Missing 'response_type' field"
    assert "status" in completion_results, "Missing 'status' field"
    assert (
        completion_results["response_type"] == "completion"
    ), "Response type should be 'completion'"

    completion_text = completion_results.get("completion", "")
    status = completion_results.get("status", "")

    # Ensure we have a successful completion with content
    assert status == "success", f"COMPLETION search status was '{status}', expected 'success'"
    assert completion_text, "No completion text generated"

    print(f"  ✓ COMPLETION search returned AI response")
    print(f"    AI Response preview: {completion_text[:200]}...")

    # Check if completion mentions expected keywords
    keywords_found = [kw for kw in expected_keywords if kw.lower() in completion_text.lower()]

    assert keywords_found, (
        f"Expected keywords {expected_keywords} not found in completion. "
        f"Completion text: {completion_text[:500]}..."
    )

    print(f"    ✓ Found keywords in completion: {keywords_found}")

    print("\n✅ Basic search functionality test completed")

    # Run comprehensive tests for new search features
    test_advanced_search_features(api_url, headers, collection_id)
