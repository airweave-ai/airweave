"""Unit tests for CredentialService.

Table-driven tests using FakeSourceRegistry and fake source classes.
No database, no real sources loaded.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

import pytest

from airweave.domains.credentials.exceptions import (
    FeatureFlagRequiredError,
    InvalidAuthFieldsError,
    InvalidConfigFieldsError,
    InvalidCredentialsError,
    SourceDoesNotSupportDirectAuthError,
)
from airweave.domains.credentials.fake_repository import FakeIntegrationCredentialRepository
from airweave.domains.credentials.service import CredentialService
from airweave.domains.credentials.tests.conftest import (
    ExplodingSourceClass,
    FailingSourceClass,
    FakeAuthConfig,
    FakeConfigClass,
    FakeSourceClass,
    NoValidateSourceClass,
    make_entry,
)
from airweave.domains.sources.exceptions import SourceNotFoundError
from airweave.domains.sources.fake import FakeSourceRegistry


def _make_service(registry: FakeSourceRegistry) -> CredentialService:
    """Build a CredentialService with a fake registry and fake repo."""
    return CredentialService(
        source_registry=registry,
        credential_repo=FakeIntegrationCredentialRepository(),
    )


# ---------------------------------------------------------------------------
# validate_auth_fields
# ---------------------------------------------------------------------------


@dataclass
class AuthFieldsCase:
    desc: str
    short_name: str
    auth_fields: dict
    seed_entry: bool = True
    auth_config_ref: Optional[type] = FakeAuthConfig
    expect_error: Optional[type] = None


AUTH_FIELDS_CASES = [
    AuthFieldsCase(
        desc="valid fields returns auth config",
        short_name="stripe",
        auth_fields={"api_key": "sk_test_123"},
    ),
    AuthFieldsCase(
        desc="valid fields with optional",
        short_name="stripe",
        auth_fields={"api_key": "sk_test_123", "api_secret": "sec"},
    ),
    AuthFieldsCase(
        desc="unknown source raises SourceNotFoundError",
        short_name="nonexistent",
        auth_fields={"api_key": "x"},
        seed_entry=False,
        expect_error=SourceNotFoundError,
    ),
    AuthFieldsCase(
        desc="source without auth_config_ref raises",
        short_name="oauth_only",
        auth_fields={"api_key": "x"},
        auth_config_ref=None,
        expect_error=SourceDoesNotSupportDirectAuthError,
    ),
    AuthFieldsCase(
        desc="missing required field raises InvalidAuthFieldsError",
        short_name="stripe",
        auth_fields={},
        expect_error=InvalidAuthFieldsError,
    ),
    AuthFieldsCase(
        desc="wrong type raises InvalidAuthFieldsError",
        short_name="stripe",
        auth_fields={"api_key": 123},
        expect_error=InvalidAuthFieldsError,
    ),
]


@pytest.mark.parametrize("case", AUTH_FIELDS_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_validate_auth_fields(case: AuthFieldsCase):
    registry = FakeSourceRegistry()
    if case.seed_entry:
        entry = make_entry(
            case.short_name, case.short_name.title(), auth_config_ref=case.auth_config_ref
        )
        registry.seed(entry)
    service = _make_service(registry)

    if case.expect_error:
        with pytest.raises(case.expect_error):
            await service.validate_auth_fields(case.short_name, case.auth_fields)
    else:
        result = await service.validate_auth_fields(case.short_name, case.auth_fields)
        assert isinstance(result, FakeAuthConfig)
        assert result.api_key == case.auth_fields["api_key"]


# ---------------------------------------------------------------------------
# validate_config_fields
# ---------------------------------------------------------------------------


@dataclass
class ConfigFieldsCase:
    desc: str
    short_name: str
    config_fields: Any
    enabled_features: list = field(default_factory=list)
    config_ref: Optional[type] = FakeConfigClass
    seed_entry: bool = True
    expect_error: Optional[type] = None
    expect_result: Optional[dict] = None


CONFIG_FIELDS_CASES = [
    ConfigFieldsCase(
        desc="valid config returns dict",
        short_name="src",
        config_fields={"repo_name": "my-repo"},
        expect_result={"repo_name": "my-repo", "premium_field": None},
    ),
    ConfigFieldsCase(
        desc="empty config returns empty dict",
        short_name="src",
        config_fields=None,
        expect_result={},
    ),
    ConfigFieldsCase(
        desc="empty dict config returns empty dict",
        short_name="src",
        config_fields={},
        expect_result={},
    ),
    ConfigFieldsCase(
        desc="source without config_ref returns normalized dict",
        short_name="no_config",
        config_fields={"anything": "goes"},
        config_ref=None,
        expect_result={"anything": "goes"},
    ),
    ConfigFieldsCase(
        desc="feature-gated field without flag raises FeatureFlagRequiredError",
        short_name="src",
        config_fields={"repo_name": "r", "premium_field": "value"},
        expect_error=FeatureFlagRequiredError,
    ),
    ConfigFieldsCase(
        desc="feature-gated field with flag passes",
        short_name="src",
        config_fields={"repo_name": "r", "premium_field": "value"},
        enabled_features=["premium_feature"],
        expect_result={"repo_name": "r", "premium_field": "value"},
    ),
    ConfigFieldsCase(
        desc="unknown source raises SourceNotFoundError",
        short_name="nonexistent",
        config_fields={"x": 1},
        seed_entry=False,
        expect_error=SourceNotFoundError,
    ),
]


@pytest.mark.parametrize("case", CONFIG_FIELDS_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_validate_config_fields(case: ConfigFieldsCase):
    registry = FakeSourceRegistry()
    if case.seed_entry:
        entry = make_entry(case.short_name, case.short_name.title(), config_ref=case.config_ref)
        registry.seed(entry)
    service = _make_service(registry)

    if case.expect_error:
        with pytest.raises(case.expect_error):
            await service.validate_config_fields(
                case.short_name, case.config_fields, case.enabled_features
            )
    else:
        result = await service.validate_config_fields(
            case.short_name, case.config_fields, case.enabled_features
        )
        if case.expect_result is not None:
            assert result == case.expect_result


# ---------------------------------------------------------------------------
# validate_direct_auth
# ---------------------------------------------------------------------------


@dataclass
class DirectAuthCase:
    desc: str
    source_class_ref: type
    expect_error: Optional[type] = None


DIRECT_AUTH_CASES = [
    DirectAuthCase(
        desc="valid credentials succeed",
        source_class_ref=FakeSourceClass,
    ),
    DirectAuthCase(
        desc="invalid credentials raise InvalidCredentialsError",
        source_class_ref=FailingSourceClass,
        expect_error=InvalidCredentialsError,
    ),
    DirectAuthCase(
        desc="source.validate() exception raises InvalidCredentialsError",
        source_class_ref=ExplodingSourceClass,
        expect_error=InvalidCredentialsError,
    ),
    DirectAuthCase(
        desc="source without validate raises InvalidCredentialsError",
        source_class_ref=NoValidateSourceClass,
        expect_error=InvalidCredentialsError,
    ),
]


@pytest.mark.parametrize("case", DIRECT_AUTH_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_validate_direct_auth(case: DirectAuthCase):
    registry = FakeSourceRegistry()
    registry.seed(make_entry("stripe", "Stripe", source_class_ref=case.source_class_ref))
    service = _make_service(registry)

    if case.expect_error:
        with pytest.raises(case.expect_error):
            await service.validate_direct_auth("stripe", {"api_key": "x"}, None)
    else:
        await service.validate_direct_auth("stripe", {"api_key": "x"}, None)


# ---------------------------------------------------------------------------
# validate_oauth_token
# ---------------------------------------------------------------------------


@dataclass
class OAuthTokenCase:
    desc: str
    source_class_ref: type
    expect_error: Optional[type] = None


OAUTH_TOKEN_CASES = [
    OAuthTokenCase(
        desc="valid token succeeds",
        source_class_ref=FakeSourceClass,
    ),
    OAuthTokenCase(
        desc="invalid token raises InvalidCredentialsError",
        source_class_ref=FailingSourceClass,
        expect_error=InvalidCredentialsError,
    ),
    OAuthTokenCase(
        desc="token exchange error raises InvalidCredentialsError",
        source_class_ref=ExplodingSourceClass,
        expect_error=InvalidCredentialsError,
    ),
]


@pytest.mark.parametrize("case", OAUTH_TOKEN_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_validate_oauth_token(case: OAuthTokenCase):
    registry = FakeSourceRegistry()
    registry.seed(make_entry("notion", "Notion", source_class_ref=case.source_class_ref))
    service = _make_service(registry)

    if case.expect_error:
        with pytest.raises(case.expect_error):
            await service.validate_oauth_token("notion", "fake-token", None)
    else:
        await service.validate_oauth_token("notion", "fake-token", None)


# ---------------------------------------------------------------------------
# validate_direct_auth for unknown source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_direct_auth_unknown_source():
    service = _make_service(FakeSourceRegistry())
    with pytest.raises(SourceNotFoundError):
        await service.validate_direct_auth("nonexistent", {}, None)


@pytest.mark.asyncio
async def test_validate_oauth_token_unknown_source():
    service = _make_service(FakeSourceRegistry())
    with pytest.raises(SourceNotFoundError):
        await service.validate_oauth_token("nonexistent", "token", None)


# ---------------------------------------------------------------------------
# _as_mapping
# ---------------------------------------------------------------------------


class TestAsMapping:
    def test_dict_passthrough(self):
        assert CredentialService._as_mapping({"a": 1}) == {"a": 1}

    def test_pydantic_model(self):
        result = CredentialService._as_mapping(FakeAuthConfig(api_key="k"))
        assert result["api_key"] == "k"

    def test_unsupported_type_raises(self):
        with pytest.raises(TypeError):
            CredentialService._as_mapping(42)
