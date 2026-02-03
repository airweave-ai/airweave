"""
E2E smoke tests for special token handling in the sync pipeline.

Tests that the chunker/embedder correctly handles special tokenizer tokens
like <|endoftext|> that may appear in user content (e.g., AI-generated text
pasted into documents).

This validates the TiktokenSafeEncoding wrapper in the chunker pipeline.
"""

import asyncio
import time
import pytest
import pytest_asyncio
import httpx
from typing import AsyncGenerator, Dict, Optional


@pytest_asyncio.fixture(scope="function")
async def special_token_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create HTTP client for special token tests."""
    from config import settings

    async with httpx.AsyncClient(
        base_url=settings.api_url,
        headers=settings.api_headers,
        timeout=httpx.Timeout(120),  # Longer timeout for sync operations
        follow_redirects=True,
    ) as client:
        yield client


async def wait_for_sync_completion(
    client: httpx.AsyncClient,
    connection_id: str,
    max_wait_time: int = 180,
    poll_interval: int = 3,
) -> Dict:
    """Wait for a source connection sync to complete and return final status.

    Args:
        client: HTTP client
        connection_id: Source connection ID to monitor
        max_wait_time: Maximum seconds to wait
        poll_interval: Seconds between status checks

    Returns:
        Final connection status dict

    Raises:
        TimeoutError: If sync doesn't complete within max_wait_time
    """
    elapsed = 0
    while elapsed < max_wait_time:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        response = await client.get(f"/source-connections/{connection_id}")
        if response.status_code != 200:
            continue

        conn = response.json()
        status = conn.get("status")

        if status == "active":
            return conn
        elif status == "error":
            return conn

    raise TimeoutError(f"Sync did not complete within {max_wait_time}s")


@pytest.mark.asyncio
async def test_sync_with_special_tokens_inject_flag(
    special_token_client: httpx.AsyncClient,
):
    """Test that sync succeeds when stub source injects special tokens.

    This tests the TiktokenSafeEncoding wrapper by:
    1. Creating a collection
    2. Creating a stub source connection with inject_special_tokens=True
    3. Running a sync (which will inject <|endoftext|> etc. into content)
    4. Verifying the sync completes successfully (not fails with tokenizer error)
    5. Verifying entities are searchable
    """
    client = special_token_client
    collection_readable_id: Optional[str] = None
    connection_id: Optional[str] = None

    try:
        # Step 1: Create collection
        collection_response = await client.post(
            "/collections/",
            json={"name": f"Special Token Test {int(time.time())}"},
        )
        assert collection_response.status_code == 200, (
            f"Failed to create collection: {collection_response.text}"
        )
        collection = collection_response.json()
        collection_readable_id = collection["readable_id"]

        # Step 2: Create stub source with special token injection enabled
        connection_data = {
            "name": f"Special Token Stub {int(time.time())}",
            "short_name": "stub",
            "readable_collection_id": collection_readable_id,
            "authentication": {"credentials": {"stub_key": "test"}},
            "config": {
                "seed": 12345,  # Deterministic seed
                "entity_count": 5,  # Small count for fast test
                "generation_delay_ms": 0,
                # Enable special token injection - this is what we're testing!
                "inject_special_tokens": True,
                # Mix of entity types to test both semantic and code chunkers
                "small_entity_weight": 30,
                "medium_entity_weight": 30,
                "large_entity_weight": 20,
                "small_file_weight": 0,
                "large_file_weight": 10,
                "code_file_weight": 10,
            },
            "sync_immediately": True,
        }

        connection_response = await client.post(
            "/source-connections",
            json=connection_data,
        )
        assert connection_response.status_code == 200, (
            f"Failed to create source connection: {connection_response.text}"
        )
        connection = connection_response.json()
        connection_id = connection["id"]

        # Step 3: Wait for sync to complete
        print("\n" + "=" * 60)
        print("TEST: test_sync_with_special_tokens_inject_flag")
        print("=" * 60)
        print("Waiting for sync with inject_special_tokens=True...")

        try:
            final_status = await wait_for_sync_completion(
                client,
                connection_id,
                max_wait_time=180,
            )
        except TimeoutError as e:
            pytest.fail(f"Sync timed out: {e}")

        # Step 4: Verify sync succeeded (this is the main assertion!)
        status = final_status.get("status")
        print(f"Sync completed with status: {status}")

        if status == "error":
            # Get the sync job for more details
            jobs_response = await client.get(
                f"/source-connections/{connection_id}/sync-jobs?limit=1"
            )
            if jobs_response.status_code == 200:
                jobs = jobs_response.json()
                if jobs:
                    error_msg = jobs[0].get("error_message", "Unknown error")
                    print(f"Sync error: {error_msg}")

                    # This is what we're testing - the sync should NOT fail
                    # with tokenizer errors like "disallowed special token"
                    assert "disallowed special token" not in error_msg.lower(), (
                        f"Sync failed due to special token handling: {error_msg}"
                    )
                    assert "endoftext" not in error_msg.lower(), (
                        f"Sync failed due to <|endoftext|> token: {error_msg}"
                    )

            pytest.fail(f"Sync failed: {final_status}")

        assert status == "active", f"Expected active status, got: {status}"

        # Step 5: Verify entities are searchable (optional but good to confirm)
        # Give Vespa/Qdrant a moment to index
        await asyncio.sleep(3)

        search_response = await client.post(
            f"/collections/{collection_readable_id}/search",
            json={
                "query": "test content",
                "limit": 10,
                "expand_query": False,
                "interpret_filters": False,
                "rerank": False,
                "generate_answer": False,
            },
            timeout=60,
        )

        assert search_response.status_code == 200, (
            f"Search failed: {search_response.text}"
        )

        results = search_response.json()
        result_count = len(results.get("results", []))
        print(f"Search returned {result_count} results")

        # We should have some indexed content
        assert result_count > 0, (
            "Expected search results after sync with special tokens"
        )

        print("=" * 60)
        print("SUCCESS: Sync with special tokens completed successfully!")
        print("=" * 60 + "\n")

    finally:
        # Cleanup
        if connection_id:
            try:
                await client.delete(f"/source-connections/{connection_id}")
            except Exception:
                pass

        if collection_readable_id:
            try:
                await client.delete(f"/collections/{collection_readable_id}")
            except Exception:
                pass


@pytest.mark.asyncio
async def test_sync_with_custom_content_prefix_special_token(
    special_token_client: httpx.AsyncClient,
):
    """Test sync with a custom content prefix containing special tokens.

    This tests explicit special token injection via custom_content_prefix,
    which gives more control over exactly what token is tested.
    """
    client = special_token_client
    collection_readable_id: Optional[str] = None
    connection_id: Optional[str] = None

    try:
        # Create collection
        collection_response = await client.post(
            "/collections/",
            json={"name": f"Custom Prefix Token Test {int(time.time())}"},
        )
        assert collection_response.status_code == 200
        collection = collection_response.json()
        collection_readable_id = collection["readable_id"]

        # Create stub source with explicit <|endoftext|> in custom prefix
        connection_data = {
            "name": f"Custom Prefix Stub {int(time.time())}",
            "short_name": "stub",
            "readable_collection_id": collection_readable_id,
            "authentication": {"credentials": {"stub_key": "test"}},
            "config": {
                "seed": 99999,
                "entity_count": 3,  # Minimal for fast test
                "generation_delay_ms": 0,
                # Explicit special token in prefix - very direct test
                "custom_content_prefix": (
                    "This content contains a special token: <|endoftext|>\n"
                    "And another: <|fim_prefix|> code here <|fim_suffix|>"
                ),
                # Simple entities only (faster)
                "small_entity_weight": 50,
                "medium_entity_weight": 50,
                "large_entity_weight": 0,
                "small_file_weight": 0,
                "large_file_weight": 0,
                "code_file_weight": 0,
            },
            "sync_immediately": True,
        }

        connection_response = await client.post(
            "/source-connections",
            json=connection_data,
        )
        assert connection_response.status_code == 200
        connection = connection_response.json()
        connection_id = connection["id"]

        print("\n" + "=" * 60)
        print("TEST: test_sync_with_custom_content_prefix_special_token")
        print("=" * 60)
        print("Syncing with explicit <|endoftext|> in content prefix...")

        # Wait for sync
        try:
            final_status = await wait_for_sync_completion(
                client,
                connection_id,
                max_wait_time=120,
            )
        except TimeoutError as e:
            pytest.fail(f"Sync timed out: {e}")

        status = final_status.get("status")
        print(f"Sync completed with status: {status}")

        # Main assertion: sync should succeed, not fail on special tokens
        assert status == "active", (
            f"Sync failed - likely due to special token handling. Status: {status}"
        )

        print("=" * 60)
        print("SUCCESS: Custom prefix with special tokens handled correctly!")
        print("=" * 60 + "\n")

    finally:
        if connection_id:
            try:
                await client.delete(f"/source-connections/{connection_id}")
            except Exception:
                pass

        if collection_readable_id:
            try:
                await client.delete(f"/collections/{collection_readable_id}")
            except Exception:
                pass
