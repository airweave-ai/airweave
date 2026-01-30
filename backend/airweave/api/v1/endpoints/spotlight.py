"""Spotlight search endpoints.

These endpoints provide agentic search capabilities using the spotlight module.
The spotlight module creates its own database connection based on its config,
completely separate from the Airweave API's database connection.
"""

from fastapi import Depends, Path

from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.shared_models import ActionType
from airweave.search.spotlight.core.agent import SpotlightAgent
from airweave.search.spotlight.schemas import SpotlightRequest, SpotlightResponse
from airweave.search.spotlight.services import SpotlightServices

router = TrailingSlashRouter()


@router.post("/{readable_id}/spotlight/search", response_model=SpotlightResponse)
async def spotlight_search(
    request: SpotlightRequest,
    collection_readable_id: str = Path(
        ..., description="The unique readable identifier of the collection"
    ),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
) -> SpotlightResponse:
    """Spotlight agentic search."""
    await guard_rail.is_allowed(ActionType.QUERIES)

    services = await SpotlightServices.create(ctx)

    try:
        agent = SpotlightAgent(services)

        response = await agent.run(collection_readable_id, request)

        await guard_rail.increment(ActionType.QUERIES)

        return response
    finally:
        await services.db.close()
