"""
First Vespa test - Sync Stripe data and search for Vitesse shirt invoice.

Run with:
  AIRWEAVE_STRIPE_API_KEY=sk_test_... poetry run python first_vespa_test.py

On first run: Creates collection, syncs Stripe data, then searches.
On subsequent runs: Skips sync (collection exists), goes directly to search.
"""

import asyncio
import os
import time

import httpx

# Configuration
BASE_URL = "http://localhost:8001"
STRIPE_API_KEY = os.environ.get("AIRWEAVE_STRIPE_API_KEY", "")

# Fixed collection name - reused across runs
COLLECTION_NAME = "Vespa Stripe Test"

# Semantic search query - NOT keyword search, but describing what we're looking for
SEARCH_QUERY = "One of our products is a football worn jersey, which player and which game is it from?"


async def get_collection_by_name(client: httpx.AsyncClient, name: str) -> dict | None:
    """Check if a collection with the given name exists."""
    response = await client.get(f"{BASE_URL}/collections/")
    response.raise_for_status()
    collections = response.json()

    for collection in collections:
        if collection.get("name") == name:
            return collection
    return None


async def wait_for_sync_completion(
    client: httpx.AsyncClient, source_connection_id: str
) -> bool:
    """Wait indefinitely for sync to complete. Returns True if successful."""
    poll_interval = 5
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time

        # Get sync jobs for the source connection
        response = await client.get(
            f"{BASE_URL}/source-connections/{source_connection_id}/jobs",
        )
        response.raise_for_status()
        jobs = response.json()

        if jobs:
            latest_job = jobs[0]  # Most recent job
            status = latest_job.get("status", "unknown").lower()

            # Stats are at top level, not nested under "stats"
            inserted = latest_job.get("entities_inserted", 0)
            updated = latest_job.get("entities_updated", 0)
            total = inserted + updated

            print(
                f"   [{int(elapsed)}s] Status: {status} | "
                f"Entities: {total} (inserted: {inserted}, updated: {updated})"
            )

            if status == "completed":
                print(f"\n✅ Sync completed in {int(elapsed)} seconds!")
                print(f"   Total entities synced: {total}")
                return True
            elif status in ("failed", "cancelled"):
                print(f"\n❌ Sync {status.upper()}")
                error = latest_job.get("error_message", "Unknown error")
                print(f"   Error: {error}")
                return False
        else:
            print(f"   [{int(elapsed)}s] Waiting for sync job to start...")

        await asyncio.sleep(poll_interval)


async def run_search(client: httpx.AsyncClient, collection_id: str) -> None:
    """Run semantic search on the collection."""
    print(f"   Query: '{SEARCH_QUERY}'")

    response = await client.post(
        f"{BASE_URL}/collections/{collection_id}/search",
        json={
            "query": SEARCH_QUERY,
            "limit": 10,
            "expand_query": False,
            "rerank": False,
            "generate_answer": True,
        },
    )
    response.raise_for_status()
    search_results = response.json()

    results = search_results.get("results", [])
    completion = search_results.get("completion")

    print(f"\n✅ Found {len(results)} results!")

    # Debug: Show raw structure of first result
    if results:
        print("\n📊 DEBUG - Raw result structure (first result):")
        print("-" * 60)
        first = results[0]
        print(f"   Top-level keys: {list(first.keys())}")
        if "payload" in first:
            payload = first["payload"]
            print(f"   Payload keys: {list(payload.keys())[:20]}")
            # Show some key fields
            for key in [
                "entity_name",
                "source_name",
                "entity_type",
                "name",
                "textual_representation",
            ]:
                if key in payload:
                    val = payload[key]
                    if isinstance(val, str) and len(val) > 100:
                        val = val[:100] + "..."
                    print(f"   payload['{key}']: {val}")
        print("-" * 60)

    if completion:
        print("\n📝 AI-Generated Answer:")
        print("-" * 40)
        print(completion)
        print("-" * 40)

    print("\n🔍 Top Results:")
    for i, result in enumerate(results[:5], 1):
        # Results have structure: {"id": ..., "score": ..., "payload": {...}}
        payload = result.get("payload", {})

        # Vespa field names use airweave_system_metadata_ prefix
        name = payload.get("name") or result.get("id", "Unknown")
        source = payload.get("airweave_system_metadata_source_name", "Unknown")
        score = result.get("score", 0)
        entity_type = payload.get("airweave_system_metadata_entity_type", "Unknown")

        print(f"\n   {i}. {name}")
        print(f"      Type: {entity_type} | Source: {source} | Score: {score:.4f}")

        # Show textual_representation preview (the searchable content)
        text_repr = payload.get("textual_representation", "")
        if text_repr:
            preview = text_repr[:200].replace("\n", " ")
            print(f"      Content: {preview}...")

        # Show some relevant metadata from payload field (JSON string)
        payload_json = payload.get("payload", "")
        if payload_json and isinstance(payload_json, str):
            import json as json_module

            try:
                metadata = json_module.loads(payload_json)
                if "amount" in metadata:
                    amount = metadata["amount"]
                    currency = metadata.get("currency", "")
                    print(f"      Amount: {amount} {currency.upper()}")
                if "description" in metadata:
                    desc = metadata["description"]
                    if desc:
                        print(f"      Description: {desc[:100]}...")
            except Exception:
                pass


async def main():
    if not STRIPE_API_KEY:
        raise RuntimeError(
            "Missing Stripe API key. Set AIRWEAVE_STRIPE_API_KEY to run this script."
        )

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # =================================================================
            # 1. Check if collection already exists
            # =================================================================
            print("\n" + "=" * 60)
            print("1. Checking for existing collection...")
            print("=" * 60)

            existing_collection = await get_collection_by_name(client, COLLECTION_NAME)

            if existing_collection:
                collection_id = existing_collection["readable_id"]
                print(f"✅ Found existing collection: {collection_id}")
                print(f"   UUID: {existing_collection['id']}")
                print("   Skipping sync - going directly to search...")
            else:
                # =============================================================
                # 2. Create collection (only if it doesn't exist)
                # =============================================================
                print(f"   Collection '{COLLECTION_NAME}' not found. Creating...")

                response = await client.post(
                    f"{BASE_URL}/collections/",
                    json={"name": COLLECTION_NAME},
                )
                response.raise_for_status()
                collection = response.json()
                collection_id = collection["readable_id"]
                print(f"✅ Created collection: {collection_id}")
                print(f"   UUID: {collection['id']}")

                # =============================================================
                # 3. Create Stripe source connection
                # =============================================================
                print("\n" + "=" * 60)
                print("2. Creating Stripe source connection...")
                print("=" * 60)

                response = await client.post(
                    f"{BASE_URL}/source-connections/",
                    json={
                        "name": "Stripe Test Connection",
                        "short_name": "stripe",
                        "readable_collection_id": collection_id,
                        "authentication": {
                            "credentials": {
                                "api_key": STRIPE_API_KEY,
                            }
                        },
                        "sync_immediately": True,  # Start sync right away
                    },
                )
                response.raise_for_status()
                source_connection = response.json()
                source_connection_id = source_connection["id"]
                print(f"✅ Created source connection: {source_connection_id}")
                print(f"   Status: {source_connection.get('status', 'unknown')}")

                # =============================================================
                # 4. Wait for sync to complete (no timeout)
                # =============================================================
                print("\n" + "=" * 60)
                print("3. Waiting for sync to complete (no timeout)...")
                print("=" * 60)

                sync_success = await wait_for_sync_completion(
                    client, source_connection_id
                )
                if not sync_success:
                    print(
                        "\n⚠️  Sync did not complete successfully, but continuing to search..."
                    )

            # =================================================================
            # 5. Search (runs regardless of whether we synced or not)
            # =================================================================
            print("\n" + "=" * 60)
            print("4. Searching for Vitesse shirt invoice (semantic search)...")
            print("=" * 60)

            # Small delay to ensure any recent writes are indexed
            await asyncio.sleep(2)

            await run_search(client, collection_id)

        except httpx.HTTPStatusError as e:
            print(f"\n❌ HTTP Error: {e.response.status_code}")
            print(f"   Response: {e.response.text}")
            raise

        print("\n" + "=" * 60)
        print("🎉 Test complete!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
