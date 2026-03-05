"""Legacy auth provider service -- [code blue] pending deletion.

Only get_runtime_auth_fields_for_source remains
(sole caller: TokenManager._refresh_via_auth_provider).
"""

from dataclasses import dataclass
from typing import List, Set, Union, get_origin

from fastapi import HTTPException
from pydantic_core import PydanticUndefined
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.core.logging import logger
from airweave.platform.locator import resource_locator

auth_provider_logger = logger.with_prefix("Auth Provider Service: ").with_context(
    component="auth_provider_service"
)


@dataclass
class AuthFieldsResponse:
    """Auth fields required for a source."""

    all_fields: List[str]
    optional_fields: Set[str]

    @property
    def required_fields(self) -> Set[str]:
        """Get the set of required (non-optional) fields."""
        return set(self.all_fields) - self.optional_fields


class AuthProviderService:
    """Legacy service -- will be deleted once TokenManager is refactored."""

    async def get_runtime_auth_fields_for_source(
        self, db: AsyncSession, source_short_name: str
    ) -> AuthFieldsResponse:
        """Get the runtime auth fields required from an auth provider for a source.

        Returns all auth config fields along with which ones are optional, so auth
        providers can skip missing optional fields instead of hard-failing.

        Args:
            db: The database session
            source_short_name: The short name of the source

        Returns:
            AuthFieldsResponse with all field names and optional field names.
            Auth providers should attempt to fetch all fields but only fail on
            missing required ones.

        Raises:
            HTTPException: If source not found
        """
        # Get the source model
        source_model = await crud.source.get_by_short_name(db, short_name=source_short_name)
        if not source_model:
            raise HTTPException(status_code=404, detail=f"Source '{source_short_name}' not found")

        # Check if source has auth_config_class (DIRECT auth sources)
        if source_model.auth_config_class:
            auth_config_class = resource_locator.get_auth_config(source_model.auth_config_class)
            all_fields = list(auth_config_class.model_fields.keys())

            # Determine which fields are optional based on Pydantic model metadata
            optional_fields: Set[str] = set()
            for name, field_info in auth_config_class.model_fields.items():
                has_default = field_info.default is not PydanticUndefined
                is_optional = get_origin(field_info.annotation) is Union
                if has_default or is_optional:
                    optional_fields.add(name)

            auth_provider_logger.debug(
                f"Source '{source_short_name}' auth fields: {all_fields}, "
                f"optional: {optional_fields}"
            )
            return AuthFieldsResponse(all_fields=all_fields, optional_fields=optional_fields)
        else:
            # Pure OAuth -- all fields are required
            if source_model.oauth_type == "with_refresh":
                return AuthFieldsResponse(
                    all_fields=["access_token", "refresh_token"], optional_fields=set()
                )
            else:
                return AuthFieldsResponse(all_fields=["access_token"], optional_fields=set())


# Singleton instance
auth_provider_service = AuthProviderService()
