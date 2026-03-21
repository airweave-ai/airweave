"""Shared fixtures and constants for activity tests."""

from datetime import datetime, timezone

ORG_ID = "00000000-0000-0000-0000-000000000001"
SYNC_ID = "00000000-0000-0000-0000-000000000010"
SYNC_JOB_ID = "00000000-0000-0000-0000-000000000020"
COLLECTION_ID = "00000000-0000-0000-0000-000000000030"
CONNECTION_ID = "00000000-0000-0000-0000-000000000040"
SOURCE_CONNECTION_ID = "00000000-0000-0000-0000-000000000050"


def make_ctx_dict(org_id: str = ORG_ID) -> dict:
    return {
        "organization": {
            "id": org_id,
            "name": "Test Org",
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
            "modified_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        }
    }


def make_sync_dict(
    sync_id: str = SYNC_ID,
    source_connection_id: str = CONNECTION_ID,
    destination_connection_ids: list | None = None,
) -> dict:
    return {
        "id": sync_id,
        "name": "test-sync",
        "source_connection_id": source_connection_id,
        "destination_connection_ids": destination_connection_ids or [CONNECTION_ID],
        "organization_id": ORG_ID,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "modified_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "cron_schedule": None,
        "sync_config": None,
    }
