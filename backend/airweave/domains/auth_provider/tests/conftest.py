"""Auth provider domain test fixtures."""

import pytest

from airweave.domains.auth_provider.types import AuthProviderRegistryEntry
from airweave.platform.configs._base import Fields


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_provider_entry(
    short_name: str = "acme",
    name: str = "Acme",
    *,
    blocked_sources: list[str] | None = None,
    field_name_mapping: dict[str, str] | None = None,
    slug_name_mapping: dict[str, str] | None = None,
) -> AuthProviderRegistryEntry:
    """Build a minimal AuthProviderRegistryEntry for tests."""
    return AuthProviderRegistryEntry(
        short_name=short_name,
        name=name,
        description=f"Test {name} provider",
        class_name=f"{name}Provider",
        provider_class_ref=type(name, (), {}),
        config_ref=type(name, (), {}),
        auth_config_ref=type(name, (), {}),
        config_fields=Fields(fields=[]),
        auth_config_fields=Fields(fields=[]),
        blocked_sources=blocked_sources or [],
        field_name_mapping=field_name_mapping or {},
        slug_name_mapping=slug_name_mapping or {},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def acme_entry():
    return _make_auth_provider_entry("acme", "Acme")


@pytest.fixture
def beta_entry():
    return _make_auth_provider_entry("beta", "Beta", blocked_sources=["slack"])
