"""Unit tests for ResponseBuilder.

Covers:
- build_response (auth, schedule, sync, entities, federated search, status)
- build_list_item (status computation, field passthrough)
- map_sync_job (duration, entity counts, error, missing attributes)
- SourceConnectionStats.from_dict (happy path, edge cases, strict keys)

Uses table-driven tests wherever possible.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import pytest

from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod, SourceConnectionStatus, SyncJobStatus
from airweave.domains.connections.fakes.repository import FakeConnectionRepository
from airweave.domains.credentials.fakes.repository import FakeIntegrationCredentialRepository
from airweave.domains.entities.fakes.entity_count_repository import FakeEntityCountRepository
from airweave.domains.source_connections.fakes.repository import FakeSourceConnectionRepository
from airweave.domains.source_connections.response import ResponseBuilder
from airweave.domains.source_connections.types import LastJobInfo, SourceConnectionStats
from airweave.domains.sources.fakes.registry import FakeSourceRegistry
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.domains.syncs.fakes.sync_job_repository import FakeSyncJobRepository
from airweave.platform.configs._base import Fields
from airweave.schemas.entity_count import EntityCountWithDefinition
from airweave.schemas.organization import Organization
from airweave.schemas.source_connection import AuthenticationMethod

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> ApiContext:
    """Build a minimal ApiContext for tests."""
    org = Organization(
        id=str(ORG_ID),
        name="Test Org",
        created_at=NOW,
        modified_at=NOW,
        enabled_features=[],
    )
    return ApiContext(
        request_id="test-req-001",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        auth_metadata={},
        logger=logger.with_context(request_id="test-req-001"),
    )


def _make_source_conn(
    *,
    is_authenticated: bool = True,
    sync_id=None,
    connection_id=None,
    config_fields=None,
    readable_auth_provider_id=None,
    connection_init_session_id=None,
    short_name: str = "slack",
    is_active: bool = True,
):
    """Build a lightweight ORM-like SourceConnection stand-in."""
    return SimpleNamespace(
        id=uuid4(),
        organization_id=ORG_ID,
        name="Test Connection",
        description="A test connection",
        short_name=short_name,
        readable_collection_id="col-test-123",
        is_authenticated=is_authenticated,
        is_active=is_active,
        sync_id=sync_id,
        connection_id=connection_id,
        config_fields=config_fields,
        readable_auth_provider_id=readable_auth_provider_id,
        connection_init_session_id=connection_init_session_id,
        created_at=NOW,
        modified_at=NOW,
    )


def _make_sync_job(
    *,
    status=SyncJobStatus.COMPLETED,
    started_at=None,
    completed_at=None,
    entities_inserted=10,
    entities_updated=5,
    entities_deleted=2,
    entities_skipped=1,
    error=None,
):
    """Build a lightweight sync job ORM stand-in."""
    return SimpleNamespace(
        id=uuid4(),
        status=status,
        started_at=started_at or NOW,
        completed_at=completed_at,
        entities_inserted=entities_inserted,
        entities_updated=entities_updated,
        entities_deleted=entities_deleted,
        entities_skipped=entities_skipped,
        error=error,
    )


def _make_registry_entry(
    short_name: str = "slack",
    *,
    federated_search: bool = False,
) -> SourceRegistryEntry:
    """Build a minimal SourceRegistryEntry for tests."""
    return SourceRegistryEntry(
        short_name=short_name,
        name=short_name.capitalize(),
        description=f"Test {short_name}",
        class_name=f"{short_name.capitalize()}Source",
        source_class_ref=type(short_name, (), {}),
        config_ref=None,
        auth_config_ref=None,
        auth_fields=Fields(fields=[]),
        config_fields=Fields(fields=[]),
        supported_auth_providers=[],
        runtime_auth_all_fields=[],
        runtime_auth_optional_fields=set(),
        auth_methods=["direct"],
        oauth_type=None,
        requires_byoc=False,
        supports_continuous=False,
        federated_search=federated_search,
        supports_temporal_relevance=True,
        supports_access_control=False,
        rate_limit_level=None,
        feature_flag=None,
        labels=None,
        output_entity_definitions=[],
    )


def _make_entity_count(name: str = "document", count: int = 100) -> EntityCountWithDefinition:
    """Build a minimal EntityCountWithDefinition."""
    return EntityCountWithDefinition(
        count=count,
        entity_definition_id=uuid4(),
        entity_definition_name=name,
        entity_definition_type="default",
        entity_definition_description=None,
        modified_at=NOW,
    )


def _make_stats(
    *,
    is_authenticated: bool = True,
    is_active: bool = True,
    last_job_status: Optional[SyncJobStatus] = None,
    last_job_completed_at: Optional[datetime] = None,
    entity_count: int = 0,
    authentication_method: Optional[str] = None,
    federated_search: bool = False,
) -> SourceConnectionStats:
    """Build a SourceConnectionStats with sensible defaults."""
    last_job = (
        LastJobInfo(status=last_job_status, completed_at=last_job_completed_at)
        if last_job_status
        else None
    )
    return SourceConnectionStats(
        id=uuid4(),
        name="Test",
        short_name="test",
        readable_collection_id="col-123",
        created_at=NOW,
        modified_at=NOW,
        is_authenticated=is_authenticated,
        readable_auth_provider_id=None,
        connection_init_session_id=None,
        is_active=is_active,
        authentication_method=authentication_method,
        last_job=last_job,
        entity_count=entity_count,
        federated_search=federated_search,
    )


class BuilderFixture:
    """Bundles a ResponseBuilder with its injectable fakes for easy seeding."""

    def __init__(self):
        self.sc_repo = FakeSourceConnectionRepository()
        self.connection_repo = FakeConnectionRepository()
        self.credential_repo = FakeIntegrationCredentialRepository()
        self.source_registry = FakeSourceRegistry()
        self.entity_count_repo = FakeEntityCountRepository()
        self.sync_job_repo = FakeSyncJobRepository()
        self.builder = ResponseBuilder(
            sc_repo=self.sc_repo,
            connection_repo=self.connection_repo,
            credential_repo=self.credential_repo,
            source_registry=self.source_registry,
            entity_count_repo=self.entity_count_repo,
            sync_job_repo=self.sync_job_repo,
        )


def _fixture() -> BuilderFixture:
    return BuilderFixture()


# ===========================================================================
# build_response — core field passthrough
# ===========================================================================


@pytest.mark.asyncio
async def test_build_response_minimal_authenticated():
    """Authenticated connection with no sync_id → schedule/sync/entities all None."""
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))
    sc = _make_source_conn(is_authenticated=True)

    result = await f.builder.build_response(None, sc, _make_ctx())

    assert result.id == sc.id
    assert result.organization_id == ORG_ID
    assert result.name == "Test Connection"
    assert result.short_name == "slack"
    assert result.readable_collection_id == "col-test-123"
    assert result.created_at == NOW
    assert result.modified_at == NOW
    assert result.auth.authenticated is True
    assert result.schedule is None
    assert result.sync is None
    assert result.entities is None
    assert result.federated_search is False


@pytest.mark.asyncio
async def test_build_response_auth_url_override():
    """auth_url_override takes precedence, no init session lookup needed."""
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))
    expiry = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    sc = _make_source_conn(is_authenticated=False)

    result = await f.builder.build_response(
        None, sc, _make_ctx(),
        auth_url_override="https://oauth.example.com/authorize",
        auth_url_expiry_override=expiry,
    )

    assert result.auth.auth_url == "https://oauth.example.com/authorize"
    assert result.auth.auth_url_expires == expiry
    assert result.auth.redirect_url is None


@pytest.mark.asyncio
async def test_build_response_auth_url_override_without_expiry():
    """auth_url_override without expiry → auth_url set, auth_url_expires None."""
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))
    sc = _make_source_conn(is_authenticated=False)

    result = await f.builder.build_response(
        None, sc, _make_ctx(),
        auth_url_override="https://oauth.example.com/authorize",
    )

    assert result.auth.auth_url == "https://oauth.example.com/authorize"
    assert result.auth.auth_url_expires is None


@pytest.mark.asyncio
async def test_build_response_init_session_resolves_via_repo():
    """connection_init_session_id → repo lookup → auth_url/redirect_url populated."""
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))
    session_id = uuid4()
    redirect_code = "redir-abc-123"
    redirect_expiry = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

    init_session = SimpleNamespace(
        overrides={"redirect_url": "https://app.example.com/callback"},
        redirect_session=SimpleNamespace(code=redirect_code, expires_at=redirect_expiry),
    )
    f.sc_repo.seed_init_session(session_id, init_session)

    sc = _make_source_conn(
        is_authenticated=False,
        connection_init_session_id=session_id,
    )
    result = await f.builder.build_response(None, sc, _make_ctx())

    assert redirect_code in result.auth.auth_url
    assert result.auth.auth_url_expires == redirect_expiry
    assert result.auth.redirect_url == "https://app.example.com/callback"


@pytest.mark.asyncio
async def test_build_response_init_session_not_found():
    """connection_init_session_id set but not in repo → all auth urls None."""
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))
    sc = _make_source_conn(
        is_authenticated=False,
        connection_init_session_id=uuid4(),
    )
    result = await f.builder.build_response(None, sc, _make_ctx())

    assert result.auth.auth_url is None
    assert result.auth.auth_url_expires is None
    assert result.auth.redirect_url is None


@pytest.mark.asyncio
async def test_build_response_init_session_not_found_uses_auth_url_fallback():
    """If init session lookup misses, fallback auth_url attributes are still honored."""
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))
    expiry = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    sc = _make_source_conn(
        is_authenticated=False,
        connection_init_session_id=uuid4(),
    )
    sc.authentication_url = "https://api.example.com/source-connections/authorize/abcd1234"
    sc.authentication_url_expiry = expiry

    result = await f.builder.build_response(None, sc, _make_ctx())

    assert result.auth.auth_url == sc.authentication_url
    assert result.auth.auth_url_expires == expiry


@pytest.mark.asyncio
async def test_build_response_config_fields_passthrough():
    """Config fields on ORM → passed through; None → None."""
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))

    sc_with = _make_source_conn(config_fields={"repo": "org/repo"})
    result_with = await f.builder.build_response(None, sc_with, _make_ctx())
    assert result_with.config == {"repo": "org/repo"}

    sc_without = _make_source_conn(config_fields=None)
    result_without = await f.builder.build_response(None, sc_without, _make_ctx())
    assert result_without.config is None


# ===========================================================================
# build_response — auth method resolution (table-driven)
# ===========================================================================


@dataclass
class AuthMethodViaCredentialCase:
    """Credential authentication_method string → expected AuthenticationMethod enum."""

    desc: str
    credential_method: str
    expect: AuthenticationMethod


AUTH_CREDENTIAL_CASES = [
    AuthMethodViaCredentialCase("oauth_token", "oauth_token", AuthenticationMethod.OAUTH_TOKEN),
    AuthMethodViaCredentialCase(
        "oauth_browser", "oauth_browser", AuthenticationMethod.OAUTH_BROWSER
    ),
    AuthMethodViaCredentialCase("oauth_byoc", "oauth_byoc", AuthenticationMethod.OAUTH_BYOC),
    AuthMethodViaCredentialCase("direct", "direct", AuthenticationMethod.DIRECT),
    AuthMethodViaCredentialCase(
        "auth_provider", "auth_provider", AuthenticationMethod.AUTH_PROVIDER
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", AUTH_CREDENTIAL_CASES, ids=lambda c: c.desc)
async def test_auth_method_via_credential(case: AuthMethodViaCredentialCase):
    """Connection → credential with known method → correct enum."""
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))

    conn_id, cred_id = uuid4(), uuid4()
    f.connection_repo.seed(conn_id, SimpleNamespace(id=conn_id, integration_credential_id=cred_id))
    f.credential_repo.seed(cred_id, SimpleNamespace(authentication_method=case.credential_method))

    sc = _make_source_conn(connection_id=conn_id)
    result = await f.builder.build_response(None, sc, _make_ctx())

    assert result.auth.method == case.expect


@dataclass
class AuthMethodFallbackCase:
    """Cases where credential lookup does not resolve, falling back to determine_auth_method."""

    desc: str
    readable_auth_provider_id: Optional[str]
    connection_id: Optional[UUID]
    credential_method: Optional[str]  # None = no credential seeded
    has_credential_id: bool  # whether connection has integration_credential_id
    is_authenticated: bool
    expect: AuthenticationMethod


AUTH_FALLBACK_CASES = [
    AuthMethodFallbackCase(
        desc="auth_provider_id set → AUTH_PROVIDER",
        readable_auth_provider_id="composio-abc",
        connection_id=None,
        credential_method=None,
        has_credential_id=False,
        is_authenticated=True,
        expect=AuthenticationMethod.AUTH_PROVIDER,
    ),
    AuthMethodFallbackCase(
        desc="unknown credential method → fallback DIRECT (authenticated)",
        readable_auth_provider_id=None,
        connection_id="GENERATE",
        credential_method="some_future_method",
        has_credential_id=True,
        is_authenticated=True,
        expect=AuthenticationMethod.DIRECT,
    ),
    AuthMethodFallbackCase(
        desc="connection has no credential → fallback DIRECT (authenticated)",
        readable_auth_provider_id=None,
        connection_id="GENERATE",
        credential_method=None,
        has_credential_id=False,
        is_authenticated=True,
        expect=AuthenticationMethod.DIRECT,
    ),
    AuthMethodFallbackCase(
        desc="connection not in repo → fallback OAUTH_BROWSER (unauthenticated)",
        readable_auth_provider_id=None,
        connection_id="MISSING",
        credential_method=None,
        has_credential_id=False,
        is_authenticated=False,
        expect=AuthenticationMethod.OAUTH_BROWSER,
    ),
    AuthMethodFallbackCase(
        desc="no connection_id, authenticated → DIRECT",
        readable_auth_provider_id=None,
        connection_id=None,
        credential_method=None,
        has_credential_id=False,
        is_authenticated=True,
        expect=AuthenticationMethod.DIRECT,
    ),
    AuthMethodFallbackCase(
        desc="no connection_id, unauthenticated → OAUTH_BROWSER",
        readable_auth_provider_id=None,
        connection_id=None,
        credential_method=None,
        has_credential_id=False,
        is_authenticated=False,
        expect=AuthenticationMethod.OAUTH_BROWSER,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", AUTH_FALLBACK_CASES, ids=lambda c: c.desc)
async def test_auth_method_fallback(case: AuthMethodFallbackCase):
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))

    conn_id = None
    if case.connection_id == "GENERATE":
        conn_id = uuid4()
        cred_id = uuid4() if case.has_credential_id else None
        f.connection_repo.seed(
            conn_id,
            SimpleNamespace(id=conn_id, integration_credential_id=cred_id),
        )
        if cred_id and case.credential_method:
            f.credential_repo.seed(
                cred_id, SimpleNamespace(authentication_method=case.credential_method)
            )
    elif case.connection_id == "MISSING":
        conn_id = uuid4()

    sc = _make_source_conn(
        connection_id=conn_id,
        is_authenticated=case.is_authenticated,
        readable_auth_provider_id=case.readable_auth_provider_id,
    )
    result = await f.builder.build_response(None, sc, _make_ctx())

    assert result.auth.method == case.expect


# ===========================================================================
# build_response — auth details fields
# ===========================================================================


@dataclass
class AuthDetailsCase:
    desc: str
    is_authenticated: bool
    readable_auth_provider_id: Optional[str]
    expect_authenticated_at_set: bool
    expect_provider_id: Optional[str]


AUTH_DETAILS_CASES = [
    AuthDetailsCase(
        desc="authenticated → authenticated_at = created_at",
        is_authenticated=True,
        readable_auth_provider_id=None,
        expect_authenticated_at_set=True,
        expect_provider_id=None,
    ),
    AuthDetailsCase(
        desc="unauthenticated → no authenticated_at",
        is_authenticated=False,
        readable_auth_provider_id=None,
        expect_authenticated_at_set=False,
        expect_provider_id=None,
    ),
    AuthDetailsCase(
        desc="auth provider → provider_id set",
        is_authenticated=True,
        readable_auth_provider_id="composio-abc123",
        expect_authenticated_at_set=True,
        expect_provider_id="composio-abc123",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", AUTH_DETAILS_CASES, ids=lambda c: c.desc)
async def test_auth_details(case: AuthDetailsCase):
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))
    sc = _make_source_conn(
        is_authenticated=case.is_authenticated,
        readable_auth_provider_id=case.readable_auth_provider_id,
    )
    result = await f.builder.build_response(None, sc, _make_ctx())

    assert result.auth.authenticated is case.is_authenticated
    if case.expect_authenticated_at_set:
        assert result.auth.authenticated_at == sc.created_at
    else:
        assert result.auth.authenticated_at is None
    assert result.auth.provider_id == case.expect_provider_id
    assert result.auth.provider_readable_id == case.expect_provider_id


# ===========================================================================
# build_response — status computation (table-driven)
# ===========================================================================


@dataclass
class StatusCase:
    desc: str
    is_authenticated: bool
    is_active: bool
    job_status: Optional[SyncJobStatus]
    expect: SourceConnectionStatus


STATUS_CASES = [
    StatusCase(
        "unauthenticated → PENDING_AUTH", False, True, None, SourceConnectionStatus.PENDING_AUTH
    ),
    StatusCase(
        "inactive → INACTIVE", True, False, SyncJobStatus.COMPLETED, SourceConnectionStatus.INACTIVE
    ),
    StatusCase(
        "running job → SYNCING", True, True, SyncJobStatus.RUNNING, SourceConnectionStatus.SYNCING
    ),
    StatusCase(
        "cancelling job → SYNCING",
        True,
        True,
        SyncJobStatus.CANCELLING,
        SourceConnectionStatus.SYNCING,
    ),
    StatusCase(
        "failed job → ERROR", True, True, SyncJobStatus.FAILED, SourceConnectionStatus.ERROR
    ),
    StatusCase(
        "completed job → ACTIVE", True, True, SyncJobStatus.COMPLETED, SourceConnectionStatus.ACTIVE
    ),
    StatusCase("no job → ACTIVE", True, True, None, SourceConnectionStatus.ACTIVE),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", STATUS_CASES, ids=lambda c: c.desc)
async def test_build_response_status(case: StatusCase):
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))
    sync_id = uuid4() if case.job_status else None
    sc = _make_source_conn(
        sync_id=sync_id,
        is_authenticated=case.is_authenticated,
        is_active=case.is_active,
    )
    if case.job_status:
        job = _make_sync_job(status=case.job_status, completed_at=NOW)
        f.sync_job_repo.seed_last_job(sync_id, job)

    result = await f.builder.build_response(None, sc, _make_ctx())

    assert result.status == case.expect


# ===========================================================================
# build_response — schedule details (table-driven)
# ===========================================================================


@dataclass
class ScheduleCase:
    desc: str
    has_sync_id: bool
    schedule_info: Optional[Dict[str, Any]]
    expect_none: bool
    expect_cron: Optional[str] = None
    expect_continuous: Optional[bool] = None


SCHEDULE_CASES = [
    ScheduleCase(
        desc="no sync_id → None",
        has_sync_id=False,
        schedule_info=None,
        expect_none=True,
    ),
    ScheduleCase(
        desc="sync_id but no info → None",
        has_sync_id=True,
        schedule_info=None,
        expect_none=True,
    ),
    ScheduleCase(
        desc="full schedule info",
        has_sync_id=True,
        schedule_info={
            "cron_expression": "0 */6 * * *",
            "next_run_at": NOW,
            "is_continuous": True,
            "cursor_field": "updated_at",
            "cursor_value": "2024-01-01",
        },
        expect_none=False,
        expect_cron="0 */6 * * *",
        expect_continuous=True,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", SCHEDULE_CASES, ids=lambda c: c.desc)
async def test_build_response_schedule(case: ScheduleCase):
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))
    sync_id = uuid4() if case.has_sync_id else None
    sc = _make_source_conn(sync_id=sync_id)
    if case.schedule_info:
        f.sc_repo.seed_schedule_info(sc.id, case.schedule_info)

    result = await f.builder.build_response(None, sc, _make_ctx())

    if case.expect_none:
        assert result.schedule is None
    else:
        assert result.schedule is not None
        assert result.schedule.cron == case.expect_cron
        assert result.schedule.continuous is case.expect_continuous
        assert result.schedule.next_run == case.schedule_info.get("next_run_at")
        assert result.schedule.cursor_field == case.schedule_info.get("cursor_field")


# ===========================================================================
# build_response — sync details (table-driven)
# ===========================================================================

T0 = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2024, 6, 1, 12, 5, 30, tzinfo=timezone.utc)


@dataclass
class SyncDetailsCase:
    desc: str
    has_sync_id: bool
    job_status: Optional[SyncJobStatus]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    entities_skipped: int
    error: Optional[str]
    expect_none: bool
    expect_duration: Optional[float] = None
    expect_successful: int = 0
    expect_failed: int = 0
    expect_entities_failed: int = 0


SYNC_DETAILS_CASES = [
    SyncDetailsCase(
        desc="no sync_id → None",
        has_sync_id=False,
        job_status=None,
        started_at=None,
        completed_at=None,
        entities_skipped=0,
        error=None,
        expect_none=True,
    ),
    SyncDetailsCase(
        desc="sync_id but no job → None",
        has_sync_id=True,
        job_status=None,
        started_at=None,
        completed_at=None,
        entities_skipped=0,
        error=None,
        expect_none=True,
    ),
    SyncDetailsCase(
        desc="completed job with duration",
        has_sync_id=True,
        job_status=SyncJobStatus.COMPLETED,
        started_at=T0,
        completed_at=T1,
        entities_skipped=3,
        error=None,
        expect_none=False,
        expect_duration=330.0,
        expect_successful=1,
        expect_failed=0,
        expect_entities_failed=3,
    ),
    SyncDetailsCase(
        desc="running job, no duration",
        has_sync_id=True,
        job_status=SyncJobStatus.RUNNING,
        started_at=T0,
        completed_at=None,
        entities_skipped=0,
        error=None,
        expect_none=False,
        expect_duration=None,
        expect_successful=0,
        expect_failed=0,
    ),
    SyncDetailsCase(
        desc="failed job with error",
        has_sync_id=True,
        job_status=SyncJobStatus.FAILED,
        started_at=T0,
        completed_at=T1,
        entities_skipped=0,
        error="Connection timeout",
        expect_none=False,
        expect_duration=330.0,
        expect_successful=0,
        expect_failed=1,
    ),
    SyncDetailsCase(
        desc="entities_skipped maps to entities_failed",
        has_sync_id=True,
        job_status=SyncJobStatus.COMPLETED,
        started_at=T0,
        completed_at=T0,
        entities_skipped=42,
        error=None,
        expect_none=False,
        expect_duration=0.0,
        expect_successful=1,
        expect_entities_failed=42,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", SYNC_DETAILS_CASES, ids=lambda c: c.desc)
async def test_build_response_sync_details(case: SyncDetailsCase):
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))
    sync_id = uuid4() if case.has_sync_id else None
    sc = _make_source_conn(sync_id=sync_id)

    if case.job_status:
        job = _make_sync_job(
            status=case.job_status,
            started_at=case.started_at,
            completed_at=case.completed_at,
            entities_skipped=case.entities_skipped,
            error=case.error,
        )
        f.sync_job_repo.seed_last_job(sync_id, job)

    result = await f.builder.build_response(None, sc, _make_ctx())

    if case.expect_none:
        assert result.sync is None
    else:
        assert result.sync is not None
        assert result.sync.last_job.duration_seconds == case.expect_duration
        assert result.sync.successful_runs == case.expect_successful
        assert result.sync.failed_runs == case.expect_failed
        assert result.sync.last_job.entities_failed == case.expect_entities_failed
        if case.error:
            assert result.sync.last_job.error == case.error


@pytest.mark.asyncio
async def test_sync_details_null_entity_counts_default_to_zero():
    """None entity count attributes on job ORM → 0 in response."""
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))
    sync_id = uuid4()
    sc = _make_source_conn(sync_id=sync_id)
    job = SimpleNamespace(
        id=uuid4(),
        status=SyncJobStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
        entities_inserted=None,
        entities_updated=None,
        entities_deleted=None,
        entities_skipped=None,
        error=None,
    )
    f.sync_job_repo.seed_last_job(sync_id, job)

    result = await f.builder.build_response(None, sc, _make_ctx())

    assert result.sync.last_job.entities_inserted == 0
    assert result.sync.last_job.entities_updated == 0
    assert result.sync.last_job.entities_deleted == 0
    assert result.sync.last_job.entities_failed == 0


# ===========================================================================
# build_response — entity summary (table-driven)
# ===========================================================================


@dataclass
class EntitySummaryCase:
    desc: str
    has_sync_id: bool
    counts: List  # list of (name, count) tuples
    expect_none: bool
    expect_total: int = 0


ENTITY_SUMMARY_CASES = [
    EntitySummaryCase("no sync_id → None", False, [], True),
    EntitySummaryCase("empty counts → None", True, [], True),
    EntitySummaryCase("single type", True, [("file", 42)], False, 42),
    EntitySummaryCase(
        "multiple types",
        True,
        [("document", 100), ("message", 250), ("attachment", 50)],
        False,
        400,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ENTITY_SUMMARY_CASES, ids=lambda c: c.desc)
async def test_build_response_entity_summary(case: EntitySummaryCase):
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("slack"))
    sync_id = uuid4() if case.has_sync_id else None
    sc = _make_source_conn(sync_id=sync_id)
    if case.has_sync_id:
        f.entity_count_repo.seed(
            sync_id, [_make_entity_count(name, cnt) for name, cnt in case.counts]
        )

    result = await f.builder.build_response(None, sc, _make_ctx())

    if case.expect_none:
        assert result.entities is None
    else:
        assert result.entities.total_entities == case.expect_total
        for name, cnt in case.counts:
            assert result.entities.by_type[name].count == cnt
            assert result.entities.by_type[name].last_updated == NOW


# ===========================================================================
# build_response — federated search (table-driven)
# ===========================================================================


@dataclass
class FederatedSearchCase:
    desc: str
    registry_federated: Optional[bool]  # None = source not in registry
    expect: bool


FEDERATED_SEARCH_CASES = [
    FederatedSearchCase("registry=True → True", True, True),
    FederatedSearchCase("registry=False → False", False, False),
    FederatedSearchCase("source not in registry → False", None, False),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", FEDERATED_SEARCH_CASES, ids=lambda c: c.desc)
async def test_build_response_federated_search(case: FederatedSearchCase):
    f = _fixture()
    short_name = "slack" if case.registry_federated is not None else "unknown"
    if case.registry_federated is not None:
        f.source_registry.seed(
            _make_registry_entry("slack", federated_search=case.registry_federated)
        )
    sc = _make_source_conn(short_name=short_name)

    result = await f.builder.build_response(None, sc, _make_ctx())

    assert result.federated_search is case.expect


# ===========================================================================
# build_response — full integration scenario
# ===========================================================================


@pytest.mark.asyncio
async def test_build_response_full_integration():
    """All sections populated: auth via credential, schedule, sync, entities."""
    f = _fixture()
    f.source_registry.seed(_make_registry_entry("github", federated_search=False))
    sync_id, conn_id, cred_id = uuid4(), uuid4(), uuid4()

    sc = _make_source_conn(
        short_name="github",
        sync_id=sync_id,
        connection_id=conn_id,
        config_fields={"repo_name": "org/repo"},
        is_authenticated=True,
    )
    f.connection_repo.seed(conn_id, SimpleNamespace(id=conn_id, integration_credential_id=cred_id))
    f.credential_repo.seed(cred_id, SimpleNamespace(authentication_method="oauth_token"))
    f.sc_repo.seed_schedule_info(sc.id, {"cron_expression": "0 0 * * *"})
    started = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    completed = datetime(2024, 6, 1, 0, 2, 0, tzinfo=timezone.utc)
    f.sync_job_repo.seed_last_job(
        sync_id, _make_sync_job(started_at=started, completed_at=completed)
    )
    f.entity_count_repo.seed(
        sync_id, [_make_entity_count("file", 500), _make_entity_count("issue", 200)]
    )

    result = await f.builder.build_response(None, sc, _make_ctx())

    assert result.auth.method == AuthenticationMethod.OAUTH_TOKEN
    assert result.auth.authenticated is True
    assert result.schedule.cron == "0 0 * * *"
    assert result.sync.last_job.duration_seconds == 120.0
    assert result.entities.total_entities == 700
    assert result.config == {"repo_name": "org/repo"}
    assert result.federated_search is False
    assert result.status == SourceConnectionStatus.ACTIVE


# ===========================================================================
# build_list_item (table-driven)
# ===========================================================================


@dataclass
class ListItemCase:
    desc: str
    is_authenticated: bool
    is_active: bool
    last_job_status: Optional[SyncJobStatus]
    entity_count: int
    authentication_method: Optional[str]
    federated_search: bool
    expect_status: SourceConnectionStatus


LIST_ITEM_CASES = [
    ListItemCase(
        "authenticated active",
        True,
        True,
        SyncJobStatus.COMPLETED,
        42,
        "direct",
        False,
        SourceConnectionStatus.ACTIVE,
    ),
    ListItemCase(
        "unauthenticated → PENDING_AUTH",
        False,
        True,
        None,
        0,
        None,
        False,
        SourceConnectionStatus.PENDING_AUTH,
    ),
    ListItemCase(
        "running → SYNCING",
        True,
        True,
        SyncJobStatus.RUNNING,
        0,
        None,
        False,
        SourceConnectionStatus.SYNCING,
    ),
    ListItemCase(
        "cancelling → SYNCING",
        True,
        True,
        SyncJobStatus.CANCELLING,
        0,
        None,
        False,
        SourceConnectionStatus.SYNCING,
    ),
    ListItemCase(
        "failed → ERROR",
        True,
        True,
        SyncJobStatus.FAILED,
        0,
        None,
        False,
        SourceConnectionStatus.ERROR,
    ),
    ListItemCase(
        "inactive → INACTIVE", True, False, None, 0, None, False, SourceConnectionStatus.INACTIVE
    ),
    ListItemCase(
        "no job → ACTIVE", True, True, None, 0, None, False, SourceConnectionStatus.ACTIVE
    ),
    ListItemCase(
        "federated_search=True passes through",
        True,
        True,
        None,
        0,
        None,
        True,
        SourceConnectionStatus.ACTIVE,
    ),
]


@pytest.mark.parametrize("case", LIST_ITEM_CASES, ids=lambda c: c.desc)
def test_build_list_item(case: ListItemCase):
    stats = _make_stats(
        is_authenticated=case.is_authenticated,
        is_active=case.is_active,
        last_job_status=case.last_job_status,
        entity_count=case.entity_count,
        authentication_method=case.authentication_method,
        federated_search=case.federated_search,
    )
    item = _fixture().builder.build_list_item(stats)

    assert item.status == case.expect_status
    assert item.short_name == stats.short_name
    assert item.entity_count == case.entity_count
    assert item.authentication_method == case.authentication_method
    assert item.federated_search is case.federated_search
    if case.last_job_status:
        assert item.last_job_status == case.last_job_status
    else:
        assert item.last_job_status is None


def test_build_list_item_preserves_all_fields():
    """All fields from the stats object are mapped correctly."""
    stats = _make_stats(
        is_authenticated=True,
        is_active=True,
        last_job_status=SyncJobStatus.COMPLETED,
        entity_count=99,
        authentication_method="direct",
        federated_search=True,
    )
    item = _fixture().builder.build_list_item(stats)

    assert item.id == stats.id
    assert item.name == "Test"
    assert item.readable_collection_id == "col-123"
    assert item.created_at == NOW
    assert item.modified_at == NOW
    assert item.entity_count == 99
    assert item.is_authenticated is True
    assert item.is_active is True
    assert item.authentication_method == "direct"
    assert item.federated_search is True


@pytest.mark.parametrize(
    "method",
    ["oauth_token", "oauth_browser", "oauth_byoc", "direct", "auth_provider"],
    ids=lambda m: m,
)
def test_build_list_item_authentication_method_passthrough(method: str):
    stats = _make_stats(authentication_method=method)
    item = _fixture().builder.build_list_item(stats)
    assert item.authentication_method == method


# ===========================================================================
# map_sync_job (table-driven)
# ===========================================================================


@dataclass
class MapJobCase:
    desc: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    entities_inserted: int
    entities_updated: int
    entities_deleted: int
    entities_skipped: int
    error: Optional[str]
    expect_duration: Optional[float]


MAP_JOB_CASES = [
    MapJobCase("completed with duration", T0, T1, 10, 5, 2, 1, None, 330.0),
    MapJobCase("running, no duration", T0, None, 10, 5, 2, 1, None, None),
    MapJobCase("pending, no duration", None, None, 0, 0, 0, 0, None, None),
    MapJobCase("zero entity counts", T0, T0, 0, 0, 0, 0, None, 0.0),
    MapJobCase("with error string", T0, T1, 10, 5, 2, 1, "Rate limit 429", 330.0),
]


@pytest.mark.parametrize("case", MAP_JOB_CASES, ids=lambda c: c.desc)
def test_map_sync_job(case: MapJobCase):
    sc_id = uuid4()
    job = SimpleNamespace(
        id=uuid4(),
        status=SyncJobStatus.COMPLETED,
        started_at=case.started_at,
        completed_at=case.completed_at,
        entities_inserted=case.entities_inserted,
        entities_updated=case.entities_updated,
        entities_deleted=case.entities_deleted,
        entities_skipped=case.entities_skipped,
        error=case.error,
    )

    result = _fixture().builder.map_sync_job(job, sc_id)

    assert result.source_connection_id == sc_id
    assert result.duration_seconds == case.expect_duration
    assert result.entities_inserted == case.entities_inserted
    assert result.entities_updated == case.entities_updated
    assert result.entities_deleted == case.entities_deleted
    assert result.entities_failed == case.entities_skipped
    assert result.error == case.error


def test_map_sync_job_preserves_all_fields():
    """Every field from a fully-populated job is mapped correctly."""
    sc_id, job_id = uuid4(), uuid4()
    job = SimpleNamespace(
        id=job_id,
        status=SyncJobStatus.FAILED,
        started_at=T0,
        completed_at=T1,
        entities_inserted=100,
        entities_updated=50,
        entities_deleted=25,
        entities_skipped=10,
        error="Connection refused",
    )
    result = _fixture().builder.map_sync_job(job, sc_id)

    assert result.id == job_id
    assert result.status == SyncJobStatus.FAILED
    assert result.started_at == T0
    assert result.completed_at == T1
    assert result.duration_seconds == 330.0
    assert result.entities_inserted == 100
    assert result.entities_updated == 50
    assert result.entities_deleted == 25
    assert result.entities_failed == 10
    assert result.error == "Connection refused"


# ===========================================================================
# SourceConnectionStats.from_dict (table-driven)
# ===========================================================================


def _full_raw_dict(**overrides) -> Dict[str, Any]:
    """Build a complete raw dict for from_dict, with optional overrides."""
    base = {
        "id": uuid4(),
        "name": "Test Source",
        "short_name": "test",
        "readable_collection_id": "col-test",
        "created_at": NOW,
        "modified_at": NOW,
        "is_authenticated": True,
        "readable_auth_provider_id": None,
        "connection_init_session_id": None,
        "is_active": True,
        "authentication_method": None,
        "last_job": None,
        "entity_count": 0,
        "federated_search": False,
    }
    base.update(overrides)
    return base


@dataclass
class FromDictCase:
    desc: str
    overrides: Dict[str, Any]
    expect_last_job_status: Optional[SyncJobStatus]
    expect_last_job_completed: Optional[datetime]
    expect_authenticated: bool
    expect_auth_method: Optional[str]


FROM_DICT_CASES = [
    FromDictCase(
        desc="happy path with completed job",
        overrides={
            "name": "Stripe",
            "is_authenticated": True,
            "authentication_method": "oauth_token",
            "last_job": {"status": SyncJobStatus.COMPLETED, "completed_at": NOW},
            "entity_count": 42,
        },
        expect_last_job_status=SyncJobStatus.COMPLETED,
        expect_last_job_completed=NOW,
        expect_authenticated=True,
        expect_auth_method="oauth_token",
    ),
    FromDictCase(
        desc="null last_job",
        overrides={"is_authenticated": False, "last_job": None},
        expect_last_job_status=None,
        expect_last_job_completed=None,
        expect_authenticated=False,
        expect_auth_method=None,
    ),
    FromDictCase(
        desc="last_job without completed_at (running)",
        overrides={
            "authentication_method": "direct",
            "last_job": {"status": SyncJobStatus.RUNNING},
        },
        expect_last_job_status=SyncJobStatus.RUNNING,
        expect_last_job_completed=None,
        expect_authenticated=True,
        expect_auth_method="direct",
    ),
    FromDictCase(
        desc="auth provider fields preserved",
        overrides={
            "readable_auth_provider_id": "composio-xyz",
            "connection_init_session_id": uuid4(),
            "authentication_method": "auth_provider",
        },
        expect_last_job_status=None,
        expect_last_job_completed=None,
        expect_authenticated=True,
        expect_auth_method="auth_provider",
    ),
]


@pytest.mark.parametrize("case", FROM_DICT_CASES, ids=lambda c: c.desc)
def test_stats_from_dict(case: FromDictCase):
    raw = _full_raw_dict(**case.overrides)
    stats = SourceConnectionStats.from_dict(raw)

    assert stats.id == raw["id"]
    assert stats.is_authenticated is case.expect_authenticated
    assert stats.authentication_method == case.expect_auth_method

    if case.expect_last_job_status:
        assert stats.last_job is not None
        assert stats.last_job.status == case.expect_last_job_status
        assert stats.last_job.completed_at == case.expect_last_job_completed
    else:
        assert stats.last_job is None

    if "readable_auth_provider_id" in case.overrides:
        assert stats.readable_auth_provider_id == case.overrides["readable_auth_provider_id"]
    if "connection_init_session_id" in case.overrides:
        assert stats.connection_init_session_id == case.overrides["connection_init_session_id"]


def test_stats_from_dict_missing_key_raises():
    """from_dict fails loudly if a required key is missing."""
    with pytest.raises(KeyError):
        SourceConnectionStats.from_dict({"id": uuid4()})


def test_stats_from_dict_last_job_missing_status_raises():
    """from_dict fails if last_job dict is present but missing status key."""
    raw = _full_raw_dict(last_job={"completed_at": NOW})
    with pytest.raises(KeyError):
        SourceConnectionStats.from_dict(raw)
