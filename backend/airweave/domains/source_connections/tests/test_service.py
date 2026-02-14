"""Unit tests for SourceConnectionService.

Uses injected fakes for all repos and sub-services.
Patches remaining singletons (sync_service, temporal_service, etc.).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from airweave.api.context import ApiContext
from airweave.core.shared_models import AuthMethod, SyncJobStatus
from airweave.adapters.event_bus.fake import FakeEventBus
from airweave.domains.collections.fake import FakeCollectionRepository
from airweave.domains.connections.fake import FakeConnectionRepository
from airweave.domains.credentials.fake import FakeCredentialService
from airweave.domains.oauth.fake import FakeOAuthFlowService
from airweave.domains.source_connections.exceptions import (
    ByocRequiredError,
    InvalidAuthMethodError,
    NoSyncError,
    SourceConnectionNotFoundError,
    SyncImmediatelyNotAllowedError,
)
from airweave.domains.source_connections.fake_auth_provider import FakeAuthProviderService
from airweave.domains.source_connections.fake_helpers import FakeSourceConnectionHelpers
from airweave.domains.source_connections.fake_repository import FakeSourceConnectionRepository
from airweave.domains.source_connections.fake_response import FakeResponseBuilder
from airweave.domains.source_connections.fake_schedule_service import FakeTemporalScheduleService
from airweave.domains.source_connections.fake_sync_job_service import FakeSyncJobService
from airweave.domains.source_connections.fake_temporal import FakeTemporalService
from airweave.domains.source_connections.service import SourceConnectionService
from airweave.domains.sources.exceptions import SourceNotFoundError
from airweave.domains.sources.fake import FakeSourceRegistry
from airweave.domains.sync_cursors.fake import FakeSyncCursorRepository
from airweave.domains.sync_jobs.fake import FakeSyncJobRepository
from airweave.domains.syncs.fake import FakeSyncRepository
from airweave.domains.syncs.fake_service import FakeSyncService
from airweave.schemas.source_connection import (
    AuthenticationMethod,
    AuthProviderAuthentication,
    DirectAuthentication,
    OAuthBrowserAuthentication,
    OAuthTokenAuthentication,
)

NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> ApiContext:
    from airweave.core.logging import logger
    from airweave.schemas.organization import Organization

    org = Organization(id=uuid4(), name="Test Org", created_at=NOW, modified_at=NOW)
    return ApiContext(
        request_id="test",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        auth_metadata={},
        logger=logger,
    )


def _make_source_conn(
    *,
    id: Optional[UUID] = None,
    short_name: str = "stripe",
    sync_id: Optional[UUID] = None,
    is_authenticated: bool = True,
    connection_id: Optional[UUID] = None,
    readable_collection_id: str = "col-1",
) -> MagicMock:
    sc = MagicMock(spec=[])
    sc.id = id or uuid4()
    sc.organization_id = uuid4()
    sc.name = "Test Connection"
    sc.description = None
    sc.short_name = short_name
    sc.sync_id = sync_id
    sc.is_authenticated = is_authenticated
    sc.connection_id = connection_id
    sc.readable_collection_id = readable_collection_id
    sc.config_fields = {}
    sc.created_at = NOW
    sc.modified_at = NOW
    sc.connection_init_session_id = None
    sc.authentication_url = None
    sc.authentication_url_expiry = None
    sc.readable_auth_provider_id = None
    sc.is_active = True
    return sc


def _make_source_entry(
    short_name: str = "stripe",
    supports_continuous: bool = False,
    requires_byoc: bool = False,
    federated_search: bool = False,
    supported_auth_methods: Optional[list] = None,
):
    entry = MagicMock(spec=[])
    entry.short_name = short_name
    entry.name = short_name.title()
    entry.oauth_type = None
    entry.auth_config_ref = None
    entry.config_ref = None
    entry.supports_continuous = supports_continuous
    entry.federated_search = federated_search

    source_cls = MagicMock()
    if supported_auth_methods is None:
        source_cls.supports_auth_method = MagicMock(return_value=True)
        source_cls.get_supported_auth_methods = MagicMock(
            return_value=[AuthenticationMethod.DIRECT]
        )
    else:
        source_cls.supports_auth_method = MagicMock(
            side_effect=lambda m: m in supported_auth_methods
        )
        source_cls.get_supported_auth_methods = MagicMock(return_value=supported_auth_methods)
    source_cls.requires_byoc = requires_byoc
    entry.source_class_ref = source_cls
    return entry


def _make_service(
    sc_repo=None,
    source_registry=None,
    sync_job_repo=None,
    sync_repo=None,
    sync_cursor_repo=None,
    collection_repo=None,
    connection_repo=None,
    credential_service=None,
    oauth_flow_service=None,
    response_builder=None,
    sync_service=None,
    temporal_service=None,
    sync_job_service=None,
    temporal_schedule_service=None,
    helpers=None,
    auth_provider_service=None,
    event_bus=None,
) -> SourceConnectionService:
    return SourceConnectionService(
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        response_builder=response_builder or FakeResponseBuilder(),
        source_registry=source_registry or FakeSourceRegistry(),
        credential_service=credential_service or FakeCredentialService(),
        oauth_flow_service=oauth_flow_service or FakeOAuthFlowService(),
        collection_repo=collection_repo or FakeCollectionRepository(),
        connection_repo=connection_repo or FakeConnectionRepository(),
        sync_job_repo=sync_job_repo or FakeSyncJobRepository(),
        sync_cursor_repo=sync_cursor_repo or FakeSyncCursorRepository(),
        sync_repo=sync_repo or FakeSyncRepository(),
        sync_service=sync_service or FakeSyncService(),
        temporal_service=temporal_service or FakeTemporalService(),
        sync_job_service=sync_job_service or FakeSyncJobService(),
        temporal_schedule_service=temporal_schedule_service or FakeTemporalScheduleService(),
        helpers=helpers or FakeSourceConnectionHelpers(),
        auth_provider_service=auth_provider_service or FakeAuthProviderService(),
        event_bus=event_bus or FakeEventBus(),
    )


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


class TestGet:
    @pytest.mark.asyncio
    async def test_returns_source_connection(self):
        sc = _make_source_conn()
        repo = FakeSourceConnectionRepository()
        repo.seed(sc)
        svc = _make_service(sc_repo=repo)
        result = await svc.get(MagicMock(), id=sc.id, ctx=_make_ctx())
        assert result.id == sc.id

    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        svc = _make_service()
        with pytest.raises(SourceConnectionNotFoundError):
            await svc.get(MagicMock(), id=uuid4(), ctx=_make_ctx())


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestList:
    @pytest.mark.asyncio
    async def test_returns_items(self):
        repo = FakeSourceConnectionRepository()
        sc = _make_source_conn()
        repo.seed(sc)
        svc = _make_service(sc_repo=repo)
        result = await svc.list(MagicMock(), ctx=_make_ctx())
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_empty_returns_empty(self):
        svc = _make_service()
        result = await svc.list(MagicMock(), ctx=_make_ctx())
        assert result == []


# ---------------------------------------------------------------------------
# get_jobs
# ---------------------------------------------------------------------------


class TestGetJobs:
    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        svc = _make_service()
        with pytest.raises(SourceConnectionNotFoundError):
            await svc.get_jobs(MagicMock(), id=uuid4(), ctx=_make_ctx())

    @pytest.mark.asyncio
    async def test_no_sync_returns_empty(self):
        sc = _make_source_conn(sync_id=None)
        repo = FakeSourceConnectionRepository()
        repo.seed(sc)
        svc = _make_service(sc_repo=repo)
        result = await svc.get_jobs(MagicMock(), id=sc.id, ctx=_make_ctx())
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_mapped_jobs(self):
        sync_id = uuid4()
        sc = _make_source_conn(sync_id=sync_id)
        repo = FakeSourceConnectionRepository()
        repo.seed(sc)

        job = MagicMock(spec=[])
        job.id = uuid4()
        job.status = SyncJobStatus.COMPLETED
        job.started_at = NOW
        job.completed_at = NOW

        fake_sync_svc = FakeSyncService()
        fake_sync_svc.seed_jobs(sync_id, [job])

        svc = _make_service(sc_repo=repo, sync_service=fake_sync_svc)
        result = await svc.get_jobs(MagicMock(), id=sc.id, ctx=_make_ctx())
        assert len(result) == 1


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


class TestRun:
    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        svc = _make_service()
        with pytest.raises(SourceConnectionNotFoundError):
            await svc.run(MagicMock(), id=uuid4(), ctx=_make_ctx())

    @pytest.mark.asyncio
    async def test_no_sync_raises(self):
        sc = _make_source_conn(sync_id=None)
        repo = FakeSourceConnectionRepository()
        repo.seed(sc)
        svc = _make_service(sc_repo=repo)
        with pytest.raises(NoSyncError):
            await svc.run(MagicMock(), id=sc.id, ctx=_make_ctx())


# ---------------------------------------------------------------------------
# cancel_job
# ---------------------------------------------------------------------------


class TestCancelJob:
    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        svc = _make_service()
        with pytest.raises(SourceConnectionNotFoundError):
            await svc.cancel_job(
                MagicMock(), source_connection_id=uuid4(), job_id=uuid4(), ctx=_make_ctx()
            )

    @pytest.mark.asyncio
    async def test_no_sync_raises(self):
        sc = _make_source_conn(sync_id=None)
        repo = FakeSourceConnectionRepository()
        repo.seed(sc)
        svc = _make_service(sc_repo=repo)
        with pytest.raises(NoSyncError):
            await svc.cancel_job(
                MagicMock(), source_connection_id=sc.id, job_id=uuid4(), ctx=_make_ctx()
            )


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDelete:
    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        svc = _make_service()
        with pytest.raises(SourceConnectionNotFoundError):
            await svc.delete(MagicMock(), id=uuid4(), ctx=_make_ctx())


# ---------------------------------------------------------------------------
# _determine_auth_method (pure logic, no async)
# ---------------------------------------------------------------------------


@dataclass
class AuthMethodCase:
    desc: str
    auth: object
    expected: AuthenticationMethod


AUTH_METHOD_CASES = [
    AuthMethodCase(
        desc="None defaults to OAUTH_BROWSER",
        auth=None,
        expected=AuthenticationMethod.OAUTH_BROWSER,
    ),
    AuthMethodCase(
        desc="DirectAuthentication returns DIRECT",
        auth=DirectAuthentication(credentials={"api_key": "k"}),
        expected=AuthenticationMethod.DIRECT,
    ),
    AuthMethodCase(
        desc="OAuthTokenAuthentication returns OAUTH_TOKEN",
        auth=OAuthTokenAuthentication(access_token="tok"),
        expected=AuthenticationMethod.OAUTH_TOKEN,
    ),
    AuthMethodCase(
        desc="OAuthBrowserAuthentication without BYOC returns OAUTH_BROWSER",
        auth=OAuthBrowserAuthentication(),
        expected=AuthenticationMethod.OAUTH_BROWSER,
    ),
    AuthMethodCase(
        desc="OAuthBrowserAuthentication with client_id+secret returns OAUTH_BYOC",
        auth=OAuthBrowserAuthentication(client_id="cid", client_secret="csec"),
        expected=AuthenticationMethod.OAUTH_BYOC,
    ),
    AuthMethodCase(
        desc="OAuthBrowserAuthentication with consumer_key+secret returns OAUTH_BYOC",
        auth=OAuthBrowserAuthentication(consumer_key="ck", consumer_secret="cs"),
        expected=AuthenticationMethod.OAUTH_BYOC,
    ),
    AuthMethodCase(
        desc="AuthProviderAuthentication returns AUTH_PROVIDER",
        auth=AuthProviderAuthentication(provider_readable_id="composio-abc"),
        expected=AuthenticationMethod.AUTH_PROVIDER,
    ),
]


@pytest.mark.parametrize("case", AUTH_METHOD_CASES, ids=lambda c: c.desc)
def test_determine_auth_method(case: AuthMethodCase):
    svc = _make_service()
    obj_in = MagicMock()
    obj_in.authentication = case.auth
    result = svc._determine_auth_method(obj_in, MagicMock())
    assert result == case.expected


# ---------------------------------------------------------------------------
# create validation
# ---------------------------------------------------------------------------


class TestCreateValidation:
    @pytest.mark.asyncio
    async def test_unknown_source_raises(self):
        svc = _make_service()
        obj_in = MagicMock()
        obj_in.short_name = "nonexistent"
        obj_in.name = None
        obj_in.authentication = None
        with pytest.raises(SourceNotFoundError):
            await svc.create(MagicMock(), obj_in=obj_in, ctx=_make_ctx())

    @pytest.mark.asyncio
    async def test_unsupported_auth_method_raises(self):
        registry = FakeSourceRegistry()
        entry = _make_source_entry(
            "stripe", supported_auth_methods=[AuthenticationMethod.OAUTH_BROWSER]
        )
        registry.seed(entry)
        svc = _make_service(source_registry=registry)

        obj_in = MagicMock()
        obj_in.short_name = "stripe"
        obj_in.name = None
        obj_in.authentication = DirectAuthentication(credentials={"api_key": "k"})
        with pytest.raises(InvalidAuthMethodError):
            await svc.create(MagicMock(), obj_in=obj_in, ctx=_make_ctx())

    @pytest.mark.asyncio
    async def test_byoc_required_raises(self):
        registry = FakeSourceRegistry()
        entry = _make_source_entry("shopify", requires_byoc=True)
        registry.seed(entry)
        svc = _make_service(source_registry=registry)

        obj_in = MagicMock()
        obj_in.short_name = "shopify"
        obj_in.name = None
        obj_in.authentication = OAuthBrowserAuthentication()
        obj_in.sync_immediately = None
        with pytest.raises(ByocRequiredError):
            await svc.create(MagicMock(), obj_in=obj_in, ctx=_make_ctx())

    @pytest.mark.asyncio
    async def test_sync_immediately_with_oauth_browser_raises(self):
        registry = FakeSourceRegistry()
        entry = _make_source_entry("slack")
        registry.seed(entry)
        svc = _make_service(source_registry=registry)

        obj_in = MagicMock()
        obj_in.short_name = "slack"
        obj_in.name = None
        obj_in.authentication = OAuthBrowserAuthentication()
        obj_in.sync_immediately = True
        with pytest.raises(SyncImmediatelyNotAllowedError):
            await svc.create(MagicMock(), obj_in=obj_in, ctx=_make_ctx())


# ===========================================================================
# Happy-path tests
# ===========================================================================

# Additional imports for happy-path tests
from airweave.core.shared_models import ConnectionStatus, IntegrationType, SourceConnectionStatus
from airweave.schemas.source_connection import (
    AuthenticationDetails,
    SourceConnection as SourceConnectionSchema,
    SourceConnectionCreate,
    SourceConnectionUpdate,
)


# ---------------------------------------------------------------------------
# Shared helpers for happy-path tests
# ---------------------------------------------------------------------------


def _mock_db():
    """Create a mock db session compatible with UnitOfWork."""
    db = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.expire_all = MagicMock()
    return db


def _make_collection_mock(*, readable_id="col-1"):
    """Collection mock with all attrs for schemas.Collection.model_validate."""
    coll = MagicMock(spec=[])
    coll.id = uuid4()
    coll.name = f"Collection {readable_id}"
    coll.readable_id = readable_id
    coll.vector_size = 3072
    coll.embedding_model_name = "text-embedding-3-large"
    coll.sync_config = None
    coll.created_at = NOW
    coll.modified_at = NOW
    coll.organization_id = uuid4()
    coll.created_by_email = None
    coll.modified_by_email = None
    return coll


def _make_sync_job_mock(*, sync_id, status=SyncJobStatus.PENDING):
    """SyncJob mock with all attrs for schemas.SyncJob.model_validate."""
    job = MagicMock(spec=[])
    job.id = uuid4()
    job.organization_id = uuid4()
    job.sync_id = sync_id
    job.status = status
    job.scheduled = False
    job.entities_inserted = 0
    job.entities_updated = 0
    job.entities_deleted = 0
    job.entities_kept = 0
    job.entities_skipped = 0
    job.entities_encountered = {}
    job.started_at = None
    job.completed_at = None
    job.failed_at = None
    job.error = None
    job.access_token = None
    job.sync_config = None
    job.sync_metadata = None
    job.created_at = NOW
    job.modified_at = NOW
    job.created_by_email = None
    job.modified_by_email = None
    job.sync_name = None
    return job


# ---------------------------------------------------------------------------
# delete -- happy paths
# ---------------------------------------------------------------------------


class TestDeleteHappyPath:
    @pytest.mark.asyncio
    async def test_delete_no_sync(self):
        """Source connection with no sync_id -- simple cascade delete."""
        sc = _make_source_conn(sync_id=None, readable_collection_id="col-1")
        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc)

        coll = _make_collection_mock(readable_id="col-1")
        coll_repo = FakeCollectionRepository()
        coll_repo.seed(coll)

        svc = _make_service(sc_repo=sc_repo, collection_repo=coll_repo)
        result = await svc.delete(MagicMock(), id=sc.id, ctx=_make_ctx())

        assert result.id == sc.id
        assert sc.id not in sc_repo._store

    @pytest.mark.asyncio
    async def test_delete_with_sync_triggers_cleanup(self):
        """Source connection with sync_id -- fires Temporal cleanup workflow."""
        sync_id = uuid4()
        sc = _make_source_conn(sync_id=sync_id, readable_collection_id="col-1")
        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc)

        coll = _make_collection_mock(readable_id="col-1")
        coll_repo = FakeCollectionRepository()
        coll_repo.seed(coll)

        temporal = FakeTemporalService()
        svc = _make_service(
            sc_repo=sc_repo,
            collection_repo=coll_repo,
            temporal_service=temporal,
        )
        result = await svc.delete(MagicMock(), id=sc.id, ctx=_make_ctx())

        assert result.id == sc.id
        assert sc.id not in sc_repo._store
        # Cleanup workflow should have been started
        assert len(temporal.cleanups) == 1
        assert temporal.cleanups[0]["sync_ids"] == [str(sync_id)]


# ---------------------------------------------------------------------------
# run -- happy path
# ---------------------------------------------------------------------------


class TestRunHappyPath:
    @pytest.mark.asyncio
    async def test_run_triggers_sync_and_starts_workflow(self):
        """Run with valid sync_id triggers sync, publishes event, starts workflow."""
        sync_id = uuid4()
        sc = _make_source_conn(sync_id=sync_id, readable_collection_id="col-1")
        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc)

        # Collection that passes schemas.Collection.model_validate
        coll = _make_collection_mock(readable_id="col-1")
        coll_repo = FakeCollectionRepository()
        coll_repo.seed(coll)

        # Seed trigger result in sync service
        sync_mock = MagicMock(spec=[])
        sync_mock.id = sync_id
        sync_job_mock = _make_sync_job_mock(sync_id=sync_id)

        fake_sync_svc = FakeSyncService()
        fake_sync_svc.seed_trigger_result(sync_id, sync_mock, sync_job_mock)

        # Response builder that includes sync_id (needed by SyncLifecycleEvent)
        sc_response = SourceConnectionSchema(
            id=sc.id,
            organization_id=sc.organization_id,
            name=sc.name,
            short_name=sc.short_name,
            readable_collection_id=sc.readable_collection_id,
            status=SourceConnectionStatus.ACTIVE,
            created_at=NOW,
            modified_at=NOW,
            sync_id=sync_id,
            auth=AuthenticationDetails(
                method=AuthenticationMethod.DIRECT, authenticated=True
            ),
        )
        rb = AsyncMock()
        rb.build_response = AsyncMock(return_value=sc_response)

        temporal = FakeTemporalService()
        event_bus = FakeEventBus()

        svc = _make_service(
            sc_repo=sc_repo,
            collection_repo=coll_repo,
            sync_service=fake_sync_svc,
            response_builder=rb,
            temporal_service=temporal,
            event_bus=event_bus,
        )

        result = await svc.run(MagicMock(), id=sc.id, ctx=_make_ctx())

        assert result.source_connection_id == sc.id
        assert result.status == SyncJobStatus.PENDING
        assert len(temporal.workflows_started) == 1
        assert len(event_bus.events) == 1


# ---------------------------------------------------------------------------
# cancel_job -- happy path
# ---------------------------------------------------------------------------


class TestCancelJobHappyPath:
    @pytest.mark.asyncio
    async def test_cancel_running_job(self):
        """Cancel a RUNNING job -- sets CANCELLING, sends to Temporal."""
        sync_id = uuid4()
        sc = _make_source_conn(sync_id=sync_id)
        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc)

        job = _make_sync_job_mock(sync_id=sync_id, status=SyncJobStatus.RUNNING)
        sync_job_repo = FakeSyncJobRepository()
        sync_job_repo.seed(job)

        sync_job_svc = FakeSyncJobService()
        temporal = FakeTemporalService()

        svc = _make_service(
            sc_repo=sc_repo,
            sync_job_repo=sync_job_repo,
            sync_job_service=sync_job_svc,
            temporal_service=temporal,
        )

        db = _mock_db()
        result = await svc.cancel_job(
            db, source_connection_id=sc.id, job_id=job.id, ctx=_make_ctx()
        )

        assert result.source_connection_id == sc.id
        # CANCELLING status was sent
        assert len(sync_job_svc.status_updates) >= 1
        assert sync_job_svc.status_updates[0]["status"] == SyncJobStatus.CANCELLING
        # Temporal received cancellation
        assert str(job.id) in temporal.cancellations


# ---------------------------------------------------------------------------
# create with direct auth -- happy path
# ---------------------------------------------------------------------------


class TestCreateDirectAuth:
    @pytest.mark.asyncio
    @patch("airweave.domains.source_connections.service.business_events")
    async def test_create_direct_auth_happy_path(self, mock_events):
        """Create with DirectAuthentication -- validates, creates cred + conn + SC."""
        registry = FakeSourceRegistry()
        entry = _make_source_entry("stripe")
        entry.source_class_ref.federated_search = False
        registry.seed(entry)

        helpers = FakeSourceConnectionHelpers()

        # Enrich create_connection to produce a model_validate-compatible mock
        _orig = helpers.create_connection

        async def _rich_create(db, name, source, credential_id, ctx, uow):
            conn = await _orig(db, name, source, credential_id, ctx, uow)
            conn.name = name
            conn.readable_id = f"conn-{str(conn.id).replace('-', '')[:8]}"
            conn.short_name = getattr(source, "short_name", "test")
            conn.integration_type = IntegrationType.SOURCE
            conn.status = ConnectionStatus.ACTIVE
            conn.created_at = NOW
            conn.modified_at = NOW
            conn.organization_id = uuid4()
            conn.description = None
            conn.integration_credential_id = credential_id
            conn.created_by_email = None
            conn.modified_by_email = None
            return conn

        helpers.create_connection = _rich_create

        cred_svc = FakeCredentialService()

        svc = _make_service(
            source_registry=registry,
            helpers=helpers,
            credential_service=cred_svc,
        )

        obj_in = SourceConnectionCreate(
            short_name="stripe",
            readable_collection_id="col-1",
            name="Test Stripe",
            authentication=DirectAuthentication(credentials={"api_key": "sk_test_123"}),
            sync_immediately=False,
        )

        db = _mock_db()
        result = await svc.create(db, obj_in=obj_in, ctx=_make_ctx())

        assert result.short_name == "stripe"
        assert result.auth.authenticated is True
        # Verify helpers were called in correct order
        method_names = [c["method"] for c in helpers.calls]
        assert "get_collection" in method_names
        assert "create_connection" in method_names
        assert "create_source_connection" in method_names
        # Credential was created
        assert len(cred_svc._created_credentials) == 1


# ---------------------------------------------------------------------------
# update -- happy path
# ---------------------------------------------------------------------------


class TestUpdateHappyPath:
    @pytest.mark.asyncio
    async def test_update_name(self):
        """Update just the name field -- simplest update path."""
        sc = _make_source_conn(short_name="stripe")
        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc)

        svc = _make_service(sc_repo=sc_repo)

        obj_in = SourceConnectionUpdate(name="Updated Name")
        db = _mock_db()
        result = await svc.update(db, id=sc.id, obj_in=obj_in, ctx=_make_ctx())

        assert result.id == sc.id
        # Verify the name was updated on the underlying mock
        assert sc.name == "Updated Name"
