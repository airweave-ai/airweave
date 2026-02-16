"""Sources API endpoints for discovering available data source connectors.

This module provides endpoints for listing and retrieving details about
the data sources that Airweave can connect to. Sources represent the
types of external systems (e.g., GitHub, Slack, Notion) that can be
synchronized with Airweave.
"""

from typing import List

from fastapi import Depends, HTTPException, Path

from airweave import schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.examples import create_single_source_response, create_source_list_response
from airweave.api.router import TrailingSlashRouter
from airweave.domains.sources.protocols import SourceServiceProtocol
from airweave.schemas.errors import NotFoundErrorResponse, RateLimitErrorResponse

router = TrailingSlashRouter()


@router.get(
    "/",
    response_model=List[schemas.Source],
    summary="List Sources",
    description="""Retrieve all available data source connectors.

Returns the complete catalog of source types that Airweave can connect to,
including their authentication methods, configuration requirements, and
supported features. Use this endpoint to discover which integrations are
available for your organization.

Each source includes:
- **Authentication methods**: How to connect (OAuth, API key, etc.)
- **Configuration schemas**: What settings are required or optional
- **Supported auth providers**: Pre-configured OAuth providers available""",
    responses={
        **create_source_list_response(["github"], "List of all available data source connectors"),
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def list(
    *,
    ctx: ApiContext = Depends(deps.get_context),
    source_service: SourceServiceProtocol = Inject(SourceServiceProtocol),
) -> List[schemas.Source]:
    """List all available data source connectors."""
    return await source_service.list(ctx)


@router.get(
    "/{short_name}",
    response_model=schemas.Source,
    summary="Get Source",
    description="""Retrieve detailed information about a specific data source connector.

Returns the complete configuration for a source type, including:

- **Authentication fields**: Schema for credentials required to connect
- **Configuration fields**: Schema for optional settings and customization
- **Supported auth providers**: Pre-configured OAuth providers available for this source

Use this endpoint before creating a source connection to understand what
authentication and configuration values are required.""",
    responses={
        **create_single_source_response(
            "github", "Source details with authentication and configuration schemas"
        ),
        404: {"model": NotFoundErrorResponse, "description": "Source Not Found"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def get(
    *,
    short_name: str = Path(
        ...,
        description="Technical identifier of the source type (e.g., 'github', 'stripe', 'slack')",
        json_schema_extra={"example": "github"},
    ),
    ctx: ApiContext = Depends(deps.get_context),
    source_service: SourceServiceProtocol = Inject(SourceServiceProtocol),
) -> schemas.Source:
    """Get detailed information about a specific data source connector."""
    try:
        return await source_service.get(short_name, ctx)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Source not found: {short_name}")
