"""The API module that contains the endpoints for sources."""

from typing import List

from fastapi import Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.examples import create_single_source_response, create_source_list_response
from airweave.api.router import TrailingSlashRouter
from airweave.core.auth_provider_service import auth_provider_service
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.platform.configs._base import Fields
from airweave.platform.locator import resource_locator

router = TrailingSlashRouter()


@router.get(
    "/",
    response_model=List[schemas.Source],
    responses=create_source_list_response(
        ["github"], "List of all available data source connectors"
    ),
)
async def list(
    *,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.Source]:
    """List all available data source connectors.

    <br/><br/>
    Returns the complete catalog of source types that Airweave can connect to.
    """
    ctx.logger.info("Starting read_sources endpoint")
    try:
        sources = await crud.source.get_all(db)
        ctx.logger.info(f"Retrieved {len(sources)} sources from database")
    except Exception as e:
        ctx.logger.error(f"Failed to retrieve sources: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sources") from e

    # Initialize auth_fields for each source
    result_sources = []
    invalid_sources = []

    for source in sources:
        try:
            # Config class is always required
            if not source.config_class:
                invalid_sources.append(f"{source.short_name} (missing config_class)")
                continue

            # Auth config class is only required for sources with DIRECT auth
            # OAuth sources don't have auth_config_class
            auth_fields = None
            if source.auth_config_class:
                # Get authentication configuration class if it exists
                try:
                    auth_config_class = resource_locator.get_auth_config(source.auth_config_class)
                    auth_fields = Fields.from_config_class(auth_config_class)
                except AttributeError as e:
                    invalid_sources.append(
                        f"{source.short_name} (invalid auth_config_class: {str(e)})"
                    )
                    continue
            else:
                # For OAuth sources, auth_fields is None (handled by OAuth flow)
                auth_fields = Fields(fields=[])

            # Get configuration class
            try:
                config_class = resource_locator.get_config(source.config_class)
                config_fields = Fields.from_config_class(config_class)
            except AttributeError as e:
                invalid_sources.append(f"{source.short_name} (invalid config_class: {str(e)})")
                continue

            # Get supported auth providers
            supported_auth_providers = auth_provider_service.get_supported_providers_for_source(
                source.short_name
            )

            # Create source model with all fields including auth_fields and config_fields
            source_dict = {
                **{key: getattr(source, key) for key in source.__dict__ if not key.startswith("_")},
                "auth_fields": auth_fields,
                "config_fields": config_fields,
                "supported_auth_providers": supported_auth_providers,
            }

            # In self-hosted mode, force requires_byoc for OAuth sources
            if settings.ENVIRONMENT == "self-hosted" and source.auth_methods:
                if "oauth_browser" in source.auth_methods or "oauth_token" in source.auth_methods:
                    source_dict["requires_byoc"] = True

            source_model = schemas.Source.model_validate(source_dict)
            result_sources.append(source_model)

        except Exception as e:
            # Log the error but continue processing other sources
            ctx.logger.exception(f"Error processing source {source.short_name}: {str(e)}")
            invalid_sources.append(f"{source.short_name} (error: {str(e)})")

    # Log any invalid sources
    if invalid_sources:
        ctx.logger.warning(
            f"Skipped {len(invalid_sources)} invalid sources: {', '.join(invalid_sources)}"
        )

    ctx.logger.info(f"Returning {len(result_sources)} valid sources")
    return result_sources


@router.get(
    "/{short_name}",
    response_model=schemas.Source,
    responses=create_single_source_response(
        "github", "Source details with authentication and configuration schemas"
    ),
)
async def get(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str = Path(
        ...,
        description="Technical identifier of the source type (e.g., 'github', 'stripe', 'slack')",
    ),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Source:
    """Get detailed information about a specific data source connector."""
    try:
        source = await crud.source.get_by_short_name(db, short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source not found: {short_name}")

        # Config class is always required
        if not source.config_class:
            raise HTTPException(
                status_code=400,
                detail=f"Source {short_name} does not have a configuration class",
            )

        # Auth fields - only for sources with auth_config_class (DIRECT auth)
        auth_fields = Fields(fields=[])
        if source.auth_config_class:
            try:
                auth_config_class = resource_locator.get_auth_config(source.auth_config_class)
                auth_fields = Fields.from_config_class(auth_config_class)
            except Exception as e:
                ctx.logger.error(f"Failed to get auth config for {short_name}: {str(e)}")
                raise HTTPException(
                    status_code=500, detail=f"Invalid auth configuration for source {short_name}"
                ) from e

        # Get config fields
        try:
            config_class = resource_locator.get_config(source.config_class)
            config_fields = Fields.from_config_class(config_class)
        except Exception as e:
            ctx.logger.error(f"Failed to get config for {short_name}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Invalid configuration for source {short_name}"
            ) from e

        # Get supported auth providers
        supported_auth_providers = auth_provider_service.get_supported_providers_for_source(
            source.short_name
        )

        # Create a dictionary with all required fields including auth_fields and config_fields
        source_dict = {
            **{key: getattr(source, key) for key in source.__dict__ if not key.startswith("_")},
            "auth_fields": auth_fields,
            "config_fields": config_fields,
            "supported_auth_providers": supported_auth_providers,
        }

        # In self-hosted mode, force requires_byoc for OAuth sources
        if settings.ENVIRONMENT == "self-hosted" and source.auth_methods:
            if "oauth_browser" in source.auth_methods or "oauth_token" in source.auth_methods:
                source_dict["requires_byoc"] = True

        # Validate in one step with all fields present
        source_model = schemas.Source.model_validate(source_dict)
        return source_model

    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=f"Source not found: {short_name}") from e

    except HTTPException:
        # Re-raise HTTP exceptions as is
        raise
    except Exception as e:
        ctx.logger.exception(f"Error retrieving source {short_name}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve source details for {short_name}"
        ) from e
