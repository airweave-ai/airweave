"""Source validation service.

Validates config and auth fields using registry-resolved Pydantic schemas.
No DB calls -- uses SourceRegistryEntry.config_ref / auth_config_ref directly.
This service is for source schema validation only (not auth-provider credentials).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from airweave.api.context import ApiContext
from airweave.domains.sources.protocols import (
    SourceRegistryProtocol,
    SourceValidationServiceProtocol,
)
from airweave.domains.sources.types import SourceRegistryEntry


class SourceValidationService(SourceValidationServiceProtocol):
    """Validates config and auth fields against registry-resolved Pydantic schemas."""

    def __init__(self, source_registry: SourceRegistryProtocol) -> None:
        """Store source registry used for schema lookup."""
        self._source_registry = source_registry

    def validate_config(
        self, short_name: str, config_fields: Mapping[str, Any] | None, ctx: ApiContext
    ) -> dict[str, Any]:
        """Validate configuration fields against source schema, returning a plain dict.

        Also strips fields that have feature flags not enabled for the organization.
        """
        entry = self._get_entry_or_404(short_name)

        if not config_fields:
            return {}

        payload = self._as_mapping(config_fields)

        config_class = entry.config_ref
        if config_class is None:
            return payload

        self._enforce_feature_flags(short_name, payload, config_class, ctx)

        try:
            model = config_class.model_validate(payload)
            return model.model_dump()
        except ValidationError as e:
            errors = "; ".join([f"{self._loc(err)}: {err.get('msg')}" for err in e.errors()])
            raise HTTPException(status_code=422, detail=f"Invalid config fields: {errors}") from e

    def validate_auth_schema(self, short_name: str, auth_fields: dict[str, Any]) -> BaseModel:
        """Validate authentication fields against source's auth config schema."""
        entry = self._get_entry_or_404(short_name)

        auth_config_class = entry.auth_config_ref
        if auth_config_class is None:
            raise HTTPException(
                status_code=422,
                detail=f"Source '{short_name}' does not support direct auth",
            )

        try:
            return auth_config_class.model_validate(auth_fields)
        except ValidationError as e:
            errors = "; ".join([f"{self._loc(err)}: {err['msg']}" for err in e.errors()])
            raise HTTPException(status_code=422, detail=f"Invalid auth fields: {errors}") from e

    def _get_entry_or_404(self, short_name: str) -> SourceRegistryEntry:
        try:
            return self._source_registry.get(short_name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Source '{short_name}' not found")

    @staticmethod
    def _loc(err: dict[str, Any]) -> str:
        loc = err.get("loc", ())
        return ".".join(str(x) for x in loc) if loc else "?"

    @staticmethod
    def _enforce_feature_flags(
        short_name: str,
        payload: dict[str, Any],
        config_class: type[BaseModel],
        ctx: ApiContext,
    ) -> None:
        enabled_features = ctx.organization.enabled_features or []
        for field_name, field_info in config_class.model_fields.items():
            json_schema_extra = field_info.json_schema_extra or {}
            feature_flag = json_schema_extra.get("feature_flag")

            if feature_flag and feature_flag not in enabled_features:
                if field_name in payload and payload[field_name] is not None:
                    ctx.logger.warning(
                        f"Rejected config field '{field_name}' for {short_name}: "
                        f"feature flag '{feature_flag}' not enabled for organization"
                    )
                    field_title = field_info.title or field_name
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            f"The '{field_title}' feature requires the '{feature_flag}' "
                            f"feature to be enabled for your organization. "
                            f"Please contact support to enable this feature."
                        ),
                    )

    @staticmethod
    def _as_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, Mapping):
            return dict(value)
        raise TypeError(f"config_fields must be mapping-like; got {type(value).__name__}")
