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
from airweave.domains.source_connections.fake_repository import FakeSourceConnectionRepository
from airweave.domains.source_connections.fake_response import FakeResponseBuilder
from airweave.domains.source_connections.service import SourceConnectionService
from airweave.domains.sources.exceptions import SourceNotFoundError
from airweave.domains.sources.fake import FakeSourceRegistry
from airweave.domains.sync_cursors.fake import FakeSyncCursorRepository
from airweave.domains.sync_jobs.fake import FakeSyncJobRepository
from airweave.domains.syncs.fake import FakeSyncRepository
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
    @patch("airweave.domains.source_connections.service.sync_service")
    async def test_returns_mapped_jobs(self, mock_sync_svc):
        sync_id = uuid4()
        sc = _make_source_conn(sync_id=sync_id)
        repo = FakeSourceConnectionRepository()
        repo.seed(sc)

        job = MagicMock()
        job.id = uuid4()
        job.status = SyncJobStatus.COMPLETED
        job.started_at = NOW
        job.completed_at = NOW
        mock_sync_svc.list_sync_jobs = AsyncMock(return_value=[job])

        svc = _make_service(sc_repo=repo)
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
