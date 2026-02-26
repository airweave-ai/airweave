from airweave.core.protocols.registry import BaseRegistryEntry
from airweave.platform.configs._base import Fields


class AuthProviderRegistryEntry(BaseRegistryEntry):
    """Precomputed auth provider metadata. Built once at startup from @auth_provider decorators."""

    # Resolved classes (read directly from decorator)
    provider_class_ref: type
    config_ref: type
    auth_config_ref: type

    # Precomputed fields
    config_fields: Fields
    auth_config_fields: Fields

    # Source compatibility
    blocked_sources: list[str]

    # Mappings (Airweave names → provider-specific names)
    field_name_mapping: dict[str, str]
    slug_name_mapping: dict[str, str]
