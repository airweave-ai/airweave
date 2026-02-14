"""Credential domain test fixtures."""

from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, Field

from airweave.domains.credentials.service import CredentialService
from airweave.domains.sources.fake import FakeSourceRegistry
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.platform.configs._base import Fields


# ---------------------------------------------------------------------------
# Fake config / auth config classes for testing
# ---------------------------------------------------------------------------


class FakeAuthConfig(BaseModel):
    """Fake auth config with one required and one optional field."""

    api_key: str
    api_secret: Optional[str] = None


class FakeConfigClass(BaseModel):
    """Fake source config with a feature-gated field."""

    repo_name: str = Field(default="default")
    premium_field: Optional[str] = Field(
        default=None,
        json_schema_extra={"feature_flag": "premium_feature"},
    )


# ---------------------------------------------------------------------------
# Fake source class
# ---------------------------------------------------------------------------


class FakeSourceClass:
    """Minimal fake source class with configurable .validate() behavior."""

    _validate_result: bool = True

    @classmethod
    async def create(cls, *args, **kwargs) -> "FakeSourceClass":
        return cls()

    async def validate(self) -> bool:
        return self._validate_result

    def set_logger(self, logger):
        pass


class FailingSourceClass:
    """Source class whose .validate() returns False."""

    @classmethod
    async def create(cls, *args, **kwargs) -> "FailingSourceClass":
        return cls()

    async def validate(self) -> bool:
        return False

    def set_logger(self, logger):
        pass


class ExplodingSourceClass:
    """Source class whose .validate() raises."""

    @classmethod
    async def create(cls, *args, **kwargs) -> "ExplodingSourceClass":
        return cls()

    async def validate(self) -> bool:
        raise ConnectionError("Connection refused")

    def set_logger(self, logger):
        pass


class NoValidateSourceClass:
    """Source class with no .validate() method."""

    @classmethod
    async def create(cls, *args, **kwargs) -> "NoValidateSourceClass":
        return cls()

    def set_logger(self, logger):
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_entry(
    short_name: str = "stripe",
    name: str = "Stripe",
    *,
    source_class_ref: type = FakeSourceClass,
    auth_config_ref: Optional[type] = FakeAuthConfig,
    config_ref: Optional[type] = None,
) -> SourceRegistryEntry:
    """Build a minimal SourceRegistryEntry for credential tests."""
    return SourceRegistryEntry(
        short_name=short_name,
        name=name,
        description=f"Test {name}",
        class_name=f"{name}Source",
        source_class_ref=source_class_ref,
        config_ref=config_ref,
        auth_config_ref=auth_config_ref,
        auth_fields=Fields(fields=[]),
        config_fields=Fields(fields=[]),
        supported_auth_providers=[],
        runtime_auth_all_fields=[],
        runtime_auth_optional_fields=set(),
        auth_methods=["direct"],
        oauth_type=None,
        requires_byoc=False,
        supports_continuous=False,
        federated_search=False,
        supports_temporal_relevance=False,
        supports_access_control=False,
        rate_limit_level=None,
        feature_flag=None,
        labels=None,
        output_entity_definitions=[],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def source_registry():
    """FakeSourceRegistry seeded with a direct-auth source."""
    registry = FakeSourceRegistry()
    registry.seed(make_entry("stripe", "Stripe"))
    return registry


@pytest.fixture
def credential_repo():
    """Fake integration credential repository."""
    from airweave.domains.credentials.fake_repository import FakeIntegrationCredentialRepository

    return FakeIntegrationCredentialRepository()


@pytest.fixture
def service(source_registry, credential_repo):
    """CredentialService wired to fake registry and fake repo."""
    return CredentialService(source_registry=source_registry, credential_repo=credential_repo)
