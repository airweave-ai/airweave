"""Manual test script for the full browse tree + node selection + targeted sync flow.

Prerequisites:
- Backend running at BASE_URL
- SharePoint 2019 V2 source is registered
- AD user hr_demo exists in Demo_HR_Team group
- SP group Demo HR Readers has Read on HR_Tasks, HR_Announcements, HR_Calendar, HR_Discussion
- All other lists are NOT accessible to hr_demo

Flow:
1. IT Admin (SP_Admin) creates SC1 (sync_immediately=false) — admin's source connection
2. IT Admin triggers ACL sync on SC1
3. IT Admin triggers metadata sync on SC1
4. HR Admin (hr_demo) sees filtered tree — only HR_* lists visible
5. HR Admin creates SC2 (own credentials, same collection, sync_immediately=false)
6. HR Admin selects nodes → stored on SC2, sync auto-triggered
7. Search scoped to SC2
"""

import asyncio
import json
import time
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8001/api/v1"

# SharePoint site
SP_SITE_URL = "http://sharepoint-2019.demos.airweave.ai"
SP_DOMAIN = "AIRWEAVE-SP2019"

# Active Directory credentials (for SID resolution — shared by both SCs)
AD_USERNAME = "sp2019admin"
AD_PASSWORD = "OEtJV0DenQDF21gug#"
AD_DOMAIN = "AIRWEAVE-SP2019"
AD_SERVER = "ldaps://108.143.169.156:636"
AD_SEARCH_BASE = "DC=AIRWEAVE-SP2019,DC=local"

# IT Admin credentials (full access — used for SC1: metadata + ACL sync)
ADMIN_SP_USERNAME = "SP_Admin"
ADMIN_SP_PASSWORD = "FOKVgLLhxvyvPwFmY#"

# HR Admin credentials (limited access — only HR_* lists via Demo HR Readers)
HR_SP_USERNAME = "hr_demo"
HR_SP_PASSWORD = "xK9mPwR2qJ7nL#"

# Collection name for this test
COLLECTION_NAME = "Browse Tree Test"

# User principal for access filtering (the HR user browsing the tree)
USER_PRINCIPAL = "user:hr_demo"

# ---------------------------------------------------------------------------
# Source connection payloads (admin vs HR user)
# ---------------------------------------------------------------------------

_BASE_SC_PAYLOAD = {
    "short_name": "sharepoint2019v2",
    "config": {
        "site_url": SP_SITE_URL,
        "ad_server": AD_SERVER,
        "ad_search_base": AD_SEARCH_BASE,
    },
    "sync_immediately": False,
}

ADMIN_SC_PAYLOAD = {
    **_BASE_SC_PAYLOAD,
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

HR_SC_PAYLOAD = {
    **_BASE_SC_PAYLOAD,
    "authentication": {
        "credentials": {
            "sharepoint_username": HR_SP_USERNAME,
            "sharepoint_password": HR_SP_PASSWORD,
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
# Step 1: IT Admin creates SC1 (sync_immediately=false)
# ---------------------------------------------------------------------------


async def step1_create_admin_sc(client: httpx.AsyncClient, collection_id: str) -> str:
    """Create admin source connection (SC1) without triggering sync."""
    print("\n" + "#" * 60)
    print("STEP 1: IT Admin creates SC1 (sync_immediately=false)")
    print("#" * 60)

    payload = {
        **ADMIN_SC_PAYLOAD,
        "name": "SP Admin (browse tree)",
        "readable_collection_id": collection_id,
    }
    data = await api(client, "POST", "/source-connections/", json=payload)
    sc1_id = str(data["id"])
    print(f"\n  -> SC1 = {sc1_id}")
    return sc1_id


# ---------------------------------------------------------------------------
# Step 2: IT Admin triggers ACL sync on SC1
# ---------------------------------------------------------------------------


async def step2_acl_sync(client: httpx.AsyncClient, sc1_id: str) -> None:
    """Trigger ACL-only sync to populate access_control_membership rows."""
    print("\n" + "#" * 60)
    print("STEP 2: IT Admin triggers ACL sync on SC1")
    print("#" * 60)

    await api(client, "POST", f"/admin/source-connections/{sc1_id}/sync-acl")
    await wait_for_sync(client, sc1_id, "ACL sync")


# ---------------------------------------------------------------------------
# Step 3: IT Admin triggers metadata sync on SC1
# ---------------------------------------------------------------------------


async def step3_metadata_sync(client: httpx.AsyncClient, sc1_id: str) -> None:
    """Trigger metadata-only sync to populate data_tree_node rows."""
    print("\n" + "#" * 60)
    print("STEP 3: IT Admin triggers metadata sync on SC1")
    print("#" * 60)

    await api(client, "POST", f"/admin/source-connections/{sc1_id}/sync-metadata")
    await wait_for_sync(client, sc1_id, "metadata sync")


# ---------------------------------------------------------------------------
# Step 4: HR Admin sees filtered tree
# ---------------------------------------------------------------------------


async def step4_browse_tree(client: httpx.AsyncClient, sc1_id: str) -> list[str]:
    """Browse the tree filtered by user access. Returns source_node_ids to select."""
    print("\n" + "#" * 60)
    print("STEP 4: HR Admin browses filtered tree")
    print("#" * 60)

    # Get root-level nodes filtered by user principal
    data = await api(
        client,
        "GET",
        f"/source-connections/{sc1_id}/browse-tree",
        params={"user_principal": USER_PRINCIPAL},
    )

    nodes = data.get("nodes", [])
    print(f"\n  Root nodes ({len(nodes)}):")
    for node in nodes:
        marker = " [+]" if node["has_children"] else ""
        print(
            f"    [{node['node_type']}] {node['title']}{marker} (id={node['source_node_id'][:40]})"
        )

    # Expand first expandable node to demo lazy loading
    for node in nodes:
        if node["has_children"]:
            print(f"\n  Expanding: {node['title']}...")
            children_data = await api(
                client,
                "GET",
                f"/source-connections/{sc1_id}/browse-tree",
                params={
                    "user_principal": USER_PRINCIPAL,
                    "parent_id": node["id"],
                },
            )
            child_nodes = children_data.get("nodes", [])
            print(f"  Children ({len(child_nodes)}):")
            for child in child_nodes[:10]:
                print(
                    f"    [{child['node_type']}] {child['title']} "
                    f"(id={child['source_node_id'][:40]})"
                )
            if len(child_nodes) > 10:
                print(f"    ... and {len(child_nodes) - 10} more")
            break

    # Select all root nodes (in a real UI, user would pick specific nodes)
    source_node_ids = [n["source_node_id"] for n in nodes]
    print(f"\n  -> Selecting {len(source_node_ids)} root nodes for targeted sync")
    return source_node_ids


# ---------------------------------------------------------------------------
# Step 5: HR Admin creates SC2 (own credentials, same collection)
# ---------------------------------------------------------------------------


async def step5_create_user_sc(client: httpx.AsyncClient, collection_id: str) -> str:
    """Create user source connection (SC2) without triggering sync."""
    print("\n" + "#" * 60)
    print("STEP 5: HR Admin creates SC2 (sync_immediately=false)")
    print("#" * 60)

    payload = {
        **HR_SC_PAYLOAD,
        "name": "SP HR Workspace",
        "readable_collection_id": collection_id,
    }
    data = await api(client, "POST", "/source-connections/", json=payload)
    sc2_id = str(data["id"])
    print(f"\n  -> SC2 = {sc2_id}")
    return sc2_id


# ---------------------------------------------------------------------------
# Step 6: HR Admin selects nodes → auto-triggers targeted sync
# ---------------------------------------------------------------------------


async def step6_select_nodes(
    client: httpx.AsyncClient,
    sc1_id: str,
    sc2_id: str,
    source_node_ids: list[str],
) -> None:
    """Submit node selections on SC2 and auto-trigger targeted sync."""
    print("\n" + "#" * 60)
    print("STEP 6: HR Admin selects nodes (auto-triggers targeted sync)")
    print("#" * 60)

    data = await api(
        client,
        "POST",
        f"/source-connections/{sc2_id}/browse-tree/select",
        json={
            "admin_source_connection_id": sc1_id,
            "source_node_ids": source_node_ids,
        },
    )

    print(f"\n  Selections stored: {data['selections_count']}")
    print(f"  Sync job triggered: {data['sync_job_id']}")

    await wait_for_sync(client, sc2_id, "targeted content sync")


# ---------------------------------------------------------------------------
# Step 7: Search scoped to SC2
# ---------------------------------------------------------------------------


async def step7_search(client: httpx.AsyncClient, collection_id: str, sc2_id: str) -> None:
    """Search within SC2's synced data."""
    print("\n" + "#" * 60)
    print("STEP 7: Search scoped to SC2")
    print("#" * 60)

    data = await api(
        client,
        "POST",
        f"/collections/{collection_id}/search",
        json={
            "query": "quarterly report",
            "source_connection_ids": [sc2_id],
            "generate_answer": False,
            "rerank": False,
        },
    )

    results = data.get("results", [])
    print(f"\n  Found {len(results)} results")
    for r in results[:5]:
        print(f"    - {r.get('name', 'untitled')} (score={r.get('score', 'N/A')})")
    if len(results) > 5:
        print(f"    ... and {len(results) - 5} more")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    """Run the full browse tree + node selection + targeted sync flow."""
    print("=" * 60)
    print("Browse Tree + Node Selection + Targeted Sync — Full Flow")
    print("=" * 60)
    print(f"  SP Site:      {SP_SITE_URL}")
    print(f"  AD Server:    {AD_SERVER}")
    print(f"  IT Admin:     {ADMIN_SP_USERNAME}")
    print(f"  HR User:      {HR_SP_USERNAME}")
    print(f"  User filter:  {USER_PRINCIPAL}")
    print()

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Setup: get or create collection
        collection_id = await get_or_create_collection(client)

        # Step 1: IT Admin creates admin SC
        sc1_id = await step1_create_admin_sc(client, collection_id)

        # Step 2: IT Admin triggers ACL sync
        await step2_acl_sync(client, sc1_id)

        # Step 3: IT Admin triggers metadata sync
        await step3_metadata_sync(client, sc1_id)

        # Step 4: HR Admin browses filtered tree, picks nodes
        source_node_ids = await step4_browse_tree(client, sc1_id)

        if not source_node_ids:
            print("\nNo nodes found in tree — nothing to select. Exiting.")
            return

        # Step 5: HR Admin creates their own SC
        sc2_id = await step5_create_user_sc(client, collection_id)

        # Step 6: HR Admin selects nodes → auto-triggers targeted sync
        await step6_select_nodes(client, sc1_id, sc2_id, source_node_ids)

        # Step 7: Search scoped to HR workspace
        await step7_search(client, collection_id, sc2_id)

    print("\n" + "=" * 60)
    print("DONE")
    print(f"  Collection: {collection_id}")
    print(f"  Admin SC (SC1): {sc1_id}")
    print(f"  User SC  (SC2): {sc2_id}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
