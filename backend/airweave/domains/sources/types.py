from airweave.core.protocols.registry import BaseRegistryEntry
from airweave.platform.configs._base import Fields


class SourceRegistryEntry(BaseRegistryEntry):
    """Precomputed source metadata. Built once at startup from @source decorators."""

    # Resolved classes (read directly from decorator — no locator needed)
    source_class_ref: type
    config_ref: type | None
    auth_config_ref: type | None

    # Precomputed fields
    auth_fields: Fields
    config_fields: Fields  # unfiltered — service filters by feature flags
    supported_auth_providers: list[str]

    # Runtime auth (for sync pipeline / token manager)
    runtime_auth_all_fields: list[str]
    runtime_auth_optional_fields: set[str]

    # Auth methods
    auth_methods: list[str] | None
    oauth_type: str | None
    requires_byoc: bool

    # Capabilities
    supports_continuous: bool
    federated_search: bool
    supports_temporal_relevance: bool
    supports_access_control: bool
    rate_limit_level: str | None
    feature_flag: str | None

    # Metadata
    labels: list[str] | None

    # Output entity definitions (short_names — use entity_definition_registry.get() for full entry)
    output_entity_definitions: list[str]
