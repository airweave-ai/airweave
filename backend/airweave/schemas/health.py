"""Health check response schemas."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class CheckStatus(str, Enum):
    """Status of an individual dependency check."""

    up = "up"
    down = "down"
    skipped = "skipped"


class DependencyCheck(BaseModel):
    """Result of a single dependency health check."""

    status: CheckStatus
    latency_ms: float | None = None
    error: str | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "up",
                "latency_ms": 1.23,
                "error": None,
            }
        }
    }


class ReadinessResponse(BaseModel):
    """Response from the readiness probe."""

    status: Literal["ready", "not_ready"]
    checks: dict[str, DependencyCheck]

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ready",
                "checks": {
                    "postgres": {"status": "up", "latency_ms": 1.23, "error": None},
                    "redis": {"status": "up", "latency_ms": 0.45, "error": None},
                    "temporal": {"status": "skipped", "latency_ms": None, "error": None},
                },
            }
        }
    }


class LivenessResponse(BaseModel):
    """Response from the liveness probe."""

    status: Literal["alive"] = "alive"
