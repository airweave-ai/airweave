"""Unit tests for OAuthCallbackService.

Covers:
- complete_oauth2_callback (happy path, session errors, Salesforce instance_url)
- complete_oauth1_callback (happy path, session errors, bad settings type)
- _complete_connection_common (federated, cron defaults, BYOC)
- _finalize_callback (sync trigger, no-op when no sync)
- _validate_config (empty, registry miss, valid, invalid)
- _reconstruct_context (org lookup, auth method)

Uses table-driven tests wherever possible, patching crud.* for un-injected DB calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod, SyncJobStatus
from airweave.domains.oauth.callback_service import OAuthCallbackService
from airweave.domains.oauth.fakes.flow_service import FakeOAuthFlowService
from airweave.domains.oauth.types import OAuth1TokenResponse
from airweave.models.connection_init_session import ConnectionInitStatus
from airweave.platform.auth.schemas import OAuth1Settings, OAuth2TokenResponse
from airweave.schemas.organization import Organization

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()
SESSION_ID = uuid4()
SOURCE_CONN_SHELL_ID = uuid4()
CONNECTION_ID = uuid4()
CREDENTIAL_ID = uuid4()
SYNC_ID = uuid4()
SYNC_JOB_ID = uuid4()
COLLECTION_ID = uuid4()

MODULE = "airweave.domains.oauth.callback_service"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> ApiContext:
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


def _make_init_session(
    *,
    short_name: str = "slack",
    status: ConnectionInitStatus = ConnectionInitStatus.PENDING,
    overrides: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    state: str = "state-abc",
    oauth_token: str = "req-tok",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=SESSION_ID,
        organization_id=ORG_ID,
        short_name=short_name,
        status=status,
        state=state,
        overrides=overrides or {},
        payload=payload or {"name": "My Conn", "config": None},
        oauth_token=oauth_token,
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )


def _make_source(
    short_name: str = "slack",
    name: str = "Slack",
    auth_config_class: Optional[str] = None,
    oauth_type: Optional[str] = "with_refresh",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        short_name=short_name,
        name=name,
        auth_config_class=auth_config_class,
        oauth_type=oauth_type,
    )


def _make_source_conn_shell(**overrides) -> SimpleNamespace:
    defaults = dict(
        id=SOURCE_CONN_SHELL_ID,
        connection_id=None,
        sync_id=None,
        readable_collection_id="col-test-123",
        connection_init_session_id=SESSION_ID,
        is_authenticated=False,
        config_fields=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_organization_model() -> SimpleNamespace:
    return SimpleNamespace(
        id=ORG_ID,
        name="Test Org",
        created_at=NOW,
        modified_at=NOW,
        enabled_features=[],
    )


def _make_credential() -> SimpleNamespace:
    return SimpleNamespace(id=CREDENTIAL_ID)


def _make_connection() -> SimpleNamespace:
    return SimpleNamespace(
        id=CONNECTION_ID,
        integration_credential_id=CREDENTIAL_ID,
        name="Test Connection",
        readable_id="test-connection-abc",
        integration_type="source",
        status="active",
        short_name="slack",
        organization_id=ORG_ID,
        created_at=NOW,
        modified_at=NOW,
    )


def _make_collection() -> SimpleNamespace:
    return SimpleNamespace(
        id=COLLECTION_ID,
        readable_id="col-test-123",
        name="Test Collection",
        vector_size=768,
        embedding_model_name="text2vec",
        created_at=NOW,
        modified_at=NOW,
        organization_id=ORG_ID,
    )


def _make_sync() -> SimpleNamespace:
    return SimpleNamespace(
        id=SYNC_ID,
        name="Test Sync",
        organization_id=ORG_ID,
        created_at=NOW,
        modified_at=NOW,
        connection_id=CONNECTION_ID,
        collection_id=COLLECTION_ID,
        cron_schedule="0 0 * * *",
        status="active",
        source_connection_id=SOURCE_CONN_SHELL_ID,
        destination_connection_ids=[],
    )


def _make_sync_job(status: SyncJobStatus = SyncJobStatus.PENDING) -> SimpleNamespace:
    return SimpleNamespace(
        id=SYNC_JOB_ID,
        status=status,
        sync_id=SYNC_ID,
        organization_id=ORG_ID,
        created_at=NOW,
        modified_at=NOW,
    )


def _make_oauth1_settings(**overrides) -> OAuth1Settings:
    defaults = dict(
        integration_short_name="twitter",
        request_token_url="https://api.twitter.com/oauth/request_token",
        authorization_url="https://api.twitter.com/oauth/authorize",
        access_token_url="https://api.twitter.com/oauth/access_token",
        consumer_key="platform-consumer-key",
        consumer_secret="platform-consumer-secret",
    )
    defaults.update(overrides)
    return OAuth1Settings(**defaults)


# ---------------------------------------------------------------------------
# Fakes (test-local)
# ---------------------------------------------------------------------------


class FakeInitSessionRepo:
    """Fake for OAuthInitSessionRepositoryProtocol with seeding."""

    def __init__(self) -> None:
        self._by_state: Dict[str, Any] = {}
        self._by_oauth_token: Dict[str, Any] = {}
        self._mark_completed_calls: List[tuple] = []

    def seed_by_state(self, state: str, session: Any) -> None:
        self._by_state[state] = session

    def seed_by_oauth_token(self, token: str, session: Any) -> None:
        self._by_oauth_token[token] = session

    async def get_by_state_no_auth(self, db, *, state: str) -> Any:
        return self._by_state.get(state)

    async def get_by_oauth_token_no_auth(self, db, *, oauth_token: str) -> Any:
        return self._by_oauth_token.get(oauth_token)

    async def mark_completed(self, db, *, session_id, final_connection_id, ctx) -> None:
        self._mark_completed_calls.append((session_id, final_connection_id))


class FakeResponseBuilder:
    """Fake for ResponseBuilderProtocol."""

    def __init__(self) -> None:
        self._response: Any = None

    def seed(self, response: Any) -> None:
        self._response = response

    async def build_response(self, db, source_conn, ctx, **kwargs) -> Any:
        return self._response or SimpleNamespace(
            id=source_conn.id,
            name="built-response",
        )


class FakeSourceRegistry:
    """Fake for SourceRegistryProtocol."""

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    def seed(self, short_name: str, entry: Any) -> None:
        self._store[short_name] = entry

    def get(self, short_name: str) -> Any:
        if short_name not in self._store:
            raise KeyError(f"Source {short_name} not found in registry")
        return self._store[short_name]


class StubSourceClass:
    """Minimal stub for source_class_ref used by callback service."""

    federated_search = False
    supports_continuous = False

    @classmethod
    async def create(cls, access_token=None, config=None):
        return cls()

    def set_logger(self, _):
        pass

    async def validate(self):
        return True


class FederatedSourceClass(StubSourceClass):
    federated_search = True


class ContinuousSourceClass(StubSourceClass):
    supports_continuous = True


def _make_registry_entry(
    source_class=StubSourceClass, config_ref=None
) -> SimpleNamespace:
    return SimpleNamespace(
        source_class_ref=source_class,
        config_ref=config_ref,
    )


# ---------------------------------------------------------------------------
# Deps + patching helper
# ---------------------------------------------------------------------------


class Deps:
    """Bundles fakes for OAuthCallbackService constructor."""

    def __init__(self) -> None:
        self.flow_svc = FakeOAuthFlowService()
        self.init_session_repo = FakeInitSessionRepo()
        self.response_builder = FakeResponseBuilder()
        self.source_registry = FakeSourceRegistry()

    def build(self) -> OAuthCallbackService:
        return OAuthCallbackService(
            oauth_flow_service=self.flow_svc,
            init_session_repo=self.init_session_repo,
            response_builder=self.response_builder,
            source_registry=self.source_registry,
            event_bus=None,
        )


class CrudMocks:
    """Structured holder for patched crud mocks."""

    def __init__(self):
        self.organization_get = AsyncMock()
        self.source_get_by_short_name = AsyncMock()
        self.source_connection_get_by_query = AsyncMock()
        self.source_connection_update = AsyncMock()
        self.integration_credential_create = AsyncMock()
        self.connection_create = AsyncMock()
        self.collection_get_by_readable_id = AsyncMock()
        self.sync_get = AsyncMock()
        self.sync_job_get_all = AsyncMock()
        self.connection_get = AsyncMock()
        self.encrypt = MagicMock(return_value="encrypted-blob")

    def configure_happy_path(
        self,
        source=None,
        shell=None,
        credential=None,
        connection=None,
        collection=None,
        sync=None,
        sync_job=None,
    ):
        source = source or _make_source()
        shell = shell or _make_source_conn_shell()
        credential = credential or _make_credential()
        connection = connection or _make_connection()
        collection = collection or _make_collection()

        self.organization_get.return_value = _make_organization_model()
        self.source_get_by_short_name.return_value = source
        self.source_connection_get_by_query.return_value = shell

        self.integration_credential_create.return_value = credential
        self.connection_create.return_value = connection
        self.collection_get_by_readable_id.return_value = collection

        async def update_side_effect(session, *, db_obj, obj_in, ctx, uow):
            for k, v in obj_in.items():
                setattr(db_obj, k, v)
            return db_obj

        self.source_connection_update.side_effect = update_side_effect

        if sync:
            self.sync_get.return_value = sync
        if sync_job:
            self.sync_job_get_all.return_value = [sync_job]
        else:
            self.sync_job_get_all.return_value = []

        self.connection_get.return_value = connection


def _make_uow_mock():
    """Create a mock UnitOfWork that works as an async context manager."""
    uow = MagicMock()
    uow.session = AsyncMock()
    uow.session.flush = AsyncMock()
    uow.session.refresh = AsyncMock()
    uow.commit = AsyncMock()

    uow_class = MagicMock()
    uow_instance = MagicMock()
    uow_instance.__aenter__ = AsyncMock(return_value=uow)
    uow_instance.__aexit__ = AsyncMock(return_value=False)
    uow_class.return_value = uow_instance
    return uow_class, uow


def _apply_crud_patches(mocks: CrudMocks):
    """Return a stack of patches for all crud.* calls in callback_service."""
    return [
        patch(f"{MODULE}.crud.organization.get", mocks.organization_get),
        patch(f"{MODULE}.crud.source.get_by_short_name", mocks.source_get_by_short_name),
        patch(
            f"{MODULE}.crud.source_connection.get_by_query_and_org",
            mocks.source_connection_get_by_query,
        ),
        patch(f"{MODULE}.crud.source_connection.update", mocks.source_connection_update),
        patch(
            f"{MODULE}.crud.integration_credential.create",
            mocks.integration_credential_create,
        ),
        patch(f"{MODULE}.crud.connection.create", mocks.connection_create),
        patch(
            f"{MODULE}.crud.collection.get_by_readable_id",
            mocks.collection_get_by_readable_id,
        ),
        patch(f"{MODULE}.crud.sync.get", mocks.sync_get),
        patch(f"{MODULE}.crud.sync_job.get_all_by_sync_id", mocks.sync_job_get_all),
        patch(f"{MODULE}.crud.connection.get", mocks.connection_get),
        patch(f"{MODULE}.credentials.encrypt", mocks.encrypt),
    ]


# ===========================================================================
# complete_oauth2_callback — error paths (table-driven)
# ===========================================================================


@dataclass
class OAuth2ErrorCase:
    desc: str
    session: Any
    expect_status: int
    expect_detail_contains: str


OAUTH2_ERROR_CASES = [
    OAuth2ErrorCase(
        "session not found → 404",
        session=None,
        expect_status=404,
        expect_detail_contains="session not found",
    ),
    OAuth2ErrorCase(
        "session already completed → 400",
        session=_make_init_session(status=ConnectionInitStatus.COMPLETED),
        expect_status=400,
        expect_detail_contains="already",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", OAUTH2_ERROR_CASES, ids=lambda c: c.desc)
async def test_complete_oauth2_callback_errors(case: OAuth2ErrorCase):
    deps = Deps()
    svc = deps.build()
    db = AsyncMock()

    if case.session:
        deps.init_session_repo.seed_by_state("state-abc", case.session)

    with pytest.raises(HTTPException) as exc_info:
        await svc.complete_oauth2_callback(db, state="state-abc", code="code-xyz")

    assert exc_info.value.status_code == case.expect_status
    assert case.expect_detail_contains in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_complete_oauth2_callback_shell_not_found():
    deps = Deps()
    svc = deps.build()
    db = AsyncMock()

    session = _make_init_session()
    deps.init_session_repo.seed_by_state("state-abc", session)

    mocks = CrudMocks()
    mocks.organization_get.return_value = _make_organization_model()
    mocks.source_connection_get_by_query.return_value = None

    patches = _apply_crud_patches(mocks)
    for p in patches:
        p.start()
    try:
        with pytest.raises(HTTPException) as exc_info:
            await svc.complete_oauth2_callback(db, state="state-abc", code="code-xyz")
        assert exc_info.value.status_code == 404
        assert "shell" in exc_info.value.detail.lower()
    finally:
        for p in patches:
            p.stop()


# ===========================================================================
# complete_oauth2_callback — happy path (federated source)
# ===========================================================================


@pytest.mark.asyncio
async def test_complete_oauth2_callback_happy_federated():
    """Federated source: no sync created, sync_id=None on updated shell."""
    deps = Deps()
    svc = deps.build()
    db = AsyncMock()

    session = _make_init_session(short_name="slack")
    deps.init_session_repo.seed_by_state("state-abc", session)
    deps.flow_svc.seed_oauth2_response(OAuth2TokenResponse(access_token="tok-123"))
    deps.source_registry.seed("slack", _make_registry_entry(source_class=FederatedSourceClass))

    source = _make_source()
    shell = _make_source_conn_shell()
    credential = _make_credential()
    connection = _make_connection()
    collection = _make_collection()

    mocks = CrudMocks()
    mocks.configure_happy_path(
        source=source,
        shell=shell,
        credential=credential,
        connection=connection,
        collection=collection,
    )

    uow_class, uow = _make_uow_mock()

    patches = _apply_crud_patches(mocks)
    patches.append(patch(f"{MODULE}.UnitOfWork", uow_class))
    for p in patches:
        p.start()
    try:
        result = await svc.complete_oauth2_callback(db, state="state-abc", code="code-xyz")
    finally:
        for p in patches:
            p.stop()

    assert result is not None
    assert shell.sync_id is None
    assert shell.connection_id == CONNECTION_ID
    assert shell.is_authenticated is True

    assert len(deps.init_session_repo._mark_completed_calls) == 1
    assert deps.init_session_repo._mark_completed_calls[0][0] == SESSION_ID

    assert ("complete_oauth2_callback", "slack", "code-xyz") in deps.flow_svc._calls


# ===========================================================================
# complete_oauth2_callback — happy path (non-federated, with sync)
# ===========================================================================


@pytest.mark.asyncio
async def test_complete_oauth2_callback_happy_with_sync():
    """Non-federated source: sync + schedule created, workflow triggered."""
    deps = Deps()
    svc = deps.build()
    db = AsyncMock()

    session = _make_init_session(short_name="slack")
    deps.init_session_repo.seed_by_state("state-abc", session)
    deps.flow_svc.seed_oauth2_response(OAuth2TokenResponse(access_token="tok-123"))
    deps.source_registry.seed("slack", _make_registry_entry())

    source = _make_source()
    shell = _make_source_conn_shell()
    sync = _make_sync()
    sync_job = _make_sync_job(status=SyncJobStatus.PENDING)

    mocks = CrudMocks()
    mocks.configure_happy_path(
        source=source,
        shell=shell,
        sync=sync,
        sync_job=sync_job,
    )

    uow_class, uow = _make_uow_mock()
    helpers_mock = MagicMock()
    helpers_mock.create_sync_without_schedule = AsyncMock(return_value=(sync, sync_job))
    schedule_mock = MagicMock()
    schedule_mock.create_or_update_schedule = AsyncMock()
    temporal_svc_mock = MagicMock()
    temporal_svc_mock.run_source_connection_workflow = AsyncMock()

    patches = _apply_crud_patches(mocks)
    patches.append(patch(f"{MODULE}.UnitOfWork", uow_class))
    patches.append(
        patch(
            "airweave.core.source_connection_service_helpers.source_connection_helpers",
            helpers_mock,
        )
    )
    patches.append(
        patch(
            "airweave.platform.temporal.schedule_service.temporal_schedule_service",
            schedule_mock,
        )
    )
    patches.append(
        patch(
            "airweave.core.temporal_service.temporal_service",
            temporal_svc_mock,
        )
    )

    for p in patches:
        p.start()
    try:
        result = await svc.complete_oauth2_callback(db, state="state-abc", code="code-xyz")
    finally:
        for p in patches:
            p.stop()

    assert result is not None
    assert shell.sync_id == SYNC_ID
    assert shell.is_authenticated is True

    helpers_mock.create_sync_without_schedule.assert_awaited_once()
    schedule_mock.create_or_update_schedule.assert_awaited_once()
    temporal_svc_mock.run_source_connection_workflow.assert_awaited_once()


# ===========================================================================
# complete_oauth2_callback — Salesforce instance_url special case
# ===========================================================================


@pytest.mark.asyncio
async def test_complete_oauth2_callback_salesforce_instance_url():
    """Salesforce instance_url from token response is extracted into config."""
    deps = Deps()
    svc = deps.build()
    db = AsyncMock()

    session = _make_init_session(
        short_name="salesforce",
        payload={"name": "SF Conn", "config": None},
    )
    deps.init_session_repo.seed_by_state("state-abc", session)
    deps.flow_svc.seed_oauth2_response(
        OAuth2TokenResponse(
            access_token="sf-tok",
            instance_url="https://acme.my.salesforce.com",
        )
    )
    deps.source_registry.seed(
        "salesforce",
        _make_registry_entry(source_class=FederatedSourceClass),
    )

    source = _make_source(short_name="salesforce", name="Salesforce")
    shell = _make_source_conn_shell()
    mocks = CrudMocks()
    mocks.configure_happy_path(source=source, shell=shell)

    uow_class, uow = _make_uow_mock()
    patches = _apply_crud_patches(mocks)
    patches.append(patch(f"{MODULE}.UnitOfWork", uow_class))

    for p in patches:
        p.start()
    try:
        await svc.complete_oauth2_callback(db, state="state-abc", code="code-xyz")
    finally:
        for p in patches:
            p.stop()

    update_call = mocks.source_connection_update
    update_call.assert_awaited_once()
    _, kwargs = update_call.call_args
    obj_in = kwargs["obj_in"]
    assert obj_in.get("config_fields", {}).get("instance_url") == "acme.my.salesforce.com"


# ===========================================================================
# complete_oauth1_callback — error paths (table-driven)
# ===========================================================================


@dataclass
class OAuth1ErrorCase:
    desc: str
    session: Any
    expect_status: int
    expect_detail_contains: str


OAUTH1_ERROR_CASES = [
    OAuth1ErrorCase(
        "session not found → 404",
        session=None,
        expect_status=404,
        expect_detail_contains="session not found",
    ),
    OAuth1ErrorCase(
        "session already completed → 400",
        session=_make_init_session(status=ConnectionInitStatus.COMPLETED),
        expect_status=400,
        expect_detail_contains="already",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", OAUTH1_ERROR_CASES, ids=lambda c: c.desc)
async def test_complete_oauth1_callback_errors(case: OAuth1ErrorCase):
    deps = Deps()
    svc = deps.build()
    db = AsyncMock()

    if case.session:
        deps.init_session_repo.seed_by_oauth_token("req-tok", case.session)

    with pytest.raises(HTTPException) as exc_info:
        await svc.complete_oauth1_callback(
            db, oauth_token="req-tok", oauth_verifier="verifier-xyz"
        )

    assert exc_info.value.status_code == case.expect_status
    assert case.expect_detail_contains in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_complete_oauth1_callback_not_oauth1_settings():
    """When integration_settings returns OAuth2Settings instead of OAuth1Settings → 400."""
    deps = Deps()
    svc = deps.build()
    db = AsyncMock()

    session = _make_init_session(short_name="slack")
    deps.init_session_repo.seed_by_oauth_token("req-tok", session)

    mocks = CrudMocks()
    mocks.organization_get.return_value = _make_organization_model()
    mocks.source_connection_get_by_query.return_value = _make_source_conn_shell()

    from airweave.platform.auth.schemas import OAuth2Settings

    oauth2_settings = OAuth2Settings(
        integration_short_name="slack",
        url="https://slack.com/oauth",
        backend_url="https://slack.com/token",
        client_id="cid",
        client_secret="csec",
        grant_type="authorization_code",
        content_type="application/x-www-form-urlencoded",
        client_credential_location="body",
    )

    patches = _apply_crud_patches(mocks)
    patches.append(
        patch(
            "airweave.platform.auth.settings.integration_settings.get_by_short_name",
            AsyncMock(return_value=oauth2_settings),
        )
    )
    for p in patches:
        p.start()
    try:
        with pytest.raises(HTTPException) as exc_info:
            await svc.complete_oauth1_callback(
                db, oauth_token="req-tok", oauth_verifier="verifier-xyz"
            )
        assert exc_info.value.status_code == 400
        assert "not configured for oauth1" in exc_info.value.detail.lower()
    finally:
        for p in patches:
            p.stop()


# ===========================================================================
# complete_oauth1_callback — happy path
# ===========================================================================


@pytest.mark.asyncio
async def test_complete_oauth1_callback_happy():
    deps = Deps()
    svc = deps.build()
    db = AsyncMock()

    session = _make_init_session(
        short_name="twitter",
        overrides={
            "consumer_key": "ck",
            "consumer_secret": "cs",
            "oauth_token": "req-tok",
            "oauth_token_secret": "req-sec",
        },
    )
    deps.init_session_repo.seed_by_oauth_token("req-tok", session)
    deps.flow_svc.seed_oauth1_response(
        OAuth1TokenResponse(oauth_token="access-tok", oauth_token_secret="access-sec")
    )
    deps.source_registry.seed("twitter", _make_registry_entry(source_class=FederatedSourceClass))

    source = _make_source(short_name="twitter", name="Twitter")
    shell = _make_source_conn_shell()
    mocks = CrudMocks()
    mocks.configure_happy_path(source=source, shell=shell)

    oauth1_settings = _make_oauth1_settings()

    uow_class, uow = _make_uow_mock()
    patches = _apply_crud_patches(mocks)
    patches.append(patch(f"{MODULE}.UnitOfWork", uow_class))
    patches.append(
        patch(
            "airweave.platform.auth.settings.integration_settings.get_by_short_name",
            AsyncMock(return_value=oauth1_settings),
        )
    )

    for p in patches:
        p.start()
    try:
        result = await svc.complete_oauth1_callback(
            db, oauth_token="req-tok", oauth_verifier="verifier-xyz"
        )
    finally:
        for p in patches:
            p.stop()

    assert result is not None
    assert shell.is_authenticated is True
    assert len(deps.init_session_repo._mark_completed_calls) == 1

    mocks.encrypt.assert_called_once()
    encrypted_fields = mocks.encrypt.call_args[0][0]
    assert encrypted_fields["oauth_token"] == "access-tok"
    assert encrypted_fields["oauth_token_secret"] == "access-sec"
    assert encrypted_fields["consumer_key"] == "ck"
    assert encrypted_fields["consumer_secret"] == "cs"


# ===========================================================================
# _finalize_callback (table-driven)
# ===========================================================================


@dataclass
class FinalizeCase:
    desc: str
    sync_id: Optional[UUID]
    sync_exists: bool = False
    job_status: SyncJobStatus = SyncJobStatus.PENDING
    has_collection: bool = True
    expect_workflow_triggered: bool = False


FINALIZE_CASES = [
    FinalizeCase(
        "no sync_id → no trigger",
        sync_id=None,
    ),
    FinalizeCase(
        "sync_id but no sync in DB → no trigger",
        sync_id=SYNC_ID,
        sync_exists=False,
    ),
    FinalizeCase(
        "pending job → triggers workflow",
        sync_id=SYNC_ID,
        sync_exists=True,
        job_status=SyncJobStatus.PENDING,
        expect_workflow_triggered=True,
    ),
    FinalizeCase(
        "running job → no trigger",
        sync_id=SYNC_ID,
        sync_exists=True,
        job_status=SyncJobStatus.RUNNING,
    ),
    FinalizeCase(
        "pending job but no collection → no trigger",
        sync_id=SYNC_ID,
        sync_exists=True,
        job_status=SyncJobStatus.PENDING,
        has_collection=False,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", FINALIZE_CASES, ids=lambda c: c.desc)
async def test_finalize_callback(case: FinalizeCase):
    deps = Deps()
    svc = deps.build()
    db = AsyncMock()
    ctx = _make_ctx()

    source_conn = _make_source_conn_shell(
        sync_id=case.sync_id,
        connection_id=CONNECTION_ID,
        readable_collection_id="col-123",
    )

    mocks = CrudMocks()
    sync_obj = _make_sync() if case.sync_exists else None
    mocks.sync_get.return_value = sync_obj

    if case.sync_exists:
        job = _make_sync_job(status=case.job_status)
        mocks.sync_job_get_all.return_value = [job]
    else:
        mocks.sync_job_get_all.return_value = []

    mocks.collection_get_by_readable_id.return_value = (
        _make_collection() if case.has_collection else None
    )
    mocks.connection_get.return_value = _make_connection()

    temporal_svc_mock = MagicMock()
    temporal_svc_mock.run_source_connection_workflow = AsyncMock()

    patches = _apply_crud_patches(mocks)
    patches.append(
        patch(
            "airweave.core.temporal_service.temporal_service",
            temporal_svc_mock,
        )
    )
    for p in patches:
        p.start()
    try:
        await svc._finalize_callback(db, source_conn, ctx)
    finally:
        for p in patches:
            p.stop()

    if case.expect_workflow_triggered:
        temporal_svc_mock.run_source_connection_workflow.assert_awaited_once()
    else:
        temporal_svc_mock.run_source_connection_workflow.assert_not_awaited()


# ===========================================================================
# _validate_config (table-driven)
# ===========================================================================


@dataclass
class ValidateConfigCase:
    desc: str
    config_fields: Any
    registry_has_source: bool = True
    config_ref: Any = None
    expect_result: Dict[str, Any] = field(default_factory=dict)
    expect_error_status: Optional[int] = None


class StubConfigModel:
    """Minimal pydantic-like config model for testing."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self._data = kwargs

    @classmethod
    def model_validate(cls, data):
        return cls(**data)

    def model_dump(self):
        return dict(self._data)


class StrictConfigModel:
    """Config model that rejects unknown fields."""

    ALLOWED = {"host", "port"}

    def __init__(self, **kwargs):
        from pydantic import ValidationError as PVE

        bad = set(kwargs) - self.ALLOWED
        if bad:
            raise ValueError(f"Unknown fields: {bad}")
        self._data = kwargs

    @classmethod
    def model_validate(cls, data):
        return cls(**data)

    def model_dump(self):
        return dict(self._data)


VALIDATE_CONFIG_CASES = [
    ValidateConfigCase(
        "None config → empty dict",
        config_fields=None,
    ),
    ValidateConfigCase(
        "empty dict → empty dict",
        config_fields={},
    ),
    ValidateConfigCase(
        "registry miss → empty dict",
        config_fields={"host": "x"},
        registry_has_source=False,
    ),
    ValidateConfigCase(
        "no config_ref → passthrough dict",
        config_fields={"host": "x", "port": 5432},
        config_ref=None,
        expect_result={"host": "x", "port": 5432},
    ),
    ValidateConfigCase(
        "valid config through model → validated dict",
        config_fields={"host": "x", "port": 5432},
        config_ref=StubConfigModel,
        expect_result={"host": "x", "port": 5432},
    ),
    ValidateConfigCase(
        "invalid config → 422",
        config_fields={"bad_field": "x"},
        config_ref=StrictConfigModel,
        expect_error_status=422,
    ),
]


@pytest.mark.parametrize("case", VALIDATE_CONFIG_CASES, ids=lambda c: c.desc)
def test_validate_config(case: ValidateConfigCase):
    deps = Deps()
    svc = deps.build()
    ctx = _make_ctx()

    source = _make_source()
    if case.registry_has_source:
        deps.source_registry.seed(
            source.short_name,
            _make_registry_entry(config_ref=case.config_ref),
        )

    if case.expect_error_status:
        with pytest.raises(HTTPException) as exc_info:
            svc._validate_config(source, case.config_fields, ctx)
        assert exc_info.value.status_code == case.expect_error_status
        return

    result = svc._validate_config(source, case.config_fields, ctx)
    assert result == case.expect_result


# ===========================================================================
# _reconstruct_context
# ===========================================================================


@pytest.mark.asyncio
async def test_reconstruct_context():
    deps = Deps()
    svc = deps.build()
    db = AsyncMock()

    session = _make_init_session()
    org_model = _make_organization_model()

    with patch(f"{MODULE}.crud.organization.get", AsyncMock(return_value=org_model)):
        ctx = await svc._reconstruct_context(db, session)

    assert ctx.auth_method == AuthMethod.OAUTH_CALLBACK
    assert str(ctx.organization.id) == str(ORG_ID)
    assert ctx.auth_metadata["session_id"] == str(SESSION_ID)
    assert ctx.request_id is not None


# ===========================================================================
# BYOC detection — OAuth2
# ===========================================================================


@pytest.mark.asyncio
async def test_complete_oauth2_byoc_detection():
    """When overrides have client_id + client_secret → OAUTH_BYOC auth method."""
    deps = Deps()
    svc = deps.build()
    db = AsyncMock()

    session = _make_init_session(
        short_name="slack",
        overrides={"client_id": "byoc-id", "client_secret": "byoc-sec"},
    )
    deps.init_session_repo.seed_by_state("state-abc", session)
    deps.flow_svc.seed_oauth2_response(
        OAuth2TokenResponse(access_token="tok-byoc")
    )
    deps.source_registry.seed("slack", _make_registry_entry(source_class=FederatedSourceClass))

    source = _make_source()
    shell = _make_source_conn_shell()
    mocks = CrudMocks()
    mocks.configure_happy_path(source=source, shell=shell)

    uow_class, uow = _make_uow_mock()
    patches = _apply_crud_patches(mocks)
    patches.append(patch(f"{MODULE}.UnitOfWork", uow_class))

    for p in patches:
        p.start()
    try:
        await svc.complete_oauth2_callback(db, state="state-abc", code="code-xyz")
    finally:
        for p in patches:
            p.stop()

    cred_create_call = mocks.integration_credential_create
    cred_create_call.assert_awaited_once()
    _, kwargs = cred_create_call.call_args
    cred_in = kwargs["obj_in"]
    from airweave.schemas.source_connection import AuthenticationMethod

    assert cred_in.authentication_method == AuthenticationMethod.OAUTH_BYOC


# ===========================================================================
# Non-federated: cron schedule defaults
# ===========================================================================


@dataclass
class CronDefaultCase:
    desc: str
    source_class: type
    payload_schedule: Optional[Dict[str, Any]]
    expect_cron_contains: Optional[str] = None
    expect_five_min: bool = False


CRON_DEFAULT_CASES = [
    CronDefaultCase(
        "explicit cron from payload",
        StubSourceClass,
        {"schedule": {"cron": "0 6 * * *"}},
        expect_cron_contains="0 6 * * *",
    ),
    CronDefaultCase(
        "continuous source defaults to 5min",
        ContinuousSourceClass,
        None,
        expect_five_min=True,
    ),
    CronDefaultCase(
        "non-continuous, no schedule → daily default",
        StubSourceClass,
        None,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CRON_DEFAULT_CASES, ids=lambda c: c.desc)
async def test_cron_schedule_defaults(case: CronDefaultCase):
    deps = Deps()
    svc = deps.build()
    db = AsyncMock()

    payload = {"name": "My Conn"}
    if case.payload_schedule:
        payload.update(case.payload_schedule)

    session = _make_init_session(short_name="slack", payload=payload)
    deps.init_session_repo.seed_by_state("state-abc", session)
    deps.flow_svc.seed_oauth2_response(OAuth2TokenResponse(access_token="tok"))
    deps.source_registry.seed("slack", _make_registry_entry(source_class=case.source_class))

    sync = _make_sync()
    sync_job = _make_sync_job()
    source = _make_source()
    shell = _make_source_conn_shell()
    mocks = CrudMocks()
    mocks.configure_happy_path(source=source, shell=shell, sync=sync, sync_job=sync_job)

    uow_class, uow = _make_uow_mock()

    helpers_mock = MagicMock()
    helpers_mock.create_sync_without_schedule = AsyncMock(return_value=(sync, sync_job))
    schedule_mock = MagicMock()
    schedule_mock.create_or_update_schedule = AsyncMock()
    temporal_svc_mock = MagicMock()
    temporal_svc_mock.run_source_connection_workflow = AsyncMock()

    patches = _apply_crud_patches(mocks)
    patches.append(patch(f"{MODULE}.UnitOfWork", uow_class))
    patches.append(
        patch(
            "airweave.core.source_connection_service_helpers.source_connection_helpers",
            helpers_mock,
        )
    )
    patches.append(
        patch(
            "airweave.platform.temporal.schedule_service.temporal_schedule_service",
            schedule_mock,
        )
    )
    patches.append(
        patch(
            "airweave.core.temporal_service.temporal_service",
            temporal_svc_mock,
        )
    )

    for p in patches:
        p.start()
    try:
        await svc.complete_oauth2_callback(db, state="state-abc", code="code-xyz")
    finally:
        for p in patches:
            p.stop()

    create_call = helpers_mock.create_sync_without_schedule
    create_call.assert_awaited_once()
    _, call_kwargs = create_call.call_args
    cron = call_kwargs["cron_schedule"]

    if case.expect_cron_contains:
        assert case.expect_cron_contains in cron
    elif case.expect_five_min:
        assert cron == "*/5 * * * *"
    else:
        parts = cron.split()
        assert len(parts) == 5
        assert parts[2] == "*"
        assert parts[3] == "*"
        assert parts[4] == "*"
