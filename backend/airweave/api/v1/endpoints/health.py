"""Health check endpoints."""

from fastapi import Response

from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.config import settings
from airweave.core.protocols import HealthServiceProtocol
from airweave.schemas.health import LivenessResponse, ReadinessResponse

router = TrailingSlashRouter()


@router.get("")
async def health_check() -> dict[str, str]:
    """Check if the API is healthy.

    Returns:
    --------
        dict: A dictionary containing the status of the API.
    """
    return {"status": "healthy"}


@router.get("/live")
async def liveness() -> LivenessResponse:
    """Liveness probe — confirms the process is running."""
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def readiness(
    response: Response,
    health: HealthServiceProtocol = Inject(HealthServiceProtocol),
) -> ReadinessResponse:
    """Readiness probe — checks critical dependencies.

    Only critical probes (Postgres) gate the HTTP status code.  Informational
    probes (Redis, Temporal) are reported for observability but do not cause
    a 503.
    """
    result = await health.check_readiness(debug=settings.DEBUG)

    if result.status != "ready":
        response.status_code = 503
    return result
