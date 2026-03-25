"""Tests for AuthProviderRegistry.get_settings_url()."""

from airweave.domains.auth_provider.registry import AuthProviderRegistry
from airweave.domains.auth_provider.types import AuthProviderRegistryEntry
from airweave.platform.configs._base import Fields


def _stub_entry(short_name: str, settings_url: str = "") -> AuthProviderRegistryEntry:
    return AuthProviderRegistryEntry(
        short_name=short_name,
        name=short_name.capitalize(),
        description="test",
        class_name=f"{short_name}Provider",
        provider_class_ref=type(short_name, (), {}),
        config_ref=type("Cfg", (), {}),
        auth_config_ref=type("AuthCfg", (), {}),
        config_fields=Fields(fields=[]),
        auth_config_fields=Fields(fields=[]),
        blocked_sources=[],
        field_name_mapping={},
        slug_name_mapping={},
        settings_url=settings_url,
    )


def test_get_settings_url_returns_url():
    reg = AuthProviderRegistry()
    reg._entries["composio"] = _stub_entry("composio", "https://platform.composio.dev/")
    assert reg.get_settings_url("composio") == "https://platform.composio.dev/"


def test_get_settings_url_empty_returns_none():
    reg = AuthProviderRegistry()
    reg._entries["noop"] = _stub_entry("noop", "")
    assert reg.get_settings_url("noop") is None


def test_get_settings_url_unknown_returns_none():
    reg = AuthProviderRegistry()
    assert reg.get_settings_url("nonexistent") is None


def test_get_settings_url_rejects_non_https():
    reg = AuthProviderRegistry()
    reg._entries["evil"] = _stub_entry("evil", "http://insecure.example.com/")
    assert reg.get_settings_url("evil") is None
