"""Unit tests for SourceConnectionCreationService.

Covers all auth flows (direct, OAuth token, auth provider, browser/OAuth2, browser/OAuth1)
and error conditions in table-driven style.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import BaseModel, Field

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod, SyncJobStatus
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.connections.fakes.repository import FakeConnectionRepository
from airweave.domains.credentials.fakes.repository import FakeIntegrationCredentialRepository
from airweave.domains.source_connections.create import SourceConnectionCreationService
from airweave.domains.source_connections.fakes.repository import FakeSourceConnectionRepository
from airweave.domains.source_connections.fakes.response import FakeResponseBuilder
from airweave.domains.sources.fakes.lifecycle import FakeSourceLifecycleService
from airweave.domains.sources.fakes.registry import FakeSourceRegistry
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.domains.syncs.fakes.sync_lifecycle_service import FakeSyncLifecycleService
from airweave.domains.syncs.types import SyncProvisionResult
from airweave.domains.temporal.fakes.service import FakeTemporalWorkflowService
from airweave.adapters.event_bus.fake import FakeEventBus
from airweave.platform.configs._base import Fields
from airweave.schemas.organization import Organization
from airweave.schemas.source_connection import (
    AuthProviderAuthentication,
    DirectAuthentication,
    OAuthBrowserAuthentication,
    OAuthTokenAuthentication,
    SourceConnectionCreate,
)

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()

ENCRYPT_PATCH = "airweave.domains.source_connections.create.encrypt_credentials"
TRACK_PATCH = "airweave.domains.source_connections.create.business_events"
INTEGRATION_SETTINGS_PATCH = "airweave.platform.auth.settings.integration_settings"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(*, enabled_features: Optional[list] = None) -> ApiContext:
    org = Organization(
        id=str(ORG_ID),
        name="Test Org",
        created_at=NOW,
        modified_at=NOW,
        enabled_features=enabled_features or [],
    )
    return ApiContext(
        request_id="test-req",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        logger=logger.with_context(request_id="test-req"),
    )


class _FakeAuthConfig(BaseModel):
    api_key: str


class _FakeConfigRef(BaseModel):
    repo_url: str
    premium: Optional[str] = Field(
        None, json_schema_extra={"feature_flag": "premium_sync"}
    )


class _TemplateConfigRef(BaseModel):
    subdomain: str

    @classmethod
    def get_template_config_fields(cls) -> list[str]:
        return ["subdomain"]


EMPTY_FIELDS = Fields(fields=[])


def _make_entry(
    *,
    short_name: str = "test_source",
    name: str = "Test Source",
    auth_config_ref: Optional[type] = _FakeAuthConfig,
    config_ref: Optional[type] = None,
    oauth_type: Optional[str] = None,
    requires_byoc: bool = False,
    supported_auth_providers: Optional[list] = None,
    auth_methods: Optional[list] = None,
) -> SourceRegistryEntry:
    return SourceRegistryEntry(
        short_name=short_name,
        name=name,
        description="A test source",
        class_name="TestSource",
        source_class_ref=type("TestSource", (), {}),
        config_ref=config_ref,
        auth_config_ref=auth_config_ref,
        auth_fields=EMPTY_FIELDS,
        config_fields=EMPTY_FIELDS,
        supported_auth_providers=supported_auth_providers or [],
        runtime_auth_all_fields=[],
        runtime_auth_optional_fields=set(),
        auth_methods=auth_methods if auth_methods is not None else ["direct"],
        oauth_type=oauth_type,
        requires_byoc=requires_byoc,
        supports_continuous=False,
        federated_search=False,
        supports_temporal_relevance=False,
        supports_access_control=False,
        rate_limit_level=None,
        feature_flag=None,
        labels=None,
        output_entity_definitions=[],
    )


def _build_creation_service(
    sc_repo: Optional[FakeSourceConnectionRepository] = None,
    collection_repo: Optional[FakeCollectionRepository] = None,
    connection_repo: Optional[FakeConnectionRepository] = None,
    cred_repo: Optional[FakeIntegrationCredentialRepository] = None,
    source_registry: Optional[FakeSourceRegistry] = None,
    sync_lifecycle: Optional[FakeSyncLifecycleService] = None,
    source_lifecycle: Optional[FakeSourceLifecycleService] = None,
    temporal: Optional[FakeTemporalWorkflowService] = None,
    event_bus: Optional[FakeEventBus] = None,
    response_builder: Optional[FakeResponseBuilder] = None,
    oauth1_service: Optional[AsyncMock] = None,
    oauth2_service: Optional[AsyncMock] = None,
) -> SourceConnectionCreationService:
    return SourceConnectionCreationService(
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        collection_repo=collection_repo or FakeCollectionRepository(),
        connection_repo=connection_repo or FakeConnectionRepository(),
        cred_repo=cred_repo or FakeIntegrationCredentialRepository(),
        source_registry=source_registry or FakeSourceRegistry(),
        response_builder=response_builder or FakeResponseBuilder(),
        sync_lifecycle=sync_lifecycle or FakeSyncLifecycleService(),
        oauth1_service=oauth1_service or AsyncMock(),
        oauth2_service=oauth2_service or AsyncMock(),
        source_lifecycle_service=source_lifecycle or FakeSourceLifecycleService(),
        temporal_workflow_service=temporal or FakeTemporalWorkflowService(),
        event_bus=event_bus or FakeEventBus(),
    )


def _make_provision_result(*, sync_immediately: bool = True) -> SyncProvisionResult:
    sync_id = uuid4()
    return SyncProvisionResult(
        sync_id=sync_id,
        sync=schemas.Sync(
            id=sync_id, name="Test Conn",
            source_connection_id=uuid4(),
            destination_connection_ids=[], organization_id=ORG_ID,
            cron_schedule=None, status="active",
            created_at=NOW, modified_at=NOW,
        ),
        sync_job=schemas.SyncJob(
            id=uuid4(), sync_id=sync_id, organization_id=ORG_ID,
            status=SyncJobStatus.PENDING,
            created_at=NOW, modified_at=NOW,
        ) if sync_immediately else None,
        cron_schedule=None,
    )


def _seed_collection(collection_repo: FakeCollectionRepository, readable_id: str = "col-abc"):
    from airweave.models.collection import Collection as CollectionModel
    col = CollectionModel(
        name="Test Collection", readable_id=readable_id,
        vector_size=768, embedding_model_name="text-embedding-3-small",
    )
    col.id = uuid4()
    col.organization_id = ORG_ID
    col.created_at = NOW
    col.modified_at = NOW
    collection_repo.seed_readable(readable_id, col)


# ---------------------------------------------------------------------------
# Input factories
# ---------------------------------------------------------------------------


def _direct_input(
    short_name: str = "test_source", *, creds: Optional[Dict[str, Any]] = None
) -> SourceConnectionCreate:
    return SourceConnectionCreate(
        name="Test Conn",
        short_name=short_name,
        readable_collection_id="col-abc",
        authentication=DirectAuthentication(credentials=creds or {"api_key": "sk-123"}),
    )


def _token_input(
    short_name: str = "test_source",
    *,
    expires_at: Optional[datetime] = None,
    refresh_token: Optional[str] = None,
) -> SourceConnectionCreate:
    return SourceConnectionCreate(
        name="Token Conn",
        short_name=short_name,
        readable_collection_id="col-xyz",
        authentication=OAuthTokenAuthentication(
            access_token="tok-abc",
            refresh_token=refresh_token,
            expires_at=expires_at,
        ),
    )


def _auth_provider_input(
    short_name: str = "test_source", provider_id: str = "my-provider-abc"
) -> SourceConnectionCreate:
    return SourceConnectionCreate(
        name="Provider Conn",
        short_name=short_name,
        readable_collection_id="col-xyz",
        authentication=AuthProviderAuthentication(provider_readable_id=provider_id),
    )


def _browser_input(
    short_name: str = "test_source",
    *,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    consumer_key: Optional[str] = None,
    consumer_secret: Optional[str] = None,
) -> SourceConnectionCreate:
    auth = OAuthBrowserAuthentication(
        client_id=client_id,
        client_secret=client_secret,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
    ) if any([client_id, client_secret, consumer_key, consumer_secret]) else None
    return SourceConnectionCreate(
        name="Browser Conn",
        short_name=short_name,
        readable_collection_id="col-abc",
        authentication=auth,
        sync_immediately=False,
    )


# ---------------------------------------------------------------------------
# Happy-path table (direct / token / auth_provider)
# ---------------------------------------------------------------------------


@dataclass
class CreateHappyCase:
    desc: str
    entry_kwargs: Dict[str, Any]
    obj_in_factory: Any
    expect_name: str
    expect_encrypt: bool
    expect_validate: bool
    conn_repo_setup: Optional[Any] = None


def _seed_provider(conn_repo: FakeConnectionRepository) -> None:
    from airweave.models.connection import Connection

    p = Connection(name="My Provider", short_name="my_provider", readable_id="my-provider-abc")
    p.id = uuid4()
    conn_repo.seed_readable("my-provider-abc", p)


CREATE_HAPPY_CASES = [
    CreateHappyCase(
        desc="direct",
        entry_kwargs={},
        obj_in_factory=_direct_input,
        expect_name="Test Conn",
        expect_encrypt=True,
        expect_validate=True,
    ),
    CreateHappyCase(
        desc="oauth_token",
        entry_kwargs={"auth_config_ref": None, "oauth_type": "with_refresh",
                      "auth_methods": ["oauth_token"]},
        obj_in_factory=_token_input,
        expect_name="Token Conn",
        expect_encrypt=True,
        expect_validate=True,
    ),
    CreateHappyCase(
        desc="auth_provider",
        entry_kwargs={"supported_auth_providers": ["my_provider"],
                      "auth_methods": ["direct", "auth_provider"]},
        obj_in_factory=_auth_provider_input,
        expect_name="Provider Conn",
        expect_encrypt=False,
        expect_validate=False,
        conn_repo_setup=_seed_provider,
    ),
]


@pytest.mark.parametrize("case", CREATE_HAPPY_CASES, ids=lambda c: c.desc)
@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_create_happy_path(mock_encrypt, mock_track, case: CreateHappyCase):
    registry = FakeSourceRegistry()
    registry.seed(_make_entry(**case.entry_kwargs))
    source_lifecycle = FakeSourceLifecycleService()
    conn_repo = FakeConnectionRepository()
    if case.conn_repo_setup:
        case.conn_repo_setup(conn_repo)

    svc = _build_creation_service(
        source_registry=registry,
        source_lifecycle=source_lifecycle,
        connection_repo=conn_repo,
    )

    result = await svc.create(AsyncMock(), case.obj_in_factory(), _make_ctx())

    assert result.short_name == "test_source"
    assert result.name == case.expect_name
    if case.expect_encrypt:
        mock_encrypt.assert_called_once()
    if case.expect_validate:
        assert len(source_lifecycle.validate_calls) == 1


# ---------------------------------------------------------------------------
# Error table
# ---------------------------------------------------------------------------


@dataclass
class CreateErrorCase:
    desc: str
    entry_kwargs: Dict[str, Any]
    obj_in_factory: Any
    expect_status: int
    expect_detail_substr: Optional[str] = None
    expect_exc_type: type = HTTPException
    conn_repo_setup: Optional[Any] = None
    source_lifecycle_setup: Optional[Any] = None
    seed_entry: bool = True


def _lifecycle_raises_bad_creds(svc: FakeSourceLifecycleService) -> None:
    svc.set_validate_raises("test_source", ValueError("Bad creds"))


def _seed_wrong_provider(conn_repo: FakeConnectionRepository) -> None:
    from airweave.models.connection import Connection

    p = Connection(name="Wrong", short_name="wrong_provider", readable_id="wrong-provider-abc")
    p.id = uuid4()
    conn_repo.seed_readable("wrong-provider-abc", p)


CREATE_ERROR_CASES = [
    CreateErrorCase(
        desc="unknown_source_404",
        entry_kwargs={},
        obj_in_factory=lambda: _direct_input(short_name="nope"),
        expect_status=404,
        seed_entry=False,
    ),
    CreateErrorCase(
        desc="bad_credentials_422",
        entry_kwargs={},
        obj_in_factory=lambda: _direct_input(creds={"wrong_field": "val"}),
        expect_status=422,
    ),
    CreateErrorCase(
        desc="source_validation_failure",
        entry_kwargs={},
        obj_in_factory=_direct_input,
        expect_status=0,
        expect_exc_type=ValueError,
        expect_detail_substr="Bad creds",
        source_lifecycle_setup=_lifecycle_raises_bad_creds,
    ),
    CreateErrorCase(
        desc="auth_provider_not_found_404",
        entry_kwargs={"supported_auth_providers": ["my_provider"],
                      "auth_methods": ["direct", "auth_provider"]},
        obj_in_factory=lambda: _auth_provider_input(provider_id="missing-provider"),
        expect_status=404,
    ),
    CreateErrorCase(
        desc="auth_provider_unsupported_400",
        entry_kwargs={"supported_auth_providers": ["other_provider"],
                      "auth_methods": ["direct", "auth_provider"]},
        obj_in_factory=lambda: _auth_provider_input(provider_id="wrong-provider-abc"),
        expect_status=400,
        expect_detail_substr="does not support",
        conn_repo_setup=_seed_wrong_provider,
    ),
    CreateErrorCase(
        desc="browser_sync_immediately_400",
        entry_kwargs={"auth_methods": ["direct", "oauth_browser"]},
        obj_in_factory=lambda: SourceConnectionCreate(
            name="Browser Conn", short_name="test_source",
            readable_collection_id="col-xyz",
            authentication=None, sync_immediately=True,
        ),
        expect_status=400,
        expect_detail_substr="sync_immediately",
    ),
    CreateErrorCase(
        desc="byoc_required_400",
        entry_kwargs={"requires_byoc": True,
                      "auth_methods": ["direct", "oauth_browser"]},
        obj_in_factory=lambda: SourceConnectionCreate(
            name="Browser Conn", short_name="test_source",
            readable_collection_id="col-xyz",
            authentication=None, sync_immediately=False,
        ),
        expect_status=400,
        expect_detail_substr="requires custom OAuth",
    ),
    CreateErrorCase(
        desc="auth_method_unsupported_400",
        entry_kwargs={"auth_methods": ["oauth_browser"]},
        obj_in_factory=_direct_input,
        expect_status=400,
        expect_detail_substr="does not support",
    ),
    CreateErrorCase(
        desc="no_auth_config_ref_422",
        entry_kwargs={"auth_config_ref": None},
        obj_in_factory=_direct_input,
        expect_status=422,
        expect_detail_substr="does not support direct auth",
    ),
    CreateErrorCase(
        desc="bad_config_422",
        entry_kwargs={"config_ref": _FakeConfigRef},
        obj_in_factory=lambda: SourceConnectionCreate(
            name="Test Conn", short_name="test_source",
            readable_collection_id="col-abc",
            authentication=DirectAuthentication(credentials={"api_key": "sk-123"}),
            config={"invalid_field": "x"},
        ),
        expect_status=422,
        expect_detail_substr="Invalid config",
    ),
    CreateErrorCase(
        desc="feature_flag_403",
        entry_kwargs={"config_ref": _FakeConfigRef},
        obj_in_factory=lambda: SourceConnectionCreate(
            name="Test Conn", short_name="test_source",
            readable_collection_id="col-abc",
            authentication=DirectAuthentication(credentials={"api_key": "sk-123"}),
            config={"repo_url": "https://gh.com/x", "premium": "on"},
        ),
        expect_status=403,
        expect_detail_substr="premium_sync",
    ),
]


@pytest.mark.parametrize("case", CREATE_ERROR_CASES, ids=lambda c: c.desc)
@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_create_error(mock_encrypt, mock_track, case: CreateErrorCase):
    registry = FakeSourceRegistry()
    if case.seed_entry:
        registry.seed(_make_entry(**case.entry_kwargs))

    conn_repo = FakeConnectionRepository()
    if case.conn_repo_setup:
        case.conn_repo_setup(conn_repo)

    source_lifecycle = FakeSourceLifecycleService()
    if case.source_lifecycle_setup:
        case.source_lifecycle_setup(source_lifecycle)

    svc = _build_creation_service(
        source_registry=registry,
        connection_repo=conn_repo,
        source_lifecycle=source_lifecycle,
    )

    if case.expect_exc_type is HTTPException:
        with pytest.raises(HTTPException) as exc_info:
            await svc.create(AsyncMock(), case.obj_in_factory(), _make_ctx())
        assert exc_info.value.status_code == case.expect_status
        if case.expect_detail_substr:
            assert case.expect_detail_substr in exc_info.value.detail
    else:
        with pytest.raises(case.expect_exc_type, match=case.expect_detail_substr or ""):
            await svc.create(AsyncMock(), case.obj_in_factory(), _make_ctx())


# ---------------------------------------------------------------------------
# Default name generation
# ---------------------------------------------------------------------------


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_create_generates_default_name(mock_encrypt, mock_track):
    registry = FakeSourceRegistry()
    registry.seed(_make_entry(name="GitHub"))

    svc = _build_creation_service(source_registry=registry)

    obj_in = SourceConnectionCreate(
        name=None,
        short_name="test_source",
        readable_collection_id="col-abc",
        authentication=DirectAuthentication(credentials={"api_key": "sk-123"}),
    )

    result = await svc.create(AsyncMock(), obj_in, _make_ctx())
    assert result.name == "GitHub Connection"


# ---------------------------------------------------------------------------
# Event bus receives sync.pending on sync_immediately (direct)
# ---------------------------------------------------------------------------


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_create_direct_publishes_sync_event(mock_encrypt, mock_track):
    registry = FakeSourceRegistry()
    registry.seed(_make_entry())

    sync_lifecycle = FakeSyncLifecycleService()
    sync_lifecycle.set_provision_result(_make_provision_result())

    collection_repo = FakeCollectionRepository()
    _seed_collection(collection_repo, "col-abc")

    event_bus = FakeEventBus()

    svc = _build_creation_service(
        source_registry=registry,
        sync_lifecycle=sync_lifecycle,
        collection_repo=collection_repo,
        event_bus=event_bus,
    )

    result = await svc.create(AsyncMock(), _direct_input(), _make_ctx())
    assert result is not None
    assert event_bus.has_event("sync.pending")


# ===========================================================================
# OAuth browser flow tests (OAuth2)
# ===========================================================================


def _mock_oauth2_service() -> AsyncMock:
    svc = AsyncMock()
    svc.generate_auth_url_with_redirect.return_value = (
        "https://auth.example.com/authorize?state=xyz",
        "pkce-verifier-123",
    )
    return svc


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
@patch(INTEGRATION_SETTINGS_PATCH)
async def test_create_oauth2_browser_happy_path(mock_settings, mock_encrypt, mock_track):
    mock_settings.get_by_short_name = AsyncMock(return_value=MagicMock(spec=[]))

    registry = FakeSourceRegistry()
    registry.seed(_make_entry(
        auth_config_ref=None,
        auth_methods=["oauth_browser"],
    ))

    oauth2 = _mock_oauth2_service()
    svc = _build_creation_service(source_registry=registry, oauth2_service=oauth2)

    result = await svc.create(AsyncMock(), _browser_input(), _make_ctx())

    assert result is not None
    assert result.short_name == "test_source"
    oauth2.generate_auth_url_with_redirect.assert_called_once()


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
@patch(INTEGRATION_SETTINGS_PATCH)
async def test_create_oauth2_browser_no_code_verifier(
    mock_settings, mock_encrypt, mock_track
):
    mock_settings.get_by_short_name = AsyncMock(return_value=MagicMock(spec=[]))

    registry = FakeSourceRegistry()
    registry.seed(_make_entry(auth_config_ref=None, auth_methods=["oauth_browser"]))

    oauth2 = AsyncMock()
    oauth2.generate_auth_url_with_redirect.return_value = (
        "https://auth.example.com/authorize",
        None,
    )
    svc = _build_creation_service(source_registry=registry, oauth2_service=oauth2)

    result = await svc.create(AsyncMock(), _browser_input(), _make_ctx())
    assert result is not None


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
@patch(INTEGRATION_SETTINGS_PATCH)
async def test_create_oauth2_byoc_client_id(mock_settings, mock_encrypt, mock_track):
    """BYOC via client_id + client_secret on OAuthBrowserAuthentication."""
    mock_settings.get_by_short_name = AsyncMock(return_value=MagicMock(spec=[]))

    registry = FakeSourceRegistry()
    registry.seed(_make_entry(
        auth_config_ref=None,
        auth_methods=["oauth_browser", "oauth_byoc"],
    ))

    oauth2 = _mock_oauth2_service()
    svc = _build_creation_service(source_registry=registry, oauth2_service=oauth2)

    obj_in = _browser_input(client_id="my-cid", client_secret="my-csec")
    result = await svc.create(AsyncMock(), obj_in, _make_ctx())

    assert result is not None
    call_kwargs = oauth2.generate_auth_url_with_redirect.call_args
    assert call_kwargs.kwargs.get("client_id") == "my-cid" or call_kwargs[1].get("client_id") == "my-cid"


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
@patch(INTEGRATION_SETTINGS_PATCH)
async def test_create_oauth2_byoc_consumer_key(mock_settings, mock_encrypt, mock_track):
    """BYOC via consumer_key + consumer_secret (maps to OAUTH_BYOC)."""
    mock_settings.get_by_short_name = AsyncMock(return_value=MagicMock(spec=[]))

    registry = FakeSourceRegistry()
    registry.seed(_make_entry(
        auth_config_ref=None,
        auth_methods=["oauth_browser", "oauth_byoc"],
    ))

    oauth2 = _mock_oauth2_service()
    svc = _build_creation_service(source_registry=registry, oauth2_service=oauth2)

    obj_in = _browser_input(consumer_key="ck-123", consumer_secret="cs-456")
    result = await svc.create(AsyncMock(), obj_in, _make_ctx())
    assert result is not None


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
@patch(INTEGRATION_SETTINGS_PATCH)
async def test_create_oauth_browser_no_settings_400(
    mock_settings, mock_encrypt, mock_track
):
    mock_settings.get_by_short_name = AsyncMock(return_value=None)

    registry = FakeSourceRegistry()
    registry.seed(_make_entry(auth_config_ref=None, auth_methods=["oauth_browser"]))

    svc = _build_creation_service(source_registry=registry)

    with pytest.raises(HTTPException) as exc_info:
        await svc.create(AsyncMock(), _browser_input(), _make_ctx())
    assert exc_info.value.status_code == 400
    assert "OAuth not configured" in exc_info.value.detail


# ===========================================================================
# OAuth browser flow tests (OAuth1)
# ===========================================================================


def _mock_oauth1_service() -> AsyncMock:
    svc = AsyncMock()
    request_token = MagicMock()
    request_token.oauth_token = "req-token-123"
    request_token.oauth_token_secret = "req-secret-456"
    svc.get_request_token.return_value = request_token
    svc.build_authorization_url.return_value = "https://oauth1.example.com/authorize?token=req-token-123"
    return svc


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
@patch(INTEGRATION_SETTINGS_PATCH)
async def test_create_oauth1_browser_happy_path(mock_settings, mock_encrypt, mock_track):
    from airweave.platform.auth.schemas import OAuth1Settings

    oauth1_settings = MagicMock(spec=OAuth1Settings)
    oauth1_settings.request_token_url = "https://api.example.com/request_token"
    oauth1_settings.authorization_url = "https://api.example.com/authorize"
    oauth1_settings.consumer_key = "platform-ck"
    oauth1_settings.consumer_secret = "platform-cs"
    oauth1_settings.scope = "read"
    oauth1_settings.expiration = "never"
    mock_settings.get_by_short_name = AsyncMock(return_value=oauth1_settings)

    registry = FakeSourceRegistry()
    registry.seed(_make_entry(auth_config_ref=None, auth_methods=["oauth_browser"]))

    oauth1 = _mock_oauth1_service()
    svc = _build_creation_service(source_registry=registry, oauth1_service=oauth1)

    result = await svc.create(AsyncMock(), _browser_input(), _make_ctx())

    assert result is not None
    oauth1.get_request_token.assert_called_once()
    oauth1.build_authorization_url.assert_called_once()


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
@patch(INTEGRATION_SETTINGS_PATCH)
async def test_create_oauth1_byoc_consumer_keys(mock_settings, mock_encrypt, mock_track):
    """BYOC consumer_key/secret overrides platform defaults in OAuth1 flow."""
    from airweave.platform.auth.schemas import OAuth1Settings

    oauth1_settings = MagicMock(spec=OAuth1Settings)
    oauth1_settings.request_token_url = "https://api.example.com/request_token"
    oauth1_settings.authorization_url = "https://api.example.com/authorize"
    oauth1_settings.consumer_key = "platform-ck"
    oauth1_settings.consumer_secret = "platform-cs"
    oauth1_settings.scope = "read"
    oauth1_settings.expiration = "never"
    mock_settings.get_by_short_name = AsyncMock(return_value=oauth1_settings)

    registry = FakeSourceRegistry()
    registry.seed(_make_entry(
        auth_config_ref=None,
        auth_methods=["oauth_browser", "oauth_byoc"],
    ))

    oauth1 = _mock_oauth1_service()
    svc = _build_creation_service(source_registry=registry, oauth1_service=oauth1)

    obj_in = _browser_input(consumer_key="user-ck", consumer_secret="user-cs")
    result = await svc.create(AsyncMock(), obj_in, _make_ctx())

    assert result is not None
    call_kwargs = oauth1.get_request_token.call_args
    assert call_kwargs.kwargs["consumer_key"] == "user-ck"
    assert call_kwargs.kwargs["consumer_secret"] == "user-cs"


# ===========================================================================
# OAuth browser with template configs
# ===========================================================================


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
@patch(INTEGRATION_SETTINGS_PATCH)
async def test_create_oauth2_browser_with_template_configs(
    mock_settings, mock_encrypt, mock_track
):
    mock_settings.get_by_short_name = AsyncMock(return_value=MagicMock(spec=[]))

    registry = FakeSourceRegistry()
    registry.seed(_make_entry(
        auth_config_ref=None,
        config_ref=_TemplateConfigRef,
        auth_methods=["oauth_browser"],
    ))

    oauth2 = _mock_oauth2_service()
    svc = _build_creation_service(source_registry=registry, oauth2_service=oauth2)

    obj_in = SourceConnectionCreate(
        name="Template Conn", short_name="test_source",
        readable_collection_id="col-abc",
        authentication=None, sync_immediately=False,
        config={"subdomain": "mycompany"},
    )
    result = await svc.create(AsyncMock(), obj_in, _make_ctx())

    assert result is not None
    call_kwargs = oauth2.generate_auth_url_with_redirect.call_args
    assert call_kwargs.kwargs.get("template_configs") == {"subdomain": "mycompany"}


# ===========================================================================
# Token with expires_at
# ===========================================================================


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_create_token_with_expires_at(mock_encrypt, mock_track):
    registry = FakeSourceRegistry()
    registry.seed(_make_entry(
        auth_config_ref=None, oauth_type="with_refresh",
        auth_methods=["oauth_token"],
    ))

    svc = _build_creation_service(source_registry=registry)

    expires = datetime(2026, 12, 31, 23, 59, 59)
    obj_in = _token_input(expires_at=expires, refresh_token="refresh-xyz")
    result = await svc.create(AsyncMock(), obj_in, _make_ctx())

    assert result is not None
    assert result.name == "Token Conn"
    call_args = mock_encrypt.call_args[0][0]
    assert "expires_at" in call_args
    assert call_args["refresh_token"] == "refresh-xyz"


# ===========================================================================
# Token with sync_immediately triggers sync
# ===========================================================================


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_create_token_triggers_sync(mock_encrypt, mock_track):
    registry = FakeSourceRegistry()
    registry.seed(_make_entry(
        auth_config_ref=None, oauth_type="with_refresh",
        auth_methods=["oauth_token"],
    ))

    sync_lifecycle = FakeSyncLifecycleService()
    sync_lifecycle.set_provision_result(_make_provision_result())

    collection_repo = FakeCollectionRepository()
    _seed_collection(collection_repo, "col-xyz")

    event_bus = FakeEventBus()
    temporal = FakeTemporalWorkflowService()

    svc = _build_creation_service(
        source_registry=registry,
        sync_lifecycle=sync_lifecycle,
        collection_repo=collection_repo,
        event_bus=event_bus,
        temporal=temporal,
    )

    result = await svc.create(AsyncMock(), _token_input(), _make_ctx())
    assert result is not None
    assert event_bus.has_event("sync.pending")
    assert any(c[0] == "run_source_connection_workflow" for c in temporal._calls)


# ===========================================================================
# Auth provider with sync_immediately triggers sync
# ===========================================================================


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_create_auth_provider_triggers_sync(mock_encrypt, mock_track):
    registry = FakeSourceRegistry()
    registry.seed(_make_entry(
        supported_auth_providers=["my_provider"],
        auth_methods=["direct", "auth_provider"],
    ))

    conn_repo = FakeConnectionRepository()
    _seed_provider(conn_repo)

    sync_lifecycle = FakeSyncLifecycleService()
    sync_lifecycle.set_provision_result(_make_provision_result())

    collection_repo = FakeCollectionRepository()
    _seed_collection(collection_repo, "col-xyz")

    event_bus = FakeEventBus()
    temporal = FakeTemporalWorkflowService()

    svc = _build_creation_service(
        source_registry=registry,
        connection_repo=conn_repo,
        sync_lifecycle=sync_lifecycle,
        collection_repo=collection_repo,
        event_bus=event_bus,
        temporal=temporal,
    )

    result = await svc.create(AsyncMock(), _auth_provider_input(), _make_ctx())
    assert result is not None
    assert event_bus.has_event("sync.pending")
    assert any(c[0] == "run_source_connection_workflow" for c in temporal._calls)


# ===========================================================================
# _trigger_provisioned_sync error paths
# ===========================================================================


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_trigger_sync_collection_load_failure_is_swallowed(
    mock_encrypt, mock_track
):
    """If collection can't be loaded, trigger silently returns without error."""
    registry = FakeSourceRegistry()
    registry.seed(_make_entry())

    sync_lifecycle = FakeSyncLifecycleService()
    sync_lifecycle.set_provision_result(_make_provision_result())

    event_bus = FakeEventBus()
    temporal = FakeTemporalWorkflowService()

    svc = _build_creation_service(
        source_registry=registry,
        sync_lifecycle=sync_lifecycle,
        event_bus=event_bus,
        temporal=temporal,
    )

    result = await svc.create(AsyncMock(), _direct_input(), _make_ctx())
    assert result is not None
    assert not event_bus.has_event("sync.pending")
    assert not any(c[0] == "run_source_connection_workflow" for c in temporal._calls)


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_trigger_sync_event_bus_failure_still_starts_workflow(
    mock_encrypt, mock_track
):
    """If event_bus.publish raises, temporal workflow is still started."""
    registry = FakeSourceRegistry()
    registry.seed(_make_entry())

    sync_lifecycle = FakeSyncLifecycleService()
    sync_lifecycle.set_provision_result(_make_provision_result())

    collection_repo = FakeCollectionRepository()
    _seed_collection(collection_repo, "col-abc")

    temporal = FakeTemporalWorkflowService()

    event_bus = AsyncMock()
    event_bus.publish.side_effect = RuntimeError("Event bus down")

    svc = _build_creation_service(
        source_registry=registry,
        sync_lifecycle=sync_lifecycle,
        collection_repo=collection_repo,
        event_bus=event_bus,
        temporal=temporal,
    )

    result = await svc.create(AsyncMock(), _direct_input(), _make_ctx())
    assert result is not None
    assert any(c[0] == "run_source_connection_workflow" for c in temporal._calls)


# ===========================================================================
# _validate_config_fields edge cases
# ===========================================================================


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_create_direct_with_valid_config(mock_encrypt, mock_track):
    """Config passes through config_ref validation successfully."""
    registry = FakeSourceRegistry()
    registry.seed(_make_entry(config_ref=_FakeConfigRef))

    svc = _build_creation_service(source_registry=registry)

    obj_in = SourceConnectionCreate(
        name="Test Conn", short_name="test_source",
        readable_collection_id="col-abc",
        authentication=DirectAuthentication(credentials={"api_key": "sk-123"}),
        config={"repo_url": "https://github.com/foo"},
    )
    result = await svc.create(AsyncMock(), obj_in, _make_ctx())
    assert result is not None


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_create_direct_config_no_ref_passthrough(mock_encrypt, mock_track):
    """Config dict passes through when entry has no config_ref."""
    registry = FakeSourceRegistry()
    registry.seed(_make_entry(config_ref=None))

    svc = _build_creation_service(source_registry=registry)

    obj_in = SourceConnectionCreate(
        name="Test Conn", short_name="test_source",
        readable_collection_id="col-abc",
        authentication=DirectAuthentication(credentials={"api_key": "sk-123"}),
        config={"arbitrary": "value"},
    )
    result = await svc.create(AsyncMock(), obj_in, _make_ctx())
    assert result is not None


class _S3ConfigRef(BaseModel):
    repo_url: str
    dest: Optional[str] = Field(
        None, json_schema_extra={"feature_flag": "s3_destination"}
    )


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_create_direct_feature_flag_allowed(mock_encrypt, mock_track):
    """Config with feature flag field succeeds when feature is enabled."""
    from airweave.core.shared_models import FeatureFlag

    registry = FakeSourceRegistry()
    registry.seed(_make_entry(config_ref=_S3ConfigRef))

    svc = _build_creation_service(source_registry=registry)

    obj_in = SourceConnectionCreate(
        name="Test Conn", short_name="test_source",
        readable_collection_id="col-abc",
        authentication=DirectAuthentication(credentials={"api_key": "sk-123"}),
        config={"repo_url": "https://gh.com/x", "dest": "my-bucket"},
    )
    ctx = _make_ctx(enabled_features=[FeatureFlag.S3_DESTINATION])
    result = await svc.create(AsyncMock(), obj_in, ctx)
    assert result is not None


# ===========================================================================
# sync_immediately default for browser vs non-browser
# ===========================================================================


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
async def test_sync_immediately_defaults_true_for_direct(mock_encrypt, mock_track):
    """When sync_immediately is None for direct auth, defaults to True."""
    registry = FakeSourceRegistry()
    registry.seed(_make_entry())

    sync_lifecycle = FakeSyncLifecycleService()
    sync_lifecycle.set_provision_result(_make_provision_result())

    collection_repo = FakeCollectionRepository()
    _seed_collection(collection_repo, "col-abc")

    svc = _build_creation_service(
        source_registry=registry,
        sync_lifecycle=sync_lifecycle,
        collection_repo=collection_repo,
    )

    obj_in = SourceConnectionCreate(
        name="Test Conn", short_name="test_source",
        readable_collection_id="col-abc",
        authentication=DirectAuthentication(credentials={"api_key": "sk-123"}),
        sync_immediately=None,
    )
    result = await svc.create(AsyncMock(), obj_in, _make_ctx())
    assert result is not None


@patch(TRACK_PATCH)
@patch(ENCRYPT_PATCH, return_value="encrypted-blob")
@patch(INTEGRATION_SETTINGS_PATCH)
async def test_sync_immediately_defaults_false_for_browser(
    mock_settings, mock_encrypt, mock_track
):
    """When sync_immediately is None for browser auth, defaults to False."""
    mock_settings.get_by_short_name = AsyncMock(return_value=MagicMock(spec=[]))

    registry = FakeSourceRegistry()
    registry.seed(_make_entry(auth_config_ref=None, auth_methods=["oauth_browser"]))

    oauth2 = _mock_oauth2_service()
    svc = _build_creation_service(source_registry=registry, oauth2_service=oauth2)

    obj_in = SourceConnectionCreate(
        name="Browser Conn", short_name="test_source",
        readable_collection_id="col-abc",
        authentication=None,
        sync_immediately=None,
    )
    result = await svc.create(AsyncMock(), obj_in, _make_ctx())
    assert result is not None
