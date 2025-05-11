"""User onboarding test with Stripe source connection.

Tests the end-to-end flow a new user would experience:
1. Connect to Stripe data source
2. Create a sync
3. Run the sync job
4. Test search functionality
5. Evaluate search results using LLM-judge
6. Test chat functionality
"""

import os
import time
import uuid
from typing import Any, Dict, List

import pytest
import requests

from airweave.core.constants.native_connections import NATIVE_QDRANT_UUID, NATIVE_TEXT2VEC_UUID
from tests.helpers.llm_judge import evaluate_search_results


@pytest.fixture
def source_connection_data() -> Dict[str, Any]:
    """Fixture to provide test source connection data for Stripe."""
    stripe_api_key = os.getenv("STRIPE_API_KEY")
    return {
        "name": "Test Source Connection",
        "auth_fields": {
            "api_key": stripe_api_key,
        },
    }


@pytest.fixture
def sync_data() -> Dict[str, Any]:
    """Fixture to provide test sync configuration data."""
    return {
        "name": f"Test Sync {uuid.uuid4()}",
        "description": "Test sync created by E2E test",
        "source_connection_id": None,  # Will be created during test
        "destination_connection_ids": [str(NATIVE_QDRANT_UUID)],
        "embedding_model_connection_id": str(NATIVE_TEXT2VEC_UUID),
        "run_immediately": False,
        "schedule": None,
    }


def create_source_connection(e2e_api_url: str, source_connection_data: Dict[str, Any]) -> str:
    """Create a source connection to Stripe.

    Args:
        e2e_api_url: Base URL for the API endpoints
        source_connection_data: Connection configuration data

    Returns:
        str: ID of the created source connection
    """
    create_connection_response = requests.post(
        f"{e2e_api_url}/connections/connect/source/stripe", json=source_connection_data
    )
    assert create_connection_response.status_code == 200, (
        f"Failed to create connection: {create_connection_response.text}"
    )
    return create_connection_response.json()["id"]


def create_sync(e2e_api_url: str, sync_data: Dict[str, Any]) -> str:
    """Create a new sync job configuration.

    Args:
        e2e_api_url: Base URL for the API endpoints
        sync_data: Sync job configuration data

    Returns:
        str: ID of the created sync job
    """
    create_sync_response = requests.post(f"{e2e_api_url}/sync/", json=sync_data)
    assert create_sync_response.status_code == 200, (
        f"Failed to create sync: {create_sync_response.text}"
    )
    return create_sync_response.json()["id"]


def run_sync_job(e2e_api_url: str, sync_id: str) -> str:
    """Trigger a sync job to run.

    Args:
        e2e_api_url: Base URL for the API endpoints
        sync_id: ID of the sync to run

    Returns:
        str: ID of the running job
    """
    run_sync_response = requests.post(f"{e2e_api_url}/sync/{sync_id}/run")
    assert run_sync_response.status_code == 200, f"Failed to run sync: {run_sync_response.text}"
    return run_sync_response.json()["id"]


def wait_for_sync_completion(
    e2e_api_url: str, sync_id: str, job_id: str, max_wait_time: int = 300
) -> None:
    """Wait for a sync job to complete with timeout.

    Args:
        e2e_api_url: Base URL for the API endpoints
        sync_id: ID of the sync
        job_id: ID of the job to wait for
        max_wait_time: Maximum time to wait in seconds

    Raises:
        AssertionError: If job fails or times out
    """
    # Check initial status
    job_status_response = requests.get(
        f"{e2e_api_url}/sync/{sync_id}/job/{job_id}", params={"sync_id": sync_id}
    )

    current_status = job_status_response.json()["status"]
    if current_status == "completed":
        return

    # Poll job status with timeout
    start_time = time.time()
    while time.time() - start_time < max_wait_time:
        job_status_response = requests.get(
            f"{e2e_api_url}/sync/{sync_id}/job/{job_id}", params={"sync_id": sync_id}
        )
        assert job_status_response.status_code == 200, (
            f"Failed to get job status: {job_status_response.text}"
        )

        current_status = job_status_response.json()["status"]
        if current_status == "completed":
            break
        elif current_status == "failed":
            raise AssertionError(f"Sync job failed: {job_status_response.json()}")

        time.sleep(10)  # Wait before polling again

    # Verify the job completed within the timeout
    assert time.time() - start_time < max_wait_time, "Sync job did not complete within timeout"
    assert current_status == "completed", f"Unexpected job status: {current_status}"


def perform_search(e2e_api_url: str, sync_id: str, query: str) -> List[Dict[str, Any]]:
    """Test search functionality against synchronized data.

    Args:
        e2e_api_url: Base URL for the API endpoints
        sync_id: ID of the sync
        query: Search query to test

    Returns:
        List[Dict[str, Any]]: Search results
    """
    search_response = requests.get(
        f"{e2e_api_url}/search/", params={"sync_id": sync_id, "query": query}
    )
    assert search_response.status_code == 200, f"Search failed: {search_response.text}"

    # Verify search results
    search_results = search_response.json()["results"]
    assert len(search_results) > 0, "No search results were returned"
    assert "payload" in search_results[0], "Result should have text content"
    assert "score" in search_results[0], "Result should have a relevance score"

    # Log search results
    print(f"\n----- Search Results for Query: '{query}' -----")
    print(f"Found {len(search_results)} results")

    for i, result in enumerate(search_results):
        print(f"\nResult #{i+1} (Score: {result['score']:.4f}):")
        print(f"Payload: {result['payload']}")
        if 'metadata' in result:
            print(f"Metadata: {result['metadata']}")
        print("-" * 50)

    return search_results


def evaluate_with_llm_judge(
    query: str, results: List[Dict[str, Any]], expected_keywords: List[str]
) -> None:
    """Evaluate search results using LLM judge.

    Args:
        query: The search query that was performed
        results: Search results to evaluate
        expected_keywords: Keywords expected to be found in results
    """
    print(f"Evaluating search results for keywords: {expected_keywords}")

    search_evaluation = evaluate_search_results(
        query=query,
        results=results,
        expected_content_keywords=expected_keywords,
        minimum_score=0.75,
        minimum_relevant_results=1,
    )

    print(f"Search evaluation results: {search_evaluation}")
    print(f"Search evaluation feedback: {search_evaluation['feedback']}")

    assert search_evaluation["completeness"] > 0.5, (
        "Search results missing too many expected keywords"
    )


def perform_chat_test(e2e_api_url: str, sync_id: str, query: str) -> None:
    """Test chat functionality with synchronized data.

    Args:
        e2e_api_url: Base URL for the API endpoints
        sync_id: ID of the sync
        query: Chat query to test
    """
    # Create a chat
    chat_create_data = {
        "name": "Test Chat",
        "sync_id": sync_id,
        "description": "Chat for testing Stripe data via ChatGPT",
        "model_name": "gpt-4o",
        "model_settings": {"temperature": 0.3, "max_tokens": 500},
    }

    chat_response = requests.post(f"{e2e_api_url}/chat/", json=chat_create_data)
    assert chat_response.status_code == 200, f"Failed to create chat: {chat_response.text}"

    chat_id = chat_response.json()["id"]

    # Send a message to the chat
    message_data = {"content": query, "role": "user"}

    message_response = requests.post(f"{e2e_api_url}/chat/{chat_id}/message", json=message_data)
    assert message_response.status_code == 200, f"Failed to send message: {message_response.text}"

    # Test streaming response
    process_streaming_response(e2e_api_url, chat_id)

    # Verify chat messages were saved
    verify_chat_messages(e2e_api_url, chat_id)


def process_streaming_response(e2e_api_url: str, chat_id: str) -> str:
    """Process and collect the streaming chat response.

    Args:
        e2e_api_url: Base URL for the API endpoints
        chat_id: ID of the chat

    Returns:
        str: Full collected response
    """
    stream_response = requests.get(f"{e2e_api_url}/chat/{chat_id}/stream", stream=True)
    assert stream_response.status_code == 200, f"Failed to stream chat: {stream_response.text}"

    print("Waiting for streaming response to complete...")
    full_response = ""
    for chunk in stream_response.iter_content(chunk_size=1024):
        if chunk:
            chunk_str = chunk.decode("utf-8")
            for line in chunk_str.split("\n"):
                if line.startswith("data: "):
                    content = line[6:]  # Remove 'data: ' prefix
                    if content == "[DONE]":
                        break
                    elif content != "[ERROR]":
                        content = content.replace("\\n", "\n")
                        full_response += content

    # Wait for response to be processed and saved
    time.sleep(3)

    return full_response


def verify_chat_messages(e2e_api_url: str, chat_id: str) -> None:
    """Verify that chat messages were properly saved.

    Args:
        e2e_api_url: Base URL for the API endpoints
        chat_id: ID of the chat to verify
    """
    chat_messages_response = requests.get(f"{e2e_api_url}/chat/{chat_id}")
    assert chat_messages_response.status_code == 200, (
        f"Failed to get chat: {chat_messages_response.text}"
    )

    chat_with_messages = chat_messages_response.json()
    messages = chat_with_messages.get("messages", [])

    # There should be at least two messages - our question and the AI response
    assert len(messages) >= 2, f"Expected at least 2 messages, got {len(messages)}"

    # Log the AI response
    ai_response = messages[-1]["content"]
    print(f"\nFull AI response from retrieved chat: {ai_response}")


def test_user_onboarding(e2e_api_url, source_connection_data, sync_data):
    """Test the end-to-end user onboarding flow with Stripe integration.

    This test performs the full onboarding workflow:
    1. Create a connection to Stripe
    2. Set up a sync job
    3. Run the sync job and wait for completion
    4. Test search functionality
    5. Evaluate search results quality
    6. Test chat functionality with the synced data

    Args:
        e2e_api_url: Base URL for the API endpoints
        source_connection_data: Source connection configuration
        sync_data: Sync job configuration
    """
    # Step 1: Create a source connection
    source_id = create_source_connection(e2e_api_url, source_connection_data)
    sync_data["source_connection_id"] = source_id

    # Step 2: Create a sync configuration
    sync_id = create_sync(e2e_api_url, sync_data)

    # Step 3: Run a sync job
    job_id = run_sync_job(e2e_api_url, sync_id)

    # Step 4: Wait for the sync job to complete
    wait_for_sync_completion(e2e_api_url, sync_id, job_id)

    # Define the test query
    search_query = "What did Neena buy according to the invoice?"

    # Step 5: Test search functionality
    search_results = perform_search(e2e_api_url, sync_id, search_query)

    # Step 6: Evaluate search results with LLM judge
    expected_keywords = ["Vitesse", "schaakbord"]
    evaluate_with_llm_judge(search_query, search_results, expected_keywords)

    # Step 7: Test chat functionality
    perform_chat_test(e2e_api_url, sync_id, search_query)
