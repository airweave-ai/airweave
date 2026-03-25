#!/usr/bin/env python3
"""Backfill SyncId search attribute on existing Temporal schedules.

Iterates all syncs that have a temporal_schedule_id and updates each of their
schedules (sync-, minute-sync-, daily-cleanup-) to include the SyncId search
attribute. Skips schedules that don't exist in Temporal.

Usage:
    # Dry-run (default) — shows what would be updated
    poetry run python -m scripts.backfill_schedule_search_attributes

    # Apply changes
    poetry run python -m scripts.backfill_schedule_search_attributes --apply

Prerequisites:
    - Temporal server must be running and have the SyncId search attribute
      registered (via temporal-init in docker-compose or the namespace job
      in Helm).
"""

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select
from temporalio.client import ScheduleUpdate
from temporalio.common import SearchAttributePair, TypedSearchAttributes
from temporalio.service import RPCError, RPCStatusCode

from airweave.db.session import AsyncSessionLocal
from airweave.domains.temporal.schedule_service import (
    SCHEDULE_PREFIXES,
    SYNC_ID_SEARCH_ATTRIBUTE,
)
from airweave.models.sync import Sync
from airweave.platform.temporal.client import temporal_client

MAX_CONCURRENCY = 10


async def backfill(apply: bool) -> None:
    """Backfill SyncId search attribute on all existing schedules."""
    client = await temporal_client.get_client()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Sync.id).where(Sync.temporal_schedule_id.isnot(None)))
        sync_ids: list[UUID] = list(result.scalars().all())

    print(f"Found {len(sync_ids)} syncs with temporal schedules")

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    updated = 0
    skipped = 0
    failed = 0

    async def update_schedule(sync_id: UUID, prefix: str) -> str:
        schedule_id = f"{prefix}{sync_id}"
        async with semaphore:
            try:
                handle = client.get_schedule_handle(schedule_id)
                if not apply:
                    await handle.describe()
                    print(f"  [dry-run] Would update {schedule_id}")
                    return "skipped"

                async def updater(input):
                    return ScheduleUpdate(
                        schedule=input.description.schedule,
                        search_attributes=TypedSearchAttributes(
                            [
                                SearchAttributePair(SYNC_ID_SEARCH_ATTRIBUTE, str(sync_id)),
                            ]
                        ),
                    )

                await handle.update(updater)
                print(f"  [updated] {schedule_id}")
                return "updated"
            except RPCError as e:
                if e.status == RPCStatusCode.NOT_FOUND:
                    return "skipped"
                print(f"  [error] {schedule_id}: {e}")
                return "failed"

    tasks = [
        update_schedule(sync_id, prefix) for sync_id in sync_ids for prefix in SCHEDULE_PREFIXES
    ]
    results = await asyncio.gather(*tasks)

    updated = results.count("updated")
    skipped = results.count("skipped")
    failed = results.count("failed")

    print(f"\nDone: {updated} updated, {skipped} skipped, {failed} failed")
    if not apply and updated == 0 and skipped > 0:
        print("Run with --apply to apply changes")


def main() -> None:
    """Parse arguments and run backfill."""
    parser = argparse.ArgumentParser(
        description="Backfill SyncId search attribute on Temporal schedules"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    args = parser.parse_args()
    asyncio.run(backfill(apply=args.apply))


if __name__ == "__main__":
    main()
