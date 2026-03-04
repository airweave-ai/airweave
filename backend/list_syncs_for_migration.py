#!/usr/bin/env python3
"""Script to list all non-orphaned syncs sorted by entity count for migration planning.

Run this script from a backend pod to get a sorted list of syncs with metadata.

Usage:
    python list_syncs_for_migration.py
"""

import asyncio
import os
import sys
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import asyncpg


async def get_postgres_connection():
    """Establish PostgreSQL connection using environment variables."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("POSTGRES_USER", "airweave")
    password = os.getenv("POSTGRES_PASSWORD")
    database = os.getenv("POSTGRES_DB", "airweave")

    if not password:
        print("ERROR: POSTGRES_PASSWORD environment variable not set")
        sys.exit(1)

    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            timeout=30.0,
        )
        print(f"✓ Connected to PostgreSQL at {host}:{port}/{database}")
        return conn
    except Exception as e:
        print(f"ERROR: Failed to connect to PostgreSQL: {e}")
        sys.exit(1)


async def get_non_orphaned_syncs(conn) -> List[Dict]:
    """Get all non-orphaned syncs with metadata.

    Returns list of dicts with:
    - sync_id
    - organization_id
    - organization_name
    - source_name (short name from source_connection)
    - collection_readable_id
    """
    query = """
        SELECT 
            s.id AS sync_id,
            s.organization_id,
            o.name AS organization_name,
            sc.source_name,
            c.readable_id AS collection_readable_id,
            s.created_at
        FROM sync s
        INNER JOIN sync_connection scn ON s.id = scn.sync_id
        INNER JOIN source_connection sc ON scn.connection_id = sc.id
        INNER JOIN organization o ON s.organization_id = o.id
        LEFT JOIN collection c ON s.collection_id = c.id
        WHERE scn.connection_type = 'source'
        ORDER BY s.created_at DESC
    """
    rows = await conn.fetch(query)

    result = []
    for row in rows:
        result.append(
            {
                "sync_id": row["sync_id"],
                "organization_id": row["organization_id"],
                "organization_name": row["organization_name"],
                "source_name": row["source_name"],
                "collection_readable_id": row["collection_readable_id"],
                "created_at": row["created_at"],
            }
        )

    return result


async def get_postgres_entity_count(conn, sync_id: UUID) -> int:
    """Get distinct entity count for a sync from PostgreSQL."""
    query = """
        SELECT COUNT(DISTINCT (entity_id, entity_definition_id))
        FROM entity
        WHERE sync_id = $1
    """
    result = await conn.fetchval(query, sync_id)
    return result or 0


async def get_arf_entity_count(sync_id: UUID) -> int:
    """Get entity count from ARF storage."""
    try:
        from airweave.platform.sync.arf.service import ArfService
        from airweave.platform.storage import storage_backend

        arf_service = ArfService(storage=storage_backend)
        count = await arf_service.get_entity_count(str(sync_id))
        return count
    except Exception:
        return 0


async def enrich_sync_with_counts(conn, sync_data: Dict) -> Dict:
    """Add entity counts to sync data."""
    sync_id = sync_data["sync_id"]

    # Get counts
    pg_count = await get_postgres_entity_count(conn, sync_id)
    arf_count = await get_arf_entity_count(sync_id)

    sync_data["pg_entity_count"] = pg_count
    sync_data["arf_entity_count"] = arf_count

    # Determine status
    if arf_count == 0 and pg_count > 0:
        sync_data["status"] = "ARF missing"
    elif pg_count > arf_count:
        sync_data["status"] = f"PG > ARF ({pg_count - arf_count})"
    else:
        sync_data["status"] = "OK"

    return sync_data


def format_number(num: int) -> str:
    """Format number with comma separators."""
    return f"{num:,}"


def truncate_string(s: Optional[str], max_len: int) -> str:
    """Truncate string to max length."""
    if s is None:
        return ""
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


async def main():
    """Main execution function."""
    print("=" * 120)
    print("Non-Orphaned Syncs - Migration Planning List")
    print("=" * 120)
    print()

    # Connect to PostgreSQL
    conn = await get_postgres_connection()

    try:
        # Get all non-orphaned syncs
        print("Fetching non-orphaned syncs from database...")
        syncs = await get_non_orphaned_syncs(conn)
        print(f"✓ Found {len(syncs)} non-orphaned syncs\n")

        if not syncs:
            print("No non-orphaned syncs found in database.")
            return

        print("Fetching entity counts (this may take a while)...")
        print()

        # Enrich with counts
        enriched_syncs = []
        for i, sync_data in enumerate(syncs, 1):
            if i % 10 == 0:
                print(f"Progress: {i}/{len(syncs)} syncs processed...")

            enriched = await enrich_sync_with_counts(conn, sync_data)
            enriched_syncs.append(enriched)

        print(f"✓ Completed processing {len(syncs)} syncs\n")

        # Sort by PostgreSQL entity count (ascending)
        enriched_syncs.sort(key=lambda x: x["pg_entity_count"])

        # Print summary statistics
        print("=" * 120)
        print("SUMMARY STATISTICS")
        print("=" * 120)
        total_syncs = len(enriched_syncs)
        total_pg_entities = sum(s["pg_entity_count"] for s in enriched_syncs)
        total_arf_entities = sum(s["arf_entity_count"] for s in enriched_syncs)
        syncs_with_issues = len([s for s in enriched_syncs if s["status"] != "OK"])

        print(f"Total non-orphaned syncs: {format_number(total_syncs)}")
        print(f"Total PostgreSQL entities: {format_number(total_pg_entities)}")
        print(f"Total ARF entities: {format_number(total_arf_entities)}")
        print(f"Syncs with ARF issues: {format_number(syncs_with_issues)}")
        print(f"Syncs OK: {format_number(total_syncs - syncs_with_issues)}")
        print()

        # Print table
        print("=" * 120)
        print("ALL NON-ORPHANED SYNCS (sorted by entity count, smallest first)")
        print("=" * 120)
        print()

        # Table header
        header = (
            f"{'#':<5} "
            f"{'Sync ID':<38} "
            f"{'Org Name':<20} "
            f"{'Source':<15} "
            f"{'PG Count':<12} "
            f"{'ARF Count':<12} "
            f"{'Status':<20}"
        )
        print(header)
        print("-" * 120)

        # Table rows
        for idx, sync in enumerate(enriched_syncs, 1):
            row = (
                f"{idx:<5} "
                f"{str(sync['sync_id']):<38} "
                f"{truncate_string(sync['organization_name'], 20):<20} "
                f"{truncate_string(sync['source_name'], 15):<15} "
                f"{format_number(sync['pg_entity_count']):<12} "
                f"{format_number(sync['arf_entity_count']):<12} "
                f"{sync['status']:<20}"
            )
            print(row)

        print()

        # Export sync IDs by size buckets
        print("=" * 120)
        print("SYNC IDS BY SIZE BUCKETS (for batch processing)")
        print("=" * 120)
        print()

        # Define buckets
        buckets = [
            (0, 100, "Tiny (0-100 entities)"),
            (101, 1000, "Small (101-1K entities)"),
            (1001, 10000, "Medium (1K-10K entities)"),
            (10001, 50000, "Large (10K-50K entities)"),
            (50001, float("inf"), "XLarge (50K+ entities)"),
        ]

        for min_size, max_size, label in buckets:
            bucket_syncs = [
                s for s in enriched_syncs if min_size <= s["pg_entity_count"] <= max_size
            ]

            if bucket_syncs:
                total_entities = sum(s["pg_entity_count"] for s in bucket_syncs)
                print(
                    f"\n{label}: {len(bucket_syncs)} syncs, {format_number(total_entities)} total entities"
                )
                print("-" * 80)
                for sync in bucket_syncs:
                    print(f"{sync['sync_id']}  # {format_number(sync['pg_entity_count'])} entities")

        print()

    finally:
        await conn.close()
        print("✓ Database connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
