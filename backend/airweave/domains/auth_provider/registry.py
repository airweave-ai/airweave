"""Auth provider registry — in-memory registry built once at startup."""

from airweave.core.logging import logger
from airweave.domains.auth_provider.protocols import AuthProviderRegistryProtocol
from airweave.domains.auth_provider.types import AuthProviderRegistryEntry
from airweave.platform.auth_providers import ALL_AUTH_PROVIDERS
from airweave.platform.configs._base import Fields

registry_logger = logger.with_prefix("AuthProviderRegistry: ").with_context(
    component="auth_provider_registry"
)


class AuthProviderRegistry(AuthProviderRegistryProtocol):
    """In-memory auth provider registry, built once at startup."""

    def __init__(self) -> None:
        """Initialize the auth provider registry."""
        self._entries: dict[str, AuthProviderRegistryEntry] = {}

    def get(self, short_name: str) -> AuthProviderRegistryEntry:
        """Get an auth provider entry by short name.

        Args:
            short_name: The unique identifier (e.g., "pipedream", "composio").

        Returns:
            The precomputed auth provider registry entry.

        Raises:
            KeyError: If no auth provider with the given short name is registered.
        """
        return self._entries[short_name]

    def list_all(self) -> list[AuthProviderRegistryEntry]:
        """List all registered auth provider entries."""
        return list(self._entries.values())

    def build(self) -> None:
        """Build the registry from auth provider classes.

        Reads class references directly from @auth_provider decorator attributes.
        Called once at startup. After this, all lookups are dict reads.
        """
        provider_classes = ALL_AUTH_PROVIDERS

        for provider_cls in provider_classes:
            short_name = provider_cls.short_name

            try:
                entry = self._build_entry(provider_cls)
                self._entries[short_name] = entry
            except Exception as e:
                registry_logger.error(f"Failed to build registry entry for '{short_name}': {e}")
                raise

        registry_logger.info(f"Built registry with {len(self._entries)} auth providers.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_entry(provider_cls: type) -> AuthProviderRegistryEntry:
        """Build a single AuthProviderRegistryEntry from a decorated class.

        All @auth_provider decorator fields are required — direct access
        so missing fields crash at startup.
        """
        # ------------------------------------------------------------------
        # Required fields — fail fast if missing
        # ------------------------------------------------------------------
        short_name: str = provider_cls.short_name
        name: str = provider_cls.provider_name
        config_ref: type = provider_cls.config_class
        auth_config_ref: type = provider_cls.auth_config_class

        # ------------------------------------------------------------------
        # Class attributes with defaults
        # ------------------------------------------------------------------
        blocked_sources: list[str] = getattr(provider_cls, "BLOCKED_SOURCES", [])
        field_name_mapping: dict[str, str] = getattr(provider_cls, "FIELD_NAME_MAPPING", {})
        slug_name_mapping: dict[str, str] = getattr(provider_cls, "SLUG_NAME_MAPPING", {})

        # ------------------------------------------------------------------
        # Precompute fields
        # ------------------------------------------------------------------
        config_fields = Fields.from_config_class(config_ref)
        auth_config_fields = Fields.from_config_class(auth_config_ref)

        return AuthProviderRegistryEntry(
            # Base
            short_name=short_name,
            name=name,
            description=provider_cls.__doc__,
            class_name=provider_cls.__name__,
            # Resolved classes
            provider_class_ref=provider_cls,
            config_ref=config_ref,
            auth_config_ref=auth_config_ref,
            # Precomputed fields
            config_fields=config_fields,
            auth_config_fields=auth_config_fields,
            # Source compatibility
            blocked_sources=blocked_sources,
            # Mappings
            field_name_mapping=field_name_mapping,
            slug_name_mapping=slug_name_mapping,
        )
