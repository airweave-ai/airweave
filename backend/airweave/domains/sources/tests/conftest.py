"""Source domain test fixtures.

Provides a pre-built SourceRegistryEntry, fake registry, fake ApiContext,
and a wired SourceService for testing in isolation.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod, FeatureFlag
from airweave.domains.sources.fake import FakeSourceRegistry
from airweave.domains.sources.service import SourceService
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.platform.configs._base import Fields
from airweave.schemas.organization import Organization


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    short_name: str = "slack",
    name: str = "Slack",
    *,
    feature_flag: str | None = None,
    auth_methods: list[str] | None = None,
    requires_byoc: bool = False,
) -> SourceRegistryEntry:
    """Build a minimal SourceRegistryEntry for tests."""
    return SourceRegistryEntry(
        short_name=short_name,
        name=name,
        description=f"Test {name} source",
        class_name=f"{name}Source",
        source_class_ref=type(name, (), {}),
        config_ref=None,
        auth_config_ref=None,
        auth_fields=Fields(fields=[]),
        config_fields=Fields(fields=[]),
        supported_auth_providers=[],
        runtime_auth_all_fields=[],
        runtime_auth_optional_fields=set(),
        auth_methods=auth_methods or ["direct"],
        oauth_type=None,
        requires_byoc=requires_byoc,
        supports_continuous=False,
        federated_search=False,
        supports_temporal_relevance=True,
        supports_access_control=False,
        rate_limit_level=None,
        feature_flag=feature_flag,
        labels=None,
        output_entity_definitions=[],
    )


def _make_ctx(enabled_features: list | None = None) -> ApiContext:
    """Build a minimal ApiContext for tests."""
    now = datetime.now(timezone.utc)
    org = Organization(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Org",
        created_at=now,
        modified_at=now,
        enabled_features=enabled_features or [],
    )
    return ApiContext(
        request_id="test-req-001",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        auth_metadata={},
        logger=logger.with_context(request_id="test-req-001"),
    )


def _make_settings(environment: str = "cloud") -> MagicMock:
    """Build a minimal mock Settings."""
    settings = MagicMock()
    settings.ENVIRONMENT = environment
    return settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def slack_entry():
    """A plain source entry with no feature flag."""
    return _make_entry("slack", "Slack")


@pytest.fixture
def github_entry():
    """A plain source entry with no feature flag."""
    return _make_entry("github", "GitHub")


@pytest.fixture
def flagged_entry():
    """A source entry gated behind a feature flag."""
    return _make_entry(
        "sharepoint2019v2",
        "SharePoint 2019 V2",
        feature_flag="sharepoint_2019_v2",
    )


@pytest.fixture
def oauth_entry():
    """A source entry using OAuth auth methods."""
    return _make_entry(
        "gmail",
        "Gmail",
        auth_methods=["oauth_browser", "oauth_token"],
        requires_byoc=False,
    )


@pytest.fixture
def source_registry(slack_entry, github_entry):
    """FakeSourceRegistry seeded with two plain sources."""
    registry = FakeSourceRegistry()
    registry.seed(slack_entry, github_entry)
    return registry


@pytest.fixture
def cloud_settings():
    """Settings with ENVIRONMENT=cloud."""
    return _make_settings("cloud")


@pytest.fixture
def self_hosted_settings():
    """Settings with ENVIRONMENT=self-hosted."""
    return _make_settings("self-hosted")


@pytest.fixture
def ctx():
    """ApiContext with no feature flags enabled."""
    return _make_ctx()


@pytest.fixture
def ctx_with_sharepoint_flag():
    """ApiContext with sharepoint_2019_v2 feature flag enabled."""
    return _make_ctx(enabled_features=[FeatureFlag.SHAREPOINT_2019_V2])


@pytest.fixture
def service(source_registry, cloud_settings):
    """SourceService wired to fake registry and cloud settings."""
    return SourceService(source_registry=source_registry, settings=cloud_settings)
