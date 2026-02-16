"""Service for managing auth provider operations."""

from dataclasses import dataclass
from typing import List, Optional, Set, Union, get_origin

from fastapi import HTTPException
from pydantic_core import PydanticUndefined
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.core.logging import logger
from airweave.platform.configs._base import ConfigValues
from airweave.platform.locator import resource_locator

auth_provider_logger = logger.with_prefix("Auth Provider Service: ").with_context(
    component="auth_provider_service"
)


@dataclass
class AuthFieldsResponse:
    """Auth fields required for a source.

    Attributes:
        all_fields: All auth field names that should be fetched
        optional_fields: Field names that are optional (can be missing without error)
    """

    all_fields: List[str]
    optional_fields: Set[str]

    @property
    def required_fields(self) -> Set[str]:
        """Get the set of required (non-optional) fields."""
        return set(self.all_fields) - self.optional_fields


# function to get most recent connection for an auth provider short name
# function to get credentials of most recent connection


class AuthProviderService:
    """Service for managing auth provider operations."""

    # CODE BLUE: mark for deprecation
    def get_supported_providers_for_source(self, source_short_name: str) -> List[str]:
        """Get auth providers that support the given source.

        Args:
            source_short_name: The short name of the source

        Returns:
            List of auth provider short names that support this source
        """
        supported = []

        # Get all available auth provider classes from the resource locator
        auth_provider_classes = resource_locator.get_available_auth_provider_classes()

        # Check each available provider
        for auth_provider_class in auth_provider_classes:
            short_name = auth_provider_class.short_name

            # Check if source is blocked
            blocked_sources = getattr(auth_provider_class, "BLOCKED_SOURCES", [])
            if source_short_name in blocked_sources:
                auth_provider_logger.debug(
                    f"Source '{source_short_name}' is blocked by auth provider '{short_name}'"
                )
                continue

            # If not blocked, it's supported
            auth_provider_logger.debug(
                f"Source '{source_short_name}' is supported by auth provider '{short_name}'"
            )
            supported.append(short_name)

        return supported

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

    async def validate_auth_provider_config(
        self,
        db: AsyncSession,
        auth_provider_short_name: str,
        auth_provider_config: Optional[ConfigValues],
    ) -> dict:
        """Validate auth provider config fields based on auth provider config class.

        Args:
            db: The database session
            auth_provider_short_name: The short name of the auth provider
            auth_provider_config: The auth provider config fields to validate (ConfigValues)

        Returns:
            The validated auth provider config fields as a dict

        Raises:
            HTTPException: If config fields are invalid or required but not provided
        """
        # Get the auth provider info
        auth_provider = await crud.auth_provider.get_by_short_name(
            db, short_name=auth_provider_short_name
        )
        if not auth_provider:
            raise HTTPException(
                status_code=404, detail=f"Auth provider '{auth_provider_short_name}' not found"
            )

        BASE_ERROR_MESSAGE = (
            "For more information about auth provider configuration, "
            "check [this page](https://docs.airweave.ai/auth-providers)."
        )

        # Check if auth provider has a config class defined - it MUST be defined
        if not hasattr(auth_provider, "config_class") or auth_provider.config_class is None:
            raise HTTPException(
                status_code=422,
                detail=f"Auth provider {auth_provider.name} does not have a "
                "configuration class defined. " + BASE_ERROR_MESSAGE,
            )

        # Config class exists but no config fields provided - check if that's allowed
        if auth_provider_config is None:
            try:
                # Get config class to check if it has required fields
                config_class = resource_locator.get_config(auth_provider.config_class)
                # Create an empty instance to see if it accepts no fields
                config = config_class()
                return config.model_dump()
            except Exception:
                # If it fails with no fields, config is required
                raise HTTPException(
                    status_code=422,
                    detail=f"Auth provider {auth_provider.name} requires config fields "
                    "but none were provided. " + BASE_ERROR_MESSAGE,
                ) from None

        # Both config class and config fields exist, validate them
        try:
            config_class = resource_locator.get_config(auth_provider.config_class)
            config = config_class(**auth_provider_config)
            return config.model_dump()
        except Exception as e:
            auth_provider_logger.error(f"Failed to validate auth provider config fields: {e}")
            # Check if it's a Pydantic validation error and format it nicely
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                # Extract the field names and error messages
                error_messages = []
                for error in e.errors():
                    field = ".".join(str(loc) for loc in error.get("loc", []))
                    msg = error.get("msg", "")
                    error_messages.append(f"Field '{field}': {msg}")

                error_detail = (
                    f"Invalid configuration for {auth_provider.config_class}:\n"
                    + "\n".join(error_messages)
                )
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid auth provider config fields: {error_detail}. "
                    + BASE_ERROR_MESSAGE,
                ) from e
            else:
                # For other types of errors
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid auth provider config fields: {str(e)}. " + BASE_ERROR_MESSAGE,
                ) from e


# Singleton instance
auth_provider_service = AuthProviderService()
