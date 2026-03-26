#!/usr/bin/env python3
"""Audit entity counts across Postgres, ARF, and Vespa.

Builds a CSV comparing entity counts per sync to identify discrepancies
where Postgres logged success but Vespa feeds silently failed.

The script is designed to be resumable: it writes progress to a JSON file
after each sync, so it can be interrupted and restarted without re-doing work.

Usage:
    # From backend/ directory (needs env vars for DB, storage, Vespa):

    # Run full audit (writes to audit_entity_counts_<timestamp>.csv)
    python -m scripts.audit_entity_counts

    # Resume a previous run
    python -m scripts.audit_entity_counts --resume audit_entity_counts_20260330_1200.json

    # Filter to specific syncs
    python -m scripts.audit_entity_counts --sync-ids "uuid1,uuid2,uuid3"

    # Adjust concurrency
    python -m scripts.audit_entity_counts --concurrency 5

    # Skip ARF or Vespa if you only need a subset
    python -m scripts.audit_entity_counts --skip-arf
    python -m scripts.audit_entity_counts --skip-vespa

Prerequisites:
    - Postgres reachable (SQLALCHEMY_ASYNC_DATABASE_URI)
    - Azure Blob / storage backend reachable (STORAGE_* env vars)
    - Vespa reachable (VESPA_URL, VESPA_PORT) — via VPN or kubectl port-forward
"""

import argparse
import asyncio
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.config import settings
from airweave.db.session import AsyncSessionLocal
from airweave.models.entity_count import EntityCount
from airweave.models.source_connection import SourceConnection
from airweave.models.sync import Sync
from airweave.platform.destinations.vespa.config import ALL_VESPA_SCHEMAS

TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
DEFAULT_OUTPUT = f"audit_entity_counts_{TIMESTAMP}"


# ---------------------------------------------------------------------------
# Postgres helpers
# ---------------------------------------------------------------------------


async def fetch_all_syncs(db: AsyncSession) -> List[Dict[str, Any]]:
    """Fetch all syncs with their source connection metadata."""
    query = (
        select(
            Sync.id,
            Sync.organization_id,
            Sync.status,
            Sync.created_at,
            SourceConnection.short_name,
            SourceConnection.readable_collection_id,
        )
        .outerjoin(SourceConnection, SourceConnection.sync_id == Sync.id)
        .order_by(Sync.created_at.desc())
    )
    result = await db.execute(query)
    return [
        {
            "sync_id": str(row.id),
            "organization_id": str(row.organization_id),
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "source_short_name": row.short_name,
            "readable_collection_id": row.readable_collection_id,
        }
        for row in result
    ]


async def fetch_specific_syncs(db: AsyncSession, sync_ids: List[UUID]) -> List[Dict[str, Any]]:
    """Fetch specific syncs by ID."""
    query = (
        select(
            Sync.id,
            Sync.organization_id,
            Sync.status,
            Sync.created_at,
            SourceConnection.short_name,
            SourceConnection.readable_collection_id,
        )
        .outerjoin(SourceConnection, SourceConnection.sync_id == Sync.id)
        .where(Sync.id.in_(sync_ids))
        .order_by(Sync.created_at.desc())
    )
    result = await db.execute(query)
    return [
        {
            "sync_id": str(row.id),
            "organization_id": str(row.organization_id),
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "source_short_name": row.short_name,
            "readable_collection_id": row.readable_collection_id,
        }
        for row in result
    ]


async def fetch_pg_entity_counts(db: AsyncSession, sync_ids: List[UUID]) -> Dict[str, int]:
    """Bulk-fetch Postgres entity counts for all syncs."""
    if not sync_ids:
        return {}
    query = (
        select(EntityCount.sync_id, func.sum(EntityCount.count).label("total"))
        .where(EntityCount.sync_id.in_(sync_ids))
        .group_by(EntityCount.sync_id)
    )
    result = await db.execute(query)
    return {str(row.sync_id): int(row.total or 0) for row in result}


async def fetch_collection_id_map(db: AsyncSession, readable_ids: List[str]) -> Dict[str, str]:
    """Map readable_collection_id -> collection UUID for Vespa queries."""
    if not readable_ids:
        return {}

    from airweave.models.collection import Collection

    unique_ids = list(set(rid for rid in readable_ids if rid))
    if not unique_ids:
        return {}

    query = select(Collection.id, Collection.readable_id).where(
        Collection.readable_id.in_(unique_ids)
    )
    result = await db.execute(query)
    return {row.readable_id: str(row.id) for row in result}


# ---------------------------------------------------------------------------
# ARF helpers
# ---------------------------------------------------------------------------


def create_arf_service():
    """Create an ArfService with the configured storage backend."""
    from airweave.core.container.factory import _create_storage_backend
    from airweave.domains.arf.service import ArfService

    storage = _create_storage_backend(settings)
    return ArfService(storage=storage)


async def get_arf_count_safe(arf_service, sync_id: str) -> Optional[int]:
    """Get ARF entity count, returning None on error."""
    try:
        return await arf_service.get_entity_count(sync_id)
    except Exception as e:
        print(f"  [ARF] Error for {sync_id}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Vespa helpers
# ---------------------------------------------------------------------------


async def get_vespa_count(
    http_client: httpx.AsyncClient,
    sync_id: str,
    collection_id: str,
) -> Optional[int]:
    """Query Vespa for total document count for a sync."""
    schemas = ", ".join(ALL_VESPA_SCHEMAS)
    yql = (
        f"select * from sources {schemas} "
        f"where airweave_system_metadata_sync_id contains '{sync_id}' "
        f"and airweave_system_metadata_collection_id contains '{collection_id}' "
        f"limit 0"
    )
    url = f"{settings.VESPA_URL}:{settings.VESPA_PORT}/search/"
    try:
        resp = await http_client.post(url, json={"yql": yql, "timeout": "30s"})
        if resp.status_code != 200:
            print(f"  [Vespa] HTTP {resp.status_code} for sync {sync_id}", file=sys.stderr)
            return None
        data = resp.json()
        root = data.get("root", {})
        errors = root.get("errors")
        if errors:
            print(f"  [Vespa] Query error for sync {sync_id}: {errors}", file=sys.stderr)
            return None
        return root.get("fields", {}).get("totalCount", 0)
    except Exception as e:
        print(f"  [Vespa] Error for sync {sync_id}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Progress / resumability
# ---------------------------------------------------------------------------


def load_progress(path: str) -> Dict[str, Dict[str, Any]]:
    """Load existing progress file (sync_id -> result row)."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p) as f:
        return json.load(f)


def save_progress(path: str, results: Dict[str, Dict[str, Any]]) -> None:
    """Save progress to JSON file."""
    with open(path, "w") as f:
        json.dump(results, f, indent=2, default=str)


def write_csv(path: str, results: Dict[str, Dict[str, Any]]) -> None:
    """Write final CSV output."""
    if not results:
        print("No results to write.")
        return

    fieldnames = [
        "sync_id",
        "organization_id",
        "source_short_name",
        "readable_collection_id",
        "status",
        "created_at",
        "pg_count",
        "arf_count",
        "vespa_count",
        "pg_vs_vespa_diff",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(results.values(), key=lambda r: r.get("created_at") or ""):
            pg = row.get("pg_count")
            vespa = row.get("vespa_count")
            row["pg_vs_vespa_diff"] = (pg - vespa) if pg is not None and vespa is not None else None
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------


async def process_sync(
    sync_info: Dict[str, Any],
    pg_counts: Dict[str, int],
    arf_service,
    http_client: Optional[httpx.AsyncClient],
    collection_id_map: Dict[str, str],
    skip_arf: bool,
    skip_vespa: bool,
) -> Dict[str, Any]:
    """Process a single sync: collect all three counts."""
    sync_id = sync_info["sync_id"]

    row = {**sync_info}
    row["pg_count"] = pg_counts.get(sync_id, 0)

    if skip_arf:
        row["arf_count"] = None
    else:
        row["arf_count"] = await get_arf_count_safe(arf_service, sync_id)

    if skip_vespa:
        row["vespa_count"] = None
    else:
        readable_cid = sync_info.get("readable_collection_id")
        collection_id = collection_id_map.get(readable_cid) if readable_cid else None
        if collection_id and http_client:
            row["vespa_count"] = await get_vespa_count(http_client, sync_id, collection_id)
        else:
            row["vespa_count"] = None

    return row


async def main(args: argparse.Namespace) -> None:
    """Run the entity count audit."""
    progress_path = f"{args.output}.json"
    csv_path = f"{args.output}.csv"

    results: Dict[str, Dict[str, Any]] = {}
    if args.resume:
        results = load_progress(args.resume)
        progress_path = args.resume
        csv_path = args.resume.replace(".json", ".csv")
        print(f"Resumed {len(results)} previously completed syncs from {args.resume}")

    # Phase 1: Fetch sync list and PG counts
    print("=" * 70)
    print("Phase 1: Fetching sync list and Postgres entity counts...")
    print("=" * 70)

    async with AsyncSessionLocal() as db:
        if args.sync_ids:
            sync_ids = [UUID(s.strip()) for s in args.sync_ids.split(",")]
            syncs = await fetch_specific_syncs(db, sync_ids)
        else:
            syncs = await fetch_all_syncs(db)

        print(f"Found {len(syncs)} syncs in Postgres")

        pending_syncs = [s for s in syncs if s["sync_id"] not in results]
        print(f"Pending (not yet audited): {len(pending_syncs)}")

        if not pending_syncs:
            print("All syncs already audited. Writing CSV...")
            write_csv(csv_path, results)
            print(f"CSV written to {csv_path}")
            return

        all_sync_ids = [UUID(s["sync_id"]) for s in pending_syncs]
        pg_counts = await fetch_pg_entity_counts(db, all_sync_ids)
        print(f"Fetched PG counts for {len(pg_counts)} syncs")

        readable_ids = [
            s["readable_collection_id"] for s in pending_syncs if s.get("readable_collection_id")
        ]
        collection_id_map = await fetch_collection_id_map(db, readable_ids)
        print(f"Resolved {len(collection_id_map)} collection ID mappings")

    # Phase 2: ARF + Vespa counts
    print(f"\n{'=' * 70}")
    print("Phase 2: Fetching ARF and Vespa counts...")
    print(f"  ARF:   {'SKIP' if args.skip_arf else 'enabled'}")
    print(f"  Vespa: {'SKIP' if args.skip_vespa else 'enabled'}")
    print(f"  Concurrency: {args.concurrency}")
    print("=" * 70)

    arf_service = None if args.skip_arf else create_arf_service()

    http_client = None
    if not args.skip_vespa:
        http_client = httpx.AsyncClient(timeout=60.0)

    semaphore = asyncio.Semaphore(args.concurrency)
    completed = 0
    total = len(pending_syncs)
    start_time = time.monotonic()

    async def process_with_limit(sync_info: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        async with semaphore:
            row = await process_sync(
                sync_info,
                pg_counts,
                arf_service,
                http_client,
                collection_id_map,
                args.skip_arf,
                args.skip_vespa,
            )
            return sync_info["sync_id"], row

    batch_size = 50
    for batch_start in range(0, total, batch_size):
        batch = pending_syncs[batch_start : batch_start + batch_size]

        tasks = [process_with_limit(s) for s in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in batch_results:
            if isinstance(result, Exception):
                print(f"  [ERROR] {result}", file=sys.stderr)
                continue
            sync_id, row = result
            results[sync_id] = row
            completed += 1

        save_progress(progress_path, results)

        elapsed = time.monotonic() - start_time
        rate = completed / elapsed if elapsed > 0 else 0
        eta = (total - completed) / rate if rate > 0 else 0
        print(
            f"  Progress: {completed}/{total} "
            f"({completed * 100 / total:.1f}%) "
            f"| {rate:.1f} syncs/s | ETA: {eta:.0f}s"
        )

    if http_client:
        await http_client.aclose()
    if arf_service and hasattr(arf_service, "_storage"):
        storage = arf_service._storage
        if hasattr(storage, "close"):
            await storage.close()

    # Phase 3: Write CSV
    print(f"\n{'=' * 70}")
    print("Phase 3: Writing CSV...")
    print("=" * 70)

    write_csv(csv_path, results)

    discrepancies = 0
    for row in results.values():
        pg = row.get("pg_count")
        vespa = row.get("vespa_count")
        if pg is not None and vespa is not None and pg != vespa:
            discrepancies += 1

    print("\nDone!")
    print(f"  Total syncs audited:  {len(results)}")
    print(f"  Discrepancies (PG != Vespa): {discrepancies}")
    print(f"  CSV:      {csv_path}")
    print(f"  Progress: {progress_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Audit entity counts across Postgres, ARF, and Vespa"
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output file prefix (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--resume",
        default=None,
        help="Path to a previous progress JSON file to resume from",
    )
    parser.add_argument(
        "--sync-ids",
        default=None,
        help="Comma-separated sync UUIDs to audit (default: all)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Max concurrent ARF/Vespa requests (default: 10)",
    )
    parser.add_argument(
        "--skip-arf",
        action="store_true",
        default=False,
        help="Skip ARF count collection",
    )
    parser.add_argument(
        "--skip-vespa",
        action="store_true",
        default=False,
        help="Skip Vespa count collection",
    )
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
