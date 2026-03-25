"""Coverage tests for SyncContext.lifecycle_data property."""

from datetime import datetime, timezone
from uuid import UUID

import pytest

from airweave import schemas
from airweave.core.shared_models import ConnectionStatus, IntegrationType
from airweave.domains.sync_pipeline.contexts.sync import SyncContext
from airweave.domains.syncs.types import LifecycleData

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
SYNC_ID = UUID("00000000-0000-0000-0000-000000000010")
SYNC_JOB_ID = UUID("00000000-0000-0000-0000-000000000020")
COLLECTION_ID = UUID("00000000-0000-0000-0000-000000000030")
CONNECTION_ID = UUID("00000000-0000-0000-0000-000000000040")
SC_ID = UUID("00000000-0000-0000-0000-000000000050")
VDB_META_ID = UUID("00000000-0000-0000-0000-000000000060")

TS = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _make_context() -> SyncContext:
    org = schemas.Organization(id=ORG_ID, name="Test", created_at=TS, modified_at=TS)
    sync = schemas.Sync(
        id=SYNC_ID,
        name="test",
        status="active",
        source_connection_id=CONNECTION_ID,
        destination_connection_ids=[CONNECTION_ID],
        organization_id=ORG_ID,
        created_at=TS,
        modified_at=TS,
    )
    sync_job = schemas.SyncJob(
        id=SYNC_JOB_ID,
        sync_id=SYNC_ID,
        status="pending",
        organization_id=ORG_ID,
        created_at=TS,
        modified_at=TS,
    )
    collection = schemas.CollectionRecord(
        id=COLLECTION_ID,
        name="test-collection",
        readable_id="test-collection",
        vector_db_deployment_metadata_id=VDB_META_ID,
        organization_id=ORG_ID,
        created_at=TS,
        modified_at=TS,
    )
    connection = schemas.Connection(
        id=CONNECTION_ID,
        name="test-conn",
        readable_id="test-conn",
        short_name="test_source",
        integration_type=IntegrationType.SOURCE,
        status=ConnectionStatus.ACTIVE,
        organization_id=ORG_ID,
        created_at=TS,
        modified_at=TS,
    )

    return SyncContext(
        organization=org,
        sync_id=SYNC_ID,
        sync_job_id=SYNC_JOB_ID,
        collection_id=COLLECTION_ID,
        source_connection_id=SC_ID,
        sync=sync,
        sync_job=sync_job,
        collection=collection,
        connection=connection,
        source_short_name="test_source",
    )


@pytest.mark.unit
def test_lifecycle_data_property():
    ctx = _make_context()
    ld = ctx.lifecycle_data

    assert isinstance(ld, LifecycleData)
    assert ld.organization_id == ORG_ID
    assert ld.sync_id == SYNC_ID
    assert ld.sync_job_id == SYNC_JOB_ID
    assert ld.collection_id == COLLECTION_ID
    assert ld.source_connection_id == SC_ID
    assert ld.source_type == "test_source"
    assert ld.collection_name == "test-collection"
    assert ld.collection_readable_id == "test-collection"
