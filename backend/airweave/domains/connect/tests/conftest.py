"""Domain-specific fixtures for Connect tests."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.connect.service import ConnectService
from airweave.domains.organizations.fakes.repository import FakeOrganizationRepository
from airweave.domains.source_connections.fakes.service import FakeSourceConnectionService
from airweave.domains.sources.fakes.service import FakeSourceService
from airweave.domains.syncs.fakes.sync_job_repository import FakeSyncJobRepository
from airweave.schemas.connect_session import ConnectSessionContext, ConnectSessionMode
from airweave.schemas.organization import Organization

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()
SESSION_ID = uuid4()
COLLECTION_ID = "test-collection-abc"


def make_org(org_id=ORG_ID) -> Organization:
    return Organization(id=str(org_id), name="Test Org", created_at=NOW, modified_at=NOW)


def make_session(
    mode: ConnectSessionMode = ConnectSessionMode.ALL,
    allowed_integrations=None,
    end_user_id=None,
    org_id=ORG_ID,
    collection_id=COLLECTION_ID,
) -> ConnectSessionContext:
    return ConnectSessionContext(
        session_id=SESSION_ID,
        organization_id=org_id,
        collection_id=collection_id,
        allowed_integrations=allowed_integrations,
        mode=mode,
        end_user_id=end_user_id,
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )


def make_ctx(org_id=ORG_ID) -> ApiContext:
    org = make_org(org_id)
    return ApiContext(
        request_id="test-req",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        logger=logger.with_context(request_id="test-req"),
    )


@pytest.fixture
def org_repo():
    repo = FakeOrganizationRepository()
    repo.seed(ORG_ID, make_org())
    return repo


@pytest.fixture
def sc_service(fake_sync_lifecycle):
    return FakeSourceConnectionService(sync_lifecycle=fake_sync_lifecycle)


@pytest.fixture
def source_service():
    return FakeSourceService()


@pytest.fixture
def collection_repo():
    return FakeCollectionRepository()


@pytest.fixture
def sync_job_repo():
    return FakeSyncJobRepository()


@pytest.fixture
def connect_service(org_repo, sc_service, source_service, collection_repo, sync_job_repo):
    return ConnectService(
        source_connection_service=sc_service,
        source_service=source_service,
        org_repo=org_repo,
        collection_repo=collection_repo,
        sync_job_repo=sync_job_repo,
    )
