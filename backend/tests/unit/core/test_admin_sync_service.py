"""Tests for admin sync service.

Tests the admin sync listing service including query building,
bulk data fetching, and optimized destination counting.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.deps import ApiContext
from airweave.core.admin_sync_service import AdminSyncQueryBuilder, AdminSyncService
from airweave.core.shared_models import SyncJobStatus, SyncStatus
from airweave.models.sync import Sync


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db():
    """Mock database session."""
    mock = AsyncMock(spec=AsyncSession)
    mock.execute = AsyncMock()
    return mock


@pytest.fixture
def mock_ctx():
    """Mock API context."""
    mock = Mock(spec=ApiContext)
    mock.logger = MagicMock()
    mock.logger.info = MagicMock()
    mock.logger.warning = MagicMock()
    mock.logger.error = MagicMock()
    return mock


@pytest.fixture
def admin_sync_service():
    """Admin sync service instance."""
    return AdminSyncService()


@pytest.fixture
def sample_sync():
    """Create a sample sync for testing."""
    return Sync(
        id=uuid4(),
        organization_id=uuid4(),
        status=SyncStatus.ACTIVE,
        created_at=MagicMock(),
        modified_at=MagicMock(),
    )


@pytest.fixture
def sample_syncs():
    """Create multiple sample syncs."""
    org_id = uuid4()
    return [
        Sync(
            id=uuid4(),
            organization_id=org_id,
            status=SyncStatus.ACTIVE,
            created_at=MagicMock(),
            modified_at=MagicMock(),
        )
        for _ in range(3)
    ]


# ============================================================================
# AdminSyncQueryBuilder Tests
# ============================================================================


def test_query_builder_initialization():
    """Test query builder initializes with base select query."""
    builder = AdminSyncQueryBuilder()
    assert builder.query is not None
    # Query should be a select statement for Sync model
    assert str(builder.query).startswith("SELECT")


def test_query_builder_with_sync_ids():
    """Test filtering by specific sync IDs."""
    builder = AdminSyncQueryBuilder()
    sync_ids = [uuid4(), uuid4()]
    
    result = builder.with_sync_ids(sync_ids)
    
    assert result is builder  # Fluent interface
    assert "sync.id IN" in str(builder.query)


def test_query_builder_with_sync_ids_empty():
    """Test that empty sync_ids list doesn't add filter."""
    builder = AdminSyncQueryBuilder()
    original_query = str(builder.query)
    
    builder.with_sync_ids([])
    
    assert str(builder.query) == original_query


def test_query_builder_with_organization_id():
    """Test filtering by organization ID."""
    builder = AdminSyncQueryBuilder()
    org_id = uuid4()
    
    result = builder.with_organization_id(org_id)
    
    assert result is builder
    assert "sync.organization_id" in str(builder.query)


def test_query_builder_with_status():
    """Test filtering by sync status."""
    builder = AdminSyncQueryBuilder()
    
    result = builder.with_status("active")
    
    assert result is builder
    assert "sync.status" in str(builder.query)


def test_query_builder_with_invalid_status():
    """Test that invalid status makes query return nothing."""
    builder = AdminSyncQueryBuilder()
    
    builder.with_status("invalid_status")
    
    # Should add a condition that returns no results
    assert "sync.id IS NULL" in str(builder.query)


def test_query_builder_with_source_connection_filter_true():
    """Test filtering for syncs with source connection."""
    builder = AdminSyncQueryBuilder()
    
    result = builder.with_source_connection_filter(True)
    
    assert result is builder
    assert "sync.id IN" in str(builder.query)
    assert "source_connection" in str(builder.query).lower()


def test_query_builder_with_source_connection_filter_false():
    """Test filtering for orphaned syncs without source connection."""
    builder = AdminSyncQueryBuilder()
    
    result = builder.with_source_connection_filter(False)
    
    assert result is builder
    assert "sync.id NOT IN" in str(builder.query)


def test_query_builder_with_is_authenticated():
    """Test filtering by authentication status."""
    builder = AdminSyncQueryBuilder()
    
    result = builder.with_is_authenticated(True)
    
    assert result is builder
    assert "is_authenticated" in str(builder.query)


def test_query_builder_with_collection_id():
    """Test filtering by collection readable ID."""
    builder = AdminSyncQueryBuilder()
    
    result = builder.with_collection_id("my_collection")
    
    assert result is builder
    assert "readable_collection_id" in str(builder.query)


def test_query_builder_with_source_type():
    """Test filtering by source short name."""
    builder = AdminSyncQueryBuilder()
    
    result = builder.with_source_type("slack")
    
    assert result is builder
    assert "short_name" in str(builder.query)


def test_query_builder_with_last_job_status():
    """Test filtering by last job status."""
    builder = AdminSyncQueryBuilder()
    
    result = builder.with_last_job_status("completed")
    
    assert result is builder
    assert "sync_job" in str(builder.query).lower()
    assert "row_number" in str(builder.query).lower()


def test_query_builder_with_ghost_syncs_filter():
    """Test filtering for ghost syncs (consecutive failures)."""
    builder = AdminSyncQueryBuilder()
    
    result = builder.with_ghost_syncs_filter(5)
    
    assert result is builder
    assert "sync_job" in str(builder.query).lower()


def test_query_builder_with_ghost_syncs_filter_none():
    """Test that None ghost_syncs_last_n doesn't add filter."""
    builder = AdminSyncQueryBuilder()
    original_query = str(builder.query)
    
    builder.with_ghost_syncs_filter(None)
    
    assert str(builder.query) == original_query


def test_query_builder_with_tags_filter():
    """Test filtering by job tags."""
    builder = AdminSyncQueryBuilder()
    
    result = builder.with_tags_filter("tag1,tag2,tag3")
    
    assert result is builder
    assert "sync_metadata" in str(builder.query)


def test_query_builder_with_exclude_tags_filter():
    """Test excluding syncs with specific tags."""
    builder = AdminSyncQueryBuilder()
    
    result = builder.with_exclude_tags_filter("exclude_tag")
    
    assert result is builder
    assert "sync.id NOT IN" in str(builder.query)


def test_query_builder_with_pagination():
    """Test pagination with skip and limit."""
    builder = AdminSyncQueryBuilder()
    
    result = builder.with_pagination(skip=10, limit=50)
    
    assert result is builder
    query_str = str(builder.query)
    assert "LIMIT" in query_str
    assert "OFFSET" in query_str


def test_query_builder_fluent_interface():
    """Test that query builder supports fluent chaining."""
    builder = AdminSyncQueryBuilder()
    org_id = uuid4()
    
    result = (
        builder
        .with_organization_id(org_id)
        .with_status("active")
        .with_source_connection_filter(True)
        .with_pagination(0, 100)
    )
    
    assert result is builder
    assert "organization_id" in str(builder.query)
    assert "status" in str(builder.query)


def test_query_builder_build():
    """Test that build returns the constructed query."""
    builder = AdminSyncQueryBuilder()
    builder.with_organization_id(uuid4())
    
    query = builder.build()
    
    assert query is not None
    assert str(query).startswith("SELECT")


# ============================================================================
# AdminSyncService List Syncs Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_syncs_empty_result(admin_sync_service, mock_db, mock_ctx):
    """Test listing syncs when no syncs match query."""
    # Mock empty result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result
    
    sync_data_list, timings = await admin_sync_service.list_syncs_with_metadata(
        db=mock_db,
        ctx=mock_ctx,
        skip=0,
        limit=100,
    )
    
    assert sync_data_list == []
    assert "total" in timings
    assert "main_query" in timings
    assert timings["main_query"] >= 0


@pytest.mark.asyncio
async def test_list_syncs_with_metadata_success(
    admin_sync_service, mock_db, mock_ctx, sample_syncs
):
    """Test successful listing of syncs with metadata."""
    # Mock main query result
    mock_main_result = MagicMock()
    mock_main_result.scalars.return_value.all.return_value = sample_syncs
    
    # Mock all subsequent queries
    mock_empty_result = MagicMock()
    mock_empty_result.all.return_value = []
    mock_empty_result.scalars.return_value.all.return_value = []
    
    mock_db.execute.side_effect = [mock_main_result] + [mock_empty_result] * 10
    
    sync_data_list, timings = await admin_sync_service.list_syncs_with_metadata(
        db=mock_db,
        ctx=mock_ctx,
        skip=0,
        limit=100,
        include_destination_counts=False,
        include_arf_counts=False,
    )
    
    assert len(sync_data_list) == 3
    assert "total" in timings
    assert "main_query" in timings
    assert "entity_counts" in timings
    assert "last_job_info" in timings
    assert "source_connections" in timings
    assert timings["total"] > 0


@pytest.mark.asyncio
async def test_list_syncs_with_filters(admin_sync_service, mock_db, mock_ctx, sample_syncs):
    """Test listing syncs with various filters applied."""
    org_id = uuid4()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = sample_syncs
    mock_empty_result = MagicMock()
    mock_empty_result.all.return_value = []
    mock_empty_result.scalars.return_value.all.return_value = []
    mock_db.execute.side_effect = [mock_result] + [mock_empty_result] * 10
    
    sync_data_list, timings = await admin_sync_service.list_syncs_with_metadata(
        db=mock_db,
        ctx=mock_ctx,
        skip=0,
        limit=10,
        organization_id=org_id,
        status="active",
        has_source_connection=True,
        include_destination_counts=False,
        include_arf_counts=False,
    )
    
    assert len(sync_data_list) == 3
    assert timings["total"] > 0


# ============================================================================
# Entity Count Fetching Tests
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_entity_counts(admin_sync_service, mock_db, sample_syncs):
    """Test fetching entity counts for syncs."""
    sync_ids = [s.id for s in sample_syncs]
    
    # Mock query result with entity counts
    mock_row_1 = MagicMock()
    mock_row_1.sync_id = sync_ids[0]
    mock_row_1.total_count = 100
    
    mock_row_2 = MagicMock()
    mock_row_2.sync_id = sync_ids[1]
    mock_row_2.total_count = 250
    
    mock_result = MagicMock()
    mock_result.__iter__ = Mock(return_value=iter([mock_row_1, mock_row_2]))
    mock_db.execute.return_value = mock_result
    
    timings = {}
    count_map = await admin_sync_service._fetch_entity_counts(
        db=mock_db,
        sync_ids=sync_ids,
        timings=timings,
    )
    
    assert count_map[sync_ids[0]] == 100
    assert count_map[sync_ids[1]] == 250
    assert "entity_counts" in timings
    assert timings["entity_counts"] >= 0


@pytest.mark.asyncio
async def test_fetch_entity_counts_empty(admin_sync_service, mock_db):
    """Test fetching entity counts when no counts exist."""
    mock_result = MagicMock()
    mock_result.__iter__ = Mock(return_value=iter([]))
    mock_db.execute.return_value = mock_result
    
    timings = {}
    count_map = await admin_sync_service._fetch_entity_counts(
        db=mock_db,
        sync_ids=[uuid4()],
        timings=timings,
    )
    
    assert count_map == {}
    assert "entity_counts" in timings


# ============================================================================
# ARF Count Fetching Tests
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_arf_counts_disabled(admin_sync_service, mock_ctx, sample_syncs):
    """Test that ARF counts are not fetched when disabled."""
    timings = {}
    
    count_map = await admin_sync_service._fetch_arf_counts(
        syncs=sample_syncs,
        include_arf_counts=False,
        ctx=mock_ctx,
        timings=timings,
    )
    
    assert all(count is None for count in count_map.values())
    assert timings["arf_counts"] == 0


@pytest.mark.asyncio
@patch("airweave.platform.sync.arf.service.ArfService")
async def test_fetch_arf_counts_success(mock_arf_service_class, admin_sync_service, mock_ctx, sample_syncs):
    """Test successful ARF count fetching."""
    mock_arf_service = AsyncMock()
    mock_arf_service.get_entity_count = AsyncMock(return_value=50)
    mock_arf_service_class.return_value = mock_arf_service
    
    timings = {}
    
    count_map = await admin_sync_service._fetch_arf_counts(
        syncs=sample_syncs,
        include_arf_counts=True,
        ctx=mock_ctx,
        timings=timings,
    )
    
    assert all(count == 50 for count in count_map.values())
    assert timings["arf_counts"] > 0


@pytest.mark.asyncio
@patch("airweave.platform.sync.arf.service.ArfService")
async def test_fetch_arf_counts_with_failures(
    mock_arf_service_class, admin_sync_service, mock_ctx, sample_syncs
):
    """Test ARF count fetching handles individual failures gracefully."""
    mock_arf_service = AsyncMock()
    mock_arf_service.get_entity_count = AsyncMock(side_effect=Exception("ARF error"))
    mock_arf_service_class.return_value = mock_arf_service
    
    timings = {}
    
    count_map = await admin_sync_service._fetch_arf_counts(
        syncs=sample_syncs,
        include_arf_counts=True,
        ctx=mock_ctx,
        timings=timings,
    )
    
    # All counts should be None due to failures
    assert all(count is None for count in count_map.values())
    assert mock_ctx.logger.warning.called


# ============================================================================
# Last Job Info Fetching Tests
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_last_job_info(admin_sync_service, mock_db, sample_syncs):
    """Test fetching last job information for syncs."""
    sync_ids = [s.id for s in sample_syncs]
    
    # Mock last job info
    mock_row = MagicMock()
    mock_row.sync_id = sync_ids[0]
    mock_row.status = SyncJobStatus.COMPLETED
    mock_row.completed_at = MagicMock()
    mock_row.error = None
    mock_row.sync_metadata = {"tags": ["test"]}
    
    mock_result = MagicMock()
    mock_result.__iter__ = Mock(return_value=iter([mock_row]))
    mock_db.execute.return_value = mock_result
    
    timings = {}
    last_job_map = await admin_sync_service._fetch_last_job_info(
        db=mock_db,
        sync_ids=sync_ids,
        timings=timings,
    )
    
    assert sync_ids[0] in last_job_map
    assert last_job_map[sync_ids[0]]["status"] == SyncJobStatus.COMPLETED
    assert "last_job_info" in timings


# ============================================================================
# Source Connection Fetching Tests
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_source_connections(admin_sync_service, mock_db, sample_syncs):
    """Test fetching source connection info with collection IDs."""
    sync_ids = [s.id for s in sample_syncs]
    collection_id = uuid4()
    
    # Mock source connection row
    mock_row = MagicMock()
    mock_row.sync_id = sync_ids[0]
    mock_row.short_name = "slack"
    mock_row.readable_collection_id = "my_collection"
    mock_row.is_authenticated = True
    mock_row.collection_id = collection_id
    
    mock_result = MagicMock()
    mock_result.__iter__ = Mock(return_value=iter([mock_row]))
    mock_db.execute.return_value = mock_result
    
    timings = {}
    source_conn_map = await admin_sync_service._fetch_source_connections(
        db=mock_db,
        sync_ids=sync_ids,
        timings=timings,
    )
    
    assert sync_ids[0] in source_conn_map
    assert source_conn_map[sync_ids[0]]["short_name"] == "slack"
    assert source_conn_map[sync_ids[0]]["collection_id"] == collection_id
    assert "source_connections" in timings


# ============================================================================
# Destination Count Fetching Tests
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_destination_counts_disabled(
    admin_sync_service, mock_ctx, sample_syncs
):
    """Test that destination counts are not fetched when disabled."""
    source_conn_map = {}
    timings = {}
    
    count_map = await admin_sync_service._fetch_destination_counts(
        syncs=sample_syncs,
        source_conn_map=source_conn_map,
        include_counts=False,
        ctx=mock_ctx,
        timings=timings,
        is_qdrant=True,
    )
    
    assert all(count is None for count in count_map.values())
    assert timings["destination_counts_qdrant"] == 0


@pytest.mark.asyncio
async def test_fetch_destination_counts_no_collection_id(
    admin_sync_service, mock_ctx, sample_syncs
):
    """Test destination count fetching when syncs have no collection IDs."""
    source_conn_map = {s.id: {} for s in sample_syncs}  # Empty dicts = no collection_id
    timings = {}
    
    count_map = await admin_sync_service._fetch_destination_counts(
        syncs=sample_syncs,
        source_conn_map=source_conn_map,
        include_counts=True,
        ctx=mock_ctx,
        timings=timings,
        is_qdrant=True,
    )
    
    # All should be None due to missing collection IDs
    assert all(count is None for count in count_map.values())


# ============================================================================
# Build Sync Data List Tests
# ============================================================================


def test_build_sync_data_list(admin_sync_service, sample_syncs):
    """Test building the final sync data list from fetched information."""
    sync_connections = {
        sample_syncs[0].id: {
            "source": uuid4(),
            "destinations": [uuid4(), uuid4()],
        }
    }
    
    source_conn_map = {
        sample_syncs[0].id: {
            "short_name": "slack",
            "readable_collection_id": "test_collection",
            "is_authenticated": True,
            "collection_id": uuid4(),
        }
    }
    
    last_job_map = {
        sample_syncs[0].id: {
            "status": SyncJobStatus.COMPLETED,
            "completed_at": MagicMock(),
            "error": None,
            "sync_metadata": {},
        }
    }
    
    all_tags_map = {sample_syncs[0].id: ["tag1", "tag2"]}
    entity_count_map = {sample_syncs[0].id: 100}
    arf_count_map = {sample_syncs[0].id: 95}
    qdrant_count_map = {sample_syncs[0].id: 100}
    vespa_count_map = {sample_syncs[0].id: 100}
    
    sync_data_list = admin_sync_service._build_sync_data_list(
        syncs=sample_syncs,
        sync_connections=sync_connections,
        source_conn_map=source_conn_map,
        last_job_map=last_job_map,
        all_tags_map=all_tags_map,
        entity_count_map=entity_count_map,
        arf_count_map=arf_count_map,
        qdrant_count_map=qdrant_count_map,
        vespa_count_map=vespa_count_map,
    )
    
    assert len(sync_data_list) == 3
    
    # Check first sync has enriched data
    sync_dict = sync_data_list[0]
    assert "source_connection_id" in sync_dict
    assert "destination_connection_ids" in sync_dict
    assert sync_dict["total_entity_count"] == 100
    assert sync_dict["total_arf_entity_count"] == 95
    assert sync_dict["total_qdrant_entity_count"] == 100
    assert sync_dict["total_vespa_entity_count"] == 100
    assert sync_dict["source_short_name"] == "slack"
    assert sync_dict["all_tags"] == ["tag1", "tag2"]


def test_build_sync_data_list_with_missing_data(admin_sync_service, sample_syncs):
    """Test building sync data list when some data is missing."""
    # Only provide minimal data
    sync_connections = {}
    source_conn_map = {}
    last_job_map = {}
    all_tags_map = {}
    entity_count_map = {}
    arf_count_map = {}
    qdrant_count_map = {}
    vespa_count_map = {}
    
    sync_data_list = admin_sync_service._build_sync_data_list(
        syncs=sample_syncs,
        sync_connections=sync_connections,
        source_conn_map=source_conn_map,
        last_job_map=last_job_map,
        all_tags_map=all_tags_map,
        entity_count_map=entity_count_map,
        arf_count_map=arf_count_map,
        qdrant_count_map=qdrant_count_map,
        vespa_count_map=vespa_count_map,
    )
    
    assert len(sync_data_list) == 3
    
    # Check defaults are applied
    sync_dict = sync_data_list[0]
    assert sync_dict["total_entity_count"] == 0  # Default from .get()
    assert sync_dict["total_arf_entity_count"] is None
    assert sync_dict["last_job_status"] is None


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_syncs_timing_information(
    admin_sync_service, mock_db, mock_ctx, sample_syncs
):
    """Test that timing information is properly recorded."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = sample_syncs
    mock_empty_result = MagicMock()
    mock_empty_result.all.return_value = []
    mock_empty_result.scalars.return_value.all.return_value = []
    mock_db.execute.side_effect = [mock_result] + [mock_empty_result] * 10
    
    _, timings = await admin_sync_service.list_syncs_with_metadata(
        db=mock_db,
        ctx=mock_ctx,
        skip=0,
        limit=100,
        include_destination_counts=False,
        include_arf_counts=False,
    )
    
    # Verify all expected timing keys exist
    expected_keys = [
        "main_query",
        "entity_counts",
        "arf_counts",
        "last_job_info",
        "all_tags",
        "source_connections",
        "sync_connections",
        "destination_counts_qdrant",
        "destination_counts_vespa",
        "build_response",
        "total",
    ]
    
    for key in expected_keys:
        assert key in timings
        assert isinstance(timings[key], (int, float))
        assert timings[key] >= 0


# ============================================================================
# Concurrency Control Tests
# ============================================================================


def test_max_concurrent_destination_queries_constant():
    """Test that max concurrent queries constant is set appropriately."""
    assert AdminSyncService.MAX_CONCURRENT_DESTINATION_QUERIES == 10


# ============================================================================
# Qdrant Count Implementation Tests
# ============================================================================


# ============================================================================
# Vespa Count Implementation Tests
# ============================================================================


@pytest.mark.asyncio
@patch("airweave.platform.destinations.vespa.VespaDestination")
async def test_count_vespa_for_collection_success(
    mock_vespa_class, admin_sync_service, mock_ctx, sample_syncs
):
    """Test Vespa counting for a collection."""
    collection_id = uuid4()
    
    # Mock Vespa destination with _client attribute (refactored API)
    mock_vespa = AsyncMock()
    mock_client = AsyncMock()
    
    # Mock successful query response (VespaQueryResponse)
    mock_response = MagicMock()
    mock_response.total_count = 150
    mock_client.execute_query = AsyncMock(return_value=mock_response)
    
    mock_vespa._client = mock_client
    mock_vespa_class.create = AsyncMock(return_value=mock_vespa)
    
    count_map = await admin_sync_service._count_vespa_for_collection(
        collection_id=collection_id,
        syncs=sample_syncs,
        ctx=mock_ctx,
    )
    
    # Verify Vespa destination was created
    mock_vespa_class.create.assert_called_once()
    
    # Verify counts were fetched for all syncs
    assert len(count_map) == 3
    assert all(count == 150 for count in count_map.values())


@pytest.mark.asyncio
@patch("airweave.platform.destinations.vespa.VespaDestination")
async def test_count_vespa_for_collection_missing_client_attribute(
    mock_vespa_class, admin_sync_service, mock_ctx, sample_syncs
):
    """Test Vespa counting when _client attribute is missing."""
    collection_id = uuid4()
    
    # Mock Vespa destination WITHOUT _client attribute
    mock_vespa = MagicMock()
    # Don't set _client attribute
    del mock_vespa._client  # Ensure it doesn't exist
    
    mock_vespa_class.create = AsyncMock(return_value=mock_vespa)
    
    count_map = await admin_sync_service._count_vespa_for_collection(
        collection_id=collection_id,
        syncs=sample_syncs,
        ctx=mock_ctx,
    )
    
    # All counts should be None due to missing _client attribute
    assert all(count is None for count in count_map.values())
    assert mock_ctx.logger.warning.call_count == 3  # One per sync


@pytest.mark.asyncio
@patch("airweave.platform.destinations.vespa.VespaDestination")
async def test_count_vespa_for_collection_creation_failure(
    mock_vespa_class, admin_sync_service, mock_ctx, sample_syncs
):
    """Test Vespa counting when destination creation fails."""
    collection_id = uuid4()
    
    # Mock creation failure
    mock_vespa_class.create = AsyncMock(side_effect=Exception("Connection failed"))
    
    count_map = await admin_sync_service._count_vespa_for_collection(
        collection_id=collection_id,
        syncs=sample_syncs,
        ctx=mock_ctx,
    )
    
    # All counts should be None due to creation failure
    assert all(count is None for count in count_map.values())
    assert mock_ctx.logger.error.called


@pytest.mark.asyncio
@patch("airweave.platform.destinations.vespa.VespaDestination")
async def test_count_vespa_for_collection_query_failure(
    mock_vespa_class, admin_sync_service, mock_ctx, sample_syncs
):
    """Test Vespa counting when queries fail."""
    collection_id = uuid4()
    
    # Mock Vespa destination with failing queries
    mock_vespa = AsyncMock()
    mock_client = AsyncMock()
    
    # Mock VespaClient.execute_query raising an error
    mock_client.execute_query = AsyncMock(side_effect=RuntimeError("Query error"))
    
    mock_vespa._client = mock_client
    mock_vespa_class.create = AsyncMock(return_value=mock_vespa)
    
    count_map = await admin_sync_service._count_vespa_for_collection(
        collection_id=collection_id,
        syncs=sample_syncs,
        ctx=mock_ctx,
    )
    
    # All counts should be None due to query failures
    assert all(count is None for count in count_map.values())
    assert mock_ctx.logger.warning.call_count == 3  # One per sync


@pytest.mark.asyncio
@patch("airweave.platform.destinations.vespa.VespaDestination")
async def test_count_vespa_for_collection_exception_during_query(
    mock_vespa_class, admin_sync_service, mock_ctx, sample_syncs
):
    """Test Vespa counting when individual queries raise exceptions."""
    collection_id = uuid4()
    
    # Mock Vespa destination
    mock_vespa = AsyncMock()
    mock_client = AsyncMock()
    mock_client.execute_query = AsyncMock(side_effect=Exception("Query failed"))
    
    mock_vespa._client = mock_client
    mock_vespa_class.create = AsyncMock(return_value=mock_vespa)
    
    count_map = await admin_sync_service._count_vespa_for_collection(
        collection_id=collection_id,
        syncs=sample_syncs,
        ctx=mock_ctx,
    )
    
    # All counts should be None due to exceptions
    assert all(count is None for count in count_map.values())
    assert mock_ctx.logger.warning.call_count == 3


# ============================================================================
# Global Instance Test
# ============================================================================


def test_global_admin_sync_service_instance():
    """Test that the global admin_sync_service instance is available."""
    from airweave.core.admin_sync_service import admin_sync_service
    
    assert isinstance(admin_sync_service, AdminSyncService)

