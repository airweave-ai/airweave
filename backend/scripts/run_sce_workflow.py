"""Start the ExtractStructuralContextWorkflow against a completed sync.

Usage:
    python scripts/run_sce_workflow.py --collection-id <UUID> --sync-id <UUID>

    # Or look up IDs from the API using readable collection ID + source connection ID:
    python scripts/run_sce_workflow.py \
        --readable-collection-id airweave-repo-yana9p \
        --source-connection-id f395eb4e-0304-414f-a7b1-adfae0899ac2
"""

import argparse
import asyncio
import sys

import httpx
from temporalio.client import Client

API_BASE = "http://localhost:8001"
TEMPORAL_ADDRESS = "localhost:7233"
TASK_QUEUE = "airweave-sync-queue"


async def lookup_ids(
    readable_collection_id: str | None,
    source_connection_id: str | None,
) -> tuple[str, str]:
    """Resolve readable IDs to UUIDs via the API."""
    async with httpx.AsyncClient(base_url=API_BASE) as api:
        # Get collection UUID from readable ID
        resp = await api.get(f"/collections/{readable_collection_id}")
        resp.raise_for_status()
        collection_uuid = resp.json()["id"]
        print(f"Collection UUID: {collection_uuid}")

        # Get sync_id from the source connection
        resp = await api.get(f"/source-connections/{source_connection_id}")
        resp.raise_for_status()
        sync_uuid = resp.json()["sync_id"]
        print(f"Sync UUID: {sync_uuid}")

    return collection_uuid, sync_uuid


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run SCE workflow")
    parser.add_argument("--collection-id", help="Collection UUID")
    parser.add_argument("--sync-id", help="Sync UUID")
    parser.add_argument("--readable-collection-id", help="Readable collection ID (looked up via API)")
    parser.add_argument("--source-connection-id", help="Source connection UUID (looked up via API)")
    args = parser.parse_args()

    # Resolve IDs
    if args.collection_id and args.sync_id:
        collection_id = args.collection_id
        sync_id = args.sync_id
    elif args.readable_collection_id and args.source_connection_id:
        collection_id, sync_id = await lookup_ids(
            args.readable_collection_id, args.source_connection_id
        )
    else:
        print("Provide either --collection-id + --sync-id, or --readable-collection-id + --source-connection-id")
        sys.exit(1)

    print(f"\nStarting SCE workflow:")
    print(f"  collection_id = {collection_id}")
    print(f"  sync_id       = {sync_id}")

    client = await Client.connect(TEMPORAL_ADDRESS)
    handle = await client.start_workflow(
        "ExtractStructuralContextWorkflow",
        args=[collection_id, sync_id],
        id=f"sce-{sync_id[:8]}",
        task_queue=TASK_QUEUE,
    )
    print(f"\nWorkflow started: {handle.id}")
    print("Waiting for result...")

    result = await handle.result()
    print(f"\nDone! Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
