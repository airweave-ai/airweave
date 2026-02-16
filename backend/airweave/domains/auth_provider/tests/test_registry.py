"""Unit tests for AuthProviderRegistry.

Table-driven tests with patched ALL_AUTH_PROVIDERS.
No real platform auth providers loaded.
"""

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest

from airweave.domains.auth_provider.registry import AuthProviderRegistry
from airweave.platform.configs._base import BaseConfig, Fields

_PATCH_PROVIDERS = "airweave.domains.auth_provider.registry.ALL_AUTH_PROVIDERS"


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


class _StubConfig(BaseConfig):
    api_key: str = ""


class _StubAuthConfig(BaseConfig):
    token: str = ""


def _make_provider_cls(
    short_name: str = "acme",
    provider_name: str = "Acme",
    *,
    blocked_sources: list[str] | None = None,
    field_name_mapping: dict[str, str] | None = None,
    slug_name_mapping: dict[str, str] | None = None,
) -> type:
    """Build a minimal stub class that looks like a @auth_provider-decorated class."""

    class Stub:
        """Stub auth provider."""

    Stub.__name__ = f"{provider_name}Provider"
    Stub.__doc__ = f"Stub {provider_name}"
    Stub.short_name = short_name
    Stub.provider_name = provider_name
    Stub.config_class = _StubConfig
    Stub.auth_config_class = _StubAuthConfig
    Stub.BLOCKED_SOURCES = blocked_sources or []
    Stub.FIELD_NAME_MAPPING = field_name_mapping or {}
    Stub.SLUG_NAME_MAPPING = slug_name_mapping or {}
    return Stub


def _build_registry(provider_classes):
    """Build an AuthProviderRegistry from stub classes with patched globals."""
    registry = AuthProviderRegistry()
    with patch(_PATCH_PROVIDERS, provider_classes):
        registry.build()
    return registry


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


@dataclass
class GetCase:
    desc: str
    short_name: str
    providers: list = field(default_factory=lambda: [("acme", "Acme")])
    expect_name: str | None = None  # None → expect KeyError


GET_CASES = [
    GetCase(desc="returns known provider", short_name="acme", expect_name="Acme"),
    GetCase(desc="unknown raises KeyError", short_name="nonexistent"),
]


@pytest.mark.parametrize("case", GET_CASES, ids=lambda c: c.desc)
def test_get(case: GetCase):
    registry = _build_registry([_make_provider_cls(s, n) for s, n in case.providers])

    if case.expect_name is None:
        with pytest.raises(KeyError):
            registry.get(case.short_name)
    else:
        assert registry.get(case.short_name).name == case.expect_name


# ---------------------------------------------------------------------------
# list_all()
# ---------------------------------------------------------------------------


@dataclass
class ListAllCase:
    desc: str
    providers: list = field(default_factory=list)
    expect_short_names: set[str] = field(default_factory=set)


LIST_ALL_CASES = [
    ListAllCase(
        desc="returns all entries",
        providers=[("acme", "Acme"), ("beta", "Beta")],
        expect_short_names={"acme", "beta"},
    ),
    ListAllCase(desc="empty when no providers", providers=[], expect_short_names=set()),
]


@pytest.mark.parametrize("case", LIST_ALL_CASES, ids=lambda c: c.desc)
def test_list_all(case: ListAllCase):
    registry = _build_registry([_make_provider_cls(s, n) for s, n in case.providers])
    assert {e.short_name for e in registry.list_all()} == case.expect_short_names


# ---------------------------------------------------------------------------
# build() — entry fields
# ---------------------------------------------------------------------------


@dataclass
class BuildFieldCase:
    desc: str
    blocked_sources: list[str] = field(default_factory=list)
    field_name_mapping: dict[str, str] = field(default_factory=dict)
    slug_name_mapping: dict[str, str] = field(default_factory=dict)


BUILD_FIELD_CASES = [
    BuildFieldCase(
        desc="blocked sources captured",
        blocked_sources=["slack", "github"],
    ),
    BuildFieldCase(
        desc="field name mapping captured",
        field_name_mapping={"api_key": "key"},
    ),
    BuildFieldCase(
        desc="slug name mapping captured",
        slug_name_mapping={"gmail": "google-mail"},
    ),
    BuildFieldCase(desc="empty defaults"),
]


@pytest.mark.parametrize("case", BUILD_FIELD_CASES, ids=lambda c: c.desc)
def test_build_field(case: BuildFieldCase):
    cls = _make_provider_cls(
        "acme",
        "Acme",
        blocked_sources=case.blocked_sources,
        field_name_mapping=case.field_name_mapping,
        slug_name_mapping=case.slug_name_mapping,
    )
    entry = _build_registry([cls]).get("acme")

    assert entry.blocked_sources == case.blocked_sources
    assert entry.field_name_mapping == case.field_name_mapping
    assert entry.slug_name_mapping == case.slug_name_mapping


# ---------------------------------------------------------------------------
# build() — derived fields
# ---------------------------------------------------------------------------


def test_config_fields_precomputed():
    entry = _build_registry([_make_provider_cls()]).get("acme")
    assert isinstance(entry.config_fields, Fields)
    assert isinstance(entry.auth_config_fields, Fields)


def test_class_refs_stored():
    cls = _make_provider_cls()
    entry = _build_registry([cls]).get("acme")
    assert entry.provider_class_ref is cls
    assert entry.config_ref is _StubConfig
    assert entry.auth_config_ref is _StubAuthConfig


def test_description_from_docstring():
    entry = _build_registry([_make_provider_cls("acme", "Acme")]).get("acme")
    assert entry.description == "Stub Acme"
