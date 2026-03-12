"""Manual test script for single-SC browse tree + node selection + targeted sync flow.

Prerequisites:
- Backend running at BASE_URL
- SharePoint 2019 V2 source is registered

Flow (single SC):
1. IT Admin creates SC1 (sync_immediately=false)
2. IT Admin triggers ACL sync on SC1
3. IT Admin browses tree (lazy-loaded from source API, unfiltered)
4. IT Admin selects nodes → stored on SC1, targeted sync auto-triggered
5. Search scoped to SC1
"""

import asyncio
import json
import os
import time
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8001"

# SharePoint site
SP_SITE_URL = "http://sharepoint-2019.demos.airweave.ai"
SP_DOMAIN = "AIRWEAVE-SP2019"

# Active Directory credentials (loaded from environment)
AD_USERNAME = os.environ.get("AD_USERNAME", "")
AD_PASSWORD = os.environ.get("AD_PASSWORD", "")
AD_DOMAIN = os.environ.get("AD_DOMAIN", "AIRWEAVE-SP2019")
AD_SERVER = os.environ.get("AD_SERVER", "")
AD_SEARCH_BASE = os.environ.get("AD_SEARCH_BASE", "DC=AIRWEAVE-SP2019,DC=local")

# IT Admin credentials (loaded from environment)
ADMIN_SP_USERNAME = os.environ.get("ADMIN_SP_USERNAME", "")
ADMIN_SP_PASSWORD = os.environ.get("ADMIN_SP_PASSWORD", "")

# User principals for search-as-user verification
FULL_ACCESS_USER = "sp_admin"  # Member of site owner/member groups — sees everything
LIMITED_ACCESS_USER = "hr_demo"  # Member of Demo HR Readers only — sees subset

# Collection name for this test
COLLECTION_NAME = "Browse Tree V2 Test"

# ---------------------------------------------------------------------------
# Source connection payload
# ---------------------------------------------------------------------------

SC_PAYLOAD = {
    "short_name": "sharepoint2019v2",
    "config": {
        "site_url": SP_SITE_URL,
        "ad_server": AD_SERVER,
        "ad_search_base": AD_SEARCH_BASE,
    },
    "sync_immediately": False,
    "authentication": {
        "credentials": {
            "sharepoint_username": ADMIN_SP_USERNAME,
            "sharepoint_password": ADMIN_SP_PASSWORD,
            "sharepoint_domain": SP_DOMAIN,
            "ad_username": AD_USERNAME,
            "ad_password": AD_PASSWORD,
            "ad_domain": AD_DOMAIN,
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def pp(data: dict) -> None:
    """Pretty-print JSON response."""
    print(json.dumps(data, indent=2, default=str))


async def api(client: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> dict:  # type: ignore[type-arg]
    """Make an API call and return the JSON response."""
    url = f"{BASE_URL}{path}"
    resp = await client.request(method, url, **kwargs)
    print(f"\n{'=' * 60}")
    print(f"{method} {path} -> {resp.status_code}")
    if resp.status_code >= 400:
        print(f"ERROR: {resp.text}")
        resp.raise_for_status()
    data: dict = resp.json()
    pp(data)
    return data


async def wait_for_sync(
    client: httpx.AsyncClient, source_connection_id: str, label: str, max_wait: int = 600
) -> None:
    """Poll sync jobs for a source connection until terminal state."""
    print(f"\nWaiting for {label} (SC {source_connection_id[:8]}...)...")
    start = time.time()
    while time.time() - start < max_wait:
        resp = await client.get(
            f"{BASE_URL}/source-connections/{source_connection_id}/jobs",
        )
        if resp.status_code == 200:
            jobs = resp.json()
            if jobs:
                latest = jobs[0]
                status = latest.get("status", "unknown").lower()
                inserted = latest.get("entities_inserted", 0)
                updated = latest.get("entities_updated", 0)
                elapsed = int(time.time() - start)
                print(
                    f"  [{elapsed}s] {status} | "
                    f"entities: {inserted + updated} "
                    f"(ins={inserted}, upd={updated})"
                )
                if status in ("completed", "failed", "cancelled"):
                    if status != "completed":
                        print(f"  WARNING: {label} ended with status={status}")
                    return
        await asyncio.sleep(5)
    print(f"  TIMEOUT: {label} did not complete within {max_wait}s")


async def get_or_create_collection(client: httpx.AsyncClient) -> str:
    """Get existing collection or create a new one. Returns readable_id."""
    resp = await client.get(f"{BASE_URL}/collections/")
    resp.raise_for_status()
    for coll in resp.json():
        if coll.get("name") == COLLECTION_NAME:
            print(f"Found existing collection: {coll['readable_id']}")
            return str(coll["readable_id"])

    data = await api(client, "POST", "/collections/", json={"name": COLLECTION_NAME})
    return str(data["readable_id"])


# ---------------------------------------------------------------------------
# Step 1: Create SC (sync_immediately=false)
# ---------------------------------------------------------------------------


async def step1_create_sc(client: httpx.AsyncClient, collection_id: str) -> str:
    """Create source connection without triggering sync."""
    print("\n" + "#" * 60)
    print("STEP 1: Create SC (sync_immediately=false)")
    print("#" * 60)

    payload = {
        **SC_PAYLOAD,
        "name": "SP Admin (browse tree v2)",
        "readable_collection_id": collection_id,
    }
    data = await api(client, "POST", "/source-connections/", json=payload)
    sc_id = str(data["id"])
    print(f"\n  -> SC = {sc_id}")
    return sc_id


# ---------------------------------------------------------------------------
# Step 2: Trigger ACL sync
# ---------------------------------------------------------------------------


async def step2_acl_sync(client: httpx.AsyncClient, sc_id: str) -> None:
    """Trigger ACL-only sync to populate access_control_membership rows."""
    print("\n" + "#" * 60)
    print("STEP 2: Trigger ACL sync")
    print("#" * 60)

    await api(client, "POST", f"/admin/source-connections/{sc_id}/sync-acl")
    await wait_for_sync(client, sc_id, "ACL sync")


# ---------------------------------------------------------------------------
# Step 3: Browse tree (lazy-loaded from source API)
# ---------------------------------------------------------------------------


async def step3_browse_tree(client: httpx.AsyncClient, sc_id: str) -> list[str]:
    """Browse the tree and return source_node_ids to select."""
    print("\n" + "#" * 60)
    print("STEP 3: Browse tree (lazy-loaded)")
    print("#" * 60)

    # Get root-level nodes
    data = await api(
        client,
        "GET",
        f"/admin/source-connections/{sc_id}/browse-tree",
    )

    nodes = data.get("nodes", [])
    print(f"\n  Root nodes ({len(nodes)}):")
    for node in nodes:
        marker = " [+]" if node["has_children"] else ""
        print(
            f"    [{node['node_type']}] {node['title']}{marker} (id={node['source_node_id'][:50]})"
        )

    # Expand root site to demo lazy loading
    for node in nodes:
        if node["has_children"]:
            print(f"\n  Expanding: {node['title']}...")
            children_data = await api(
                client,
                "GET",
                f"/admin/source-connections/{sc_id}/browse-tree",
                params={"parent_node_id": node["source_node_id"]},
            )
            child_nodes = children_data.get("nodes", [])
            print(f"  Children ({len(child_nodes)}):")
            for child in child_nodes[:10]:
                marker = " [+]" if child["has_children"] else ""
                print(
                    f"    [{child['node_type']}] {child['title']}{marker} "
                    f"(id={child['source_node_id'][:50]})"
                )
            if len(child_nodes) > 10:
                print(f"    ... and {len(child_nodes) - 10} more")

            # Select some list nodes for targeted sync
            list_nodes = [n for n in child_nodes if n["node_type"] == "list"]
            if list_nodes:
                selected = [n["source_node_id"] for n in list_nodes[:3]]
                print(f"\n  -> Selecting {len(selected)} list nodes for targeted sync")
                return selected
            break

    # Fallback: select root node
    if nodes:
        return [nodes[0]["source_node_id"]]
    return []


# ---------------------------------------------------------------------------
# Step 4: Select nodes → auto-trigger targeted sync
# ---------------------------------------------------------------------------


async def step4_select_nodes(
    client: httpx.AsyncClient,
    sc_id: str,
    source_node_ids: list[str],
) -> None:
    """Submit node selections and auto-trigger targeted sync."""
    print("\n" + "#" * 60)
    print("STEP 4: Select nodes (auto-triggers targeted sync)")
    print("#" * 60)

    data = await api(
        client,
        "POST",
        f"/admin/source-connections/{sc_id}/browse-tree/select",
        json={"source_node_ids": source_node_ids},
    )

    print(f"\n  Selections stored: {data['selections_count']}")
    print(f"  Sync job triggered: {data['sync_job_id']}")

    await wait_for_sync(client, sc_id, "targeted content sync")


# ---------------------------------------------------------------------------
# Step 5: Search scoped to SC
# ---------------------------------------------------------------------------


async def search_as_user(
    client: httpx.AsyncClient, collection_id: str, user_principal: str, query: str
) -> list[dict[str, Any]]:
    """Search as a specific user and return results."""
    data = await api(
        client,
        "POST",
        f"/admin/collections/{collection_id}/search/as-user",
        params={"user_principal": user_principal, "destination": "vespa"},
        json={
            "query": query,
            "limit": 50,
            "expand_query": False,
            "interpret_filters": False,
            "rerank": False,
            "generate_answer": False,
        },
    )
    return data.get("results", [])


async def step5_search(client: httpx.AsyncClient, collection_id: str) -> None:
    """Search as different users to verify access control."""
    print("\n" + "#" * 60)
    print("STEP 5: Search-as-user (access control verification)")
    print("#" * 60)

    query = "Calendar Standup"

    # 5a: Search as full-access user — should see all entities
    print(f"\n  --- 5a: Search as {FULL_ACCESS_USER} (full access) ---")
    admin_results = await search_as_user(client, collection_id, FULL_ACCESS_USER, query)
    print(f"\n  {FULL_ACCESS_USER} sees {len(admin_results)} results:")
    for r in admin_results[:10]:
        print(f"    - {r.get('name', 'untitled')} (score={r.get('score', 'N/A')})")

    # 5b: Search as limited-access user — should see fewer or no entities
    print(f"\n  --- 5b: Search as {LIMITED_ACCESS_USER} (limited access) ---")
    limited_results = await search_as_user(client, collection_id, LIMITED_ACCESS_USER, query)
    print(f"\n  {LIMITED_ACCESS_USER} sees {len(limited_results)} results:")
    for r in limited_results[:10]:
        print(f"    - {r.get('name', 'untitled')} (score={r.get('score', 'N/A')})")

    # Summary
    print("\n  --- Access control summary ---")
    print(f"    {FULL_ACCESS_USER:20s} (full):    {len(admin_results)} results")
    print(f"    {LIMITED_ACCESS_USER:20s} (limited): {len(limited_results)} results")
    if len(admin_results) > len(limited_results):
        print("    ✓ Access control is filtering correctly")
    elif len(admin_results) == len(limited_results) == 0:
        print("    ⚠ No results for either user — check if entities were synced")
    else:
        print("    ⚠ Both users see same results — check ACL data")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    """Run the single-SC browse tree + node selection + targeted sync flow."""
    print("=" * 60)
    print("Browse Tree V2 — Single-SC Flow")
    print("=" * 60)
    print(f"  SP Site:   {SP_SITE_URL}")
    print(f"  AD Server: {AD_SERVER}")
    print(f"  Admin:     {ADMIN_SP_USERNAME}")
    print()

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Setup: get or create collection
        collection_id = await get_or_create_collection(client)

        # Step 1: Create SC
        sc_id = await step1_create_sc(client, collection_id)

        # Step 2: Trigger ACL sync
        await step2_acl_sync(client, sc_id)

        # Step 3: Browse tree, pick nodes
        source_node_ids = await step3_browse_tree(client, sc_id)

        if not source_node_ids:
            print("\nNo nodes found in tree — nothing to select. Exiting.")
            return

        # Step 4: Select nodes → auto-triggers targeted sync
        await step4_select_nodes(client, sc_id, source_node_ids)

        # Step 5: Search as different users to verify access control
        await step5_search(client, collection_id)

    print("\n" + "=" * 60)
    print("DONE")
    print(f"  Collection: {collection_id}")
    print(f"  SC: {sc_id}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
