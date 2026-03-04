"""Source registry — in-memory registry built once at startup from @source decorators."""

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.domains.auth_provider.protocols import AuthProviderRegistryProtocol
from airweave.domains.entities.protocols import EntityDefinitionRegistryProtocol
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.platform.configs._base import Fields
from airweave.platform.sources import ALL_SOURCES

registry_logger = logger.with_prefix("SourceRegistry: ").with_context(component="source_registry")


def _enum_to_str(value: object | None) -> str | None:
    """Convert an enum value to its string representation, or pass through None/str."""
    if value is None:
        return None
    return value.value if hasattr(value, "value") else value


class SourceRegistry(SourceRegistryProtocol):
    """In-memory source registry, built once at startup from ALL_SOURCES."""

    def __init__(
        self,
        auth_provider_registry: AuthProviderRegistryProtocol,
        entity_definition_registry: EntityDefinitionRegistryProtocol,
    ) -> None:
        """Initialize the source registry.

        Args:
            auth_provider_registry: Used to compute which auth providers
                support each source (via blocked_sources).
            entity_definition_registry: Used to resolve which entity
                classes each source produces.
        """
        self._auth_provider_registry = auth_provider_registry
        self._entity_definition_registry = entity_definition_registry
        self._entries: dict[str, SourceRegistryEntry] = {}

    def get(self, short_name: str) -> SourceRegistryEntry:
        """Get a source entry by short name.

        Args:
            short_name: The unique identifier for the source (e.g., "github", "slack").

        Returns:
            The precomputed source registry entry.

        Raises:
            KeyError: If no source with the given short name is registered.
        """
        return self._entries[short_name]

    def list_all(self) -> list[SourceRegistryEntry]:
        """List all registered source entries.

        Returns:
            All source registry entries.
        """
        return list(self._entries.values())

    def build(self) -> None:
        """Build the registry from ALL_SOURCES.

        Reads class references directly from @source decorator attributes —
        no ResourceLocator or database needed. Precomputes all derived fields
        (Fields, supported auth providers, runtime auth field names, output entities).

        Called once at startup. After this, all lookups are dict reads.
        """
        # Filter internal sources based on settings
        source_classes = ALL_SOURCES
        if not settings.ENABLE_INTERNAL_SOURCES:
            source_classes = [s for s in source_classes if not s.is_internal()]

        for source_cls in source_classes:
            short_name = source_cls.short_name

            try:
                entry = self._build_entry(source_cls)
                self._entries[short_name] = entry
            except Exception as e:
                registry_logger.error(f"Failed to build registry entry for '{short_name}': {e}")
                raise

        registry_logger.info(f"Built registry with {len(self._entries)} sources.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_entry(self, source_cls: type) -> SourceRegistryEntry:
        """Build a single SourceRegistryEntry from a decorated source class.

        Reads all fields directly from class attributes (set by @source decorator,
        with ClassVar defaults on BaseSource). Missing required fields will raise
        AttributeError at startup.
        """
        # config_class and auth_config_class are actual types or None.
        # auth_config_class is None for OAuth sources (they don't use direct auth).
        # config_class is None for sources with no configuration.
        config_ref = source_cls.config_class
        auth_config_ref = source_cls.auth_config_class

        runtime_all, runtime_optional = self._compute_runtime_auth_fields(auth_config_ref)

        # Resolve output entity definition short_names from the entity definition registry
        entity_entries = self._entity_definition_registry.list_for_source(source_cls.short_name)
        output_entity_definitions = [entry.short_name for entry in entity_entries]

        return SourceRegistryEntry(
            short_name=source_cls.short_name,
            name=source_cls.source_name,
            description=source_cls.__doc__,
            class_name=source_cls.__name__,
            source_class_ref=source_cls,
            config_ref=config_ref,
            auth_config_ref=auth_config_ref,
            # OAuth sources have no auth config — empty fields is correct
            auth_fields=Fields.from_config_class(auth_config_ref)
            if auth_config_ref
            else Fields(fields=[]),
            config_fields=Fields.from_config_class(config_ref) if config_ref else Fields(fields=[]),
            supported_auth_providers=self._compute_supported_auth_providers(
                source_cls.short_name, self._auth_provider_registry
            ),
            runtime_auth_all_fields=runtime_all,
            runtime_auth_optional_fields=runtime_optional,
            auth_methods=[m.value for m in source_cls.auth_methods],
            oauth_type=_enum_to_str(source_cls.oauth_type),
            requires_byoc=source_cls.requires_byoc,
            supports_continuous=source_cls.supports_continuous,
            federated_search=source_cls.federated_search,
            supports_temporal_relevance=source_cls.supports_temporal_relevance,
            supports_access_control=source_cls.supports_access_control,
            rate_limit_level=_enum_to_str(source_cls.rate_limit_level),
            feature_flag=source_cls.feature_flag,
            labels=source_cls.labels,
            output_entity_definitions=output_entity_definitions,
        )

    @staticmethod
    def _compute_supported_auth_providers(
        source_short_name: str,
        auth_provider_registry: AuthProviderRegistryProtocol,
    ) -> list[str]:
        """Compute which auth providers support this source.

        A provider supports a source unless the source appears in
        the provider's blocked_sources list.
        """
        supported = []
        for entry in auth_provider_registry.list_all():
            if source_short_name not in entry.blocked_sources:
                supported.append(entry.short_name)
        return supported

    @staticmethod
    def _compute_runtime_auth_fields(
        auth_config_ref: type | None,
    ) -> tuple[list[str], set[str]]:
        """Precompute the auth field names the sync pipeline needs.

        OAuth sources have no auth_config_class — returns empty for those.
        """
        if auth_config_ref is None:
            return [], set()

        all_fields = list(auth_config_ref.model_fields.keys())
        optional_fields = {
            name for name, info in auth_config_ref.model_fields.items() if not info.is_required()
        }
        return all_fields, optional_fields
