"""Unit tests for SourceRegistry.

Table-driven tests with patched ALL_SOURCES and fake sibling registries.
No real platform sources loaded.
"""

from dataclasses import dataclass, field
from enum import Enum
from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field

from airweave.domains.auth_provider.fake import FakeAuthProviderRegistry
from airweave.domains.auth_provider.types import AuthProviderRegistryEntry
from airweave.domains.entities.fake import FakeEntityDefinitionRegistry
from airweave.domains.entities.types import EntityDefinitionEntry
from airweave.domains.sources.registry import SourceRegistry
from airweave.platform.configs._base import Fields


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------

_PATCH_ALL_SOURCES = "airweave.domains.sources.registry.ALL_SOURCES"
_PATCH_SETTINGS = "airweave.domains.sources.registry.settings"


class _AuthMethod(Enum):
    DIRECT = "direct"
    OAUTH_BROWSER = "oauth_browser"


def _make_source_cls(
    short_name: str = "test_src",
    source_name: str = "Test Source",
    *,
    auth_methods: list | None = None,
    is_internal: bool = False,
) -> type:
    """Build a minimal stub class that looks like a @source-decorated class."""

    class Stub:
        """Stub source."""

    Stub.__name__ = f"{source_name.replace(' ', '')}Source"
    Stub.__doc__ = f"Stub {source_name}"
    Stub.short_name = short_name
    Stub.source_name = source_name
    Stub.config_class = None
    Stub.auth_config_class = None
    Stub.auth_methods = auth_methods or [_AuthMethod.DIRECT]
    Stub.oauth_type = None
    Stub.requires_byoc = False
    Stub.supports_continuous = False
    Stub.federated_search = False
    Stub.supports_temporal_relevance = True
    Stub.supports_access_control = False
    Stub.rate_limit_level = None
    Stub.feature_flag = None
    Stub.labels = None
    Stub.is_internal = staticmethod(lambda: is_internal)
    return Stub


def _make_auth_provider_entry(
    short_name: str = "acme",
    blocked_sources: list[str] | None = None,
) -> AuthProviderRegistryEntry:
    return AuthProviderRegistryEntry(
        short_name=short_name,
        name=short_name.title(),
        description=f"Test {short_name}",
        class_name=f"{short_name}Provider",
        provider_class_ref=type(short_name, (), {}),
        config_ref=type(short_name, (), {}),
        auth_config_ref=type(short_name, (), {}),
        config_fields=Fields(fields=[]),
        auth_config_fields=Fields(fields=[]),
        blocked_sources=blocked_sources or [],
        field_name_mapping={},
        slug_name_mapping={},
    )


def _make_entity_entry(short_name: str, module_name: str) -> EntityDefinitionEntry:
    return EntityDefinitionEntry(
        short_name=short_name,
        name=short_name.title(),
        description=f"Test {short_name}",
        class_name=short_name.title(),
        entity_class_ref=type(short_name, (), {}),
        module_name=module_name,
    )


def _build_registry(source_classes, *, auth_entries=None, entity_entries=None, enable_internal=True):
    """Build a SourceRegistry from stub classes with patched globals."""
    auth_reg = FakeAuthProviderRegistry()
    if auth_entries:
        auth_reg.seed(*auth_entries)
    entity_reg = FakeEntityDefinitionRegistry()
    if entity_entries:
        entity_reg.seed(*entity_entries)

    registry = SourceRegistry(auth_reg, entity_reg)
    with (
        patch(_PATCH_ALL_SOURCES, source_classes),
        patch(_PATCH_SETTINGS) as mock_settings,
    ):
        mock_settings.ENABLE_INTERNAL_SOURCES = enable_internal
        registry.build()
    return registry


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


@dataclass
class GetCase:
    desc: str
    short_name: str
    sources: list = field(default_factory=lambda: [("slack", "Slack")])
    expect_name: str | None = None  # None → expect KeyError


GET_CASES = [
    GetCase(
        desc="returns known source",
        short_name="slack",
        expect_name="Slack",
    ),
    GetCase(
        desc="unknown raises KeyError",
        short_name="nonexistent",
    ),
]


@pytest.mark.parametrize("case", GET_CASES, ids=lambda c: c.desc)
def test_get(case: GetCase):
    registry = _build_registry([_make_source_cls(s, n) for s, n in case.sources])

    if case.expect_name is None:
        with pytest.raises(KeyError):
            registry.get(case.short_name)
    else:
        entry = registry.get(case.short_name)
        assert entry.name == case.expect_name


# ---------------------------------------------------------------------------
# list_all()
# ---------------------------------------------------------------------------


@dataclass
class ListAllCase:
    desc: str
    sources: list = field(default_factory=list)  # (short_name, name) tuples
    expect_short_names: set[str] = field(default_factory=set)


LIST_ALL_CASES = [
    ListAllCase(
        desc="returns all entries",
        sources=[("slack", "Slack"), ("github", "GitHub")],
        expect_short_names={"slack", "github"},
    ),
    ListAllCase(
        desc="empty when no sources",
        sources=[],
        expect_short_names=set(),
    ),
]


@pytest.mark.parametrize("case", LIST_ALL_CASES, ids=lambda c: c.desc)
def test_list_all(case: ListAllCase):
    registry = _build_registry([_make_source_cls(s, n) for s, n in case.sources])
    assert {e.short_name for e in registry.list_all()} == case.expect_short_names


# ---------------------------------------------------------------------------
# Internal source filtering
# ---------------------------------------------------------------------------


@dataclass
class InternalCase:
    desc: str
    enable_internal: bool
    expect_count: int


INTERNAL_CASES = [
    InternalCase(desc="filtered when disabled", enable_internal=False, expect_count=1),
    InternalCase(desc="included when enabled", enable_internal=True, expect_count=2),
]


@pytest.mark.parametrize("case", INTERNAL_CASES, ids=lambda c: c.desc)
def test_internal_sources(case: InternalCase):
    sources = [
        _make_source_cls("slack", "Slack"),
        _make_source_cls("internal", "Internal", is_internal=True),
    ]
    registry = _build_registry(sources, enable_internal=case.enable_internal)
    assert len(registry.list_all()) == case.expect_count


# ---------------------------------------------------------------------------
# Auth provider blocking
# ---------------------------------------------------------------------------


@dataclass
class BlockCase:
    desc: str
    blocked_sources: list[str]
    expect_supported: bool


BLOCK_CASES = [
    BlockCase(desc="blocked provider excluded", blocked_sources=["slack"], expect_supported=False),
    BlockCase(desc="unblocked provider included", blocked_sources=[], expect_supported=True),
    BlockCase(desc="other source blocked, not us", blocked_sources=["github"], expect_supported=True),
]


@pytest.mark.parametrize("case", BLOCK_CASES, ids=lambda c: c.desc)
def test_auth_provider_blocking(case: BlockCase):
    provider = _make_auth_provider_entry("acme", blocked_sources=case.blocked_sources)
    registry = _build_registry(
        [_make_source_cls("slack", "Slack")],
        auth_entries=[provider],
    )
    entry = registry.get("slack")
    assert ("acme" in entry.supported_auth_providers) is case.expect_supported


# ---------------------------------------------------------------------------
# Output entity definitions
# ---------------------------------------------------------------------------


def test_output_entity_definitions_resolved():
    entity = _make_entity_entry("slack_msg_entity", module_name="slack")
    registry = _build_registry(
        [_make_source_cls("slack", "Slack")],
        entity_entries=[entity],
    )
    assert "slack_msg_entity" in registry.get("slack").output_entity_definitions


# ---------------------------------------------------------------------------
# Auth methods serialization
# ---------------------------------------------------------------------------


def test_auth_methods_serialized_from_enum():
    cls = _make_source_cls("slack", "Slack", auth_methods=[_AuthMethod.DIRECT, _AuthMethod.OAUTH_BROWSER])
    registry = _build_registry([cls])
    assert registry.get("slack").auth_methods == ["direct", "oauth_browser"]


# ---------------------------------------------------------------------------
# _compute_runtime_auth_fields
# ---------------------------------------------------------------------------


@dataclass
class RuntimeAuthCase:
    desc: str
    auth_config: type | None
    expect_all: list[str]
    expect_optional: set[str]


class _FakeAuthConfig(BaseModel):
    api_key: str
    workspace: str = Field(default="default")


RUNTIME_AUTH_CASES = [
    RuntimeAuthCase(
        desc="None returns empty",
        auth_config=None,
        expect_all=[],
        expect_optional=set(),
    ),
    RuntimeAuthCase(
        desc="model returns required and optional",
        auth_config=_FakeAuthConfig,
        expect_all=["api_key", "workspace"],
        expect_optional={"workspace"},
    ),
]


@pytest.mark.parametrize("case", RUNTIME_AUTH_CASES, ids=lambda c: c.desc)
def test_compute_runtime_auth_fields(case: RuntimeAuthCase):
    all_fields, optional = SourceRegistry._compute_runtime_auth_fields(case.auth_config)
    assert all_fields == case.expect_all
    assert optional == case.expect_optional
