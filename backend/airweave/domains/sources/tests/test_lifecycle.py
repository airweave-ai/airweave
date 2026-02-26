"""Unit tests for SourceLifecycleService.

All external dependencies are fakes — no patching of module-level singletons.
Only `credentials.decrypt` (pure function) and `TokenManager` (per-request
constructor) are patched when needed.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from airweave.domains.connections.fakes.repository import FakeConnectionRepository
from airweave.domains.credentials.fakes.repository import FakeIntegrationCredentialRepository
from airweave.domains.oauth.fakes.oauth2_service import FakeOAuth2Service
from airweave.domains.source_connections.fakes.repository import FakeSourceConnectionRepository
from airweave.core.exceptions import NotFoundException
from airweave.domains.auth_provider.fake import FakeAuthProviderRegistry
from airweave.domains.auth_provider.types import AuthProviderRegistryEntry
from airweave.domains.sources.exceptions import (
    SourceCreationError,
    SourceNotFoundError,
    SourceValidationError,
)
from airweave.domains.sources.fakes.registry import FakeSourceRegistry
from airweave.domains.sources.lifecycle import SourceLifecycleService
from airweave.domains.sources.tests.conftest import _make_ctx, _make_entry
from airweave.domains.sources.types import AuthConfig, SourceConnectionData
from airweave.platform.auth_providers.auth_result import AuthProviderMode
from airweave.platform.configs._base import Fields


# ---------------------------------------------------------------------------
# Stub source classes
# ---------------------------------------------------------------------------


class _StubSourceValid:
    """Source whose create() and validate() both succeed."""

    _http_client_factory = None

    @classmethod
    async def create(cls, credentials, config=None):
        instance = cls()
        instance._credentials = credentials
        instance._config = config
        instance._logger = None
        instance._token_manager = None
        instance._sync_org_id = None
        instance._sync_sc_id = None
        return instance

    async def validate(self):
        return True

    def set_logger(self, logger):
        self._logger = logger

    def set_http_client_factory(self, factory):
        self._http_client_factory = factory

    def set_sync_identifiers(self, organization_id, source_connection_id):
        self._sync_org_id = organization_id
        self._sync_sc_id = source_connection_id

    def set_token_manager(self, tm):
        self._token_manager = tm


class _StubSourceValidateFalse:
    @classmethod
    async def create(cls, credentials, config=None):
        return cls()

    async def validate(self):
        return False


class _StubSourceValidateRaises:
    @classmethod
    async def create(cls, credentials, config=None):
        return cls()

    async def validate(self):
        raise ConnectionError("cannot reach API")


class _StubSourceCreateRaises:
    @classmethod
    async def create(cls, credentials, config=None):
        raise ValueError("bad credentials format")


class _StubSourceMinimal:
    """Source with no set_* methods at all."""

    _http_client_factory = None

    @classmethod
    async def create(cls, credentials, config=None):
        return cls()

    async def validate(self):
        return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry_with_class(short_name: str, source_class: type, **kwargs) -> Any:
    """Build a registry entry with a custom source_class_ref."""
    entry = _make_entry(short_name, short_name.title(), **kwargs)
    object.__setattr__(entry, "source_class_ref", source_class)
    return entry


def _make_auth_provider_entry(
    short_name: str = "pipedream",
    provider_class_ref: type = MagicMock,
) -> AuthProviderRegistryEntry:
    """Build a minimal auth provider registry entry."""
    return AuthProviderRegistryEntry(
        short_name=short_name,
        name=short_name.title(),
        description=f"Test {short_name}",
        class_name=f"{short_name.title()}AuthProvider",
        provider_class_ref=provider_class_ref,
        config_ref=type("Cfg", (), {"model_fields": {}}),
        auth_config_ref=type("AuthCfg", (), {"model_fields": {}}),
        config_fields=Fields(fields=[]),
        auth_config_fields=Fields(fields=[]),
        blocked_sources=[],
        field_name_mapping={},
        slug_name_mapping={},
    )


def _make_service(
    source_entries=None,
    auth_provider_entries=None,
    sc_repo=None,
    conn_repo=None,
    cred_repo=None,
    oauth2_service=None,
) -> SourceLifecycleService:
    """Build a SourceLifecycleService with fakes."""
    source_registry = FakeSourceRegistry()
    if source_entries:
        source_registry.seed(*source_entries)

    auth_provider_registry = FakeAuthProviderRegistry()
    if auth_provider_entries:
        auth_provider_registry.seed(*auth_provider_entries)

    return SourceLifecycleService(
        source_registry=source_registry,
        auth_provider_registry=auth_provider_registry,
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        conn_repo=conn_repo or FakeConnectionRepository(),
        cred_repo=cred_repo or FakeIntegrationCredentialRepository(),
        oauth2_service=oauth2_service or FakeOAuth2Service(),
    )


def _mock_source_connection(
    short_name="github",
    connection_id=None,
    config_fields=None,
    readable_auth_provider_id=None,
    auth_provider_config=None,
):
    sc = MagicMock()
    sc.id = uuid4()
    sc.short_name = short_name
    sc.connection_id = connection_id or uuid4()
    sc.config_fields = config_fields
    sc.readable_auth_provider_id = readable_auth_provider_id
    sc.auth_provider_config = auth_provider_config
    return sc


def _mock_connection(integration_credential_id=None, short_name="pipedream"):
    conn = MagicMock()
    conn.id = uuid4()
    conn.integration_credential_id = integration_credential_id or uuid4()
    conn.short_name = short_name
    return conn


def _mock_credential(encrypted="encrypted-blob"):
    cred = MagicMock()
    cred.encrypted_credentials = encrypted
    return cred


def _sc_data(
    short_name="github",
    source_class=_StubSourceValid,
    config_fields=None,
    auth_config_class=None,
    oauth_type=None,
    readable_auth_provider_id=None,
    auth_provider_config=None,
) -> SourceConnectionData:
    """Build a SourceConnectionData for testing private methods."""
    return SourceConnectionData(
        source_connection_obj=MagicMock(),
        connection=MagicMock(),
        source_class=source_class,
        config_fields=config_fields or {},
        short_name=short_name,
        source_connection_id=uuid4(),
        auth_config_class=auth_config_class,
        connection_id=uuid4(),
        integration_credential_id=uuid4(),
        oauth_type=oauth_type,
        readable_auth_provider_id=readable_auth_provider_id,
        auth_provider_config=auth_provider_config,
    )


# ===========================================================================
# validate() — table-driven
# ===========================================================================


@dataclass
class ValidateCase:
    id: str
    short_name: str
    source_class: type = _StubSourceValid
    credentials: Any = "test-token"
    config: Optional[dict] = None
    seed: bool = True
    expect_error: type | None = None
    error_substring: str = ""


VALIDATE_TABLE = [
    ValidateCase(id="happy-string-creds", short_name="github"),
    ValidateCase(id="happy-dict-creds", short_name="github",
                 credentials={"access_token": "tok", "refresh_token": "ref"}),
    ValidateCase(id="happy-with-config", short_name="github",
                 config={"repo": "owner/repo"}),
    ValidateCase(id="not-in-registry", short_name="nonexistent", seed=False,
                 expect_error=SourceNotFoundError,
                 error_substring="nonexistent"),
    ValidateCase(id="create-raises", short_name="bad_source",
                 source_class=_StubSourceCreateRaises,
                 expect_error=SourceCreationError,
                 error_substring="bad credentials format"),
    ValidateCase(id="validate-raises", short_name="unreachable",
                 source_class=_StubSourceValidateRaises,
                 expect_error=SourceValidationError,
                 error_substring="validation raised"),
    ValidateCase(id="validate-returns-false", short_name="invalid_creds",
                 source_class=_StubSourceValidateFalse,
                 expect_error=SourceValidationError,
                 error_substring="validate() returned False"),
]


@pytest.mark.parametrize("case", VALIDATE_TABLE, ids=lambda c: c.id)
@pytest.mark.asyncio
async def test_validate(case: ValidateCase):
    if case.seed:
        entry = _entry_with_class(case.short_name, case.source_class)
        service = _make_service(source_entries=[entry])
    else:
        service = _make_service()

    if case.expect_error:
        with pytest.raises(case.expect_error) as exc_info:
            await service.validate(case.short_name, case.credentials, case.config)
        assert case.error_substring in str(exc_info.value)
    else:
        await service.validate(case.short_name, case.credentials, case.config)


@pytest.mark.asyncio
async def test_validate_not_found_error_attributes():
    """SourceNotFoundError carries the short_name for caller inspection."""
    service = _make_service()
    with pytest.raises(SourceNotFoundError) as exc_info:
        await service.validate("missing", "tok")
    assert exc_info.value.short_name == "missing"


@pytest.mark.asyncio
async def test_validate_creation_error_attributes():
    """SourceCreationError carries short_name + reason."""
    entry = _entry_with_class("bad", _StubSourceCreateRaises)
    service = _make_service(source_entries=[entry])
    with pytest.raises(SourceCreationError) as exc_info:
        await service.validate("bad", "tok")
    assert exc_info.value.short_name == "bad"
    assert "bad credentials format" in exc_info.value.reason


@pytest.mark.asyncio
async def test_validate_validation_error_attributes():
    """SourceValidationError carries short_name + reason."""
    entry = _entry_with_class("fail", _StubSourceValidateFalse)
    service = _make_service(source_entries=[entry])
    with pytest.raises(SourceValidationError) as exc_info:
        await service.validate("fail", "tok")
    assert exc_info.value.short_name == "fail"
    assert exc_info.value.reason == "validate() returned False"


# ===========================================================================
# _load_source_connection_data() — table-driven
# ===========================================================================


@dataclass
class LoadSCDataCase:
    id: str
    sc_exists: bool = True
    short_name: str = "github"
    source_in_registry: bool = True
    conn_exists: bool = True
    has_cred_id: bool = True
    readable_auth_provider_id: str | None = None
    config_fields: dict | None = None
    expect_error: type | None = None
    error_match: str = ""


LOAD_SC_DATA_TABLE = [
    LoadSCDataCase(id="happy-path"),
    LoadSCDataCase(id="sc-not-found", sc_exists=False,
                   expect_error=NotFoundException, error_match="not found"),
    LoadSCDataCase(id="not-in-registry", source_in_registry=False,
                   expect_error=SourceNotFoundError, error_match="github"),
    LoadSCDataCase(id="conn-not-found", conn_exists=False,
                   expect_error=NotFoundException, error_match="Connection not found"),
    LoadSCDataCase(id="no-cred-no-auth-provider", has_cred_id=False,
                   expect_error=NotFoundException, error_match="no integration credential"),
    LoadSCDataCase(id="auth-provider-skips-cred-check",
                   has_cred_id=False, readable_auth_provider_id="pipedream-123"),
    LoadSCDataCase(id="preserves-config", config_fields={"repo": "o/r", "branch": "main"}),
]


@pytest.mark.parametrize("case", LOAD_SC_DATA_TABLE, ids=lambda c: c.id)
@pytest.mark.asyncio
async def test_load_source_connection_data(case: LoadSCDataCase):
    sc = _mock_source_connection(
        short_name=case.short_name,
        readable_auth_provider_id=case.readable_auth_provider_id,
        config_fields=case.config_fields,
    )
    conn = _mock_connection()
    if not case.has_cred_id:
        conn.integration_credential_id = None

    entry = _entry_with_class(case.short_name, _StubSourceValid)

    sc_repo = FakeSourceConnectionRepository()
    if case.sc_exists:
        sc_repo.seed(sc.id, sc)

    conn_repo = FakeConnectionRepository()
    if case.conn_exists:
        conn_repo.seed(sc.connection_id, conn)

    source_entries = [entry] if case.source_in_registry else []
    service = _make_service(source_entries=source_entries, sc_repo=sc_repo, conn_repo=conn_repo)
    ctx = _make_ctx()

    if case.expect_error:
        with pytest.raises(case.expect_error, match=case.error_match):
            await service._load_source_connection_data(
                db=MagicMock(), source_connection_id=sc.id, ctx=ctx, logger=ctx.logger
            )
    else:
        data = await service._load_source_connection_data(
            db=MagicMock(), source_connection_id=sc.id, ctx=ctx, logger=ctx.logger
        )
        assert isinstance(data, SourceConnectionData)
        assert data.short_name == case.short_name
        assert data.source_class is _StubSourceValid
        if case.readable_auth_provider_id:
            assert data.readable_auth_provider_id == case.readable_auth_provider_id
        if case.config_fields:
            assert data.config_fields == case.config_fields
        if not case.has_cred_id and case.readable_auth_provider_id:
            assert data.integration_credential_id is None


# ===========================================================================
# _get_auth_configuration() — routing table
# ===========================================================================


@dataclass
class AuthConfigRoutingCase:
    id: str
    access_token: str | None = None
    readable_auth_provider_id: str | None = None
    auth_provider_config: dict | None = None
    expected_route: str = "database"  # "direct" | "auth_provider" | "database"


AUTH_CONFIG_ROUTING_TABLE = [
    AuthConfigRoutingCase(id="direct-token", access_token="tok-123",
                          expected_route="direct"),
    AuthConfigRoutingCase(id="direct-token-beats-auth-provider",
                          access_token="tok", readable_auth_provider_id="pd-1",
                          auth_provider_config={"k": "v"}, expected_route="direct"),
    AuthConfigRoutingCase(id="auth-provider", readable_auth_provider_id="pd-1",
                          auth_provider_config={"k": "v"},
                          expected_route="auth_provider"),
    AuthConfigRoutingCase(id="database-fallthrough", expected_route="database"),
    AuthConfigRoutingCase(id="auth-provider-id-but-no-config",
                          readable_auth_provider_id="pd-1",
                          expected_route="database"),
]


@pytest.mark.parametrize("case", AUTH_CONFIG_ROUTING_TABLE, ids=lambda c: c.id)
@pytest.mark.asyncio
async def test_get_auth_configuration_routing(case: AuthConfigRoutingCase):
    service = _make_service()
    ctx = _make_ctx()
    data = _sc_data(
        readable_auth_provider_id=case.readable_auth_provider_id,
        auth_provider_config=case.auth_provider_config,
    )

    if case.expected_route == "direct":
        result = await service._get_auth_configuration(
            db=MagicMock(), source_connection_data=data, ctx=ctx,
            logger=ctx.logger, access_token=case.access_token,
        )
        assert isinstance(result, AuthConfig)
        assert result.credentials == case.access_token
        assert result.auth_mode == AuthProviderMode.DIRECT
    elif case.expected_route == "auth_provider":
        with patch.object(service, "_get_auth_provider_configuration",
                          new_callable=AsyncMock) as mock_ap:
            mock_ap.return_value = AuthConfig(
                credentials="ap", auth_mode=AuthProviderMode.DIRECT,
                http_client_factory=None, auth_provider_instance=None,
            )
            result = await service._get_auth_configuration(
                db=MagicMock(), source_connection_data=data, ctx=ctx,
                logger=ctx.logger, access_token=case.access_token,
            )
            mock_ap.assert_called_once()
    else:
        with patch.object(service, "_get_database_credentials",
                          new_callable=AsyncMock) as mock_db:
            mock_db.return_value = AuthConfig(
                credentials="db", auth_mode=AuthProviderMode.DIRECT,
                http_client_factory=None, auth_provider_instance=None,
            )
            result = await service._get_auth_configuration(
                db=MagicMock(), source_connection_data=data, ctx=ctx,
                logger=ctx.logger, access_token=case.access_token,
            )
            mock_db.assert_called_once()


# ===========================================================================
# _get_database_credentials() — table-driven
# ===========================================================================


@dataclass
class DBCredCase:
    id: str
    has_cred_id: bool = True
    cred_found: bool = True
    auth_config_class: str | None = None
    expect_error: type | None = None
    error_match: str = ""


DB_CRED_TABLE = [
    DBCredCase(id="happy-no-auth-config"),
    DBCredCase(id="no-cred-id", has_cred_id=False,
               expect_error=NotFoundException, error_match="no integration credential"),
    DBCredCase(id="cred-not-found", cred_found=False,
               expect_error=NotFoundException, error_match="credential not found"),
    DBCredCase(id="with-auth-config-delegates", auth_config_class="StripeAuthConfig"),
]


@pytest.mark.parametrize("case", DB_CRED_TABLE, ids=lambda c: c.id)
@pytest.mark.asyncio
async def test_get_database_credentials(case: DBCredCase):
    cred = _mock_credential()
    cred_id = uuid4()
    cred_repo = FakeIntegrationCredentialRepository()
    if case.cred_found:
        cred_repo.seed(cred_id, cred)

    service = _make_service(cred_repo=cred_repo)
    ctx = _make_ctx()
    data = _sc_data(auth_config_class=case.auth_config_class)
    data.integration_credential_id = cred_id if case.has_cred_id else None

    if case.expect_error:
        with pytest.raises(case.expect_error, match=case.error_match):
            await service._get_database_credentials(
                db=MagicMock(), source_connection_data=data, ctx=ctx, logger=ctx.logger
            )
    elif case.auth_config_class:
        with (
            patch("airweave.domains.sources.lifecycle.credentials") as mock_creds,
            patch.object(service, "_handle_auth_config_credentials",
                         new_callable=AsyncMock) as mock_handle,
        ):
            mock_creds.decrypt.return_value = {"api_key": "sk"}
            mock_handle.return_value = {"api_key": "sk"}
            result = await service._get_database_credentials(
                db=MagicMock(), source_connection_data=data, ctx=ctx, logger=ctx.logger
            )
        assert isinstance(result, AuthConfig)
        assert result.credentials == {"api_key": "sk"}
        mock_handle.assert_called_once()
    else:
        with patch("airweave.domains.sources.lifecycle.credentials") as mock_creds:
            mock_creds.decrypt.return_value = {"access_token": "decrypted"}
            result = await service._get_database_credentials(
                db=MagicMock(), source_connection_data=data, ctx=ctx, logger=ctx.logger
            )
        assert isinstance(result, AuthConfig)
        assert result.credentials == {"access_token": "decrypted"}
        assert result.auth_mode == AuthProviderMode.DIRECT


# ===========================================================================
# _handle_auth_config_credentials() — table-driven
# ===========================================================================


@dataclass
class HandleAuthConfigCase:
    id: str
    has_auth_config_ref: bool = True
    has_refresh_token: bool = False
    refresh_token_value: str = ""
    expect_raw_passthrough: bool = False


HANDLE_AUTH_CONFIG_TABLE = [
    HandleAuthConfigCase(id="no-auth-config-ref-passthrough",
                         has_auth_config_ref=False, expect_raw_passthrough=True),
    HandleAuthConfigCase(id="no-refresh-token-returns-validated",
                         has_auth_config_ref=True, has_refresh_token=False),
    HandleAuthConfigCase(id="with-refresh-token-refreshes",
                         has_auth_config_ref=True, has_refresh_token=True,
                         refresh_token_value="ref-tok"),
]


@pytest.mark.parametrize("case", HANDLE_AUTH_CONFIG_TABLE, ids=lambda c: c.id)
@pytest.mark.asyncio
async def test_handle_auth_config_credentials(case: HandleAuthConfigCase):
    mock_auth_config = MagicMock()
    if case.has_refresh_token:
        mock_validated = MagicMock()
        mock_validated.refresh_token = case.refresh_token_value
    else:
        mock_validated = MagicMock(spec=[])
    mock_auth_config.model_validate.return_value = mock_validated

    entry = _entry_with_class("src", _StubSourceValid)
    if case.has_auth_config_ref:
        object.__setattr__(entry, "auth_config_ref", mock_auth_config)

    oauth2_fake = FakeOAuth2Service()
    if case.has_refresh_token:
        oauth2_fake.seed_refresh("src", "new-access-tok")

    service = _make_service(source_entries=[entry], oauth2_service=oauth2_fake)
    decrypted = {"access_token": "old", "refresh_token": case.refresh_token_value}
    data = _sc_data(short_name="src", auth_config_class="Cfg")

    result = await service._handle_auth_config_credentials(
        db=MagicMock(), source_connection_data=data,
        decrypted_credential=decrypted, ctx=_make_ctx(), connection_id=uuid4(),
    )

    if case.expect_raw_passthrough:
        assert result == decrypted
    elif case.has_refresh_token:
        assert result is mock_auth_config.model_validate.return_value
        expected_dict = {**decrypted, "access_token": "new-access-tok"}
        mock_auth_config.model_validate.assert_called_with(expected_dict)
        assert len(oauth2_fake._calls) == 1
    else:
        assert result is mock_validated


@pytest.mark.asyncio
async def test_handle_auth_config_oauth2_error_propagates():
    mock_auth_config = MagicMock()
    mock_validated = MagicMock()
    mock_validated.refresh_token = "ref"
    mock_auth_config.model_validate.return_value = mock_validated

    entry = _entry_with_class("src", _StubSourceValid)
    object.__setattr__(entry, "auth_config_ref", mock_auth_config)

    oauth2_fake = FakeOAuth2Service()
    oauth2_fake.set_error(RuntimeError("token server down"))

    service = _make_service(source_entries=[entry], oauth2_service=oauth2_fake)
    data = _sc_data(short_name="src")

    with pytest.raises(RuntimeError, match="token server down"):
        await service._handle_auth_config_credentials(
            db=MagicMock(), source_connection_data=data,
            decrypted_credential={"access_token": "x", "refresh_token": "ref"},
            ctx=_make_ctx(), connection_id=uuid4(),
        )


# ===========================================================================
# _process_credentials_for_source() — table-driven
# ===========================================================================


@dataclass
class ProcessCredsCase:
    id: str
    oauth_type: str | None = None
    has_auth_config_ref: bool = False
    raw_credentials: Any = "plain-token"
    expected: Any = "plain-token"
    expect_error: type | None = None


PROCESS_CREDS_TABLE = [
    ProcessCredsCase(id="passthrough-no-oauth-no-config",
                     raw_credentials="plain-token", expected="plain-token"),
    ProcessCredsCase(id="oauth-extract-access-token", oauth_type="with_refresh",
                     raw_credentials={"access_token": "tok", "refresh_token": "r"},
                     expected="tok"),
    ProcessCredsCase(id="oauth-string-passthrough", oauth_type="access_only",
                     raw_credentials="already-string", expected="already-string"),
    ProcessCredsCase(id="oauth-unexpected-format-passthrough", oauth_type="access_only",
                     raw_credentials=12345, expected=12345),
    ProcessCredsCase(id="auth-config-dict-conversion", has_auth_config_ref=True,
                     raw_credentials={"api_key": "sk"}, expected="VALIDATED"),
    ProcessCredsCase(id="auth-config-conversion-error", has_auth_config_ref=True,
                     raw_credentials={"bad": "x"}, expect_error=ValueError),
]


@pytest.mark.parametrize("case", PROCESS_CREDS_TABLE, ids=lambda c: c.id)
def test_process_credentials_for_source(case: ProcessCredsCase):
    mock_config_class = MagicMock()
    mock_config_class.__name__ = "TestAuthConfig"

    if case.expect_error:
        mock_config_class.model_validate.side_effect = ValueError("invalid")
    else:
        mock_config_class.model_validate.return_value = "VALIDATED"

    entry = _entry_with_class("src", _StubSourceValid)
    if case.has_auth_config_ref:
        object.__setattr__(entry, "auth_config_ref", mock_config_class)

    service = _make_service(source_entries=[entry])
    ctx = _make_ctx()
    data = _sc_data(short_name="src", oauth_type=case.oauth_type,
                    auth_config_class="TestAuthConfig" if case.has_auth_config_ref else None)

    if case.expect_error:
        with pytest.raises(case.expect_error):
            service._process_credentials_for_source(
                raw_credentials=case.raw_credentials,
                source_connection_data=data, logger=ctx.logger,
            )
    else:
        result = service._process_credentials_for_source(
            raw_credentials=case.raw_credentials,
            source_connection_data=data, logger=ctx.logger,
        )
        assert result == case.expected


# ===========================================================================
# _configure_token_manager() — table-driven
# ===========================================================================


@dataclass
class TokenManagerCase:
    id: str
    access_token: str | None = None
    auth_mode: AuthProviderMode = AuthProviderMode.DIRECT
    oauth_type: str | None = None
    expect_tm_set: bool = False


TOKEN_MANAGER_TABLE = [
    TokenManagerCase(id="skip-direct-injection", access_token="injected"),
    TokenManagerCase(id="skip-proxy-mode", auth_mode=AuthProviderMode.PROXY),
    TokenManagerCase(id="skip-no-oauth-type", oauth_type=None),
    TokenManagerCase(id="skip-access-only-oauth", oauth_type="access_only"),
    TokenManagerCase(id="happy-with-refresh", oauth_type="with_refresh",
                     expect_tm_set=True),
    TokenManagerCase(id="happy-rotating-refresh", oauth_type="with_rotating_refresh",
                     expect_tm_set=True),
]


@pytest.mark.parametrize("case", TOKEN_MANAGER_TABLE, ids=lambda c: c.id)
@pytest.mark.asyncio
async def test_configure_token_manager(case: TokenManagerCase):
    source = MagicMock() if case.expect_tm_set else await _StubSourceValid.create("tok")
    data = _sc_data(short_name="src", oauth_type=case.oauth_type)
    ctx = _make_ctx()
    auth_config = AuthConfig(
        credentials="tok",
        http_client_factory=None,
        auth_provider_instance=None,
        auth_mode=case.auth_mode,
    )

    if case.expect_tm_set:
        with patch("airweave.domains.sources.lifecycle.TokenManager") as mock_tm:
            mock_tm.return_value = MagicMock()
            await SourceLifecycleService._configure_token_manager(
                db=MagicMock(), source=source, source_connection_data=data,
                source_credentials="tok", ctx=ctx, logger=ctx.logger,
                access_token=case.access_token, auth_config=auth_config,
            )
        source.set_token_manager.assert_called_once()
    else:
        await SourceLifecycleService._configure_token_manager(
            db=MagicMock(), source=source, source_connection_data=data,
            source_credentials="tok", ctx=ctx, logger=ctx.logger,
            access_token=case.access_token, auth_config=auth_config,
        )
        assert source._token_manager is None


# ===========================================================================
# _configure_* static helpers — table-driven
# ===========================================================================


class TestConfigureLogger:
    def test_sets_logger(self):
        source = MagicMock()
        logger = MagicMock()
        SourceLifecycleService._configure_logger(source, logger)
        source.set_logger.assert_called_once_with(logger)

    def test_noop_when_no_set_logger(self):
        source = MagicMock(spec=[])
        SourceLifecycleService._configure_logger(source, MagicMock())


class TestConfigureHttpClientFactory:
    def test_sets_when_present(self):
        source = MagicMock()
        factory = MagicMock()
        ac = AuthConfig(
            credentials="x", http_client_factory=factory,
            auth_provider_instance=None, auth_mode=AuthProviderMode.DIRECT,
        )
        SourceLifecycleService._configure_http_client_factory(source, ac)
        source.set_http_client_factory.assert_called_once_with(factory)

    def test_noop_when_none(self):
        source = MagicMock()
        ac = AuthConfig(
            credentials="x", http_client_factory=None,
            auth_provider_instance=None, auth_mode=AuthProviderMode.DIRECT,
        )
        SourceLifecycleService._configure_http_client_factory(source, ac)
        source.set_http_client_factory.assert_not_called()


class TestConfigureSyncIdentifiers:
    def test_happy(self):
        source = MagicMock()
        ctx = _make_ctx()
        SourceLifecycleService._configure_sync_identifiers(source, _sc_data(), ctx)
        source.set_sync_identifiers.assert_called_once()

    def test_swallows_exception(self):
        source = MagicMock()
        source.set_sync_identifiers.side_effect = AttributeError
        ctx = _make_ctx()
        SourceLifecycleService._configure_sync_identifiers(source, _sc_data(), ctx)


# ===========================================================================
# _wrap_source_with_airweave_client() — table-driven
# ===========================================================================


@dataclass
class WrapClientCase:
    id: str
    has_existing_factory: bool = False


WRAP_CLIENT_TABLE = [
    WrapClientCase(id="no-existing-factory"),
    WrapClientCase(id="with-existing-factory", has_existing_factory=True),
]


@pytest.mark.parametrize("case", WRAP_CLIENT_TABLE, ids=lambda c: c.id)
def test_wrap_source_with_airweave_client(case: WrapClientCase):
    source = _StubSourceValid()
    original = MagicMock() if case.has_existing_factory else None
    source._http_client_factory = original
    ctx = _make_ctx()

    SourceLifecycleService._wrap_source_with_airweave_client(
        source=source, source_short_name="src",
        source_connection_id=uuid4(), ctx=ctx, logger=ctx.logger,
    )

    assert source._http_client_factory is not None
    assert source._http_client_factory is not original


# ===========================================================================
# _merge_source_config() — table-driven
# ===========================================================================


@dataclass
class MergeConfigCase:
    id: str
    existing: dict | None
    provider: dict
    expected_key: str
    expected_value: str


MERGE_CONFIG_TABLE = [
    MergeConfigCase(id="new-key-added", existing={},
                    provider={"k": "v"}, expected_key="k", expected_value="v"),
    MergeConfigCase(id="user-value-preserved", existing={"k": "user"},
                    provider={"k": "provider"}, expected_key="k", expected_value="user"),
    MergeConfigCase(id="none-value-overwritten", existing={"k": None},
                    provider={"k": "provider"}, expected_key="k", expected_value="provider"),
    MergeConfigCase(id="null-config-fields", existing=None,
                    provider={"k": "v"}, expected_key="k", expected_value="v"),
]


@pytest.mark.parametrize("case", MERGE_CONFIG_TABLE, ids=lambda c: c.id)
def test_merge_source_config(case: MergeConfigCase):
    data = _sc_data()
    data.config_fields = case.existing  # may be None for the null-config-fields case
    SourceLifecycleService._merge_source_config(data, case.provider)
    assert data.config_fields[case.expected_key] == case.expected_value


# ===========================================================================
# _build_source_config_field_mappings() — table-driven
# ===========================================================================


@dataclass
class ConfigMappingCase:
    id: str
    short_name: str | None = None
    in_registry: bool = False
    has_config_ref: bool = False
    has_auth_field: bool = False
    expected: dict = field(default_factory=dict)


CONFIG_MAPPING_TABLE = [
    ConfigMappingCase(id="no-short-name", short_name=None),
    ConfigMappingCase(id="not-in-registry", short_name="unknown"),
    ConfigMappingCase(id="no-config-ref", short_name="src", in_registry=True),
    ConfigMappingCase(id="config-no-auth-fields", short_name="src",
                      in_registry=True, has_config_ref=True),
    ConfigMappingCase(id="with-auth-field", short_name="src",
                      in_registry=True, has_config_ref=True, has_auth_field=True,
                      expected={"org": "org_slug"}),
]


@pytest.mark.parametrize("case", CONFIG_MAPPING_TABLE, ids=lambda c: c.id)
def test_build_source_config_field_mappings(case: ConfigMappingCase):
    entries = []
    if case.in_registry:
        entry = _entry_with_class(case.short_name, _StubSourceValid)
        if case.has_config_ref:
            if case.has_auth_field:
                mock_field = MagicMock()
                mock_field.json_schema_extra = {"auth_provider_field": "org_slug"}
                config_cls = type("Cfg", (), {"model_fields": {"org": mock_field}})
            else:
                plain_field = MagicMock()
                plain_field.json_schema_extra = None
                config_cls = type("Cfg", (), {"model_fields": {"f": plain_field}})
            object.__setattr__(entry, "config_ref", config_cls)
        entries.append(entry)

    service = _make_service(source_entries=entries)
    data = _sc_data(short_name=case.short_name or "")
    result = service._build_source_config_field_mappings(data)
    assert result == case.expected


# ===========================================================================
# _create_auth_provider_instance() — table-driven
# ===========================================================================


@dataclass
class AuthProviderInstanceCase:
    id: str
    conn_found: bool = True
    has_cred_id: bool = True
    cred_found: bool = True
    in_ap_registry: bool = True
    expect_error: type | None = None
    error_match: str = ""


AUTH_PROVIDER_INSTANCE_TABLE = [
    AuthProviderInstanceCase(id="happy-path"),
    AuthProviderInstanceCase(id="conn-not-found", conn_found=False,
                             expect_error=NotFoundException, error_match="readable_id"),
    AuthProviderInstanceCase(id="no-cred-on-conn", has_cred_id=False,
                             expect_error=NotFoundException, error_match="no integration credential"),
    AuthProviderInstanceCase(id="cred-not-found", cred_found=False,
                             expect_error=NotFoundException, error_match="credential not found"),
    AuthProviderInstanceCase(id="not-in-ap-registry", in_ap_registry=False,
                             expect_error=NotFoundException, error_match="not found in registry"),
]


@pytest.mark.parametrize("case", AUTH_PROVIDER_INSTANCE_TABLE, ids=lambda c: c.id)
@pytest.mark.asyncio
async def test_create_auth_provider_instance(case: AuthProviderInstanceCase):
    mock_provider_instance = MagicMock()

    class _StubProvider:
        create = AsyncMock(return_value=mock_provider_instance)

    conn = _mock_connection()
    if not case.has_cred_id:
        conn.integration_credential_id = None
    cred = _mock_credential()

    conn_repo = FakeConnectionRepository()
    if case.conn_found:
        conn_repo.seed_readable("pd-1", conn)

    cred_repo = FakeIntegrationCredentialRepository()
    if case.cred_found and case.has_cred_id:
        cred_repo.seed(conn.integration_credential_id, cred)

    ap_entries = []
    if case.in_ap_registry:
        ap_entries.append(_make_auth_provider_entry(
            short_name=conn.short_name, provider_class_ref=_StubProvider))

    service = _make_service(conn_repo=conn_repo, cred_repo=cred_repo,
                            auth_provider_entries=ap_entries)
    ctx = _make_ctx()

    if case.expect_error:
        with patch("airweave.domains.sources.lifecycle.credentials") as mock_creds:
            mock_creds.decrypt.return_value = {"token": "d"}
            with pytest.raises(case.expect_error, match=case.error_match):
                await service._create_auth_provider_instance(
                    db=MagicMock(), readable_auth_provider_id="pd-1",
                    auth_provider_config={}, ctx=ctx, logger=ctx.logger,
                )
    else:
        with patch("airweave.domains.sources.lifecycle.credentials") as mock_creds:
            mock_creds.decrypt.return_value = {"token": "d"}
            result = await service._create_auth_provider_instance(
                db=MagicMock(), readable_auth_provider_id="pd-1",
                auth_provider_config={"env": "prd"}, ctx=ctx, logger=ctx.logger,
            )
        assert result is mock_provider_instance
        _StubProvider.create.assert_called_once()


# ===========================================================================
# create() — full orchestration table
# ===========================================================================


@dataclass
class CreateCase:
    id: str
    access_token: str | None = None
    expect_logger: bool = True
    expect_http_client: bool = True


CREATE_TABLE = [
    CreateCase(id="db-creds-no-sync-job"),
    CreateCase(id="access-token-injection", access_token="injected"),
]


@pytest.mark.parametrize("case", CREATE_TABLE, ids=lambda c: c.id)
@pytest.mark.asyncio
async def test_create(case: CreateCase):
    sc = _mock_source_connection(short_name="src")
    conn = _mock_connection()
    cred = _mock_credential()
    entry = _entry_with_class("src", _StubSourceValid)

    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)
    conn_repo = FakeConnectionRepository()
    conn_repo.seed(sc.connection_id, conn)
    cred_repo = FakeIntegrationCredentialRepository()
    cred_repo.seed(conn.integration_credential_id, cred)

    service = _make_service(source_entries=[entry], sc_repo=sc_repo,
                            conn_repo=conn_repo, cred_repo=cred_repo)
    ctx = _make_ctx()

    with patch("airweave.domains.sources.lifecycle.credentials") as mock_creds:
        mock_creds.decrypt.return_value = {"access_token": "tok"}

        source = await service.create(
            db=MagicMock(), source_connection_id=sc.id, ctx=ctx,
            access_token=case.access_token,
        )

    assert isinstance(source, _StubSourceValid)
    if case.expect_logger:
        assert source._logger is not None
    if case.expect_http_client:
        assert source._http_client_factory is not None


# ===========================================================================
# FakeSourceLifecycleService — test double correctness
# ===========================================================================


@pytest.mark.asyncio
async def test_fake_lifecycle_service():
    from airweave.domains.sources.fakes.lifecycle import FakeSourceLifecycleService

    fake = FakeSourceLifecycleService()
    sc_id = uuid4()
    mock_source = MagicMock()
    fake.seed_source(sc_id, mock_source)

    result = await fake.create(MagicMock(), sc_id, MagicMock())
    assert result is mock_source
    assert len(fake.create_calls) == 1

    await fake.validate("slack", "tok")
    assert len(fake.validate_calls) == 1

    fake.set_validate_raises("bad", SourceValidationError("bad", "boom"))
    with pytest.raises(SourceValidationError):
        await fake.validate("bad", "tok")

    fake.clear()
    assert len(fake.create_calls) == 0

    with pytest.raises(KeyError):
        await fake.create(MagicMock(), uuid4(), MagicMock())
