"""Source service."""

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.config.settings import Settings
from airweave.core.shared_models import FeatureFlag as FeatureFlagEnum
from airweave.domains.sources.protocols import (
    SourceRegistryProtocol,
    SourceServiceProtocol,
)
from airweave.domains.sources.types import SourceRegistryEntry


class SourceService(SourceServiceProtocol):
    """Service for managing sources.

    Uses the SourceRegistry for all metadata lookups — no database
    or ResourceLocator needed at request time.
    """

    def __init__(
        self,
        source_registry: SourceRegistryProtocol,
        settings: Settings,
    ):
        """Initialize the source service."""
        self.source_registry = source_registry
        self.settings = settings

    async def get(self, short_name: str, ctx: ApiContext) -> schemas.Source:
        """Get a source by short name."""
        entry = self.source_registry.get(short_name)

        enabled_features = ctx.organization.enabled_features or []

        if self._is_hidden_by_feature_flag(entry, enabled_features, ctx):
            raise KeyError(short_name)

        return self._entry_to_schema(entry, enabled_features)

    async def list(self, ctx: ApiContext) -> list[schemas.Source]:
        """List all sources."""
        entries = self.source_registry.list_all()
        enabled_features = ctx.organization.enabled_features or []

        result_sources = []
        for entry in entries:
            if self._is_hidden_by_feature_flag(entry, enabled_features, ctx):
                continue
            mapped_schema = self._entry_to_schema(entry, enabled_features)
            result_sources.append(mapped_schema)

        ctx.logger.info(f"Returning {len(result_sources)} sources")
        return result_sources

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _entry_to_schema(
        self, entry: SourceRegistryEntry, enabled_features: list
    ) -> schemas.Source:
        """Convert a registry entry to an API schema.

        Applies per-request concerns: feature-flag filtering of config fields,
        and self-hosted requires_byoc override.
        """
        # Filter config fields by the organization's enabled features
        config_fields = entry.config_fields.filter_by_features(enabled_features)

        requires_byoc = entry.requires_byoc
        if self.settings.ENVIRONMENT == "self-hosted" and entry.auth_methods:
            if "oauth_browser" in entry.auth_methods or "oauth_token" in entry.auth_methods:
                requires_byoc = True

        try:
            schema = schemas.Source.model_validate(
                {
                    "name": entry.name,
                    "short_name": entry.short_name,
                    "description": entry.description,
                    "class_name": entry.class_name,
                    "auth_methods": entry.auth_methods,
                    "oauth_type": entry.oauth_type,
                    "requires_byoc": requires_byoc,
                    "auth_fields": entry.auth_fields,
                    "config_fields": config_fields,
                    "supported_auth_providers": entry.supported_auth_providers,
                    "supports_continuous": entry.supports_continuous,
                    "federated_search": entry.federated_search,
                    "supports_temporal_relevance": entry.supports_temporal_relevance,
                    "supports_access_control": entry.supports_access_control,
                    "rate_limit_level": entry.rate_limit_level,
                    "feature_flag": entry.feature_flag,
                    "labels": entry.labels,
                    "output_entity_definitions": entry.output_entity_definitions,
                }
            )
        except Exception as e:
            raise ValueError(f"Error validating source {entry.short_name}: {e}")

        return schema

    def _is_hidden_by_feature_flag(
        self, entry: SourceRegistryEntry, enabled_features: list, ctx: ApiContext
    ) -> bool:
        """Check if a source should be hidden due to feature flag requirements."""
        if not entry.feature_flag:
            return False

        try:
            required_flag = FeatureFlagEnum(entry.feature_flag)
            if required_flag not in enabled_features:
                ctx.logger.debug(
                    f"Hidden source {entry.short_name} "
                    f"(requires feature flag: {entry.feature_flag})"
                )
                return True
        except ValueError:
            ctx.logger.warning(f"Source {entry.short_name} has invalid flag {entry.feature_flag}")

        return False
