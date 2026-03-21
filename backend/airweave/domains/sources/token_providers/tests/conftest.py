"""Token providers test fixtures.

Provides lightweight fakes for OAuth2Service, AuthProvider, and SourceRegistry
so token provider tests run without any real I/O.
"""

from __future__ import annotations

from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.core.logging import logger
from airweave.domains.oauth.types import RefreshResult
from airweave.domains.sources.token_providers.protocol import AuthProviderKind
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.platform.configs._base import Fields


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_oauth2_service(
    *,
    refresh_result: Optional[RefreshResult] = None,
    refresh_error: Optional[Exception] = None,
) -> AsyncMock:
    """Build a fake OAuth2ServiceProtocol.

    If ``refresh_error`` is set, ``refresh_and_persist`` raises it.
    Otherwise returns ``refresh_result`` (defaults to a fresh token).
    """
    svc = AsyncMock()
    if refresh_error:
        svc.refresh_and_persist.side_effect = refresh_error
    else:
        result = refresh_result or RefreshResult(access_token="refreshed-tok", expires_in=3600)
        svc.refresh_and_persist.return_value = result
    return svc


def make_ctx() -> MagicMock:
    """Build a minimal ApiContext mock."""
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = uuid4()
    ctx.logger = logger.with_context(request_id="test-tp")
    return ctx


def make_registry_entry(
    short_name: str = "github",
    *,
    runtime_auth_all_fields: Optional[list[str]] = None,
    runtime_auth_optional_fields: Optional[set[str]] = None,
) -> SourceRegistryEntry:
    """Build a minimal SourceRegistryEntry for token provider tests."""
    return SourceRegistryEntry(
        short_name=short_name,
        name=short_name.title(),
        description=f"Test {short_name}",
        class_name=f"{short_name.title()}Source",
        source_class_ref=type(short_name, (), {}),
        config_ref=None,
        auth_config_ref=None,
        auth_fields=Fields(fields=[]),
        config_fields=Fields(fields=[]),
        supported_auth_providers=[],
        runtime_auth_all_fields=runtime_auth_all_fields or ["access_token"],
        runtime_auth_optional_fields=runtime_auth_optional_fields or set(),
        auth_methods=["direct"],
        oauth_type=None,
        requires_byoc=False,
        supports_continuous=False,
        supports_cursor=False,
        federated_search=False,
        supports_temporal_relevance=True,
        supports_access_control=False,
        supports_browse_tree=False,
        rate_limit_level=None,
        feature_flag=None,
        labels=None,
        output_entity_definitions=[],
    )


class FakeSourceRegistryForTP:
    """Minimal source registry fake for token provider tests."""

    def __init__(self) -> None:
        self._entries: dict[str, SourceRegistryEntry] = {}

    def seed(self, *entries: SourceRegistryEntry) -> None:
        for e in entries:
            self._entries[e.short_name] = e

    def get(self, short_name: str) -> SourceRegistryEntry:
        return self._entries[short_name]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def oauth2_service():
    """A fake OAuth2 service that returns a refreshed token."""
    return make_oauth2_service()


@pytest.fixture
def ctx():
    """A minimal ApiContext mock."""
    return make_ctx()


@pytest.fixture
def source_registry():
    """A FakeSourceRegistry seeded with a github entry."""
    reg = FakeSourceRegistryForTP()
    reg.seed(make_registry_entry("github"))
    return reg
