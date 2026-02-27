from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional
from uuid import UUID

from airweave.core.protocols.registry import BaseRegistryEntry
from airweave.models.connection import Connection
from airweave.models.source_connection import SourceConnection
from airweave.platform.auth_providers._base import BaseAuthProvider
from airweave.platform.auth_providers.auth_result import AuthProviderMode
from airweave.platform.configs._base import BaseConfig, Fields


class SourceRegistryEntry(BaseRegistryEntry):
    """Precomputed source metadata. Built once at startup from @source decorators."""

    # Resolved classes (read directly from decorator — no locator needed)
    source_class_ref: type
    config_ref: type[BaseConfig] | None
    auth_config_ref: type[BaseConfig] | None

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


# ---------------------------------------------------------------------------
# Internal value objects for SourceLifecycleService
# ---------------------------------------------------------------------------


@dataclass
class SourceConnectionData:
    """Loaded source connection + connection metadata, passed between lifecycle methods.

    Built by _load_source_connection_data(), consumed by auth, credential,
    and configuration helpers. Not frozen — _merge_source_config mutates config_fields.
    """

    source_connection_obj: SourceConnection
    connection: Connection
    source_class: type
    config_fields: dict
    short_name: str
    source_connection_id: UUID
    auth_config_class: Optional[str]
    connection_id: UUID
    integration_credential_id: Optional[UUID]
    oauth_type: Optional[str]
    readable_auth_provider_id: Optional[str]
    auth_provider_config: Optional[dict]


@dataclass(frozen=True)
class AuthConfig:
    """Resolved auth configuration returned by _get_auth_configuration().

    Carries credentials, optional HTTP client factory (for proxy mode),
    auth provider instance, and the resolved auth mode.
    """

    credentials: Any
    http_client_factory: Optional[Callable]
    auth_provider_instance: Optional[BaseAuthProvider]
    auth_mode: AuthProviderMode
