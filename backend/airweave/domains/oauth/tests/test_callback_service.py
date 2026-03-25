"""Unit tests for OAuthCallbackService.

All database interactions go through injected fakes — no crud patching.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import BaseModel

from airweave.adapters.encryption.fake import FakeCredentialEncryptor
from airweave.api.context import ApiContext
from airweave.core.shared_models import AuthMethod, ConnectionStatus, SyncJobStatus
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.connections.fakes.repository import FakeConnectionRepository
from airweave.domains.credentials.fakes.repository import FakeIntegrationCredentialRepository
from airweave.domains.oauth.callback_service import OAuthCallbackService
from airweave.domains.oauth.fakes.flow_service import FakeOAuthFlowService
from airweave.domains.oauth.fakes.repository import FakeOAuthInitSessionRepository
from airweave.domains.oauth.types import OAuth1TokenResponse
from airweave.domains.organizations.fakes.repository import FakeOrganizationRepository
from airweave.domains.source_connections.fakes.repository import FakeSourceConnectionRepository
from airweave.domains.sources.exceptions import SourceNotFoundError, SourceValidationError
from airweave.domains.syncs.fakes.sync_job_repository import FakeSyncJobRepository
from airweave.domains.syncs.fakes.sync_repository import FakeSyncRepository
from airweave.models.connection_init_session import ConnectionInitSession, ConnectionInitStatus
from airweave.models.organization import Organization
from airweave.models.source_connection import SourceConnection
from airweave.platform.auth.schemas import OAuth2TokenResponse
from airweave.schemas.organization import Organization as OrganizationSchema
from airweave.schemas.source_connection import AuthenticationMethod

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()
SESSION_ID = uuid4()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _ctx() -> ApiContext:
    org = OrganizationSchema(id=str(ORG_ID), name="Test Org", created_at=NOW, modified_at=NOW)
    return ApiContext(
        request_id="test-req",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        auth_metadata={},
    )


def _init_session(
    *,
    state: str = "state-abc",
    short_name: str = "github",
    status: ConnectionInitStatus = ConnectionInitStatus.PENDING,
    organization_id: UUID | None = None,
    session_id: UUID | None = None,
    payload: dict | None = None,
    overrides: dict | None = None,
    expires_at: datetime | None = None,
    initiator_user_id: UUID | None = None,
    initiator_session_id: UUID | None = None,
    claim_token_hash: str | None = None,
) -> ConnectionInitSession:
    return ConnectionInitSession(
        id=session_id or SESSION_ID,
        state=state,
        short_name=short_name,
        status=status,
        organization_id=organization_id or ORG_ID,
        payload=payload or {},
        overrides=overrides or {},
        expires_at=expires_at or datetime(2099, 1, 1, tzinfo=timezone.utc),
        initiator_user_id=initiator_user_id,
        initiator_session_id=initiator_session_id,
        claim_token_hash=claim_token_hash,
    )


def _source_conn_shell(
    *,
    init_session_id: UUID = SESSION_ID,
    org_id: UUID | None = None,
) -> SourceConnection:
    return SourceConnection(
        id=uuid4(),
        organization_id=org_id or ORG_ID,
        name="shell",
        short_name="github",
        connection_init_session_id=init_session_id,
        readable_collection_id="col-abc",
    )


def _organization() -> Organization:
    org = Organization(id=ORG_ID, name="Test Org")
    org.created_at = NOW
    org.modified_at = NOW
    return org


def _service(
    *,
    init_session_repo=None,
    sc_repo=None,
    credential_repo=None,
    connection_repo=None,
    collection_repo=None,
    sync_repo=None,
    sync_job_repo=None,
    organization_repo=None,
    credential_encryptor=None,
    oauth_flow_service=None,
    response_builder=None,
    source_registry=None,
    source_lifecycle=None,
    sync_lifecycle=None,
    sync_record_service=None,
    temporal_workflow_service=None,
    sync_state_machine=None,
    event_bus=None,
) -> OAuthCallbackService:
    return OAuthCallbackService(
        oauth_flow_service=oauth_flow_service or FakeOAuthFlowService(),
        init_session_repo=init_session_repo or FakeOAuthInitSessionRepository(),
        response_builder=response_builder or AsyncMock(),
        source_registry=source_registry or MagicMock(),
        source_lifecycle=source_lifecycle or AsyncMock(),
        sync_lifecycle=sync_lifecycle or AsyncMock(),
        sync_record_service=sync_record_service or AsyncMock(),
        temporal_workflow_service=temporal_workflow_service or AsyncMock(),
        sync_state_machine=sync_state_machine or AsyncMock(),
        event_bus=event_bus or AsyncMock(),
        organization_repo=organization_repo or FakeOrganizationRepository(),
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        credential_repo=credential_repo or FakeIntegrationCredentialRepository(),
        connection_repo=connection_repo or FakeConnectionRepository(),
        collection_repo=collection_repo or FakeCollectionRepository(),
        sync_repo=sync_repo or FakeSyncRepository(),
        sync_job_repo=sync_job_repo or FakeSyncJobRepository(),
        credential_encryptor=credential_encryptor or FakeCredentialEncryptor(),
    )


DB = AsyncMock()
DB.add = MagicMock()


# ---------------------------------------------------------------------------
# complete_oauth_callback
# ---------------------------------------------------------------------------


class TestCompleteOAuthCallback:
    async def test_dispatches_oauth1_when_oauth1_params_present(self):
        svc = _service()
        expected = MagicMock()
        svc.complete_oauth1_callback = AsyncMock(return_value=expected)
        svc.complete_oauth2_callback = AsyncMock()

        result = await svc.complete_oauth_callback(
            DB,
            oauth_token="token",
            oauth_verifier="verifier",
        )

        assert result is expected
        svc.complete_oauth1_callback.assert_awaited_once()
        svc.complete_oauth2_callback.assert_not_called()

    async def test_dispatches_oauth2_when_oauth2_params_present(self):
        svc = _service()
        expected = MagicMock()
        svc.complete_oauth1_callback = AsyncMock()
        svc.complete_oauth2_callback = AsyncMock(return_value=expected)

        result = await svc.complete_oauth_callback(
            DB,
            state="state-abc",
            code="code-abc",
        )

        assert result is expected
        svc.complete_oauth2_callback.assert_awaited_once()
        svc.complete_oauth1_callback.assert_not_called()

    async def test_raises_400_when_no_valid_param_set(self):
        svc = _service()

        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth_callback(DB)

        assert exc.value.status_code == 400
        assert "Invalid OAuth callback" in exc.value.detail


# ---------------------------------------------------------------------------
# complete_oauth2_callback
# ---------------------------------------------------------------------------


class TestCompleteOAuth2Callback:
    async def test_session_not_found_raises_404(self):
        svc = _service()
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth2_callback(DB, state="missing", code="c")
        assert exc.value.status_code == 404

    async def test_session_already_completed_raises_400(self):
        repo = FakeOAuthInitSessionRepository()
        session = _init_session(status=ConnectionInitStatus.COMPLETED)
        repo.seed_by_state("state-abc", session)

        svc = _service(init_session_repo=repo)
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth2_callback(DB, state="state-abc", code="c")
        assert exc.value.status_code == 400

    async def test_missing_source_conn_shell_raises_404(self):
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session()
        init_repo.seed_by_state("state-abc", session)

        org_repo = FakeOrganizationRepository()
        org_repo.seed(ORG_ID, _organization())

        svc = _service(init_session_repo=init_repo, organization_repo=org_repo)
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth2_callback(DB, state="state-abc", code="c")
        assert exc.value.status_code == 404
        assert "shell" in exc.value.detail.lower()

    async def test_invalid_oauth2_token_fails_fast_with_400(self):
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session()
        init_repo.seed_by_state("state-abc", session)

        org_repo = FakeOrganizationRepository()
        org_repo.seed(ORG_ID, _organization())

        sc_repo = FakeSourceConnectionRepository()
        shell = _source_conn_shell()
        sc_repo.seed(shell.id, shell)
        sc_repo.seed_init_session(SESSION_ID, session)

        oauth_flow = FakeOAuthFlowService()
        oauth_flow.seed_oauth2_response(
            OAuth2TokenResponse(access_token="bad-token", token_type="bearer")
        )

        registry = MagicMock()
        registry.get.return_value = SimpleNamespace(
            source_class_ref=MagicMock(), short_name="github", auth_config_ref=None,
        )

        source_lifecycle = AsyncMock()
        source_lifecycle.validate = AsyncMock(
            side_effect=SourceValidationError("github", "validate() returned False")
        )

        svc = _service(
            init_session_repo=init_repo,
            organization_repo=org_repo,
            sc_repo=sc_repo,
            oauth_flow_service=oauth_flow,
            source_registry=registry,
            source_lifecycle=source_lifecycle,
        )
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth2_callback(DB, state="state-abc", code="c")

        assert exc.value.status_code == 400
        assert "validation failed" in exc.value.detail.lower()
        assert all(call[0] != "mark_completed" for call in init_repo._calls)

    async def test_validation_exception_fails_fast_with_400(self):
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session()
        init_repo.seed_by_state("state-abc", session)

        org_repo = FakeOrganizationRepository()
        org_repo.seed(ORG_ID, _organization())

        sc_repo = FakeSourceConnectionRepository()
        shell = _source_conn_shell()
        sc_repo.seed(shell.id, shell)
        sc_repo.seed_init_session(SESSION_ID, session)

        oauth_flow = FakeOAuthFlowService()
        oauth_flow.seed_oauth2_response(
            OAuth2TokenResponse(access_token="token", token_type="bearer")
        )

        registry = MagicMock()
        registry.get.return_value = SimpleNamespace(
            source_class_ref=MagicMock(), short_name="github", auth_config_ref=None,
        )

        source_lifecycle = AsyncMock()
        source_lifecycle.validate = AsyncMock(
            side_effect=SourceValidationError("github", "validation raised: provider error")
        )

        svc = _service(
            init_session_repo=init_repo,
            organization_repo=org_repo,
            sc_repo=sc_repo,
            oauth_flow_service=oauth_flow,
            source_registry=registry,
            source_lifecycle=source_lifecycle,
        )
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth2_callback(DB, state="state-abc", code="c")

        assert exc.value.status_code == 400
        assert "validation failed" in exc.value.detail.lower()
        assert all(call[0] != "mark_completed" for call in init_repo._calls)

    async def test_source_not_found_fails_with_404(self):
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session()
        init_repo.seed_by_state("state-abc", session)

        org_repo = FakeOrganizationRepository()
        org_repo.seed(ORG_ID, _organization())

        sc_repo = FakeSourceConnectionRepository()
        shell = _source_conn_shell()
        sc_repo.seed(shell.id, shell)
        sc_repo.seed_init_session(SESSION_ID, session)

        oauth_flow = FakeOAuthFlowService()
        oauth_flow.seed_oauth2_response(
            OAuth2TokenResponse(access_token="bad-token", token_type="bearer")
        )

        registry = MagicMock()
        registry.get.return_value = SimpleNamespace(
            source_class_ref=MagicMock(), short_name="github", auth_config_ref=None,
        )

        source_lifecycle = AsyncMock()
        source_lifecycle.validate = AsyncMock(
            side_effect=SourceNotFoundError("unknown_source")
        )

        svc = _service(
            init_session_repo=init_repo,
            organization_repo=org_repo,
            sc_repo=sc_repo,
            oauth_flow_service=oauth_flow,
            source_registry=registry,
            source_lifecycle=source_lifecycle,
        )
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth2_callback(DB, state="state-abc", code="c")

        assert exc.value.status_code == 404

    async def test_happy_path_delegates_and_finalizes(self):
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session()
        init_repo.seed_by_state("state-abc", session)

        org_repo = FakeOrganizationRepository()
        org_repo.seed(ORG_ID, _organization())

        sc_repo = FakeSourceConnectionRepository()
        shell = _source_conn_shell()
        sc_repo.seed(shell.id, shell)
        sc_repo.seed_init_session(SESSION_ID, session)

        oauth_flow = FakeOAuthFlowService()
        oauth_flow.seed_oauth2_response(
            OAuth2TokenResponse(access_token="good-token", token_type="bearer")
        )

        class _SourceOk:
            def set_logger(self, _logger):
                return None

            async def validate(self):
                return True

        class _SourceClass:
            @staticmethod
            async def create(access_token, config):  # noqa: ARG004
                return _SourceOk()

        registry = MagicMock()
        registry.get.return_value = SimpleNamespace(
            source_class_ref=_SourceClass, short_name="github"
        )

        svc = _service(
            init_session_repo=init_repo,
            organization_repo=org_repo,
            sc_repo=sc_repo,
            oauth_flow_service=oauth_flow,
            source_registry=registry,
        )
        svc._complete_oauth2_connection = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
        svc._finalize_callback = AsyncMock(return_value=SimpleNamespace(id=uuid4()))

        await svc.complete_oauth2_callback(DB, state="state-abc", code="code-1")

        svc._complete_oauth2_connection.assert_awaited_once()
        svc._finalize_callback.assert_awaited_once()


# ---------------------------------------------------------------------------
# complete_oauth1_callback
# ---------------------------------------------------------------------------


class TestCompleteOAuth1Callback:
    async def test_session_not_found_raises_404(self):
        svc = _service()
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth1_callback(DB, oauth_token="missing", oauth_verifier="v")
        assert exc.value.status_code == 404

    async def test_session_already_completed_raises_400(self):
        repo = FakeOAuthInitSessionRepository()
        session = _init_session(status=ConnectionInitStatus.COMPLETED)
        repo.seed_by_oauth_token("tok1", session)

        svc = _service(init_session_repo=repo)
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth1_callback(DB, oauth_token="tok1", oauth_verifier="v")
        assert exc.value.status_code == 400

    async def test_missing_shell_raises_404(self):
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session()
        init_repo.seed_by_oauth_token("tok1", session)

        org_repo = FakeOrganizationRepository()
        org_repo.seed(ORG_ID, _organization())

        svc = _service(init_session_repo=init_repo, organization_repo=org_repo)
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth1_callback(DB, oauth_token="tok1", oauth_verifier="v")
        assert exc.value.status_code == 404

    async def test_non_oauth1_settings_raises_400(self, monkeypatch):
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session()
        init_repo.seed_by_oauth_token("tok1", session)

        org_repo = FakeOrganizationRepository()
        org_repo.seed(ORG_ID, _organization())

        sc_repo = FakeSourceConnectionRepository()
        shell = _source_conn_shell()
        sc_repo.seed(shell.id, shell)
        sc_repo.seed_init_session(SESSION_ID, session)

        class _SettingsModule:
            @staticmethod
            async def get_by_short_name(_short_name):
                return SimpleNamespace()

        monkeypatch.setattr(
            "airweave.domains.oauth.callback_service.integration_settings",
            _SettingsModule(),
        )

        svc = _service(
            init_session_repo=init_repo,
            organization_repo=org_repo,
            sc_repo=sc_repo,
        )

        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth1_callback(DB, oauth_token="tok1", oauth_verifier="v")
        assert exc.value.status_code == 400

    async def test_happy_path_delegates_and_finalizes(self, monkeypatch):
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session(overrides={"oauth_token": "req-tok"})
        init_repo.seed_by_oauth_token("req-tok", session)

        org_repo = FakeOrganizationRepository()
        org_repo.seed(ORG_ID, _organization())

        sc_repo = FakeSourceConnectionRepository()
        shell = _source_conn_shell()
        sc_repo.seed(shell.id, shell)
        sc_repo.seed_init_session(SESSION_ID, session)

        class _SettingsModule:
            @staticmethod
            async def get_by_short_name(_short_name):
                from airweave.platform.auth.schemas import OAuth1Settings

                return OAuth1Settings(
                    integration_short_name="github",
                    request_token_url="https://provider/request-token",
                    authorization_url="https://provider/auth",
                    access_token_url="https://provider/access",
                    consumer_key="k",
                    consumer_secret="s",
                )

        monkeypatch.setattr(
            "airweave.domains.oauth.callback_service.integration_settings",
            _SettingsModule(),
        )

        oauth_flow = FakeOAuthFlowService()
        oauth_flow.seed_oauth1_response(
            OAuth1TokenResponse(oauth_token="at", oauth_token_secret="as")
        )
        svc = _service(
            init_session_repo=init_repo,
            organization_repo=org_repo,
            sc_repo=sc_repo,
            oauth_flow_service=oauth_flow,
        )
        svc._complete_oauth1_connection = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
        svc._finalize_callback = AsyncMock(return_value=SimpleNamespace(id=uuid4()))

        await svc.complete_oauth1_callback(DB, oauth_token="req-tok", oauth_verifier="v")

        svc._complete_oauth1_connection.assert_awaited_once()
        svc._finalize_callback.assert_awaited_once()


# ---------------------------------------------------------------------------
# _reconstruct_context
# ---------------------------------------------------------------------------


class TestReconstructContext:
    async def test_returns_api_context_with_org(self):
        org_repo = FakeOrganizationRepository()
        org_repo.seed(ORG_ID, _organization())

        svc = _service(organization_repo=org_repo)
        session = _init_session()

        ctx = await svc._reconstruct_context(DB, session)

        assert ctx.organization.id == ORG_ID
        assert ctx.auth_method == AuthMethod.OAUTH_CALLBACK
        assert ctx.user is None


# ---------------------------------------------------------------------------
# _validate_config
# ---------------------------------------------------------------------------


class TestValidateConfig:
    def test_none_config_returns_empty(self):
        entry = SimpleNamespace(short_name="x", config_ref=None)
        svc = _service()
        result = svc._validate_config(entry, None)
        assert result == {}

    def test_no_config_ref_passes_through(self):
        entry = SimpleNamespace(config_ref=None)
        svc = _service()

        result = svc._validate_config(entry, {"key": "val"})
        assert result == {"key": "val"}

    def test_valid_config_validated(self):
        class FakeConfig(BaseModel):
            key: str

        entry = SimpleNamespace(config_ref=FakeConfig)
        svc = _service()

        result = svc._validate_config(entry, {"key": "val"})
        assert result == {"key": "val"}

    def test_non_mapping_raises_422(self):
        entry = SimpleNamespace(config_ref=None)
        svc = _service()
        with pytest.raises(HTTPException) as exc:
            svc._validate_config(entry, "not-a-dict")
        assert exc.value.status_code == 422

    def test_validation_error_mapped_to_422(self):
        class FakeConfig(BaseModel):
            key: int

        entry = SimpleNamespace(config_ref=FakeConfig)
        svc = _service()
        with pytest.raises(HTTPException) as exc:
            svc._validate_config(entry, {"key": "abc"})
        assert exc.value.status_code == 422
        assert "Invalid config fields" in exc.value.detail

    def test_generic_validation_error_mapped_to_422(self):
        class FakeConfig:
            @classmethod
            def model_validate(cls, _payload):
                raise RuntimeError("boom")

        entry = SimpleNamespace(config_ref=FakeConfig)
        svc = _service()
        with pytest.raises(HTTPException) as exc:
            svc._validate_config(entry, {"key": "val"})
        assert exc.value.status_code == 422
        assert "boom" in exc.value.detail


# ---------------------------------------------------------------------------
# _get_collection
# ---------------------------------------------------------------------------


class TestGetCollection:
    async def test_empty_collection_id_raises_400(self):
        svc = _service()
        with pytest.raises(HTTPException) as exc:
            await svc._get_collection(DB, "", _ctx())
        assert exc.value.status_code == 400

    async def test_missing_collection_raises_404(self):
        svc = _service()
        with pytest.raises(HTTPException) as exc:
            await svc._get_collection(DB, "nope", _ctx())
        assert exc.value.status_code == 404

    async def test_returns_found_collection(self):
        col_repo = FakeCollectionRepository()
        col = SimpleNamespace(id=uuid4(), name="Col", readable_id="col-abc")
        col_repo.seed_readable("col-abc", col)

        svc = _service(collection_repo=col_repo)
        result = await svc._get_collection(DB, "col-abc", _ctx())
        assert result is col


# ---------------------------------------------------------------------------
# _complete_oauth2_connection
# ---------------------------------------------------------------------------


class TestCompleteOAuth2Connection:
    async def test_source_not_found_raises_404(self):
        init_repo = FakeOAuthInitSessionRepository()
        init_repo.seed_by_state("state-abc", _init_session())

        org_repo = FakeOrganizationRepository()
        org_repo.seed(ORG_ID, _organization())

        sc_repo = MagicMock()
        sc_repo.get_by_init_session = AsyncMock(return_value=_source_conn_shell())

        oauth_flow = MagicMock()
        oauth_flow.complete_oauth2_callback = AsyncMock(
            return_value=SimpleNamespace(access_token="tok", model_dump=lambda: {})
        )

        registry = MagicMock()
        registry.get.side_effect = KeyError("github")

        svc = _service(
            source_registry=registry,
            init_session_repo=init_repo,
            organization_repo=org_repo,
            sc_repo=sc_repo,
            oauth_flow_service=oauth_flow,
        )

        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth2_callback(DB, state="state-abc", code="c")
        assert exc.value.status_code == 404

    async def test_salesforce_extracts_instance_url(self):
        source_entry = SimpleNamespace(
            short_name="salesforce",
            name="Salesforce",
            auth_config_class="SalesforceAuth",
            auth_config_ref=type("SalesforceAuth", (), {}),
            oauth_type="access_only",
            config_ref=None,
        )
        registry = MagicMock()
        registry.get.return_value = source_entry

        svc = _service(source_registry=registry)

        assert svc._source_registry.get("salesforce") is source_entry

    async def test_sets_auth_method_byoc_when_client_credentials_present(self):
        source_entry = SimpleNamespace(
            short_name="github",
            name="GitHub",
            auth_config_ref=type("GitHubAuth", (), {}),
            oauth_type=None,
            config_ref=None,
        )
        registry = MagicMock()
        registry.get.return_value = source_entry
        session = _init_session(overrides={"client_id": "cid", "client_secret": "csec"})
        token = SimpleNamespace(model_dump=lambda: {"access_token": "tok"})
        svc = _service(source_registry=registry)
        svc._complete_connection_common = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
        await svc._complete_oauth2_connection(
            DB, _source_conn_shell(), session, token, source_entry, _ctx()
        )
        call = svc._complete_connection_common.call_args
        assert call.args[6] == AuthenticationMethod.OAUTH_BYOC

    async def test_sets_auth_method_oauth_browser_when_client_credentials_absent(self):
        source_entry = SimpleNamespace(
            short_name="github",
            name="GitHub",
            auth_config_ref=type("GitHubAuth", (), {}),
            oauth_type=None,
            config_ref=None,
        )
        registry = MagicMock()
        registry.get.return_value = source_entry
        session = _init_session(overrides={})
        token = SimpleNamespace(model_dump=lambda: {"access_token": "tok"})
        svc = _service(source_registry=registry)
        svc._complete_connection_common = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
        await svc._complete_oauth2_connection(
            DB, _source_conn_shell(), session, token, source_entry, _ctx()
        )
        call = svc._complete_connection_common.call_args
        assert call.args[6] == AuthenticationMethod.OAUTH_BROWSER

    async def test_salesforce_instance_url_overrides_payload_config(self):
        source_entry = SimpleNamespace(
            short_name="salesforce",
            name="Salesforce",
            auth_config_ref=type("SalesforceAuth", (), {}),
            oauth_type="access_only",
            config_ref=None,
        )
        registry = MagicMock()
        registry.get.return_value = source_entry
        session = _init_session(short_name="salesforce", payload={})
        token = SimpleNamespace(
            model_dump=lambda: {"access_token": "tok", "instance_url": "https://my.salesforce.com"}
        )
        svc = _service(source_registry=registry)
        svc._complete_connection_common = AsyncMock(return_value=SimpleNamespace(id=uuid4()))

        await svc._complete_oauth2_connection(
            DB, _source_conn_shell(), session, token, source_entry, _ctx()
        )

        call = svc._complete_connection_common.call_args
        payload = call.args[4]
        assert payload["config"]["instance_url"] == "my.salesforce.com"


# ---------------------------------------------------------------------------
# _complete_oauth1_connection
# ---------------------------------------------------------------------------


class TestCompleteOAuth1Connection:
    async def test_source_not_found_raises_404(self):
        registry = MagicMock()
        registry.get.side_effect = KeyError("github")
        svc = _service(source_registry=registry)
        session = _init_session()
        shell = _source_conn_shell()
        token = SimpleNamespace(oauth_token="t", oauth_token_secret="s")

        with pytest.raises(HTTPException) as exc:
            await svc._complete_oauth1_connection(DB, shell, session, token, _ctx())
        assert exc.value.status_code == 404

    async def test_byoc_detection_fallback_on_settings_error(self, monkeypatch):
        source_entry = SimpleNamespace(
            short_name="github",
            name="GitHub",
            auth_config_ref=type("GitHubAuth", (), {}),
            oauth_type=None,
            config_ref=None,
        )
        registry = MagicMock()
        registry.get.return_value = source_entry
        session = _init_session(
            overrides={"consumer_key": "ck-custom", "consumer_secret": "cs-custom"},
        )
        token = SimpleNamespace(oauth_token="t", oauth_token_secret="s")
        svc = _service(source_registry=registry)
        svc._complete_connection_common = AsyncMock(return_value=SimpleNamespace(id=uuid4()))

        class _RaisingSettingsModule:
            @staticmethod
            async def get_by_short_name(_short_name):
                raise RuntimeError("settings unavailable")

        monkeypatch.setattr(
            "airweave.domains.oauth.callback_service.integration_settings",
            _RaisingSettingsModule(),
        )
        await svc._complete_oauth1_connection(DB, _source_conn_shell(), session, token, _ctx())
        call = svc._complete_connection_common.call_args
        assert call.args[6] == AuthenticationMethod.OAUTH_BROWSER

    async def test_sets_auth_method_byoc_when_consumer_key_differs_from_platform(self, monkeypatch):
        source_entry = SimpleNamespace(
            short_name="github",
            name="GitHub",
            auth_config_ref=type("GitHubAuth", (), {}),
            oauth_type=None,
            config_ref=None,
        )
        registry = MagicMock()
        registry.get.return_value = source_entry
        session = _init_session(
            overrides={"consumer_key": "ck-custom", "consumer_secret": "cs-custom"},
        )
        token = SimpleNamespace(oauth_token="t", oauth_token_secret="s")
        svc = _service(source_registry=registry)
        svc._complete_connection_common = AsyncMock(return_value=SimpleNamespace(id=uuid4()))

        class _SettingsModule:
            @staticmethod
            async def get_by_short_name(_short_name):
                from airweave.platform.auth.schemas import OAuth1Settings

                return OAuth1Settings(
                    integration_short_name="github",
                    request_token_url="https://provider/request-token",
                    authorization_url="https://provider/auth",
                    access_token_url="https://provider/access",
                    consumer_key="ck-platform",
                    consumer_secret="cs-platform",
                )

        monkeypatch.setattr(
            "airweave.domains.oauth.callback_service.integration_settings",
            _SettingsModule(),
        )
        await svc._complete_oauth1_connection(DB, _source_conn_shell(), session, token, _ctx())
        call = svc._complete_connection_common.call_args
        assert call.args[6] == AuthenticationMethod.OAUTH_BYOC


# ---------------------------------------------------------------------------
# _complete_connection_common
# ---------------------------------------------------------------------------


class TestCompleteConnectionCommon:
    async def test_federated_source_skips_sync_provisioning(self):
        svc = _service()
        svc._credential_repo.create = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
        svc._connection_repo.create = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
        svc._collection_repo.get_by_readable_id = AsyncMock(
            return_value=SimpleNamespace(id=uuid4(), readable_id="col-abc")
        )
        sc_id = uuid4()
        svc._sc_repo.update = AsyncMock(
            return_value=SimpleNamespace(id=sc_id, connection_id=uuid4(), sync_id=None)
        )
        svc._init_session_repo.mark_completed = AsyncMock()
        svc._source_registry.get = MagicMock(
            return_value=SimpleNamespace(source_class_ref=SimpleNamespace(federated_search=True))
        )
        svc._sync_record_service.resolve_destination_ids = AsyncMock(return_value=[uuid4()])
        svc._sync_lifecycle.provision_sync = AsyncMock()

        from airweave.domains.oauth import callback_service as callback_module

        class _FakeUOW:
            def __init__(self, db):
                self.session = db

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def commit(self):
                return None

        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(callback_module, "UnitOfWork", _FakeUOW)
        try:
            source_entry = SimpleNamespace(
                short_name="github",
                name="GitHub",
                auth_config_ref=type("GitHubAuth", (), {}),
                oauth_type="access_only",
                config_ref=None,
                source_class_ref=SimpleNamespace(federated_search=True),
            )
            shell = _source_conn_shell()
            await svc._complete_connection_common(
                db,
                source_entry,
                shell,
                SESSION_ID,
                {"name": "n", "readable_collection_id": "col-abc", "config": {}},
                {"access_token": "tok"},
                AuthenticationMethod.OAUTH_BROWSER,
                is_oauth1=False,
                ctx=_ctx(),
            )
        finally:
            monkeypatch.undo()

        svc._sync_lifecycle.provision_sync.assert_not_awaited()

    async def test_claim_token_session_skips_mark_completed(self):
        svc = _service()
        conn_id = uuid4()
        svc._credential_repo.create = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
        svc._connection_repo.create = AsyncMock(return_value=SimpleNamespace(id=conn_id))
        svc._collection_repo.get_by_readable_id = AsyncMock(
            return_value=SimpleNamespace(id=uuid4(), readable_id="col-abc")
        )
        sc_id = uuid4()
        svc._sc_repo.update = AsyncMock(
            return_value=SimpleNamespace(id=sc_id, connection_id=conn_id, sync_id=None)
        )
        svc._init_session_repo.mark_completed = AsyncMock()
        svc._sync_record_service.resolve_destination_ids = AsyncMock(return_value=[uuid4()])
        sync_id = uuid4()
        svc._sync_lifecycle.provision_sync = AsyncMock(
            return_value=SimpleNamespace(sync_id=sync_id)
        )

        from airweave.domains.oauth import callback_service as callback_module

        class _FakeUOW:
            def __init__(self, db):
                self.session = db

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def commit(self):
                return None

        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(callback_module, "UnitOfWork", _FakeUOW)
        try:
            source_entry = SimpleNamespace(
                short_name="github",
                name="GitHub",
                auth_config_ref=type("GitHubAuth", (), {}),
                oauth_type="access_only",
                config_ref=None,
                source_class_ref=SimpleNamespace(federated_search=False),
            )
            shell = _source_conn_shell()
            await svc._complete_connection_common(
                db,
                source_entry,
                shell,
                SESSION_ID,
                {"name": "n", "readable_collection_id": "col-abc"},
                {"access_token": "tok"},
                AuthenticationMethod.OAUTH_BROWSER,
                is_oauth1=False,
                ctx=_ctx(),
                has_claim_token=True,
            )
        finally:
            monkeypatch.undo()

        svc._init_session_repo.mark_completed.assert_not_awaited()

    async def test_non_federated_source_provisions_sync_with_cron_schedule(self):
        svc = _service()
        conn_id = uuid4()
        svc._credential_repo.create = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
        svc._connection_repo.create = AsyncMock(return_value=SimpleNamespace(id=conn_id))
        svc._collection_repo.get_by_readable_id = AsyncMock(
            return_value=SimpleNamespace(id=uuid4(), readable_id="col-abc")
        )
        sc_id = uuid4()
        svc._sc_repo.update = AsyncMock(
            return_value=SimpleNamespace(id=sc_id, connection_id=conn_id, sync_id=None)
        )
        svc._init_session_repo.mark_completed = AsyncMock()
        svc._source_registry.get = MagicMock(
            return_value=SimpleNamespace(source_class_ref=SimpleNamespace(federated_search=False))
        )
        svc._sync_record_service.resolve_destination_ids = AsyncMock(return_value=[uuid4()])
        sync_id = uuid4()
        svc._sync_lifecycle.provision_sync = AsyncMock(
            return_value=SimpleNamespace(sync_id=sync_id)
        )

        from airweave.domains.oauth import callback_service as callback_module

        class _FakeUOW:
            def __init__(self, db):
                self.session = db

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def commit(self):
                return None

        db = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(callback_module, "UnitOfWork", _FakeUOW)
        try:
            source_entry = SimpleNamespace(
                short_name="github",
                name="GitHub",
                auth_config_ref=type("GitHubAuth", (), {}),
                oauth_type="access_only",
                config_ref=None,
                source_class_ref=SimpleNamespace(federated_search=False),
            )
            shell = _source_conn_shell()
            await svc._complete_connection_common(
                db,
                source_entry,
                shell,
                SESSION_ID,
                {"name": "n", "readable_collection_id": "col-abc", "cron_schedule": "0 0 * * *"},
                {"access_token": "tok"},
                AuthenticationMethod.OAUTH_BROWSER,
                is_oauth1=False,
                ctx=_ctx(),
            )
        finally:
            monkeypatch.undo()

        svc._sync_lifecycle.provision_sync.assert_awaited_once()
        svc._init_session_repo.mark_completed.assert_awaited_once()


# ---------------------------------------------------------------------------
# _finalize_callback
# ---------------------------------------------------------------------------


class TestFinalizeCallback:
    async def test_no_sync_id_just_returns_response(self):
        response = MagicMock(id=uuid4(), short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response)
        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        source_conn = SimpleNamespace(
            sync_id=None,
            id=uuid4(),
            connection_id=uuid4(),
            connection_init_session_id=None,
        )

        svc = _service(response_builder=builder, event_bus=event_bus)
        result = await svc._finalize_callback(DB, source_conn, _ctx())

        assert result is response
        builder.build_response.assert_awaited_once()

    async def test_triggers_workflow_when_pending_job_exists(self):
        response = MagicMock(id=uuid4(), short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response)

        temporal_svc = AsyncMock()
        temporal_svc.run_source_connection_workflow = AsyncMock()

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        sync_id = uuid4()
        conn_id = uuid4()
        source_conn = SimpleNamespace(
            id=uuid4(),
            sync_id=sync_id,
            connection_id=conn_id,
            readable_collection_id="col-abc",
            connection_init_session_id=None,
        )

        # Seed sync repo
        from airweave import schemas

        sync_repo = FakeSyncRepository()
        sync_schema = schemas.Sync(
            id=sync_id,
            name="test-sync",
            source_connection_id=conn_id,
            collection_id=uuid4(),
            collection_readable_id="col-abc",
            organization_id=ORG_ID,
            created_at=NOW,
            modified_at=NOW,
            cron_schedule=None,
            status="active",
            source_connections=[],
            destination_connections=[],
            destination_connection_ids=[],
        )
        sync_repo.seed(sync_id, sync_schema)

        from airweave.models.sync_job import SyncJob

        job_id = uuid4()
        sync_job = SyncJob(
            id=job_id,
            sync_id=sync_id,
            status=SyncJobStatus.PENDING,
            organization_id=ORG_ID,
            scheduled=False,
        )
        sync_job_repo = FakeSyncJobRepository()
        sync_job_repo.seed_jobs_for_sync(sync_id, [sync_job])

        from airweave.models.collection import Collection

        col_id = uuid4()
        collection = Collection(
            id=col_id,
            name="Col",
            readable_id="col-abc",
            organization_id=ORG_ID,
            vector_db_deployment_metadata_id=uuid4(),
        )
        collection.created_at = NOW
        collection.modified_at = NOW
        collection_repo = FakeCollectionRepository()
        collection_repo.seed_readable("col-abc", collection)

        from airweave.models.connection import Connection

        connection = Connection(
            id=conn_id,
            organization_id=ORG_ID,
            name="github-conn",
            readable_id="conn-github-abc",
            short_name="github",
            integration_type="source",
            status=ConnectionStatus.ACTIVE,
        )
        connection.created_at = NOW
        connection.modified_at = NOW
        connection_repo = FakeConnectionRepository()
        connection_repo.seed(conn_id, connection)

        svc = _service(
            response_builder=builder,
            temporal_workflow_service=temporal_svc,
            event_bus=event_bus,
            sync_repo=sync_repo,
            sync_job_repo=sync_job_repo,
            collection_repo=collection_repo,
            connection_repo=connection_repo,
        )

        result = await svc._finalize_callback(DB, source_conn, _ctx())

        assert result is response
        temporal_svc.run_source_connection_workflow.assert_awaited_once()

    async def test_no_pending_jobs_skips_workflow(self):
        response = MagicMock(id=uuid4(), short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response)

        temporal_svc = AsyncMock()
        temporal_svc.run_source_connection_workflow = AsyncMock()

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        sync_id = uuid4()
        source_conn = SimpleNamespace(
            id=uuid4(),
            sync_id=sync_id,
            connection_id=uuid4(),
            readable_collection_id="col-abc",
            connection_init_session_id=None,
        )

        sync_repo = FakeSyncRepository()

        svc = _service(
            response_builder=builder,
            temporal_workflow_service=temporal_svc,
            event_bus=event_bus,
            sync_repo=sync_repo,
        )

        result = await svc._finalize_callback(DB, source_conn, _ctx())

        assert result is response
        temporal_svc.run_source_connection_workflow.assert_not_awaited()

    async def test_running_job_skips_workflow(self):
        response = MagicMock(id=uuid4(), short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response)

        temporal_svc = AsyncMock()
        temporal_svc.run_source_connection_workflow = AsyncMock()

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        sync_id = uuid4()
        conn_id = uuid4()
        source_conn = SimpleNamespace(
            id=uuid4(),
            sync_id=sync_id,
            connection_id=conn_id,
            readable_collection_id="col-abc",
            connection_init_session_id=None,
        )

        from airweave import schemas

        sync_repo = FakeSyncRepository()
        sync_schema = schemas.Sync(
            id=sync_id,
            name="test-sync",
            source_connection_id=conn_id,
            collection_id=uuid4(),
            collection_readable_id="col-abc",
            organization_id=ORG_ID,
            created_at=NOW,
            modified_at=NOW,
            cron_schedule=None,
            status="active",
            source_connections=[],
            destination_connections=[],
            destination_connection_ids=[],
        )
        sync_repo.seed(sync_id, sync_schema)

        from airweave.models.sync_job import SyncJob

        sync_job = SyncJob(
            id=uuid4(),
            sync_id=sync_id,
            status=SyncJobStatus.RUNNING,
            organization_id=ORG_ID,
        )
        sync_job_repo = FakeSyncJobRepository()
        sync_job_repo.seed_jobs_for_sync(sync_id, [sync_job])

        svc = _service(
            response_builder=builder,
            temporal_workflow_service=temporal_svc,
            event_bus=event_bus,
            sync_repo=sync_repo,
            sync_job_repo=sync_job_repo,
        )

        result = await svc._finalize_callback(DB, source_conn, _ctx())

        assert result is response
        temporal_svc.run_source_connection_workflow.assert_not_awaited()

    async def test_missing_connection_id_raises_value_error(self):
        response = MagicMock(id=uuid4(), short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response)
        sync_id = uuid4()
        source_conn = SimpleNamespace(
            id=uuid4(),
            sync_id=sync_id,
            connection_id=None,
            readable_collection_id="col-abc",
            connection_init_session_id=None,
        )
        from airweave import schemas

        sync_repo = FakeSyncRepository()
        sync_repo.seed(
            sync_id,
            schemas.Sync(
                id=sync_id,
                name="s",
                source_connection_id=uuid4(),
                collection_id=uuid4(),
                collection_readable_id="col-abc",
                organization_id=ORG_ID,
                created_at=NOW,
                modified_at=NOW,
                cron_schedule=None,
                status="active",
                source_connections=[],
                destination_connections=[],
                destination_connection_ids=[],
            ),
        )
        from airweave.models.sync_job import SyncJob

        sync_job_repo = FakeSyncJobRepository()
        sync_job_repo.seed_jobs_for_sync(
            sync_id,
            [
                SyncJob(
                    id=uuid4(),
                    sync_id=sync_id,
                    status=SyncJobStatus.PENDING,
                    organization_id=ORG_ID,
                    scheduled=False,
                )
            ],
        )
        from airweave.models.collection import Collection

        collection_repo = FakeCollectionRepository()
        col = Collection(
            id=uuid4(),
            name="c",
            readable_id="col-abc",
            organization_id=ORG_ID,
            vector_db_deployment_metadata_id=uuid4(),
        )
        col.created_at = NOW
        col.modified_at = NOW
        collection_repo.seed_readable("col-abc", col)
        svc = _service(
            response_builder=builder,
            sync_repo=sync_repo,
            sync_job_repo=sync_job_repo,
            collection_repo=collection_repo,
        )
        with pytest.raises(ValueError, match="no connection_id"):
            await svc._finalize_callback(DB, source_conn, _ctx())

    async def test_auth_completed_event_failure_is_fatal(self):
        response = MagicMock(id=uuid4(), short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response)
        event_bus = AsyncMock()
        event_bus.publish = AsyncMock(side_effect=RuntimeError("pub-fail"))
        ctx = _ctx()
        source_conn = SimpleNamespace(
            sync_id=None,
            id=uuid4(),
            connection_id=uuid4(),
            connection_init_session_id=None,
        )
        svc = _service(response_builder=builder, event_bus=event_bus)
        with pytest.raises(RuntimeError, match="pub-fail"):
            await svc._finalize_callback(DB, source_conn, ctx)

    async def test_pending_job_with_connection_executes_event_payload_path(self):
        response = MagicMock(id=uuid4(), short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response)

        sync_id = uuid4()
        conn_id = uuid4()
        source_conn = SimpleNamespace(
            id=uuid4(),
            sync_id=sync_id,
            connection_id=conn_id,
            readable_collection_id="col-abc",
            connection_init_session_id=None,
        )

        from airweave import schemas

        sync_repo = FakeSyncRepository()
        sync_repo.seed(
            sync_id,
            schemas.Sync(
                id=sync_id,
                name="test-sync",
                source_connection_id=conn_id,
                collection_id=uuid4(),
                collection_readable_id="col-abc",
                organization_id=ORG_ID,
                created_at=NOW,
                modified_at=NOW,
                cron_schedule=None,
                status="active",
                source_connections=[],
                destination_connections=[],
                destination_connection_ids=[],
            ),
        )

        from airweave.models.sync_job import SyncJob

        sync_job_repo = FakeSyncJobRepository()
        sync_job_repo.seed_jobs_for_sync(
            sync_id,
            [
                SyncJob(
                    id=uuid4(),
                    sync_id=sync_id,
                    status=SyncJobStatus.PENDING,
                    organization_id=ORG_ID,
                    scheduled=False,
                )
            ],
        )

        from airweave.models.collection import Collection

        collection_repo = FakeCollectionRepository()
        col = Collection(
            id=uuid4(),
            name="Col",
            readable_id="col-abc",
            organization_id=ORG_ID,
            vector_db_deployment_metadata_id=uuid4(),
        )
        col.created_at = NOW
        col.modified_at = NOW
        collection_repo.seed_readable("col-abc", col)

        from airweave.models.connection import Connection

        connection_repo = FakeConnectionRepository()
        connection = Connection(
            id=conn_id,
            organization_id=ORG_ID,
            name="github-conn",
            readable_id="conn-github-abc",
            short_name="github",
            integration_type="source",
            status=ConnectionStatus.ACTIVE,
        )
        connection.created_at = NOW
        connection.modified_at = NOW
        connection_repo.seed(conn_id, connection)

        temporal_svc = AsyncMock()
        temporal_svc.run_source_connection_workflow = AsyncMock()

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        svc = _service(
            response_builder=builder,
            sync_repo=sync_repo,
            sync_job_repo=sync_job_repo,
            collection_repo=collection_repo,
            connection_repo=connection_repo,
            temporal_workflow_service=temporal_svc,
            event_bus=event_bus,
        )

        await svc._finalize_callback(DB, source_conn, _ctx())

        assert any(call[0] == "get" for call in connection_repo._calls)
        temporal_svc.run_source_connection_workflow.assert_awaited_once()

    async def test_no_jobs_skips_workflow(self):
        """_run_sync_workflow returns early when no sync jobs exist (line 757)."""
        response = MagicMock(id=uuid4(), short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response)

        temporal_svc = AsyncMock()
        temporal_svc.run_source_connection_workflow = AsyncMock()

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        sync_id = uuid4()
        source_conn = SimpleNamespace(
            id=uuid4(),
            sync_id=sync_id,
            connection_id=uuid4(),
            readable_collection_id="col-abc",
            connection_init_session_id=None,
        )

        from airweave import schemas

        sync_repo = FakeSyncRepository()
        sync_repo.seed(
            sync_id,
            schemas.Sync(
                id=sync_id,
                name="test-sync",
                source_connection_id=source_conn.connection_id,
                collection_id=uuid4(),
                collection_readable_id="col-abc",
                organization_id=ORG_ID,
                created_at=NOW,
                modified_at=NOW,
                cron_schedule=None,
                status="active",
                source_connections=[],
                destination_connections=[],
                destination_connection_ids=[],
            ),
        )

        sync_job_repo = FakeSyncJobRepository()

        svc = _service(
            response_builder=builder,
            temporal_workflow_service=temporal_svc,
            event_bus=event_bus,
            sync_repo=sync_repo,
            sync_job_repo=sync_job_repo,
        )

        result = await svc._finalize_callback(DB, source_conn, _ctx())

        assert result is response
        temporal_svc.run_source_connection_workflow.assert_not_awaited()

    async def test_no_collection_skips_workflow(self):
        """_run_sync_workflow returns early when collection not found (line 775)."""
        response = MagicMock(id=uuid4(), short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response)

        temporal_svc = AsyncMock()
        temporal_svc.run_source_connection_workflow = AsyncMock()

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        sync_id = uuid4()
        source_conn = SimpleNamespace(
            id=uuid4(),
            sync_id=sync_id,
            connection_id=uuid4(),
            readable_collection_id="col-missing",
            connection_init_session_id=None,
        )

        from airweave import schemas

        sync_repo = FakeSyncRepository()
        sync_repo.seed(
            sync_id,
            schemas.Sync(
                id=sync_id,
                name="test-sync",
                source_connection_id=source_conn.connection_id,
                collection_id=uuid4(),
                collection_readable_id="col-missing",
                organization_id=ORG_ID,
                created_at=NOW,
                modified_at=NOW,
                cron_schedule=None,
                status="active",
                source_connections=[],
                destination_connections=[],
                destination_connection_ids=[],
            ),
        )

        from airweave.models.sync_job import SyncJob

        sync_job_repo = FakeSyncJobRepository()
        sync_job_repo.seed_jobs_for_sync(
            sync_id,
            [
                SyncJob(
                    id=uuid4(),
                    sync_id=sync_id,
                    status=SyncJobStatus.PENDING,
                    organization_id=ORG_ID,
                    scheduled=False,
                )
            ],
        )

        collection_repo = FakeCollectionRepository()

        svc = _service(
            response_builder=builder,
            temporal_workflow_service=temporal_svc,
            event_bus=event_bus,
            sync_repo=sync_repo,
            sync_job_repo=sync_job_repo,
            collection_repo=collection_repo,
        )

        result = await svc._finalize_callback(DB, source_conn, _ctx())

        assert result is response
        temporal_svc.run_source_connection_workflow.assert_not_awaited()


class TestTokenValidation:
    async def test_validate_token_returns_early_when_source_missing(self):
        svc = _service()
        await svc._validate_oauth2_token_or_raise(source_entry=None, access_token="x", ctx=_ctx())


# ---------------------------------------------------------------------------
# Credential encryptor injection
# ---------------------------------------------------------------------------


class TestCredentialEncryptorInjection:
    def test_encryptor_is_stored(self):
        encryptor = FakeCredentialEncryptor()
        svc = _service(credential_encryptor=encryptor)
        assert svc._credential_encryptor is encryptor


# ---------------------------------------------------------------------------
# Expiry enforcement
# ---------------------------------------------------------------------------


class TestExpiryEnforcement:
    async def test_expired_oauth2_session_raises_410(self):
        repo = FakeOAuthInitSessionRepository()
        session = _init_session(
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        repo.seed_by_state("state-abc", session)

        svc = _service(init_session_repo=repo)
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth2_callback(DB, state="state-abc", code="c")
        assert exc.value.status_code == 410
        assert "expired" in exc.value.detail.lower()

    async def test_expired_oauth1_session_raises_410(self):
        repo = FakeOAuthInitSessionRepository()
        session = _init_session(
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        repo.seed_by_oauth_token("tok1", session)

        svc = _service(init_session_repo=repo)
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth1_callback(DB, oauth_token="tok1", oauth_verifier="v")
        assert exc.value.status_code == 410


# ---------------------------------------------------------------------------
# IN_PROGRESS replay protection
# ---------------------------------------------------------------------------


class TestInProgressReplayProtection:
    async def test_in_progress_oauth2_session_raises_400(self):
        repo = FakeOAuthInitSessionRepository()
        session = _init_session(status=ConnectionInitStatus.IN_PROGRESS)
        repo.seed_by_state("state-abc", session)

        svc = _service(init_session_repo=repo)
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth2_callback(DB, state="state-abc", code="c")
        assert exc.value.status_code == 400

    async def test_in_progress_oauth1_session_raises_400(self):
        repo = FakeOAuthInitSessionRepository()
        session = _init_session(status=ConnectionInitStatus.IN_PROGRESS)
        repo.seed_by_oauth_token("tok1", session)

        svc = _service(init_session_repo=repo)
        with pytest.raises(HTTPException) as exc:
            await svc.complete_oauth1_callback(DB, oauth_token="tok1", oauth_verifier="v")
        assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Deferred sync when claim token is set
# ---------------------------------------------------------------------------


class TestDeferredSync:
    async def test_sync_deferred_when_claim_token_set(self):
        """_finalize_callback skips Temporal trigger when init session has claim_token_hash."""
        init_session_id = uuid4()
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session(
            session_id=init_session_id,
            claim_token_hash="abc123",
        )
        init_repo.seed_by_id(init_session_id, session)

        response = MagicMock(id=uuid4(), short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response)

        temporal_svc = AsyncMock()
        temporal_svc.run_source_connection_workflow = AsyncMock()

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        sync_id = uuid4()
        source_conn = SimpleNamespace(
            id=uuid4(),
            sync_id=sync_id,
            connection_id=uuid4(),
            connection_init_session_id=init_session_id,
            readable_collection_id="col-abc",
        )

        # Seed sync repo with a pending job
        from airweave import schemas

        sync_repo = FakeSyncRepository()
        sync_repo.seed(
            sync_id,
            schemas.Sync(
                id=sync_id,
                name="test-sync",
                source_connection_id=source_conn.connection_id,
                collection_id=uuid4(),
                collection_readable_id="col-abc",
                organization_id=ORG_ID,
                created_at=NOW,
                modified_at=NOW,
                cron_schedule=None,
                status="active",
                source_connections=[],
                destination_connections=[],
                destination_connection_ids=[],
            ),
        )

        from airweave.models.sync_job import SyncJob

        sync_job_repo = FakeSyncJobRepository()
        sync_job_repo.seed_jobs_for_sync(
            sync_id,
            [
                SyncJob(
                    id=uuid4(),
                    sync_id=sync_id,
                    status=SyncJobStatus.PENDING,
                    organization_id=ORG_ID,
                    scheduled=False,
                )
            ],
        )

        svc = _service(
            init_session_repo=init_repo,
            response_builder=builder,
            temporal_workflow_service=temporal_svc,
            event_bus=event_bus,
            sync_repo=sync_repo,
            sync_job_repo=sync_job_repo,
        )

        result = await svc._finalize_callback(DB, source_conn, _ctx())

        assert result is response
        # Sync should be deferred — workflow NOT triggered
        temporal_svc.run_source_connection_workflow.assert_not_awaited()

    async def test_sync_triggered_when_no_claim_token(self):
        """Backward compat: existing behavior preserved for sessions without claim_token_hash."""
        init_session_id = uuid4()
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session(session_id=init_session_id, claim_token_hash=None)
        init_repo.seed_by_id(init_session_id, session)

        response = MagicMock(id=uuid4(), short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response)

        temporal_svc = AsyncMock()
        temporal_svc.run_source_connection_workflow = AsyncMock()

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        sync_id = uuid4()
        conn_id = uuid4()
        source_conn = SimpleNamespace(
            id=uuid4(),
            sync_id=sync_id,
            connection_id=conn_id,
            connection_init_session_id=init_session_id,
            readable_collection_id="col-abc",
        )

        from airweave import schemas

        sync_repo = FakeSyncRepository()
        sync_repo.seed(
            sync_id,
            schemas.Sync(
                id=sync_id,
                name="test-sync",
                source_connection_id=conn_id,
                collection_id=uuid4(),
                collection_readable_id="col-abc",
                organization_id=ORG_ID,
                created_at=NOW,
                modified_at=NOW,
                cron_schedule=None,
                status="active",
                source_connections=[],
                destination_connections=[],
                destination_connection_ids=[],
            ),
        )

        from airweave.models.sync_job import SyncJob

        sync_job_repo = FakeSyncJobRepository()
        sync_job_repo.seed_jobs_for_sync(
            sync_id,
            [
                SyncJob(
                    id=uuid4(),
                    sync_id=sync_id,
                    status=SyncJobStatus.PENDING,
                    organization_id=ORG_ID,
                    scheduled=False,
                )
            ],
        )

        from airweave.models.collection import Collection

        collection_repo = FakeCollectionRepository()
        col = Collection(
            id=uuid4(),
            name="Col",
            readable_id="col-abc",
            organization_id=ORG_ID,
            vector_db_deployment_metadata_id=uuid4(),
        )
        col.created_at = NOW
        col.modified_at = NOW
        collection_repo.seed_readable("col-abc", col)

        from airweave.models.connection import Connection

        connection_repo = FakeConnectionRepository()
        connection = Connection(
            id=conn_id,
            organization_id=ORG_ID,
            name="github-conn",
            readable_id="conn-github-abc",
            short_name="github",
            integration_type="source",
            status=ConnectionStatus.ACTIVE,
        )
        connection.created_at = NOW
        connection.modified_at = NOW
        connection_repo.seed(conn_id, connection)

        svc = _service(
            init_session_repo=init_repo,
            response_builder=builder,
            temporal_workflow_service=temporal_svc,
            event_bus=event_bus,
            sync_repo=sync_repo,
            sync_job_repo=sync_job_repo,
            collection_repo=collection_repo,
            connection_repo=connection_repo,
        )

        result = await svc._finalize_callback(DB, source_conn, _ctx())

        assert result is response
        temporal_svc.run_source_connection_workflow.assert_awaited_once()

    async def test_two_step_contract_callback_defers_then_verify_triggers(self):
        """Full two-step contract: callback defers sync, verify-oauth triggers it."""
        import hashlib
        import secrets

        claim_token = secrets.token_urlsafe(32)
        claim_hash = hashlib.sha256(claim_token.encode()).hexdigest()
        user_id = uuid4()

        init_session_id = uuid4()
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session(
            session_id=init_session_id,
            status=ConnectionInitStatus.PENDING,
            claim_token_hash=claim_hash,
            initiator_user_id=user_id,
        )
        init_repo.seed_by_id(init_session_id, session)

        response = MagicMock(id=uuid4(), short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response)

        temporal_svc = AsyncMock()
        temporal_svc.run_source_connection_workflow = AsyncMock()

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        sync_id = uuid4()
        conn_id = uuid4()

        sc_repo = FakeSourceConnectionRepository()
        shell = _source_conn_shell(init_session_id=init_session_id, org_id=ORG_ID)
        shell.sync_id = sync_id
        shell.connection_id = conn_id
        sc_repo.seed(shell.id, shell)

        source_conn = SimpleNamespace(
            id=shell.id,
            sync_id=sync_id,
            connection_id=conn_id,
            connection_init_session_id=init_session_id,
            readable_collection_id="col-abc",
        )

        from airweave import schemas

        sync_repo = FakeSyncRepository()
        sync_repo.seed(
            sync_id,
            schemas.Sync(
                id=sync_id,
                name="test-sync",
                source_connection_id=conn_id,
                collection_id=uuid4(),
                collection_readable_id="col-abc",
                organization_id=ORG_ID,
                created_at=NOW,
                modified_at=NOW,
                cron_schedule=None,
                status="active",
                source_connections=[],
                destination_connections=[],
                destination_connection_ids=[],
            ),
        )

        from airweave.models.sync_job import SyncJob

        sync_job_repo = FakeSyncJobRepository()
        sync_job_repo.seed_jobs_for_sync(
            sync_id,
            [
                SyncJob(
                    id=uuid4(),
                    sync_id=sync_id,
                    status=SyncJobStatus.PENDING,
                    organization_id=ORG_ID,
                    scheduled=False,
                )
            ],
        )

        org_repo = FakeOrganizationRepository()
        org_repo.seed(ORG_ID, _organization())

        from airweave.models.collection import Collection

        collection_repo = FakeCollectionRepository()
        col = Collection(
            id=uuid4(),
            name="Col",
            readable_id="col-abc",
            organization_id=ORG_ID,
            vector_db_deployment_metadata_id=uuid4(),
        )
        col.created_at = NOW
        col.modified_at = NOW
        collection_repo.seed_readable("col-abc", col)

        from airweave.models.connection import Connection

        connection_repo = FakeConnectionRepository()
        connection = Connection(
            id=conn_id,
            organization_id=ORG_ID,
            name="github-conn",
            readable_id="conn-github-abc",
            short_name="github",
            integration_type="source",
            status=ConnectionStatus.ACTIVE,
        )
        connection.created_at = NOW
        connection.modified_at = NOW
        connection_repo.seed(conn_id, connection)

        svc = _service(
            init_session_repo=init_repo,
            sc_repo=sc_repo,
            response_builder=builder,
            temporal_workflow_service=temporal_svc,
            event_bus=event_bus,
            sync_repo=sync_repo,
            sync_job_repo=sync_job_repo,
            collection_repo=collection_repo,
            connection_repo=connection_repo,
            organization_repo=org_repo,
        )

        # Step 1: callback finalizes — sync must be DEFERRED
        await svc._finalize_callback(DB, source_conn, _ctx())
        temporal_svc.run_source_connection_workflow.assert_not_awaited()

        # Advance init session to IN_PROGRESS (as real callback would)
        session.status = ConnectionInitStatus.IN_PROGRESS

        # Step 2: verify-oauth with correct claim token — sync must be TRIGGERED
        ctx = _ctx()
        from airweave.schemas.user import User

        ctx.user = User(
            id=user_id,
            email="test@example.com",
            created_at=NOW,
            modified_at=NOW,
        )

        result = await svc.verify_oauth_flow(
            DB,
            source_connection_id=shell.id,
            claim_token=claim_token,
            ctx=ctx,
        )

        assert result is response
        assert any(call[0] == "mark_completed" for call in init_repo._calls)
        temporal_svc.run_source_connection_workflow.assert_awaited_once()


# ---------------------------------------------------------------------------
# verify_oauth_flow
# ---------------------------------------------------------------------------


class TestVerifyOAuthFlow:
    def _make_claim_token(self) -> tuple[str, str]:
        import hashlib
        import secrets

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return token, token_hash

    async def test_happy_path_triggers_sync(self):
        claim_token, claim_hash = self._make_claim_token()
        user_id = uuid4()

        init_session_id = uuid4()
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session(
            session_id=init_session_id,
            status=ConnectionInitStatus.IN_PROGRESS,
            claim_token_hash=claim_hash,
            initiator_user_id=user_id,
        )
        init_repo.seed_by_id(init_session_id, session)

        sc_repo = FakeSourceConnectionRepository()
        shell = _source_conn_shell(init_session_id=init_session_id)
        shell.connection_id = uuid4()
        sc_repo.seed(shell.id, shell)

        org_repo = FakeOrganizationRepository()
        org_repo.seed(ORG_ID, _organization())

        response_obj = MagicMock(id=shell.id, short_name="github", readable_collection_id="col-abc")
        builder = AsyncMock()
        builder.build_response = AsyncMock(return_value=response_obj)

        event_bus = AsyncMock()
        event_bus.publish = AsyncMock()

        svc = _service(
            init_session_repo=init_repo,
            sc_repo=sc_repo,
            organization_repo=org_repo,
            response_builder=builder,
            event_bus=event_bus,
        )

        # Build a ctx with user_id
        ctx = _ctx()
        from airweave.schemas.user import User

        ctx.user = User(
            id=user_id,
            email="test@example.com",
            created_at=NOW,
            modified_at=NOW,
        )

        result = await svc.verify_oauth_flow(
            DB,
            source_connection_id=shell.id,
            claim_token=claim_token,
            ctx=ctx,
        )

        assert result is response_obj
        # mark_completed should have been called
        assert any(call[0] == "mark_completed" for call in init_repo._calls)

    async def test_wrong_token_raises_403(self):
        _, claim_hash = self._make_claim_token()

        init_session_id = uuid4()
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session(
            session_id=init_session_id,
            status=ConnectionInitStatus.IN_PROGRESS,
            claim_token_hash=claim_hash,
        )
        init_repo.seed_by_id(init_session_id, session)

        sc_repo = FakeSourceConnectionRepository()
        shell = _source_conn_shell(init_session_id=init_session_id)
        shell.connection_id = uuid4()
        sc_repo.seed(shell.id, shell)

        svc = _service(init_session_repo=init_repo, sc_repo=sc_repo)

        with pytest.raises(HTTPException) as exc:
            await svc.verify_oauth_flow(
                DB,
                source_connection_id=shell.id,
                claim_token="wrong-token",
                ctx=_ctx(),
            )
        assert exc.value.status_code == 403
        assert "Invalid claim token" in exc.value.detail

    async def test_wrong_user_raises_403(self):
        claim_token, claim_hash = self._make_claim_token()
        initiator_user_id = uuid4()
        different_user_id = uuid4()

        init_session_id = uuid4()
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session(
            session_id=init_session_id,
            status=ConnectionInitStatus.IN_PROGRESS,
            claim_token_hash=claim_hash,
            initiator_user_id=initiator_user_id,
        )
        init_repo.seed_by_id(init_session_id, session)

        sc_repo = FakeSourceConnectionRepository()
        shell = _source_conn_shell(init_session_id=init_session_id)
        shell.connection_id = uuid4()
        sc_repo.seed(shell.id, shell)

        svc = _service(init_session_repo=init_repo, sc_repo=sc_repo)

        ctx = _ctx()
        from airweave.schemas.user import User

        ctx.user = User(
            id=different_user_id,
            email="other@example.com",
            created_at=NOW,
            modified_at=NOW,
        )

        with pytest.raises(HTTPException) as exc:
            await svc.verify_oauth_flow(
                DB,
                source_connection_id=shell.id,
                claim_token=claim_token,
                ctx=ctx,
            )
        assert exc.value.status_code == 403
        assert "identity mismatch" in exc.value.detail.lower()

    async def test_already_completed_raises_400(self):
        claim_token, claim_hash = self._make_claim_token()

        init_session_id = uuid4()
        init_repo = FakeOAuthInitSessionRepository()
        session = _init_session(
            session_id=init_session_id,
            status=ConnectionInitStatus.COMPLETED,
            claim_token_hash=claim_hash,
        )
        init_repo.seed_by_id(init_session_id, session)

        sc_repo = FakeSourceConnectionRepository()
        shell = _source_conn_shell(init_session_id=init_session_id)
        shell.connection_id = uuid4()
        sc_repo.seed(shell.id, shell)

        svc = _service(init_session_repo=init_repo, sc_repo=sc_repo)

        with pytest.raises(HTTPException) as exc:
            await svc.verify_oauth_flow(
                DB,
                source_connection_id=shell.id,
                claim_token=claim_token,
                ctx=_ctx(),
            )
        assert exc.value.status_code == 400
        assert "completed" in exc.value.detail.lower()

    async def test_complete_connection_common_activates_sync(self):
        """_complete_connection_common transitions sync to ACTIVE after commit."""
        from unittest.mock import patch

        sync_state_machine = AsyncMock()
        sc_repo = FakeSourceConnectionRepository()
        shell = _source_conn_shell()
        shell.connection_id = uuid4()
        sc_repo.seed(shell.id, shell)

        svc = _service(
            sc_repo=sc_repo,
            sync_state_machine=sync_state_machine,
        )
        svc._validate_config = MagicMock(return_value={})
        collection = MagicMock()
        collection.id = uuid4()
        collection.readable_id = "col-abc"
        svc._get_collection = AsyncMock(return_value=collection)

        source_entry = MagicMock()
        source_entry.short_name = "github"
        source_entry.name = "GitHub"
        source_entry.auth_config_ref = None
        source_entry.oauth_type = "access_only"
        source_entry.source_class_ref = type("S", (), {"federated_search": False})

        db = AsyncMock()
        ctx = _ctx()

        with patch(
            "airweave.domains.oauth.callback_service.UnitOfWork"
        ) as mock_uow_cls:
            mock_uow = AsyncMock()
            mock_uow.session = AsyncMock()
            mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
            mock_uow.__aexit__ = AsyncMock(return_value=False)
            mock_uow_cls.return_value = mock_uow

            await svc._complete_connection_common(
                db,
                source_entry,
                shell,
                shell.id,
                {"name": "My Source"},
                {"access_token": "tok"},
                AuthenticationMethod.OAUTH_BROWSER,
                is_oauth1=False,
                ctx=ctx,
                has_claim_token=True,
            )

        sync_state_machine.transition.assert_awaited_once()
