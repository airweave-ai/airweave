"""Source registry — in-memory registry built once at startup from @source decorators."""

import inspect
import re

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.domains.auth_provider.protocols import AuthProviderRegistryProtocol
from airweave.domains.entities.protocols import EntityDefinitionRegistryProtocol
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.platform.auth.schemas import OAuth2Settings
from airweave.platform.auth.settings import integration_settings
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
        self._validate_template_config(source_cls)
        self._validate_source_contract(source_cls)

        config_ref = source_cls.config_class
        auth_config_ref = source_cls.auth_config_class

        runtime_all, runtime_optional = self._compute_runtime_auth_fields(
            auth_config_ref, oauth_type=source_cls.oauth_type
        )

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
            supports_cursor=source_cls.cursor_class is not None,
            federated_search=source_cls.federated_search,
            supports_temporal_relevance=source_cls.supports_temporal_relevance,
            supports_access_control=source_cls.supports_access_control,
            supports_browse_tree=source_cls.supports_browse_tree,
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
        oauth_type: object | None = None,
    ) -> tuple[list[str], set[str]]:
        """Precompute the auth field names the sync pipeline needs.

        For sources with auth_config_class, fields come from the Pydantic model.
        For pure OAuth sources (no auth_config_class but has oauth_type), returns
        the standard OAuth field set so auth providers know which credentials to
        fetch.
        """
        if auth_config_ref is not None:
            all_fields = list(auth_config_ref.model_fields.keys())
            optional_fields = {
                name
                for name, info in auth_config_ref.model_fields.items()
                if not info.is_required()
            }
            return all_fields, optional_fields

        if oauth_type is not None:
            oauth_str = _enum_to_str(oauth_type)
            if oauth_str == "with_refresh" or oauth_str == "with_rotating_refresh":
                return ["access_token", "refresh_token"], set()
            return ["access_token"], set()

        return [], set()

    @staticmethod
    def _validate_source_contract(source_cls: type) -> None:
        """Validate that source method signatures conform to the BaseSource v2 contract.

        Checks ``create()`` and ``generate_entities()`` for expected keyword-only
        params. Warns (not errors) for sources not yet migrated so we can roll
        this out incrementally.

        Raises ValueError once all sources are migrated and we flip to strict mode.
        """
        short_name = source_cls.short_name

        # --- create() ---
        create_expected = {"auth", "logger", "http_client", "config"}
        try:
            create_sig = inspect.signature(source_cls.create)
            create_params = {
                name
                for name, p in create_sig.parameters.items()
                if p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD) and name != "cls"
            }
            missing_create = create_expected - create_params
            if missing_create:
                registry_logger.warning(
                    f"Source '{short_name}' create() missing params: {sorted(missing_create)}. "
                    f"Has: {sorted(create_params)}. "
                    f"Migrate to v2 contract: create(*, auth, logger, http_client, config)."
                )
        except (ValueError, TypeError) as e:
            registry_logger.warning(f"Could not inspect create() for '{short_name}': {e}")

        # --- generate_entities() ---
        gen_expected = {"cursor", "files", "node_selections"}
        try:
            gen_sig = inspect.signature(source_cls.generate_entities)
            gen_params = {
                name
                for name, p in gen_sig.parameters.items()
                if p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD) and name != "self"
            }
            missing_gen = gen_expected - gen_params
            if missing_gen:
                registry_logger.warning(
                    f"Source '{short_name}' generate_entities() missing params: "
                    f"{sorted(missing_gen)}. Has: {sorted(gen_params)}. "
                    f"Migrate to v2 contract: generate_entities(*, cursor, files, node_selections)."
                )
        except (ValueError, TypeError) as e:
            registry_logger.warning(
                f"Could not inspect generate_entities() for '{short_name}': {e}"
            )

    @staticmethod
    def _validate_template_config(source_cls: type) -> None:
        """Validate that YAML template variables match config RequiredTemplateConfig fields.

        Raises ValueError on mismatch so the app fails fast at startup.
        """
        short_name = source_cls.short_name
        config_class = source_cls.config_class
        if not config_class:
            return

        try:
            oauth_settings = integration_settings.get_settings(short_name)
            if not isinstance(oauth_settings, OAuth2Settings) or not oauth_settings.url_template:
                return

            url_vars = set(re.findall(r"\{(\w+)\}", oauth_settings.url))
            if oauth_settings.backend_url_template:
                url_vars |= set(re.findall(r"\{(\w+)\}", oauth_settings.backend_url))

            if not url_vars:
                registry_logger.warning(
                    f"Source '{short_name}' has url_template=true but no template variables found"
                )
                return

            config_fields = set(config_class.get_template_config_fields())

            missing = url_vars - config_fields
            if missing:
                raise ValueError(
                    f"Source '{short_name}' template validation failed:\n"
                    f"  YAML template variables: {sorted(url_vars)}\n"
                    f"  Config template fields: {sorted(config_fields)}\n"
                    f"  Missing in config class: {sorted(missing)}\n\n"
                    f"Fix: Add to {config_class.__name__}:\n"
                    + "\n".join(
                        f"    {var}: str = RequiredTemplateConfig("
                        f'title="{var.replace("_", " ").title()}")'
                        for var in sorted(missing)
                    )
                )

            extra = config_fields - url_vars
            if extra:
                registry_logger.warning(
                    f"Source '{short_name}' has template config fields not used in YAML: "
                    f"{sorted(extra)}. These may be for direct auth or API calls."
                )

        except ValueError:
            raise
        except Exception as e:
            registry_logger.warning(
                f"Could not validate templates for '{short_name}': {e}. "
                f"This is non-fatal but templates may not work correctly."
            )
